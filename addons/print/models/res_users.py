"""User printing preferences"""

from odoo import api, fields, models
from odoo.tools.translate import _
from odoo.exceptions import ValidationError


class User(models.Model):
    """Extend ``res.user`` to include a concept of default printer"""

    _inherit = 'res.users'

    printer_ids = fields.Many2many('print.printer', string="Default Printers")

    def get_printer(self, report_type=None):
        """
        Identify and return user default ungrouped printer (for backwards compatibility) 
        for report type (if specified)
        """
        self.ensure_one()
        printer = self.printer_ids.filtered(
            lambda p: not p.group_id and (report_type is None or p.report_type == report_type)
        )
        # If multiple printers are found, return the first one
        return printer[:1]

    @api.multi
    @api.constrains('printer_ids')
    def _check_printer_ids(self):
        """Constrain user to having one default printer per group, for each report type"""
        for user in self:
            groups_by_report_type = set((p.group_id, p.report_type) for p in user.printer_ids)
            if len(user.printer_ids) != len(groups_by_report_type):
                raise ValidationError(
                    _("User may have at most one default printer per group for each report type")
                )
