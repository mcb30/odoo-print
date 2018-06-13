"""Printing tests"""

from unittest.mock import patch, Mock, ANY
from odoo.tests import common

MOCK_LPR = 'MOCK_LPR'


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
        self.mock_popen_kwargs = {
            'stdin': ANY,
            'stdout': ANY,
            'stderr': ANY,
        }

    def test01_spool_test_page(self):
        """Test printing a test page"""
        Printer = self.env['print.printer']
        Printer.spool_test_page()
        self.mock_subprocess.Popen.assert_called_once_with(
            [MOCK_LPR, '-T', ANY], **self.mock_popen_kwargs
        )
