from odoo import api, fields, models
from odoo.exceptions import UserError


EDI_STATES = [
    ('draft', 'Draft'),
    ('validated', 'Validated'),
    ('queued', 'Queued'),
    ('sent', 'Sent'),
    ('delivered', 'Delivered'),
    ('accepted', 'Accepted'),
    ('rejected', 'Rejected'),
    ('error', 'Error'),
]


class AccountMove(models.Model):
    _inherit = 'account.move'

    edi_state = fields.Selection(
        selection=EDI_STATES,
        string='EDI State',
        default='draft',
        copy=False,
        index=True,
    )
    edi_provider = fields.Char(
        string='EDI Provider',
        copy=False,
    )
    edi_external_id = fields.Char(
        string='EDI External ID',
        copy=False,
        index=True,
    )
    edi_last_error = fields.Text(
        string='EDI Last Error',
        copy=False,
    )
    edi_sent_at = fields.Datetime(
        string='EDI Sent At',
        copy=False,
    )
    edi_invoice_hash = fields.Char(
        string='EDI Invoice Hash',
        copy=False,
        index=True,
    )
    edi_log_ids = fields.One2many(
        comodel_name='edi.invoice.log',
        inverse_name='move_id',
        string='EDI Logs',
    )
    edi_log_count = fields.Integer(
        compute='_compute_edi_log_count',
    )

    @api.depends('edi_log_ids')
    def _compute_edi_log_count(self):
        for move in self:
            move.edi_log_count = len(move.edi_log_ids)

    def action_send_edi(self):
        """Queue invoice for EDI transmission."""
        for move in self:
            if move.state != 'posted':
                raise UserError("Invoice must be posted before EDI transmission.")
            if move.edi_state not in ('draft', 'error', 'rejected'):
                raise UserError(f"Cannot send invoice in EDI state '{move.edi_state}'.")
            move._edi_set_state('queued')
            move.with_delay()._job_send_edi()

    def _edi_set_state(self, new_state, payload=None, provider_response=None):
        for move in self:
            old_state = move.edi_state
            move.edi_state = new_state
            self.env['edi.invoice.log'].create({
                'move_id': move.id,
                'event_type': f'{old_state}_to_{new_state}',
                'old_state': old_state,
                'new_state': new_state,
                'payload': payload or '',
                'provider_response': provider_response or '',
            })

    def action_view_edi_logs(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'EDI Logs',
            'res_model': 'edi.invoice.log',
            'view_mode': 'list,form',
            'domain': [('move_id', '=', self.id)],
            'context': {'default_move_id': self.id},
        }
