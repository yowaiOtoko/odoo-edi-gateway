from types import SimpleNamespace
import xml.etree.ElementTree as ET
import unittest

from odoo.tests.common import TransactionCase

from ..services.facturx_generator import FacturXGenerator

try:
    from facturx import xml_check_xsd
    _FACTURX_VALIDATOR_AVAILABLE = True
except ImportError:
    xml_check_xsd = None
    _FACTURX_VALIDATOR_AVAILABLE = False


NS = {
    'rsm': 'urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100',
    'ram': 'urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100',
    'udt': 'urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100',
}


class _LineCollection(list):

    def filtered(self, predicate):
        return _LineCollection([line for line in self if predicate(line)])


class TestFacturXGenerator(TransactionCase):

    def _make_move(self):
        line1 = SimpleNamespace(
            display_type=False,
            name='Consulting',
            price_unit=1000.0,
            quantity=1.0,
            price_subtotal=1000.0,
            product_uom_id=SimpleNamespace(name='C62'),
            tax_ids=[SimpleNamespace(amount_type='percent', amount=20.0)],
        )
        line2 = SimpleNamespace(
            display_type=False,
            name='Support',
            price_unit=250.0,
            quantity=2.0,
            price_subtotal=500.0,
            product_uom_id=SimpleNamespace(name='C62'),
            tax_ids=[SimpleNamespace(amount_type='percent', amount=20.0)],
        )
        return SimpleNamespace(
            name='INV-2026-001',
            invoice_date=None,
            company_id=SimpleNamespace(name='Acme SARL', siret='12345678901234'),
            partner_id=SimpleNamespace(name='Client SA', siret='98765432109876'),
            currency_id=SimpleNamespace(name='EUR'),
            amount_untaxed=1500.0,
            amount_tax=300.0,
            amount_total=1800.0,
            amount_residual=1800.0,
            invoice_line_ids=_LineCollection([line1, line2]),
            env=SimpleNamespace(),
            ids=[1],
        )

    def test_build_xml_emits_one_trade_line_item_per_invoice_line(self):
        generator = FacturXGenerator(self._make_move())
        root = ET.fromstring(generator._build_xml())

        self.assertIsNotNone(root.find('.//ram:ApplicableHeaderTradeDelivery', NS))
        self.assertIsNotNone(root.find('.//ram:ApplicableHeaderTradeSettlement/ram:ApplicableTradeTax', NS))
        self.assertIsNotNone(root.find('.//ram:SpecifiedTradeSettlementHeaderMonetarySummation/ram:TaxBasisTotalAmount', NS))
        items = root.findall('.//ram:IncludedSupplyChainTradeLineItem', NS)
        self.assertEqual(len(items), 2)
        for item in items:
            self.assertIsNotNone(item.find('ram:AssociatedDocumentLineDocument', NS))
            self.assertIsNotNone(item.find('ram:SpecifiedLineTradeDelivery/ram:BilledQuantity', NS))
            self.assertIsNotNone(item.find('ram:SpecifiedLineTradeSettlement/ram:ApplicableTradeTax', NS))

    @unittest.skipUnless(_FACTURX_VALIDATOR_AVAILABLE, 'factur-x validator is not installed')
    def test_build_xml_passes_facturx_schema_validation(self):
        generator = FacturXGenerator(self._make_move())
        xml_bytes = generator._build_xml()

        self.assertTrue(xml_check_xsd(xml_bytes, flavor='factur-x', level='en16931'))
