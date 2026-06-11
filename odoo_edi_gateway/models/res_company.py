from odoo import fields, models


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
        default='https://api.sandbox.super-pdp.tech/v1.beta',
    )
    edi_super_pdp_auth_url = fields.Char(
        string='SUPER PDP Auth URL',
        default='https://api.sandbox.super-pdp.tech',
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
