"""Printers"""

import logging
import os
import subprocess
from odoo import api, fields, models
from odoo.tools.translate import _
from odoo.tools.misc import find_in_path
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


def _find_lpr_exec():
    """Find usable lpr executable"""
    try:
        lpr_exec = find_in_path('lpr')
        return lpr_exec
    except IOError:
        raise UserError(_("Cannot find lpr executable"))


class Printer(models.Model):
    """Printer"""

    _name = 'print.printer'
    _description = 'Printer'
    _parent_name = 'group_id'
    _order = 'parent_left, name'
    _parent_store = True
    _parent_order = 'name'
    _rec_name = 'full_name'

    name = fields.Char(string="Name", index=True, required=True)
    full_name = fields.Char(string="Full Name", compute='_compute_full_name',
                            store=True, index=True)
    barcode = fields.Char(string="Barcode", index=True)
    queue = fields.Char(string="Print Queue Name", index=True)
    report_type = fields.Selection([('qweb-pdf', "PDF"),
                                    ('qweb-html', "HTML"),
                                    ('qweb-cpcl', "CPCL/XML")],
                                   string="Report Type", required=True,
                                   default='qweb-pdf')
    is_default = fields.Boolean(string="System Default", index=True,
                                default=False)
    is_user_default = fields.Boolean(string="User Default",
                                     compute='_compute_is_user_default')
    is_ephemeral = fields.Boolean(string="Clear On Logout", default=False)
    is_group = fields.Boolean(string="Printer Group", default=False)
    group_id = fields.Many2one('print.printer', string="Printer Group",
                               index=True, ondelete='cascade',
                               domain=[('is_group', '=', True)])
    child_ids = fields.One2many('print.printer', 'group_id',
                                string="Grouped Printers")
    parent_left = fields.Integer(string="Left parent", index=True)
    parent_right = fields.Integer(string="Right parent", index=True)

    _sql_constraints = [
        ('barcode_uniq', 'unique (barcode)', "The Barcode must be unique"),
        ('single_default',
         'exclude (is_default with =) where (is_default and group_id is null)',
         "There must be only one System Default Printer"),
        ('single_group_default',
         'exclude (group_id with =) where (is_default)',
         "There must be only one System Default Printer per group"),
    ]

    @api.multi
    @api.depends('name', 'group_id.full_name')
    def _compute_full_name(self):
        """Calculate full name (including group name(s))"""
        for printer in self:
            if printer.group_id.full_name:
                printer.full_name = '%s / %s' % (
                    printer.group_id.full_name, printer.name
                )
            else:
                printer.full_name = printer.name

    @api.multi
    def _compute_is_user_default(self):
        """Calculate user default flag"""
        for printer in self:
            printer.is_user_default = printer in self.env.user.printer_ids

    @api.multi
    @api.constrains('is_group', 'group_id', 'child_ids')
    def _check_groups(self):
        """Constrain group existence"""
        for printer in self:
            if printer.group_id and not printer.group_id.is_group:
                raise ValidationError(_("%s is not a printer group") %
                                      printer.group_id.name)
            if printer.child_ids and not printer.is_group:
                raise ValidationError(_("%s is not a printer group") %
                                      printer.name)

    @api.multi
    def printers(self, raise_if_not_found=False):
        """Determine printers to use"""

        # Start with explicitly specified list of printers, falling
        # back to user's default printer, falling back to system
        # default printer
        printers = (self or self.env.user.printer_id or
                    self.search([('is_default', '=', True),
                                 ('group_id', '=', False)]))

        # Iteratively reduce any printer groups to their user or
        # system default printers
        while printers.filtered(lambda x: x.is_group):
            printers = printers.mapped(lambda p: (
                p if not p.is_group else
                ((p.child_ids & self.env.user.printer_ids) or
                 (p.child_ids.filtered(lambda x: x.is_default)))
            ))

        # Fail if no printers were found, if applicable
        if raise_if_not_found and not printers:
            raise UserError(_("No default printer specified"))

        return printers

    @api.multi
    def _spool_lpr(self, document, title=None, copies=1):
        """Spool document to printer via lpr"""
        lpr_exec = _find_lpr_exec()
        for printer in self.printers(raise_if_not_found=True):

            # Construct lpr command line
            args = [lpr_exec]
            if printer.queue:
                args += ['-P', printer.queue]
            if title is not None:
                args += ['-T', title]
            if copies > 1:
                args += ['-#', str(copies)]

            # Pipe document into lpr
            _logger.info("Printing via %s", ' '.join(args))
            lpr = subprocess.Popen(args, stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT)
            output = lpr.communicate(document)[0]
            if lpr.returncode != 0:
                raise UserError(_("lpr failed (error code: %s). Message: %s") %
                                (str(lpr.returncode), output))

    @api.multi
    def spool(self, document, title=None, copies=1):
        """Spool document to printer"""

        # Spool document via OS-dependent spooler mechanism
        if os.name == 'posix':
            self._spool_lpr(document, title=title, copies=copies)
        else:
            raise UserError(_("Cannot print on OS: %s" % os.name))
        return True

    @api.multi
    def spool_report(self, docids, report_name, data=None, title=None,
                     copies=1):
        """Spool report to printer"""
        # pylint: disable=too-many-arguments, too-many-locals

        # Identify reports
        if isinstance(report_name, models.BaseModel):
            reports = report_name
        else:
            name = report_name
            Report = self.env['ir.actions.report']
            reports = Report._get_report_from_name(name)
            if not reports:
                reports = self.env.ref(name, raise_if_not_found=False)
            if not reports:
                raise UserError(_("Undefined report %s") % name)

        # Identify required report types
        printers = self.printers(raise_if_not_found=True)
        required = set(printers.mapped('report_type'))
        available = set(reports.mapped('report_type'))
        missing = required - available
        if missing:
            raise UserError(_("Missing reports of types: %s") %
                            ', '.join(missing))

        # Generate reports for each required report type
        documents = {
            x.report_type: (
                ("%s %s" % (x.name, str(docids))) if title is None else title,
                x.render(docids, data)[0]
            )
            for x in reports if x.report_type in required
        }

        # Send appropriate report to each printer
        for printer in printers:
            title, document = documents[printer.report_type]
            printer.spool(document, title=title, copies=copies)

        return True

    @api.model
    def test_page_report(self):
        """Get printer test pages"""
        Report = self.env['ir.actions.report']
        return Report.search([
            ('model', '=', 'print.printer'),
            ('report_name', '=like', 'print.%'),
        ])

    @api.multi
    def spool_test_page(self):
        """Print test page"""
        for printer in self.printers(raise_if_not_found=True):
            printer.spool_report(printer.ids, self.test_page_report(),
                                 title="Test page")
        return True

    @api.multi
    def clear_user_default(self):
        """Clear as user default printer"""
        self.env.user.printer_ids -= self
        return {'type': 'ir.actions.client', 'tag': 'reload'}

    @api.multi
    def clear_system_default(self):
        """Clear as system default printer"""
        self.write({'is_default': False})
        return {'type': 'ir.actions.client', 'tag': 'reload'}

    @api.multi
    def set_user_default(self):
        """Set as user default printer (within group, if applicable)"""
        self.ensure_one()
        self.env.user.printer_ids.filtered(
            lambda x: x.group_id == self.group_id
        ).with_env(self.env).clear_user_default()
        self.env.user.printer_ids += self
        return {'type': 'ir.actions.client', 'tag': 'reload'}

    @api.multi
    def set_system_default(self):
        """Set as system default printer (within group, if applicable)"""
        self.ensure_one()
        self.search([
            ('is_default', '=', True),
            ('group_id', '=', self.group_id.id)
        ]).clear_system_default()
        self.is_default = True
        return {'type': 'ir.actions.client', 'tag': 'reload'}

    @api.model
    def clear_ephemeral(self):
        """Clear all ephemeral user default printers"""
        self.env.user.printer_ids.filtered(
            lambda x: x.is_ephemeral
        ).with_env(self.env).clear_user_default()
        return {'type': 'ir.actions.client', 'tag': 'reload'}
