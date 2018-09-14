"""Printing tests"""

import os
from unittest.mock import patch, Mock, ANY
import tempfile
from reportlab.pdfgen.canvas import Canvas
from odoo.exceptions import UserError
from odoo.tools import config
from odoo.tools.mimetypes import guess_mimetype
from odoo.tests import common

MOCK_LPR = 'MOCK_LPR'


@common.at_install(False)
@common.post_install(True)
class TestPrintPrinter(common.SavepointCase):
    """Printing tests"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Printer = cls.env['print.printer']
        User = cls.env['res.users']

        # Reset system default printer
        cls.printer_default = cls.env.ref('print.default_printer')
        cls.printer_default.queue = None
        cls.printer_default.set_system_default()

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

    def setUp(self):
        super().setUp()

        # Patch find_in_path() as used in print_printer.py
        patch_find_in_path = patch(
            'odoo.addons.print.models.print_printer.find_in_path',
            autospec=True, return_value=MOCK_LPR,
        )
        self.mock_find_in_path = patch_find_in_path.start()
        self.addCleanup(patch_find_in_path.stop)

        # Patch subprocess as used in print_printer.py
        patch_subprocess = patch(
            'odoo.addons.print.models.print_printer.subprocess',
            autospec=True,
        )
        self.mock_subprocess = patch_subprocess.start()
        self.addCleanup(patch_subprocess.stop)

        # Create mock lpr subprocess
        self.mock_lpr = Mock()
        self.mock_lpr.communicate.return_value = ('', '')
        self.mock_lpr.returncode = 0
        self.mock_subprocess.Popen.return_value = self.mock_lpr

        # Create mock test_report_directory to ensure that
        # ir.actions.report.render_qweb_pdf() will actually attempt to
        # generate a PDF
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        patch_config = patch.dict(config.options, {
            'test_report_directory': self.tempdir.name,
        })
        patch_config.start()
        self.addCleanup(patch_config.stop)

    def assertPrintedLpr(self, *args, mimetype='application/pdf'):
        """Assert that ``lpr`` was invoked with the specified argument list"""
        self.mock_subprocess.Popen.assert_called_once_with(
            [MOCK_LPR, *args], stdin=ANY, stdout=ANY, stderr=ANY
        )
        self.mock_lpr.communicate.assert_called_once()
        document = self.mock_lpr.communicate.call_args[0][0]
        self.assertEqual(guess_mimetype(document), mimetype)
        self.mock_lpr.reset_mock()
        self.mock_subprocess.Popen.reset_mock()

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
        self.assertPrintedLpr('-T', ANY, mimetype='text/html')

    def test16_cpcl(self):
        """Test generating CPCL/XML data"""
        self.printer_default.spool_report(self.printer_default.ids,
                                          'print.action_report_test_page_cpcl')
        self.assertPrintedLpr('-T', ANY, mimetype='text/xml')
