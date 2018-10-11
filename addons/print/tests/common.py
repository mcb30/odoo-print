"""Printing tests"""

import tempfile
from unittest.mock import patch, Mock, ANY
from odoo.tools import config
from odoo.tools.mimetypes import guess_mimetype
from odoo.tests import common

MOCK_LPR = 'MOCK_LPR'
HTML_MIMETYPE = guess_mimetype(b'<html><body></body></html>')
XML_MIMETYPE = guess_mimetype(b'<?xml version="1.0"/>')


@common.at_install(False)
@common.post_install(True)
class PrinterCase(common.SavepointCase):
    """Base test case for printing"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Reset system default printer
        cls.printer_default = cls.env.ref('print.default_printer')
        cls.printer_default.queue = None
        cls.printer_default.set_system_default()

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
