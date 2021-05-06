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
    user_ids = fields.Many2many('res.users', string="Users")
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
    def printers(self, report_type=None, raise_if_not_found=False):
        """Determine printers to use"""
        if self:
            # Printers are specified in self
            printers = self

            if report_type:
                # Filter out printers which don't match the report type
                printers = self.filtered(lambda p: p.report_type == report_type)
        else:
            # Fall back to user default
            printers = self.env.user.get_printer(report_type)

            if not printers:
                # Fall back to system default
                printers = self.get_system_default_printer(report_type=report_type)

        # Iteratively reduce any printer groups to their user or
        # system default printers
        while printers.filtered(lambda p: p.is_group):
            printers = printers.mapped(
                lambda p: (
                    p
                    if not p.is_group and (report_type is None or p.report_type == report_type)
                    else (
                        (p.child_ids & self.env.user.printer_ids)
                        or (p.child_ids.filtered(lambda x: x.is_default))
                    )
                )
            )

        # Fail if no printers were found, if applicable
        if raise_if_not_found and not printers:
            error_msg = _("No default printer specified")
            if report_type:
                report_type_label = self.get_report_type_label(report_type)
                error_msg += (
                    _(" for %s report format") % report_type_label
                )

            raise UserError(error_msg)

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
    def spool_report(self, docids, report_name, data=None, title=None, copies=1):
        """Spool report to printer"""
        # pylint: disable=too-many-arguments, too-many-locals

        if copies <= 0:
            _logger.info(_('Zero or fewer copies requested, nothing will be printed.'))
            return True

        # Identify reports
        if isinstance(report_name, models.BaseModel):
            reports = report_name
        else:
            name = report_name
            Report = self.env["ir.actions.report"]
            reports = Report._get_report_from_name(name)
            if not reports:
                reports = self.env.ref(name, raise_if_not_found=False)
            if not reports:
                raise UserError(_("Undefined report %s") % name)

        # Identify required report types
        report_types = set(reports.mapped("report_type"))

        # If there is only 1 report type to print out then raise an error if printer not found,
        # otherwise continue checking for other report types
        printer_raise_if_not_found = len(report_types) == 1

        # Identify printer to use for each report type, only include report type in dictionary
        # if a printer is identified
        printers_by_report_type = {
            rt: p
            for rt in report_types
            for p in (self.printers(raise_if_not_found=printer_raise_if_not_found, report_type=rt))
            if p
        }

        if printers_by_report_type:
            required_types = set(printers_by_report_type.keys())
            missing = required_types - report_types
        else:
            missing = report_types

        if missing:
            # Get labels of missing report types from selection list
            missing_labels = [self.get_report_type_label(rt) for rt in missing]
            raise UserError(_("Missing reports of types: %s") % ", ".join(missing_labels))

        # CPCL reports require number of copies passed into the template via data
        cpcl_data = {'copies': copies}
        if data:
            cpcl_data.update(data)

        # Generate reports for each required report type
        documents = {
            x.report_type: (
                ("%s %s" % (x.name, str(docids))) if title is None else title,
                x.render(docids, cpcl_data if x.report_type == "qweb-cpcl" else data)[0],
            )
            for x in reports
        }

        # Send appropriate report to each printer
        for report_type, printer in printers_by_report_type.items():
            title, document = documents[report_type]
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
            lambda x: x.group_id == self.group_id and x.report_type == self.report_type
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

    def get_report_type_label(self, report_type):
        """Get the label of the supplied report type code"""
        # Use `_description_selection` to ensure translations are used
        report_type_labels = dict(self._fields["report_type"]._description_selection(self.env))
        return report_type_labels.get(report_type)

    def get_system_default_printer(self, report_type=None):
        """Find and return system default printer for the supplied report_type, if specified"""
        system_default_args = [("is_default", "=", True), ("group_id", "=", False)]
        if report_type:
            system_default_args.append(("report_type", "=", report_type))
        return self.search(system_default_args, limit=1)
