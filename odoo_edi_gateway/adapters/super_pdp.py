import base64
import hashlib
import hmac
import logging

import requests

from .base import PDPAdapter, SendResult, StatusResult

_logger = logging.getLogger(__name__)

# SUPER PDP lifecycle state → internal EDI state mapping
_STATE_MAP = {
    'SUBMITTED': 'sent',
    'DELIVERED': 'delivered',
    'ACCEPTED': 'accepted',
    'REJECTED': 'rejected',
    'ERROR': 'error',
}

_TIMEOUT = 30  # seconds


class SuperPDPAdapter(PDPAdapter):
    """SUPER PDP REST API adapter (sandbox + production)."""

    def _base_url(self) -> str:
        return (self.company.edi_super_pdp_base_url or 'https://api.sandbox.super-pdp.fr/v1').rstrip('/')

    def _headers(self) -> dict:
        return {
            'Authorization': f'Bearer {self.company.edi_super_pdp_api_key}',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'X-Sandbox': 'true' if self.company.edi_super_pdp_sandbox else 'false',
        }

    def send_invoice(self, facturx_pdf: bytes, invoice_hash: str, metadata: dict) -> SendResult:
        url = f'{self._base_url()}/invoices'
        payload = {
            'document': base64.b64encode(facturx_pdf).decode(),
            'document_format': 'FACTURX',
            'idempotency_key': invoice_hash,
            'sender_siret': metadata.get('sender_siret', ''),
            'recipient_siret': metadata.get('recipient_siret', ''),
            'invoice_number': metadata.get('invoice_number', ''),
            'invoice_date': metadata.get('invoice_date', ''),
            'total_amount_ati': metadata.get('total_amount_ati', 0),
        }
        try:
            resp = requests.post(url, json=payload, headers=self._headers(), timeout=_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
            return SendResult(
                success=True,
                external_id=data.get('invoice_id') or data.get('id'),
                raw_response=data,
            )
        except requests.HTTPError as exc:
            body = {}
            try:
                body = exc.response.json()
            except Exception:
                pass
            error_msg = body.get('message') or str(exc)
            _logger.error("SUPER PDP send_invoice HTTP error: %s — %s", exc.response.status_code, error_msg)
            return SendResult(success=False, error=error_msg, raw_response=body)
        except requests.RequestException as exc:
            _logger.error("SUPER PDP send_invoice request error: %s", exc)
            return SendResult(success=False, error=str(exc))

    def get_status(self, external_id: str) -> StatusResult:
        url = f'{self._base_url()}/invoices/{external_id}/status'
        try:
            resp = requests.get(url, headers=self._headers(), timeout=_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
            raw_state = data.get('status', '').upper()
            edi_state = _STATE_MAP.get(raw_state)
            if not edi_state:
                _logger.warning("SUPER PDP unknown status '%s' for invoice %s", raw_state, external_id)
            return StatusResult(success=True, edi_state=edi_state, raw_response=data)
        except requests.HTTPError as exc:
            body = {}
            try:
                body = exc.response.json()
            except Exception:
                pass
            error_msg = body.get('message') or str(exc)
            _logger.error("SUPER PDP get_status HTTP error: %s — %s", exc.response.status_code, error_msg)
            return StatusResult(success=False, error=error_msg, raw_response=body)
        except requests.RequestException as exc:
            _logger.error("SUPER PDP get_status request error: %s", exc)
            return StatusResult(success=False, error=str(exc))

    def validate_webhook(self, headers: dict, body: bytes) -> bool:
        secret = self.company.edi_webhook_secret
        if not secret:
            _logger.warning("No webhook secret configured for company %s — skipping validation", self.company.id)
            return False
        signature = headers.get('X-SuperPDP-Signature') or headers.get('x-superpdp-signature', '')
        if not signature:
            return False
        expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature.lower())
