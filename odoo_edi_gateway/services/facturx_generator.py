import hashlib
import io
import logging
from datetime import date

_logger = logging.getLogger(__name__)

try:
    from facturx import generate_from_file
    _FACTURX_AVAILABLE = True
except ImportError:
    _FACTURX_AVAILABLE = False
    _logger.warning("facturx library not installed — Factur-X generation unavailable")


class FacturXGenerator:
    """Generate Factur-X PDF/A-3 with embedded EN16931 XML from an account.move."""

    def __init__(self, move):
        self.move = move

    def generate(self) -> bytes:
        """Return Factur-X PDF bytes."""
        xml_bytes = self._build_xml()
        pdf_bytes = self._get_invoice_pdf()
        if not _FACTURX_AVAILABLE:
            _logger.error("Cannot generate Factur-X: facturx library missing")
            return pdf_bytes
        output = io.BytesIO()
        generate_from_file(
            io.BytesIO(pdf_bytes),
        io.BytesIO(xml_bytes),
            output_pdf_file=output,
        )
        return output.getvalue()

    def compute_hash(self, pdf_bytes: bytes) -> str:
        return hashlib.sha256(pdf_bytes).hexdigest()

    def get_metadata(self) -> dict:
        move = self.move
        partner = move.partner_id
        company = move.company_id
        return {
            'invoice_number': move.name,
            'invoice_date': move.invoice_date.isoformat() if move.invoice_date else date.today().isoformat(),
            'total_amount_ati': float(move.amount_total),
            'sender_siret': company.siret if hasattr(company, 'siret') else '',
            'recipient_siret': partner.siret if hasattr(partner, 'siret') else '',
        }

    def _get_invoice_pdf(self) -> bytes:
        report_id = self.move._get_name_invoice_report()
        pdf_content, _ = self.move.env['ir.actions.report']._render_qweb_pdf(
            report_id,
            res_ids=self.move.ids,
        )
        return pdf_content

    def _build_xml(self) -> bytes:
        move = self.move
        lines_xml = ''.join(self._line_xml(line, i + 1) for i, line in enumerate(move.invoice_line_ids.filtered(lambda l: not l.display_type)))
        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<rsm:CrossIndustryInvoice
    xmlns:rsm="urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100"
    xmlns:ram="urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100"
    xmlns:udt="urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100">
  <rsm:ExchangedDocumentContext>
    <ram:GuidelineSpecifiedDocumentContextParameter>
      <ram:ID>urn:cen.eu:en16931:2017#conformant#urn:factur-x.eu:1p0:en16931</ram:ID>
    </ram:GuidelineSpecifiedDocumentContextParameter>
  </rsm:ExchangedDocumentContext>
  <rsm:ExchangedDocument>
    <ram:ID>{move.name}</ram:ID>
    <ram:TypeCode>380</ram:TypeCode>
    <ram:IssueDateTime>
      <udt:DateTimeString format="102">{(move.invoice_date or date.today()).strftime('%Y%m%d')}</udt:DateTimeString>
    </ram:IssueDateTime>
  </rsm:ExchangedDocument>
  <rsm:SupplyChainTradeTransaction>
    <ram:IncludedSupplyChainTradeLineItem>
{lines_xml}
    </ram:IncludedSupplyChainTradeLineItem>
    <ram:ApplicableHeaderTradeAgreement>
      <ram:SellerTradeParty>
        <ram:Name>{move.company_id.name}</ram:Name>
        <ram:SpecifiedLegalOrganization>
          <ram:ID schemeID="0002">{getattr(move.company_id, 'siret', '')}</ram:ID>
        </ram:SpecifiedLegalOrganization>
      </ram:SellerTradeParty>
      <ram:BuyerTradeParty>
        <ram:Name>{move.partner_id.name}</ram:Name>
        <ram:SpecifiedLegalOrganization>
          <ram:ID schemeID="0002">{getattr(move.partner_id, 'siret', '')}</ram:ID>
        </ram:SpecifiedLegalOrganization>
      </ram:BuyerTradeParty>
    </ram:ApplicableHeaderTradeAgreement>
    <ram:ApplicableHeaderTradeSettlement>
      <ram:InvoiceCurrencyCode>{move.currency_id.name}</ram:InvoiceCurrencyCode>
      <ram:SpecifiedTradeSettlementHeaderMonetarySummation>
        <ram:LineTotalAmount>{move.amount_untaxed:.2f}</ram:LineTotalAmount>
        <ram:TaxTotalAmount currencyID="{move.currency_id.name}">{move.amount_tax:.2f}</ram:TaxTotalAmount>
        <ram:GrandTotalAmount>{move.amount_total:.2f}</ram:GrandTotalAmount>
        <ram:DuePayableAmount>{move.amount_residual:.2f}</ram:DuePayableAmount>
      </ram:SpecifiedTradeSettlementHeaderMonetarySummation>
    </ram:ApplicableHeaderTradeSettlement>
  </rsm:SupplyChainTradeTransaction>
</rsm:CrossIndustryInvoice>"""
        return xml.encode('utf-8')

    def _line_xml(self, line, index: int) -> str:
        return f"""      <ram:AssociatedDocumentLineDocument>
        <ram:LineID>{index}</ram:LineID>
      </ram:AssociatedDocumentLineDocument>
      <ram:SpecifiedTradeProduct>
        <ram:Name>{line.name or ''}</ram:Name>
      </ram:SpecifiedTradeProduct>
      <ram:SpecifiedLineTradeAgreement>
        <ram:NetPriceProductTradePrice>
          <ram:ChargeAmount>{line.price_unit:.2f}</ram:ChargeAmount>
        </ram:NetPriceProductTradePrice>
      </ram:SpecifiedLineTradeAgreement>
      <ram:SpecifiedLineTradeDelivery>
        <ram:BilledQuantity unitCode="{line.product_uom_id.name if line.product_uom_id else 'C62'}">{line.quantity:.4f}</ram:BilledQuantity>
      </ram:SpecifiedLineTradeDelivery>
      <ram:SpecifiedLineTradeSettlement>
        <ram:SpecifiedTradeSettlementLineMonetarySummation>
          <ram:LineTotalAmount>{line.price_subtotal:.2f}</ram:LineTotalAmount>
        </ram:SpecifiedTradeSettlementLineMonetarySummation>
      </ram:SpecifiedLineTradeSettlement>"""
