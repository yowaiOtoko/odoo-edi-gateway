from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    edi_pdp_provider = fields.Selection(
        selection=[('super_pdp', 'SUPER PDP')],
        string='PDP Provider',
        default='super_pdp',
    )
    edi_super_pdp_api_key = fields.Char(string='SUPER PDP API Key')
    edi_super_pdp_base_url = fields.Char(
        string='SUPER PDP Base URL',
        default='https://api.sandbox.super-pdp.fr/v1',
    )
    edi_super_pdp_sandbox = fields.Boolean(
        string='Sandbox Mode',
        default=True,
    )
    edi_polling_enabled = fields.Boolean(
        string='Enable Fallback Polling',
        default=False,
    )
    edi_polling_interval = fields.Integer(
        string='Polling Interval (minutes)',
        default=15,
    )
    edi_webhook_secret = fields.Char(string='Webhook Signing Secret')
