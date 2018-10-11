"""Printing tests"""

import os
from unittest.mock import patch, ANY
from reportlab.pdfgen.canvas import Canvas
from odoo.exceptions import UserError
from .common import PrinterCase, HTML_MIMETYPE, XML_MIMETYPE


class TestPrintPrinter(PrinterCase):
    """Printing tests"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Printer = cls.env['print.printer']
        User = cls.env['res.users']

        # Create additional printers
        cls.printer_dotmatrix = Printer.create({
            'name': "Dot matrix",
            'queue': 'dotmatrix',
        })
        cls.printer_plotter = Printer.create({
            'name': "Plotter",
            'queue': 'plotter',
        })

        # Create users
        cls.user_alice = User.create({
            'name': "Alice",
            'login': 'alice',
        })
        cls.user_bob = User.create({
            'name': "Bob",
            'login': 'bob',
        })

    def test01_spool_test_page(self):
        """Test printing a test page to unspecified (default) printer"""
        Printer = self.env['print.printer']
        Printer.spool_test_page()
        self.assertPrintedLpr('-T', ANY)

    def test02_specific_printer(self):
        """Test printing a test page to specified printers"""
        self.printer_default.spool_test_page()
        self.assertPrintedLpr('-T', ANY)
        self.printer_dotmatrix.spool_test_page()
        self.assertPrintedLpr('-P', 'dotmatrix', '-T', ANY)
        self.printer_plotter.spool_test_page()
        self.assertPrintedLpr('-P', 'plotter', '-T', ANY)

    def test03_title(self):
        """Test specifying job title"""
        self.printer_default.spool_report(self.printer_default.ids,
                                          'print.report_test_page',
                                          title="Not a test page")
        self.assertPrintedLpr('-T', "Not a test page")

    def test04_copies(self):
        """Test specifying number of copies"""
        self.printer_default.spool_report(self.printer_default.ids,
                                          'print.report_test_page', copies=42)
        self.assertPrintedLpr('-T', ANY, '-#', '42')

    def test05_system_default(self):
        """Test changing system default printer"""
        Printer = self.env['print.printer']
        Printer.spool_test_page()
        self.assertPrintedLpr('-T', ANY)
        self.printer_dotmatrix.set_system_default()
        Printer.spool_test_page()
        self.assertPrintedLpr('-P', 'dotmatrix', '-T', ANY)

    def test06_user_default(self):
        """Test changing user default printer"""
        Printer = self.env['print.printer']
        Printer.sudo(self.user_alice).spool_test_page()
        self.assertPrintedLpr('-T', ANY)
        Printer.sudo(self.user_bob).spool_test_page()
        self.assertPrintedLpr('-T', ANY)
        self.printer_dotmatrix.sudo(self.user_alice).set_user_default()
        self.assertEqual(self.user_alice.printer_id, self.printer_dotmatrix)
        self.printer_plotter.sudo(self.user_bob).set_user_default()
        self.assertEqual(self.user_bob.printer_id, self.printer_plotter)
        Printer.sudo(self.user_alice).spool_test_page()
        self.assertPrintedLpr('-P', 'dotmatrix', '-T', ANY)
        Printer.sudo(self.user_bob).spool_test_page()
        self.assertPrintedLpr('-P', 'plotter', '-T', ANY)

    def test07_no_printer(self):
        """Test UserError when no default printer is specified"""
        Printer = self.env['print.printer']
        self.printer_default.is_default = False
        with self.assertRaises(UserError):
            Printer.spool_test_page()

    def test08_missing_lpr(self):
        """Test UserError when lpr binary is missing"""
        Printer = self.env['print.printer']
        self.mock_find_in_path.side_effect = IOError
        with self.assertRaises(UserError):
            Printer.spool_test_page()

    def test09_failing_lpr(self):
        """Test UserError when lpr fails"""
        Printer = self.env['print.printer']
        self.mock_lpr.returncode = 1
        with self.assertRaises(UserError):
            Printer.spool_test_page()

    def test10_unsupported_os(self):
        """Test UserError when OS is unsupported"""
        Printer = self.env['print.printer']
        with patch.object(os, 'name', 'msdos'):
            with self.assertRaises(UserError):
                Printer.spool_test_page()

    def test11_untitled(self):
        """Test ability to omit document title"""
        canvas = Canvas('')
        canvas.drawString(100, 750, "Hello world!")
        document = canvas.getpdfdata()
        self.printer_default.spool(document)
        self.assertPrintedLpr()

    def test12_barcode(self):
        """Test ability to print with barcode"""
        self.printer_dotmatrix.barcode = 'DOTMATRIX'
        self.printer_dotmatrix.spool_test_page()
        self.assertPrintedLpr('-P', 'dotmatrix', '-T', ANY)

    def test13_nonexistent(self):
        """Test UserError for nonexistent report"""
        with self.assertRaises(UserError):
            self.printer_default.spool_report(self.printer_default.ids,
                                              'print.nonexistent_report')

    def test14_xmlid(self):
        """Test ability to use XML ID to identify a report"""
        self.printer_default.spool_report(self.printer_default.ids,
                                          'print.action_report_test_page')
        self.assertPrintedLpr('-T', ANY)

    def test15_non_pdf(self):
        """Test ability to send non-PDF data to printer"""
        Report = self.env['ir.actions.report']
        report = Report._get_report_from_name('print.report_test_page')
        report.report_type = 'qweb-html'
        Printer = self.env['print.printer']
        Printer.spool_test_page()
        self.assertPrintedLpr('-T', ANY, mimetype=HTML_MIMETYPE)

    def test16_cpcl(self):
        """Test generating CPCL/XML data"""
        self.printer_default.spool_report(self.printer_default.ids,
                                          'print.action_report_test_page_cpcl')
        self.assertPrintedLpr('-T', ANY, mimetype=XML_MIMETYPE)
