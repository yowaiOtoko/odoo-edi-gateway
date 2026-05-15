import json
from odoo import api, fields, models


INBOUND_STATES = [
    ('received', 'Received'),
    ('parsing', 'Parsing'),
    ('parsed', 'Parsed'),
    ('creating', 'Creating Invoice'),
    ('done', 'Done'),
    ('error', 'Error'),
]


class EdiInboundInvoice(models.Model):
    _name = 'edi.inbound.invoice'
    _description = 'EDI Inbound Invoice'
    _order = 'create_date desc'
    _rec_name = 'external_id'

    external_id = fields.Char(
        string='External ID',
        required=True,
        index=True,
        copy=False,
    )
    provider = fields.Char(string='PDP Provider')
    raw_xml = fields.Text(string='Raw XML')
    raw_pdf = fields.Binary(string='Raw PDF', attachment=True)
    parsed_data = fields.Text(string='Parsed Data (JSON)')
    state = fields.Selection(
        selection=INBOUND_STATES,
        string='State',
        default='received',
        index=True,
    )
    error_message = fields.Text(string='Error')
    move_id = fields.Many2one(
        comodel_name='account.move',
        string='Created Invoice',
        copy=False,
        readonly=True,
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Company',
        default=lambda self: self.env.company,
        required=True,
    )

    _sql_constraints = [
        ('external_id_uniq', 'UNIQUE(external_id, provider)', 'External ID must be unique per provider.'),
    ]

    def get_parsed_data(self):
        self.ensure_one()
        if self.parsed_data:
            return json.loads(self.parsed_data)
        return {}

    def set_parsed_data(self, data: dict):
        self.ensure_one()
        self.parsed_data = json.dumps(data, ensure_ascii=False, indent=2)

    def action_process(self):
        """Trigger parsing and invoice creation via queue_job."""
        for rec in self:
            if rec.state not in ('received', 'error'):
                continue
            rec.state = 'parsing'
            rec.with_delay()._job_process_inbound()

    def action_view_invoice(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Invoice',
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': self.move_id.id,
        }
