"""Printing tests"""

import os
from unittest.mock import patch, ANY
from reportlab.pdfgen.canvas import Canvas
from odoo.exceptions import UserError, ValidationError
from .common import PrinterCase, HTML_MIMETYPE, PDF_MIMETYPE, XML_MIMETYPE


class TestPrintPrinter(PrinterCase):
    """Printing tests"""
    # pylint: disable=too-many-public-methods

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
        cls.printer_laser = Printer.create({
            'name': "Laser",
            'queue': 'laser',
        })
        cls.printer_inkjet = Printer.create({
            'name': "Inkjet",
            'queue': 'inkjet',
        })

        # Create printer groups
        cls.group_upstairs = Printer.create({
            'name': "Upstairs",
            'is_group': True,
        })
        cls.group_downstairs = Printer.create({
            'name': "Downstairs",
            'is_group': True,
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

    def print_test_report(self, copies=1):
        self.printer_dotmatrix.barcode = 'DOTMATRIX'
        self.printer_dotmatrix.report_type = 'qweb-cpcl'
        xmlid = 'print.action_report_test_page_cpcl'
        self.printer_dotmatrix.spool_report(self.printer_dotmatrix.ids, xmlid, copies=copies)
        qty_args = ['-#', str(copies)] if copies > 1 else []
        self.assertPrintedLpr('-P', 'dotmatrix', '-T', ANY,
                              mimetype=XML_MIMETYPE, *qty_args)
        render_data = {'copies': copies} if copies > 1 else None
        return self.env.ref(xmlid).render(self.printer_dotmatrix.ids, render_data)[0]

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
        self.assertEqual(Printer.printers(), self.printer_default)
        Printer.spool_test_page()
        self.assertPrintedLpr('-T', ANY)
        self.printer_dotmatrix.set_system_default()
        self.assertEqual(Printer.printers(), self.printer_dotmatrix)
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
        self.assertTrue(
            self.printer_dotmatrix.sudo(self.user_alice).is_user_default
        )
        self.assertIn(self.printer_dotmatrix, self.user_alice.printer_ids)
        self.assertIn(self.user_alice, self.printer_dotmatrix.user_ids)
        self.assertEqual(self.user_alice.printer_id, self.printer_dotmatrix)
        self.assertEqual(Printer.sudo(self.user_alice).printers(),
                         self.printer_dotmatrix)
        self.printer_plotter.sudo(self.user_bob).set_user_default()
        self.assertTrue(
            self.printer_plotter.sudo(self.user_bob).is_user_default
        )
        self.assertIn(self.printer_plotter, self.user_bob.printer_ids)
        self.assertIn(self.user_bob, self.printer_plotter.user_ids)
        self.assertEqual(self.user_bob.printer_id, self.printer_plotter)
        self.assertEqual(Printer.sudo(self.user_bob).printers(),
                         self.printer_plotter)
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
        self.printer_default.report_type = 'qweb-html'
        self.printer_default.spool_test_page()
        self.assertPrintedLpr('-T', ANY, mimetype=HTML_MIMETYPE)

    def test16_cpcl(self):
        """Test generating CPCL/XML data"""
        cpcl = self.print_test_report()
        self.assertCpclReport(cpcl, 'dotmatrix_test_page.xml')

    def test17_spool_by_record(self):
        """Test spooling ir.actions.report record (rather than report name)"""
        report = self.env.ref('print.action_report_test_page')
        self.printer_default.spool_report(self.printer_default.ids, report)
        self.assertPrintedLpr('-T', ANY)

    def test18_full_name(self):
        """Test full name"""
        self.assertEqual(self.printer_dotmatrix.full_name, "Dot matrix")
        self.printer_dotmatrix.group_id = self.group_downstairs
        self.assertEqual(self.printer_dotmatrix.full_name,
                         "Downstairs / Dot matrix")
        self.group_downstairs.group_id = self.group_upstairs
        self.assertEqual(self.printer_dotmatrix.full_name,
                         "Upstairs / Downstairs / Dot matrix")

    def test19_require_is_group(self):
        """Test requirement for is_group to be set on groups"""
        with self.assertRaises(ValidationError):
            self.printer_dotmatrix.group_id = self.printer_plotter
        with self.assertRaises(ValidationError):
            self.printer_plotter.child_ids += self.printer_dotmatrix
        self.printer_dotmatrix.group_id = self.group_upstairs
        with self.assertRaises(ValidationError):
            self.group_upstairs.is_group = False

    def test20_single_per_group(self):
        """Test requirement for user default printer to be unique per group"""
        self.printer_dotmatrix.group_id = self.group_upstairs
        self.printer_plotter.group_id = self.group_upstairs
        self.printer_laser.group_id = self.group_downstairs
        self.printer_inkjet.group_id = self.group_downstairs
        self.user_alice.printer_ids = (self.printer_dotmatrix |
                                       self.printer_laser)
        with self.assertRaises(ValidationError):
            self.user_alice.printer_ids = (self.printer_dotmatrix |
                                           self.printer_plotter)

    def test21_system_groups(self):
        """Test selection via printer groups with system defaults"""
        Printer = self.env['print.printer']
        self.printer_dotmatrix.group_id = self.group_upstairs
        self.printer_plotter.group_id = self.group_upstairs
        self.printer_laser.group_id = self.group_downstairs
        self.printer_inkjet.group_id = self.group_downstairs
        self.assertFalse(self.group_upstairs.printers())
        self.assertFalse(self.group_downstairs.printers())
        self.printer_dotmatrix.set_system_default()
        self.printer_laser.set_system_default()
        self.printer_inkjet.set_system_default()
        self.assertTrue(self.printer_default.is_default)
        self.assertTrue(self.printer_dotmatrix.is_default)
        self.assertFalse(self.printer_plotter.is_default)
        self.assertFalse(self.printer_laser.is_default)
        self.assertTrue(self.printer_inkjet.is_default)
        self.assertEqual(Printer.printers(), self.printer_default)
        self.assertEqual(self.group_upstairs.printers(),
                         self.printer_dotmatrix)
        self.assertEqual(self.group_downstairs.printers(),
                         self.printer_inkjet)

    def test22_user_groups(self):
        """Test selection via printer groups with user defaults"""
        Printer = self.env['print.printer']
        self.printer_dotmatrix.group_id = self.group_upstairs
        self.printer_plotter.group_id = self.group_upstairs
        self.printer_laser.group_id = self.group_downstairs
        self.printer_inkjet.group_id = self.group_downstairs
        self.printer_dotmatrix.sudo(self.user_alice).set_user_default()
        self.printer_plotter.sudo(self.user_alice).set_user_default()
        self.printer_inkjet.sudo(self.user_alice).set_user_default()
        self.printer_dotmatrix.sudo(self.user_bob).set_user_default()
        self.printer_laser.sudo(self.user_bob).set_user_default()
        self.printer_inkjet.sudo(self.user_bob).set_user_default()
        self.group_downstairs.sudo(self.user_bob).set_user_default()
        self.assertEqual(Printer.printers(), self.printer_default)
        self.assertFalse(self.group_upstairs.printers())
        self.assertFalse(self.group_downstairs.printers())
        self.assertEqual(Printer.sudo(self.user_alice).printers(),
                         self.printer_default)
        self.assertEqual(Printer.sudo(self.user_bob).printers(),
                         self.printer_inkjet)
        self.assertEqual(self.group_upstairs.sudo(self.user_alice).printers(),
                         self.printer_plotter)
        self.assertEqual(self.group_downstairs.sudo(self.user_alice).printers(),
                         self.printer_inkjet)
        self.assertEqual(self.group_upstairs.sudo(self.user_bob).printers(),
                         self.printer_dotmatrix)
        self.assertEqual(self.group_downstairs.sudo(self.user_bob).printers(),
                         self.printer_inkjet)

    def test23_select_type(self):
        """Test ability to automatically select correct report type"""
        self.printer_dotmatrix.barcode = 'DOTMATRIX'
        self.printer_dotmatrix.spool_test_page()
        self.assertPrintedLpr('-P', 'dotmatrix', '-T', ANY,
                              mimetype=PDF_MIMETYPE)
        self.printer_dotmatrix.report_type = 'qweb-cpcl'
        self.printer_dotmatrix.spool_test_page()
        self.assertPrintedLpr('-P', 'dotmatrix', '-T', ANY,
                              mimetype=XML_MIMETYPE)

    def test24_wrong_type(self):
        """Test UserError when report is incorrect type"""
        self.printer_default.report_type = 'qweb-cpcl'
        with self.assertRaises(UserError):
            self.printer_default.spool_report(self.printer_default.ids,
                                              'print.action_report_test_page')

    def test25_ephemeral(self):
        """Test clearing ephemeral printers"""
        Printer = self.env['print.printer']
        self.printer_dotmatrix.sudo(self.user_alice).set_user_default()
        self.assertIn(self.printer_dotmatrix, self.user_alice.printer_ids)
        self.assertIn(self.user_alice, self.printer_dotmatrix.user_ids)
        Printer.sudo(self.user_alice).clear_ephemeral()
        self.assertIn(self.printer_dotmatrix, self.user_alice.printer_ids)
        self.assertIn(self.user_alice, self.printer_dotmatrix.user_ids)
        self.printer_dotmatrix.is_ephemeral = True
        Printer.sudo(self.user_bob).clear_ephemeral()
        self.assertIn(self.printer_dotmatrix, self.user_alice.printer_ids)
        self.assertIn(self.user_alice, self.printer_dotmatrix.user_ids)
        Printer.sudo(self.user_alice).clear_ephemeral()
        self.assertNotIn(self.printer_dotmatrix, self.user_alice.printer_ids)
        self.assertNotIn(self.user_alice, self.printer_dotmatrix.user_ids)

    def test26_cpcl_qty(self):
        """Test generating CPCL/XML data"""
        cpcl = self.print_test_report(copies=2)
        self.assertCpclReport(cpcl, 'dotmatrix_test_page_qty2.xml')
        cpcl = self.print_test_report(copies=5)
        self.assertCpclReport(cpcl, 'dotmatrix_test_page_qty5.xml')
