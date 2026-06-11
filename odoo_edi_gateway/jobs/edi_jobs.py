"""queue_job-based async tasks for EDI processing."""
import logging

from odoo import api, models

from ..services.edi_service import EDIService
from ..services.sentry import capture_exception

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = 'account.move'

    def _job_send_edi(self):
        """Async job: generate Factur-X and submit to PDP."""
        from ..adapters import is_edi_configured
        if not is_edi_configured(self.company_id):
            _logger.warning("EDI not configured for company %s, skipping _job_send_edi", self.company_id.id)
            return
        service = EDIService(self.env)
        try:
            service.send_invoice(self)
        except Exception as exc:
            _logger.error("EDI send job failed for move %s: %s", self.id, exc)
            capture_exception(exc, env=self.env, context={
                'operation': 'job_send_edi',
                'move_id': self.id,
                'company_id': self.company_id.id,
            })
            raise

    @api.model
    def _cron_poll_edi_status(self):
        """Cron: poll PDP for status updates on in-flight invoices (optional fallback)."""
        from ..adapters import is_edi_configured
        companies = self.env['res.company'].search([('edi_polling_enabled', '=', True)])
        for company in companies:
            if not is_edi_configured(company):
                _logger.warning("EDI not configured for company %s, skipping poll", company.id)
                continue
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
                    capture_exception(exc, env=self.env, context={
                        'operation': 'cron_poll_edi_status',
                        'move_id': move.id,
                        'company_id': company.id,
                    })


class EdiInboundInvoice(models.Model):
    _inherit = 'edi.inbound.invoice'

    def _job_process_inbound(self):
        """Async job: parse inbound invoice XML and create draft account.move."""
        service = EDIService(self.env)
        try:
            service.process_inbound(self)
        except Exception as exc:
            _logger.error("Inbound EDI job failed for %s: %s", self.external_id, exc)
            capture_exception(exc, env=self.env, context={
                'operation': 'job_process_inbound',
                'inbound_id': self.id,
                'external_id': self.external_id,
            })
            raise
