import base64
import hashlib
import hmac
import logging
from datetime import datetime, timedelta

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
    """SUPER PDP REST API adapter (sandbox + production) with OAuth2 client credentials flow."""

    def _base_url(self) -> str:
        return (self.company.edi_super_pdp_base_url or 'https://api.sandbox.super-pdp.tech/v1.beta').rstrip('/')

    def _auth_url(self) -> str:
        return (self.company.edi_super_pdp_auth_url or 'https://api.sandbox.super-pdp.tech').rstrip('/')

    def _get_access_token(self) -> str | None:
        """Obtain or refresh OAuth2 access token via client credentials flow."""
        client_id = self.company.edi_super_pdp_client_id
        client_secret = self.company.edi_super_pdp_client_secret
        
        if not client_id or not client_secret:
            _logger.error("Super PDP: client_id or client_secret not configured")
            return None
        
        # Check if cached token is still valid
        cached_token = self.company.edi_super_pdp_access_token
        token_expiry = self.company.edi_super_pdp_token_expiry
        if cached_token and token_expiry:
            if datetime.utcnow() < token_expiry:
                _logger.debug("Using cached SUPER PDP access token")
                return cached_token
        
        token_url = f'{self._auth_url()}/oauth2/token'
        payload = {
            'grant_type': 'client_credentials',
            'client_id': client_id,
            'client_secret': client_secret,
        }
        
        try:
            resp = requests.post(token_url, data=payload, timeout=_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
            access_token = data.get('access_token')
            expires_in = data.get('expires_in', 3600)  # default 1 hour
            
            if access_token:
                # Cache token with expiry (subtract 60s buffer for safety)
                expiry = datetime.utcnow() + timedelta(seconds=expires_in - 60)
                self.company.edi_super_pdp_access_token = access_token
                self.company.edi_super_pdp_token_expiry = expiry
                _logger.debug("Obtained new SUPER PDP access token, expires at %s", expiry)
                return access_token
            else:
                _logger.error("SUPER PDP oauth2/token response missing access_token: %s", data)
                return None
        except requests.HTTPError as exc:
            body = {}
            try:
                body = exc.response.json()
            except Exception:
                pass
            _logger.error("SUPER PDP oauth2/token HTTP error: %s — %s", exc.response.status_code, body)
            return None
        except requests.RequestException as exc:
            _logger.error("SUPER PDP oauth2/token request error: %s", exc)
            return None

    def _headers(self) -> dict:
        access_token = self._get_access_token()
        if not access_token:
            return {}
        return {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }

    def send_invoice(self, facturx_pdf: bytes, invoice_hash: str, metadata: dict) -> SendResult:
        url = f'{self._base_url()}/invoices'
        headers = self._headers()
        if not headers:
            return SendResult(
                success=False,
                error='Unable to obtain SUPER PDP access token (check client_id/client_secret)',
            )
        
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
            resp = requests.post(url, json=payload, headers=headers, timeout=_TIMEOUT)
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
        headers = self._headers()
        if not headers:
            return StatusResult(
                success=False,
                error='Unable to obtain SUPER PDP access token (check client_id/client_secret)',
            )
        
        try:
            resp = requests.get(url, headers=headers, timeout=_TIMEOUT)
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
