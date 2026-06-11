from odoo import api, fields, models
from odoo.exceptions import UserError

from ..services.edi_service import EDIService


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

    edi_company_provider = fields.Selection(
        related='company_id.edi_pdp_provider',
        string='EDI Company Provider',
        readonly=True,
    )
    edi_company_sandbox = fields.Boolean(
        related='company_id.edi_super_pdp_sandbox',
        string='EDI Company Sandbox',
        readonly=True,
    )

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

    def action_send_sandbox_test_edi(self):
        """Manual trigger to generate/send a fake test invoice via SUPER PDP sandbox."""
        service = EDIService(self.env)
        for move in self:
            if move.state != 'posted':
                raise UserError("Invoice must be posted before sandbox test transmission.")
            service.send_sandbox_test_invoice(move)

    def action_poll_edi_status_now(self):
        """Manual trigger: poll provider status for this invoice now."""
        service = EDIService(self.env)
        for move in self:
            if not move.edi_external_id:
                raise UserError("No EDI external ID found. Send the invoice first.")
            service.poll_invoice_status(move)

    def action_retry_edi(self):
        """Force re-queue the EDI job regardless of current EDI state."""
        for move in self:
            if move.state != 'posted':
                raise UserError("Invoice must be posted before EDI transmission.")
            move._edi_set_state('queued')
            move.with_delay()._job_send_edi()

    def action_view_queue_jobs(self):
        """Open the queue.job list filtered to this invoice's EDI jobs."""
        return {
            'type': 'ir.actions.act_window',
            'name': 'EDI Queue Jobs',
            'res_model': 'queue.job',
            'view_mode': 'list,form',
            'domain': [
                ('channel_method_name', 'like', '_job_send_edi'),
                ('model_name', '=', 'account.move'),
            ],
        }

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
