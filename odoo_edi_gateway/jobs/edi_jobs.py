"""queue_job-based async tasks for EDI processing."""
import logging

from odoo import api, models

from ..services.edi_service import EDIService

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = 'account.move'

    def _job_send_edi(self):
        """Async job: generate Factur-X and submit to PDP."""
        service = EDIService(self.env)
        try:
            service.send_invoice(self)
        except Exception as exc:
            _logger.error("EDI send job failed for move %s: %s", self.id, exc)
            raise

    @api.model
    def _cron_poll_edi_status(self):
        """Cron: poll PDP for status updates on in-flight invoices (optional fallback)."""
        companies = self.env['res.company'].search([('edi_polling_enabled', '=', True)])
        for company in companies:
            moves = self.search([
                ('company_id', '=', company.id),
                ('edi_state', 'in', ['sent', 'delivered']),
                ('edi_external_id', '!=', False),
            ])
            service = EDIService(self.env)
            for move in moves:
                try:
                    service.poll_invoice_status(move)
                except Exception as exc:
                    _logger.error("Polling error for move %s: %s", move.id, exc)


class EdiInboundInvoice(models.Model):
    _inherit = 'edi.inbound.invoice'

    def _job_process_inbound(self):
        """Async job: parse inbound invoice XML and create draft account.move."""
        service = EDIService(self.env)
        try:
            service.process_inbound(self)
        except Exception as exc:
            _logger.error("Inbound EDI job failed for %s: %s", self.external_id, exc)
            raise
