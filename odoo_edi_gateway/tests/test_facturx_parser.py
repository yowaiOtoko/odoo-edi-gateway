from odoo.tests.common import TransactionCase

from ..services.facturx_parser import FacturXParser

SAMPLE_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<rsm:CrossIndustryInvoice
    xmlns:rsm="urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100"
    xmlns:ram="urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100"
    xmlns:udt="urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100">
  <rsm:ExchangedDocumentContext>
    <ram:GuidelineSpecifiedDocumentContextParameter>
      <ram:ID>urn:cen.eu:en16931:2017</ram:ID>
    </ram:GuidelineSpecifiedDocumentContextParameter>
  </rsm:ExchangedDocumentContext>
  <rsm:ExchangedDocument>
    <ram:ID>INV-2026-001</ram:ID>
    <ram:TypeCode>380</ram:TypeCode>
    <ram:IssueDateTime>
      <udt:DateTimeString format="102">20260101</udt:DateTimeString>
    </ram:IssueDateTime>
  </rsm:ExchangedDocument>
  <rsm:SupplyChainTradeTransaction>
    <ram:IncludedSupplyChainTradeLineItem>
      <ram:AssociatedDocumentLineDocument><ram:LineID>1</ram:LineID></ram:AssociatedDocumentLineDocument>
      <ram:SpecifiedTradeProduct><ram:Name>Consulting</ram:Name></ram:SpecifiedTradeProduct>
      <ram:SpecifiedLineTradeAgreement>
        <ram:NetPriceProductTradePrice><ram:ChargeAmount>1000.00</ram:ChargeAmount></ram:NetPriceProductTradePrice>
      </ram:SpecifiedLineTradeAgreement>
      <ram:SpecifiedLineTradeDelivery>
        <ram:BilledQuantity unitCode="C62">1.0000</ram:BilledQuantity>
      </ram:SpecifiedLineTradeDelivery>
      <ram:SpecifiedLineTradeSettlement>
        <ram:SpecifiedTradeSettlementLineMonetarySummation>
          <ram:LineTotalAmount>1000.00</ram:LineTotalAmount>
        </ram:SpecifiedTradeSettlementLineMonetarySummation>
      </ram:SpecifiedLineTradeSettlement>
    </ram:IncludedSupplyChainTradeLineItem>
    <ram:ApplicableHeaderTradeAgreement>
      <ram:SellerTradeParty>
        <ram:Name>Acme SARL</ram:Name>
        <ram:SpecifiedLegalOrganization><ram:ID schemeID="0002">12345678901234</ram:ID></ram:SpecifiedLegalOrganization>
      </ram:SellerTradeParty>
      <ram:BuyerTradeParty>
        <ram:Name>Client SA</ram:Name>
        <ram:SpecifiedLegalOrganization><ram:ID schemeID="0002">98765432109876</ram:ID></ram:SpecifiedLegalOrganization>
      </ram:BuyerTradeParty>
    </ram:ApplicableHeaderTradeAgreement>
    <ram:ApplicableHeaderTradeSettlement>
      <ram:InvoiceCurrencyCode>EUR</ram:InvoiceCurrencyCode>
      <ram:SpecifiedTradeSettlementHeaderMonetarySummation>
        <ram:LineTotalAmount>1000.00</ram:LineTotalAmount>
        <ram:TaxTotalAmount currencyID="EUR">200.00</ram:TaxTotalAmount>
        <ram:GrandTotalAmount>1200.00</ram:GrandTotalAmount>
        <ram:DuePayableAmount>1200.00</ram:DuePayableAmount>
      </ram:SpecifiedTradeSettlementHeaderMonetarySummation>
    </ram:ApplicableHeaderTradeSettlement>
  </rsm:SupplyChainTradeTransaction>
</rsm:CrossIndustryInvoice>"""


class TestFacturXParser(TransactionCase):

    def test_parse_invoice_number(self):
        parser = FacturXParser()
        data = parser.parse(SAMPLE_XML)
        self.assertEqual(data['invoice_number'], 'INV-2026-001')

    def test_parse_supplier(self):
        parser = FacturXParser()
        data = parser.parse(SAMPLE_XML)
        self.assertEqual(data['supplier']['name'], 'Acme SARL')
        self.assertEqual(data['supplier']['siret'], '12345678901234')

    def test_parse_customer(self):
        parser = FacturXParser()
        data = parser.parse(SAMPLE_XML)
        self.assertEqual(data['customer']['name'], 'Client SA')

    def test_parse_totals(self):
        parser = FacturXParser()
        data = parser.parse(SAMPLE_XML)
        self.assertAlmostEqual(data['amount_untaxed'], 1000.0)
        self.assertAlmostEqual(data['amount_tax'], 200.0)
        self.assertAlmostEqual(data['amount_total'], 1200.0)

    def test_parse_lines(self):
        parser = FacturXParser()
        data = parser.parse(SAMPLE_XML)
        self.assertEqual(len(data['lines']), 1)
        line = data['lines'][0]
        self.assertEqual(line['name'], 'Consulting')
        self.assertAlmostEqual(line['price_unit'], 1000.0)
        self.assertAlmostEqual(line['quantity'], 1.0)

    def test_parse_invalid_xml(self):
        parser = FacturXParser()
        data = parser.parse(b'not xml at all')
        self.assertEqual(data, {})

    def test_parse_currency(self):
        parser = FacturXParser()
        data = parser.parse(SAMPLE_XML)
        self.assertEqual(data['currency'], 'EUR')
