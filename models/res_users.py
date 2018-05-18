from odoo import api, fields, models


class User(models.Model):

    _inherit = 'res.users'

    printer_id = fields.Many2one('print.printer', 'Default Printer')
