Print directly to backend printers
==================================

This module provides a ```print.printer``` model to represent printers
connected to the Odoo server.  This allows for backend code to send
reports directly to a printer, rather than requiring the user to
download a PDF to be printed manually.

The primary use case is for printing reports: this can be triggered in
the Python code via e.g.

    Printer = self.env['print.printer']
    Picking = self.env['stock.picking']
    pick = Picking.search([('name', '=', 'PICK00009')])
    Printer.spool_report(pick.ids, 'stock.report_deliveryslip')

Note that ```spool_report()``` may be called on a specific printer or
directly on the model.  If called directly on the model, the user's
default printer (or system default printer) will be used.

Another common use case is to identify a printer by barcode and
associate it as the current user's default printer:

    Printer = self.env['print.printer']
    printer = Printer.search([('barcode', '=', 'PRNLAB02')])
    printer.set_user_default()
