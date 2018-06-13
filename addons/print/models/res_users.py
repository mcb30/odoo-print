"""User printing preferences"""

from odoo import fields, models


class User(models.Model):
    """Extend ``res.user`` to include a concept of default printer"""

    _inherit = 'res.users'

    printer_id = fields.Many2one('print.printer', 'Default Printer')
