"""Printing tests"""

from psycopg2 import IntegrityError
from contextlib import contextmanager
from io import BytesIO
import pathlib
import tempfile
import sys
from unittest.mock import patch, Mock, ANY, call
from lxml import etree
from odoo.modules.module import get_resource_from_path, get_resource_path
from odoo.tools import config, mute_logger
from odoo.tools.mimetypes import guess_mimetype
from odoo.tests import common

MOCK_LPR = 'MOCK_LPR'
HTML_MIMETYPE = guess_mimetype(b'<html><body></body></html>')
XML_MIMETYPE = guess_mimetype(b'<?xml version="1.0"/>')
PDF_MIMETYPE = 'application/pdf'


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

        # Locate test file directory corresponding to the class (which
        # may be a derived class in a different module).
        module_file = sys.modules[cls.__module__].__file__
        module = get_resource_from_path(module_file)[0]

        path = get_resource_path(module, 'tests', 'files')
        if path:
            cls.files = pathlib.Path(path)

        cls.safety = "print.default_test_print"
        # Enable default print safety for tests
        config.misc["print"] = {"default_test_print": 1}

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

        # Force test_enable to True (which is not necessarily the case
        # when tests are run via the "-f" command-line option) to
        # prevent ir.actions.report from committing the assets bundle
        # and hence releasing the savepoint.
        #
        # Create mock test_report_directory to ensure that
        # ir.actions.report.render_qweb_pdf() will actually attempt to
        # generate a PDF
        #
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        patch_config = patch.dict(config.options, {
            'test_enable': True,
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

    def assertPrintedLprMulti(self, *seq_args):
        """Assert that ``lpr`` was invoked with the sequence of args lists"""
        def seq_calls():
            """Generate the sequence of calls expected for ``seq_args``."""
            for args in seq_args:
                yield call([MOCK_LPR, *args], stdin=ANY, stdout=ANY, stderr=ANY)
                yield call().communicate(ANY)
        self.mock_subprocess.Popen.assert_has_calls(seq_calls())
        self.mock_lpr.reset_mock()
        self.mock_subprocess.Popen.reset_mock()

    def assertCpclReport(self, cpcl, filename):
        """Assert that generated CPCL/XML report matches the test file"""
        def canonical(doc):
            """Canonicalize and pretty-print XML document"""
            with BytesIO() as f:
                doc.write_c14n(f)
                compact = etree.fromstring(f.getvalue())
            return etree.tostring(compact, pretty_print=True).decode()
        parser = etree.XMLParser(remove_blank_text=True)
        path = self.files.joinpath(filename)
        expected = canonical(etree.parse(str(path), parser))
        actual = canonical(etree.ElementTree(etree.fromstring(cpcl, parser)))
        try:
            maxDiff = self.maxDiff
            self.maxDiff = None
            self.assertEqual(actual, expected)
        finally:
            self.maxDiff = maxDiff


@common.at_install(False)
@common.post_install(True)
class PrinterHttpCase(common.HttpCase):
    """Base HTTP test case for printing"""

    def setUp(self):
        super().setUp()

        # Use default test cursor for default environment
        def restore(cr=self.cr, env=self.env):
            """Restore original cursor and environment"""
            self.env = env
            self.cr = cr
        self.cr = self.registry.cursor()
        self.env = self.env(self.cr)
        self.addCleanup(restore)

    @contextmanager
    def release(self):
        """Temporarily release test cursor

        Temporarily release the test cursor to allow for use by
        external threads (e.g. the thread handling an HTTP request).
        """

        # Commit (i.e. create a savepoint) so that any changes are
        # visible to external threads
        self.cr.commit()

        # Release our thread's cursor lock
        self.cr.release()

        try:

            # Allow external thread(s) to use the cursor
            yield

        finally:

            # Reacquire our thread's cursor lock
            self.cr.acquire()

            # Flush cache so that we pick up any external changes
            self.env.clear()

    def url_open(self, *args, **kwargs):
        # pylint: disable=arguments-differ
        with self.release():
            return super().url_open(*args, **kwargs)

class ActionPrintCase(PrinterCase):
    """Base printing action tests for all print strategy models.

       This class is not for running tests directly. Instead, classes for
       running tests must derive from this class. The placement of this
       class in this module requires that this module is not searched for
       tests.

       To use this class in a derived class for running tests you must import
       this class by importing the module which contains this class. If you
       directly import this class and not the whole module then the unittest
       framework will find this class and run the tests against an instance
       of this base class, which is not the intended use. In order to protect
       against this `strategy_model` is set to None which will cause test
       failures. (This mechanism requires that 'strategy_id' is mandatory in
       the data model for `action_model`. If it is not, then the behaviour of
       running tests in this class is not defined.)

       Derived classes must set `strategy_model` as appropriate. Derived
       classes are also responsible for maintaining test method numbering.
       Though unit tests should ideally never assume the order in which they
       are written, these tests are not unit tests: they are higher level
       tests executed using the unittest framework. Derived classes must not
       assume that the order in which tests are executed is unimportant and
       must maintain test method naming (numbering) such that derived class
       tests are executed after base class tests. It should be assumed that
       further test cases will be added to this class.
    """
    action_model = 'ir.actions.server'
    # derived classes MUST set the strategy model to test
    # None ensures running tests in an instance of this class fails
    strategy_model = None

    @property
    def default_report(self):
        """Return the default report"""
        return self.env.ref('print.action_report_test_page')

    @property
    def default_printer(self):
        """Return the default printer"""
        return self.env.ref('print.default_printer')

    @classmethod
    def model_id(cls, model):
        """Return the model id of `model`."""
        return cls.env['ir.model']._get_id(model)

    def create_action(self, name, model=True):
        """Return a new print action with `name` and print strategy `model`.
           If `model` is True, then use :attr:`strategy_model` instead.
        """
        if model is True:
            model = self.strategy_model
        return self.env[self.action_model].create({
            'name': name,
            'model_id': self.model_id(self.action_model),
            'state': 'print',
            'strategy_id': None if model is None else self.model_id(model),
        })

    def create_strategy(self, name, report, printer,
                        safety=None, model=True, **kwargs):
        """Return a new print strategy instance from kwargs overridden by args.
           If `model` is True, then use :attr:`strategy_model` instead.
        """
        if safety is None:
            safety = self.safety
        if model is True:
            model = self.strategy_model
        kwargs.update({
            'name': name,
            'report_id': None if report is None else report.id,
            'printer_id': None if printer is None else printer.id,
            'safety': safety,
        })
        return self.env[model].create(kwargs)

    def action_context(self, obj):
        """Return an action run context which may select strategies."""
        return {'active_model': obj._name, 'active_ids': obj.ids}

    def benign_context(self, obj):
        """Return an action run context which selects no strategies."""
        return self.action_context(obj)

    def test01_missing_strategy(self):
        """Test print action must specify strategy_id"""
        with mute_logger('odoo.sql_db'), self.assertRaises(IntegrityError):
            self.create_action('missing strategy_id', None)

    def test02_no_strategies(self):
        """Test print action with no strategies"""
        action = self.create_action('no strategies')
        # nothing to be printed when the action is run in the wrong context
        action.with_context(**self.benign_context(action)).run()
        self.mock_subprocess.Popen.assert_not_called()

    def test03_missing_report(self):
        """Test print strategy must specify report_id"""
        with mute_logger('odoo.sql_db'), self.assertRaises(IntegrityError):
            self.create_strategy('missing report_id', None, None)

    def test04_missing_printer(self):
        """Test print strategy may omit printer_id"""
        self.create_strategy('missing printer_id', self.default_report, None)

    def test05_one_strategy(self):
        """Test print action with one strategy"""
        action = self.create_action('one strategy')
        self.create_strategy('Chesney', self.default_report, None)
        # nothing to be printed when the action is run in the wrong context
        action.with_context(**self.benign_context(action)).run()
        self.mock_subprocess.Popen.assert_not_called()
        # a single document to be printed when run in the right context
        printer = self.default_printer
        action.with_context(**self.action_context(printer)).run()
        self.assertPrintedLpr('-T', ANY)

    def test06_two_strategies(self):
        """Test print action with two strategies"""
        action = self.create_action('two strategies')
        self.create_strategy('Ant', self.default_report, None)
        self.create_strategy('Dec', self.default_report, None)
        # nothing to be printed when the action is run in the wrong context
        action.with_context(**self.benign_context(action)).run()
        self.mock_subprocess.Popen.assert_not_called()
        # two documents to be printed when run in the right context
        printer = self.default_printer
        action.with_context(**self.action_context(printer)).run()
        self.assertPrintedLprMulti(
            ('-T', ANY),
            ('-T', ANY),
        )

    def test07_safety_catch(self):
        """Test print strategy disabled by safety catch"""
        action = self.create_action('safety strategy')
        self.create_strategy('Test safety', self.default_report, None, 'safety')
        # nothing to be printed when the safety catch is not disabled
        printer = self.default_printer
        action.with_context(**self.action_context(printer)).run()
        self.mock_subprocess.Popen.assert_not_called()
