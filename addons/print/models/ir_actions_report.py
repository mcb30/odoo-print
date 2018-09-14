"""Reports"""

from lxml import etree
from odoo import api, fields, models


class IrActionsReport(models.Model):
    """Add support for CPCL reports"""

    _inherit = 'ir.actions.report'

    report_type = fields.Selection(selection_add=[('qweb-cpcl', 'CPCL')])

    @api.multi
    def render_qweb_cpcl(self, docids, data=None):
        """Render CPCL/XML report"""
        html = self.render_qweb_html(docids, data=data)[0]
        cpcl = etree.fromstring(html)
        for element in cpcl.iter():
            attrs = element.attrib
            remove = [x for x in attrs if x.startswith('data-')]
            for attr in remove:
                del attrs[attr]
        return (etree.tostring(cpcl, xml_declaration=True), 'cpcl')
