"""User printing preferences"""

from odoo import api, fields, models
from odoo.tools.translate import _
from odoo.exceptions import ValidationError


class User(models.Model):
    """Extend ``res.user`` to include a concept of default printer"""

    _inherit = 'res.users'

    printer_ids = fields.Many2many('print.printer', string="Default Printers")
    printer_id = fields.Many2one('print.printer', string="Default Printer",
                                 compute='_compute_printer_id', store=True)

    @api.multi
    @api.depends('printer_ids')
    def _compute_printer_id(self):
        """Compute default ungrouped printer (for backwards compatibility)"""
        for user in self:
            user.printer_id = user.printer_ids.filtered(
                lambda x: not x.group_id
            )

    @api.multi
    @api.constrains('printer_ids')
    def _check_printer_ids(self):
        """Constrain user to having one default printer per group"""
        for user in self:
            groups = set(x.group_id for x in user.printer_ids)
            if len(user.printer_ids) != len(groups):
                raise ValidationError(_(
                    "User may have at most one default printer per group"
                ))
