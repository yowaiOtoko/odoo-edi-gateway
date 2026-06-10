import hashlib
import hmac
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from odoo.tests.common import TransactionCase

from ..adapters.super_pdp import SuperPDPAdapter


class TestSuperPDPAdapter(TransactionCase):

    def _make_company(self, **kwargs):
        company = MagicMock()
        company.edi_super_pdp_client_id = 'test-client-id'
        company.edi_super_pdp_client_secret = 'test-client-secret'
        company.edi_super_pdp_base_url = 'https://api.sandbox.super-pdp.tech/v1.beta'
        company.edi_super_pdp_auth_url = 'https://api.sandbox.super-pdp.tech'
        company.edi_super_pdp_sandbox = True
        company.edi_super_pdp_access_token = None
        company.edi_super_pdp_token_expiry = None
        company.edi_webhook_secret = 'webhook-secret'
        for k, v in kwargs.items():
            setattr(company, k, v)
        return company

    def test_get_access_token_success(self):
        company = self._make_company()
        adapter = SuperPDPAdapter(company)
        mock_resp = MagicMock()
        mock_resp.json.return_value = {'access_token': 'test-token-123', 'expires_in': 3600}
        mock_resp.raise_for_status.return_value = None
        with patch('requests.post', return_value=mock_resp) as mock_post:
            token = adapter._get_access_token()
        self.assertEqual(token, 'test-token-123')
        self.assertEqual(company.edi_super_pdp_access_token, 'test-token-123')
        self.assertIsNotNone(company.edi_super_pdp_token_expiry)
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        self.assertIn('/oauth2/token', call_args[0][0])

    def test_get_access_token_missing_credentials(self):
        company = self._make_company(
            edi_super_pdp_client_id=None,
            edi_super_pdp_client_secret=None,
        )
        adapter = SuperPDPAdapter(company)
        token = adapter._get_access_token()
        self.assertIsNone(token)

    def test_get_access_token_cached_and_valid(self):
        company = self._make_company()
        company.edi_super_pdp_access_token = 'cached-token'
        company.edi_super_pdp_token_expiry = datetime.utcnow() + timedelta(hours=1)
        adapter = SuperPDPAdapter(company)
        with patch('requests.post') as mock_post:
            token = adapter._get_access_token()
        self.assertEqual(token, 'cached-token')
        mock_post.assert_not_called()

    def test_send_invoice_success(self):
        company = self._make_company()
        adapter = SuperPDPAdapter(company)
        mock_token_resp = MagicMock()
        mock_token_resp.json.return_value = {'access_token': 'test-token', 'expires_in': 3600}
        mock_token_resp.raise_for_status.return_value = None
        mock_invoice_resp = MagicMock()
        mock_invoice_resp.json.return_value = {'invoice_id': 'EXT-123', 'status': 'SUBMITTED'}
        mock_invoice_resp.raise_for_status.return_value = None
        with patch('requests.post') as mock_post:
            mock_post.side_effect = [mock_token_resp, mock_invoice_resp]
            result = adapter.send_invoice(b'%PDF fake', 'abc123', {'invoice_number': 'INV-1'})
        self.assertTrue(result.success)
        self.assertEqual(result.external_id, 'EXT-123')
        # Should have called oauth2/token first, then POST /invoices
        self.assertEqual(mock_post.call_count, 2)

    def test_send_invoice_http_error(self):
        import requests as req
        company = self._make_company()
        adapter = SuperPDPAdapter(company)
        mock_token_resp = MagicMock()
        mock_token_resp.json.return_value = {'access_token': 'test-token', 'expires_in': 3600}
        mock_token_resp.raise_for_status.return_value = None
        mock_invoice_resp = MagicMock()
        mock_invoice_resp.status_code = 422
        mock_invoice_resp.json.return_value = {'message': 'Invalid SIRET'}
        http_err = req.HTTPError(response=mock_invoice_resp)
        mock_invoice_resp.raise_for_status.side_effect = http_err
        with patch('requests.post') as mock_post:
            mock_post.side_effect = [mock_token_resp, mock_invoice_resp]
            result = adapter.send_invoice(b'%PDF fake', 'abc123', {})
        self.assertFalse(result.success)
        self.assertIn('Invalid SIRET', result.error)

    def test_get_status_accepted(self):
        company = self._make_company()
        adapter = SuperPDPAdapter(company)
        mock_token_resp = MagicMock()
        mock_token_resp.json.return_value = {'access_token': 'test-token', 'expires_in': 3600}
        mock_token_resp.raise_for_status.return_value = None
        mock_status_resp = MagicMock()
        mock_status_resp.json.return_value = {'status': 'ACCEPTED', 'invoice_id': 'EXT-123'}
        mock_status_resp.raise_for_status.return_value = None
        with patch('requests.post', return_value=mock_token_resp):
            with patch('requests.get', return_value=mock_status_resp):
                result = adapter.get_status('EXT-123')
        self.assertTrue(result.success)
        self.assertEqual(result.edi_state, 'accepted')

    def test_validate_webhook_valid(self):
        company = self._make_company()
        adapter = SuperPDPAdapter(company)
        body = b'{"invoice_id": "EXT-123", "status": "ACCEPTED"}'
        sig = hmac.new(b'webhook-secret', body, hashlib.sha256).hexdigest()
        headers = {'X-SuperPDP-Signature': sig}
        self.assertTrue(adapter.validate_webhook(headers, body))

    def test_validate_webhook_invalid(self):
        company = self._make_company()
        adapter = SuperPDPAdapter(company)
        body = b'{"invoice_id": "EXT-123"}'
        headers = {'X-SuperPDP-Signature': 'badsignature'}
        self.assertFalse(adapter.validate_webhook(headers, body))

    def test_validate_webhook_no_secret(self):
        company = self._make_company(edi_webhook_secret=None)
        adapter = SuperPDPAdapter(company)
        self.assertFalse(adapter.validate_webhook({}, b'body'))
