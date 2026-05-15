import hashlib
import hmac
from unittest.mock import MagicMock, patch

from odoo.tests.common import TransactionCase

from ..adapters.super_pdp import SuperPDPAdapter


class TestSuperPDPAdapter(TransactionCase):

    def _make_company(self, **kwargs):
        company = MagicMock()
        company.edi_super_pdp_base_url = 'https://api.sandbox.super-pdp.fr/v1'
        company.edi_super_pdp_api_key = 'test-api-key'
        company.edi_super_pdp_sandbox = True
        company.edi_webhook_secret = 'webhook-secret'
        for k, v in kwargs.items():
            setattr(company, k, v)
        return company

    def test_send_invoice_success(self):
        company = self._make_company()
        adapter = SuperPDPAdapter(company)
        mock_resp = MagicMock()
        mock_resp.json.return_value = {'invoice_id': 'EXT-123', 'status': 'SUBMITTED'}
        mock_resp.raise_for_status.return_value = None
        with patch('requests.post', return_value=mock_resp) as mock_post:
            result = adapter.send_invoice(b'%PDF fake', 'abc123', {'invoice_number': 'INV-1'})
        self.assertTrue(result.success)
        self.assertEqual(result.external_id, 'EXT-123')
        mock_post.assert_called_once()

    def test_send_invoice_http_error(self):
        import requests as req
        company = self._make_company()
        adapter = SuperPDPAdapter(company)
        mock_resp = MagicMock()
        mock_resp.status_code = 422
        mock_resp.json.return_value = {'message': 'Invalid SIRET'}
        http_err = req.HTTPError(response=mock_resp)
        mock_resp.raise_for_status.side_effect = http_err
        with patch('requests.post', return_value=mock_resp):
            result = adapter.send_invoice(b'%PDF fake', 'abc123', {})
        self.assertFalse(result.success)
        self.assertIn('Invalid SIRET', result.error)

    def test_get_status_accepted(self):
        company = self._make_company()
        adapter = SuperPDPAdapter(company)
        mock_resp = MagicMock()
        mock_resp.json.return_value = {'status': 'ACCEPTED', 'invoice_id': 'EXT-123'}
        mock_resp.raise_for_status.return_value = None
        with patch('requests.get', return_value=mock_resp):
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
