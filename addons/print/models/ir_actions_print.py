"""Print actions."""

import logging
from odoo import api, fields, models
from odoo.tools import config

_logger = logging.getLogger(__name__)

class IrActionsPrint(models.Model):
    """Print actions.

       Odoo actions are like named events. Raised in the context of a modelled
       object, actions are decoupled from the behaviour to effect when handling
       the event. Print actions further decouple behaviour by allowing
       different print strategies to be executed for different modelled objects.

       If the report specified for a print strategy cannot render a document
       from records selected from the modelled object by the strategy then an
       error is logged and the strategy is skipped.
    """

    _inherit = 'ir.actions.server'

    state = fields.Selection(selection_add=[('print', 'Print')])

    # A print action must be configured with a print strategy model. The print
    # strategies to execute for an object are selected from that model.
    strategy_id = fields.Many2one('ir.model', 'Print Strategy')

    _sql_constraints = [(
        'print_strategy',
        "CHECK (NOT (state = 'print' AND strategy_id IS NULL))",
        'Print Strategy must be set',
    )]

    @api.multi
    def run_action_print(self, action, eval_context=None): # pylint: disable=unused-argument
        """Print a report using the print strategies for the context object."""
        # get the context object
        context = action.env.context
        if 'skip_printing' in context and context['skip_printing']:
            _logger.info('Skipping printing due to context switch')
            return False
        active_model = context['active_model']
        active_id = context['active_id']
        obj = action.env[active_model].browse(active_id)
        # execute strategies for printing the object
        for strategy in self.env[self.strategy_id.model].strategies(obj):
            if not strategy.enabled():
                continue
            # the strategy model must produce print strategies
            printer = strategy.printer_id
            report = strategy.report_id
            records = strategy.records(obj, context)
            # print
            if records is not None:
                _logger.info(
                    'executing %s action with strategy %s for %s id %d',
                    action.state, strategy.name,
                    active_model, active_id)
                printer.spool_report(records.ids, report)

class PrintStrategy(models.Model):
    """Print strategy.

       The base print strategy is to print the context object using the
       specified report on the specified printer.
    """
    _name = 'print.strategy'

    name = fields.Char(required=True)

    # the report to render for each selected record
    report_id = fields.Many2one(
        'ir.actions.report', string='Report',
        required=True,
    )

    # the model of context object which this strategy will render
    model = fields.Char(
        related='report_id.model',
        readonly=True,
    )

    # the printer to print each rendered document with
    printer_id = fields.Many2one(
        'print.printer', string='Printer',
        required=False,
    )

    # configurable safety catch
    safety = fields.Char(
        string='Safety Catch',
        help="""Configuration file option required for operation.

        If present, this option must have a truthy value within the
        local configuration file to enable printing using this strategy.
        """
    )

    @api.model
    def strategies(self, obj):
        """Return the print strategies to use for context `obj`."""
        return self.search([
            ('model', '=', obj._name),
        ])

    @api.multi
    def enabled(self):
        """Return True if a print strategy is enabled, False otherwise."""
        self.ensure_one()
        if not self.safety:
            _logger.info('%s %s disabled, enable by configuring safety.',
                             self._name, self.name)
            return False
        else:
            section, _sep, key = self.safety.rpartition('.')
            if not config.get_misc(section or self._name, key):
                _logger.info('%s %s disabled, enable by configuring safety %s in config file.',
                             self._name, self.name,
                             '.'.join((section or self._name, key)))
                return False
        return True

    @api.multi
    def records(self, obj, context=None):
        """Return the records to render for context `obj`

           Return None if this strategy should be skipped
        """
        return obj
