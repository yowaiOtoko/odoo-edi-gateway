import json
import logging

from odoo import http
from odoo.http import request

from ..adapters import get_adapter
from ..services.edi_service import EDIService

_logger = logging.getLogger(__name__)


class EDIWebhookController(http.Controller):

    @http.route(
        '/edi/pdp/webhook/inbound',
        type='http',
        auth='none',
        methods=['POST'],
        csrf=False,
    )
    def webhook_inbound(self, **kwargs):
        """Receive inbound invoice payload from PDP."""
        body = request.httprequest.data
        headers = dict(request.httprequest.headers)
        company = self._resolve_company(headers)
        if not company:
            _logger.warning("Inbound webhook: no matching company found")
            return request.make_response('Unauthorized', status=401)

        adapter = get_adapter(company)
        if not adapter.validate_webhook(headers, body):
            _logger.warning("Inbound webhook: invalid signature for company %s", company.id)
            return request.make_response('Forbidden', status=403)

        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            return request.make_response('Bad Request', status=400)

        external_id = payload.get('invoice_id') or payload.get('id')
        raw_xml = payload.get('xml') or payload.get('facturx_xml') or ''

        if not external_id:
            return request.make_response('Bad Request: missing invoice_id', status=400)

        existing = request.env['edi.inbound.invoice'].sudo().search([
            ('external_id', '=', external_id),
            ('provider', '=', company.edi_pdp_provider),
        ], limit=1)

        if existing:
            _logger.info("Inbound webhook: duplicate external_id=%s, skipping", external_id)
            return request.make_response('OK', status=200)

        inbound = request.env['edi.inbound.invoice'].sudo().create({
            'external_id': external_id,
            'provider': company.edi_pdp_provider,
            'raw_xml': raw_xml,
            'state': 'received',
            'company_id': company.id,
        })
        inbound.with_delay()._job_process_inbound()

        return request.make_response('OK', status=200)

    @http.route(
        '/edi/pdp/webhook/lifecycle',
        type='http',
        auth='none',
        methods=['POST'],
        csrf=False,
    )
    def webhook_lifecycle(self, **kwargs):
        """Receive lifecycle state update from PDP."""
        body = request.httprequest.data
        headers = dict(request.httprequest.headers)
        company = self._resolve_company(headers)
        if not company:
            return request.make_response('Unauthorized', status=401)

        adapter = get_adapter(company)
        if not adapter.validate_webhook(headers, body):
            return request.make_response('Forbidden', status=403)

        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            return request.make_response('Bad Request', status=400)

        service = EDIService(request.env.sudo())
        try:
            service.handle_lifecycle_webhook(company, payload)
        except Exception as exc:
            _logger.error("Lifecycle webhook processing error: %s", exc)
            return request.make_response('Internal Server Error', status=500)

        return request.make_response('OK', status=200)

    def _resolve_company(self, headers: dict):
        """Identify company from X-Company-ID header or fall back to first."""
        company_id = headers.get('X-Company-Id') or headers.get('X-Company-ID')
        if company_id:
            try:
                return request.env['res.company'].sudo().browse(int(company_id))
            except Exception:
                pass
        return request.env['res.company'].sudo().search([], limit=1)
