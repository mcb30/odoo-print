"""Printing action tests"""

from unittest.mock import ANY

from psycopg2 import IntegrityError

from odoo.tools import mute_logger
from .common import PrinterCase

class TestActionPrint(PrinterCase):
    """Printing action tests"""
    action_model = 'ir.actions.server'
    strategy_model = 'print.strategy'

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
        self.create_strategy('Test 07', self.default_report, None, 'test07')
        # nothing to be printed when the safety catch is not disabled
        printer = self.default_printer
        action.with_context(**self.action_context(printer)).run()
        self.mock_subprocess.Popen.assert_not_called()
