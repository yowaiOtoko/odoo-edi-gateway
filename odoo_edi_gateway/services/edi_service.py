import json
import logging

from odoo import fields
from odoo.exceptions import UserError

from ..adapters import get_adapter
from .facturx_generator import FacturXGenerator
from .facturx_parser import FacturXParser
from .sentry import capture_exception

_logger = logging.getLogger(__name__)

MAX_RETRIES = 5


class EDIService:
    """Orchestrates outbound and inbound EDI flows."""

    def __init__(self, env):
        self.env = env

    # -------------------------------------------------------------------------
    # Outbound
    # -------------------------------------------------------------------------

    def send_invoice(self, move):
        """Generate Factur-X, submit to PDP, update state."""
        from ..adapters import get_adapter
        adapter = get_adapter(move.company_id)
        if not adapter:
            _logger.warning("EDI not configured for company %s, skipping send_invoice", move.company_id.id)
            return
        generator = FacturXGenerator(move)
        try:
            pdf_bytes = generator.generate()
        except Exception as exc:
            _logger.error("Factur-X generation failed for move %s: %s", move.id, exc)
            move._edi_set_state('error', provider_response=str(exc))
            capture_exception(exc, env=self.env, context={
                'operation': 'facturx_generate',
                'move_id': move.id,
                'company_id': move.company_id.id,
            })
            raise

        invoice_hash = generator.compute_hash(pdf_bytes)

        if move.edi_invoice_hash and move.edi_invoice_hash == invoice_hash and move.edi_external_id:
            _logger.info("Skipping duplicate submission for move %s (hash match)", move.id)
            return

        move.edi_invoice_hash = invoice_hash
        metadata = generator.get_metadata()
        result = adapter.send_invoice(pdf_bytes, invoice_hash, metadata)

        if result.success:
            move.edi_external_id = result.external_id
            move.edi_provider = move.company_id.edi_pdp_provider
            move.edi_sent_at = fields.Datetime.now()
            move.edi_last_error = False
            move._edi_set_state('sent', payload=json.dumps(metadata), provider_response=json.dumps(result.raw_response))
        else:
            move.edi_last_error = result.error
            move._edi_set_state('error', provider_response=json.dumps(result.raw_response))
            raise UserError(f"EDI transmission failed: {result.error}")

    def handle_lifecycle_webhook(self, company, payload: dict):
        """Process an inbound lifecycle update webhook from PDP."""
        external_id = payload.get('invoice_id') or payload.get('id')
        raw_status = (payload.get('status') or '').upper()
        if not external_id:
            _logger.warning("Webhook payload missing invoice_id: %s", payload)
            return

        move = self.env['account.move'].search([
            ('edi_external_id', '=', external_id),
            ('company_id', '=', company.id),
        ], limit=1)
        if not move:
            _logger.warning("Webhook: no invoice found for external_id=%s", external_id)
            return

        from ..adapters.super_pdp import _STATE_MAP
        new_state = _STATE_MAP.get(raw_status)
        if new_state and new_state != move.edi_state:
            move._edi_set_state(new_state, provider_response=json.dumps(payload))

    def poll_invoice_status(self, move):
        """Fallback polling: fetch current status from PDP and sync."""
        from ..adapters import get_adapter
        if not move.edi_external_id:
            return
        adapter = get_adapter(move.company_id)
        if not adapter:
            _logger.warning("EDI not configured for company %s, skipping poll_invoice_status", move.company_id.id)
            return
        result = adapter.get_status(move.edi_external_id)
        if result.success and result.edi_state and result.edi_state != move.edi_state:
            move._edi_set_state(result.edi_state, provider_response=json.dumps(result.raw_response))
        elif not result.success:
            _logger.error("Polling failed for move %s: %s", move.id, result.error)
            move.edi_last_error = result.error
            move._edi_set_state('error', provider_response=json.dumps(result.raw_response or {}))
            raise UserError(f"EDI polling failed: {result.error}")

    def send_sandbox_test_invoice(self, move):
        """Manual trigger: ask SUPER PDP sandbox to generate a fake test invoice."""
        adapter = get_adapter(move.company_id)
        if not adapter:
            raise UserError("EDI is not configured for this company.")
        if move.company_id.edi_pdp_provider != 'super_pdp':
            raise UserError("Sandbox test generation is currently available only for SUPER PDP.")
        if not move.company_id.edi_super_pdp_sandbox:
            raise UserError("Sandbox mode must be enabled to generate a fake test invoice.")

        result = adapter.generate_test_invoice()
        if result.success:
            move.edi_external_id = result.external_id or move.edi_external_id
            move.edi_provider = move.company_id.edi_pdp_provider
            move.edi_sent_at = fields.Datetime.now()
            move.edi_last_error = False
            move._edi_set_state(
                'sent',
                payload=json.dumps({'manual_test': True, 'source': 'super_pdp_generate_test_invoice'}),
                provider_response=json.dumps(result.raw_response or {}),
            )
            return

        move.edi_last_error = result.error
        move._edi_set_state('error', provider_response=json.dumps(result.raw_response or {}))
        raise UserError(f"Sandbox test invoice failed: {result.error}")

    # -------------------------------------------------------------------------
    # Inbound
    # -------------------------------------------------------------------------

    def process_inbound(self, inbound):
        """Parse raw XML and create a draft account.move."""
        inbound.state = 'parsing'
        parser = FacturXParser()
        try:
            data = parser.parse((inbound.raw_xml or '').encode('utf-8'))
        except Exception as exc:
            inbound.state = 'error'
            inbound.error_message = str(exc)
            _logger.error("Inbound parse error for %s: %s", inbound.external_id, exc)
            capture_exception(exc, env=self.env, context={
                'operation': 'process_inbound_parse',
                'inbound_id': inbound.id,
                'external_id': inbound.external_id,
            })
            return

        if not data:
            inbound.state = 'error'
            inbound.error_message = 'Parser returned empty result'
            return

        inbound.set_parsed_data(data)
        inbound.state = 'parsed'

        try:
            move = self._create_draft_invoice(inbound, data)
            inbound.move_id = move.id
            inbound.state = 'done'
        except Exception as exc:
            inbound.state = 'error'
            inbound.error_message = str(exc)
            _logger.error("Inbound invoice creation error for %s: %s", inbound.external_id, exc)
            capture_exception(exc, env=self.env, context={
                'operation': 'process_inbound_create_move',
                'inbound_id': inbound.id,
                'external_id': inbound.external_id,
            })

    def _create_draft_invoice(self, inbound, data: dict):
        supplier_name = data.get('supplier', {}).get('name', '')
        partner = self.env['res.partner'].search([('name', 'ilike', supplier_name)], limit=1)
        if not partner:
            partner = self.env['res.partner'].create({
                'name': supplier_name,
                'company_type': 'company',
            })

        currency = self.env['res.currency'].search([('name', '=', data.get('currency', 'EUR'))], limit=1)

        invoice_vals = {
            'move_type': 'in_invoice',
            'partner_id': partner.id,
            'ref': data.get('invoice_number', ''),
            'currency_id': currency.id if currency else self.env.company.currency_id.id,
            'company_id': inbound.company_id.id,
            'invoice_line_ids': [
                (0, 0, {
                    'name': line.get('name') or 'Service',
                    'quantity': line.get('quantity', 1.0),
                    'price_unit': line.get('price_unit', 0.0),
                })
                for line in data.get('lines', [])
            ],
        }
        return self.env['account.move'].create(invoice_vals)
