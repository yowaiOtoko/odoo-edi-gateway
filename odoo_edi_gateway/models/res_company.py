from odoo import fields, models

from ..services.edi_service import EDIService
from ..services.sentry import capture_exception


class ResCompany(models.Model):
    _inherit = 'res.company'

    edi_pdp_provider = fields.Selection(
        selection=[('super_pdp', 'SUPER PDP')],
        string='PDP Provider',
        default='super_pdp',
    )
    edi_super_pdp_client_id = fields.Char(string='SUPER PDP Client ID')
    edi_super_pdp_client_secret = fields.Char(string='SUPER PDP Client Secret')
    edi_super_pdp_base_url = fields.Char(
        string='SUPER PDP API Base URL',
        default='https://api.sandbox.superpdp.tech/v1.beta',
    )
    edi_super_pdp_auth_url = fields.Char(
        string='SUPER PDP Auth URL',
        default='https://api.sandbox.superpdp.tech',
    )
    edi_super_pdp_sandbox = fields.Boolean(
        string='Sandbox Mode',
        default=True,
    )
    edi_super_pdp_access_token = fields.Char(string='SUPER PDP Access Token (cached)', readonly=True)
    edi_super_pdp_token_expiry = fields.Datetime(string='Token Expiry (UTC)', readonly=True)
    edi_polling_enabled = fields.Boolean(
        string='Enable Fallback Polling',
        default=False,
    )
    edi_polling_interval = fields.Integer(
        string='Polling Interval (minutes)',
        default=15,
    )
    edi_webhook_secret = fields.Char(string='Webhook Signing Secret')

    def action_manual_poll_edi_status(self):
        """Manual trigger: poll all in-flight invoices for this company."""
        self.ensure_one()
        moves = self.env['account.move'].search([
            ('company_id', '=', self.id),
            ('edi_state', 'in', ['sent', 'delivered']),
            ('edi_external_id', '!=', False),
        ])
        service = EDIService(self.env)
        ok_count = 0
        error_count = 0
        for move in moves:
            try:
                service.poll_invoice_status(move)
                ok_count += 1
            except Exception as exc:
                error_count += 1
                capture_exception(exc, env=self.env, context={
                    'operation': 'manual_poll_company',
                    'company_id': self.id,
                    'move_id': move.id,
                })

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'EDI Manual Poll Complete',
                'message': f'Checked {ok_count} invoice(s), {error_count} error(s).',
                'type': 'success' if error_count == 0 else 'warning',
                'sticky': False,
            },
        }
