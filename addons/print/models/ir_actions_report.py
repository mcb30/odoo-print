"""Reports"""

from lxml import etree
from odoo import api, fields, models


class IrActionsReport(models.Model):
    """Add support for CPCL reports"""

    _inherit = 'ir.actions.report'

    report_type = fields.Selection(selection_add=[('qweb-cpcl', 'CPCL')])

    @staticmethod
    def add_print_qty(cpcl, copies):
        """ Searches the CPCL tree for the print statement and adds
        the number of copies to it if it is not already present
        """
        prints = cpcl.findall("{http://www.fensystems.co.uk/xmlns/cpcl}print")
        if copies > 1 and prints:
            for el in prints:
                if not el.attrib.get('qty', False):
                    el.set('qty', str(copies))
        return cpcl

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

        # Add print copies to CPCL template
        copies = 1
        if data:
            copies = data.get('copies', 1)
        cpcl = self.add_print_qty(cpcl, copies)

        return etree.tostring(cpcl, xml_declaration=True), 'cpcl'
