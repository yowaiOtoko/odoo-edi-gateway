from unittest.mock import MagicMock, patch

from odoo.tests.common import TransactionCase

from ..adapters.base import SendResult, StatusResult
from ..services.edi_service import EDIService


class TestEDIServiceOutbound(TransactionCase):

    def _make_move(self, **kwargs):
        move = MagicMock()
        move.id = 1
        move.state = 'posted'
        move.edi_state = 'queued'
        move.edi_invoice_hash = None
        move.edi_external_id = None
        move.company_id = MagicMock()
        move.company_id.edi_pdp_provider = 'super_pdp'
        move._edi_set_state = MagicMock()
        for k, v in kwargs.items():
            setattr(move, k, v)
        return move

    def test_send_invoice_success(self):
        move = self._make_move()
        mock_result = SendResult(success=True, external_id='EXT-999', raw_response={'invoice_id': 'EXT-999'})
        with patch('odoo_edi_gateway.services.edi_service.FacturXGenerator') as MockGen, \
             patch('odoo_edi_gateway.services.edi_service.get_adapter') as mock_get_adapter:
            gen_instance = MockGen.return_value
            gen_instance.generate.return_value = b'%PDF'
            gen_instance.compute_hash.return_value = 'newhash'
            gen_instance.get_metadata.return_value = {'invoice_number': 'INV-1'}
            mock_get_adapter.return_value.send_invoice.return_value = mock_result

            service = EDIService(self.env)
            service.send_invoice(move)

        move._edi_set_state.assert_called_with(
            'sent',
            payload=unittest.mock.ANY,
            provider_response=unittest.mock.ANY,
        )
        self.assertEqual(move.edi_external_id, 'EXT-999')

    def test_send_invoice_idempotent(self):
        """Same hash + external_id → skip re-submission."""
        move = self._make_move(edi_invoice_hash='samehash', edi_external_id='EXT-1')
        with patch('odoo_edi_gateway.services.edi_service.FacturXGenerator') as MockGen, \
             patch('odoo_edi_gateway.services.edi_service.get_adapter') as mock_get_adapter:
            gen_instance = MockGen.return_value
            gen_instance.generate.return_value = b'%PDF'
            gen_instance.compute_hash.return_value = 'samehash'

            service = EDIService(self.env)
            service.send_invoice(move)

        mock_get_adapter.return_value.send_invoice.assert_not_called()


import unittest.mock


class TestEDIServiceInbound(TransactionCase):

    def test_process_inbound_creates_draft(self):
        """parse → create account.move in draft."""
        from ..tests.test_facturx_parser import SAMPLE_XML

        inbound = self.env['edi.inbound.invoice'].create({
            'external_id': 'TEST-INBOUND-001',
            'provider': 'super_pdp',
            'raw_xml': SAMPLE_XML.decode('utf-8'),
            'state': 'received',
        })

        service = EDIService(self.env)
        service.process_inbound(inbound)

        self.assertEqual(inbound.state, 'done')
        self.assertTrue(inbound.move_id)
        self.assertEqual(inbound.move_id.move_type, 'in_invoice')
        self.assertEqual(inbound.move_id.state, 'draft')

    def test_process_inbound_invalid_xml(self):
        inbound = self.env['edi.inbound.invoice'].create({
            'external_id': 'TEST-INBOUND-002',
            'provider': 'super_pdp',
            'raw_xml': 'not xml',
            'state': 'received',
        })

        service = EDIService(self.env)
        service.process_inbound(inbound)

        self.assertEqual(inbound.state, 'error')
