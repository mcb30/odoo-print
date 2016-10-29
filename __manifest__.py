{
    'name': 'Printing',
    'summary': 'Printer integration',
    'description': """
Print directly to backend printers
==================================

Print documents and reports directly to printers connected to the Odoo
backend server.

Key Features
------------
* Identify printers by barcode
* Define a default printer for each user
* Define a system default printer
    """,
    'version': '0.1',
    'depends': ['report'],
    'author': 'Michael Brown <mbrown@fensystems.co.uk>',
    'category': 'Extra Tools',
    'data': [
             'security/ir.model.access.csv',
             'report/test_page_templates.xml',
             'report/test_page_reports.xml',
             'views/res_users_views.xml',
             'views/print_printer_views.xml',
             'data/print_printer_data.xml',
            ],
}
