from odoo import fields, models


class EdiInvoiceLog(models.Model):
    _name = 'edi.invoice.log'
    _description = 'EDI Invoice Audit Log'
    _order = 'create_date desc'
    _rec_name = 'event_type'

    move_id = fields.Many2one(
        comodel_name='account.move',
        string='Invoice',
        required=True,
        ondelete='cascade',
        index=True,
    )
    event_type = fields.Char(string='Event', required=True)
    old_state = fields.Char(string='From State')
    new_state = fields.Char(string='To State')
    payload = fields.Text(string='Payload Sent')
    provider_response = fields.Text(string='Provider Response')
    create_date = fields.Datetime(string='Timestamp', readonly=True)
