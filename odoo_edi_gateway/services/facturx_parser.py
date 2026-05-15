import logging
import xml.etree.ElementTree as ET
from decimal import Decimal

_logger = logging.getLogger(__name__)

NS = {
    'rsm': 'urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100',
    'ram': 'urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100',
    'udt': 'urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100',
}


def _text(node, path) -> str:
    el = node.find(path, NS)
    return el.text.strip() if el is not None and el.text else ''


def _decimal(node, path) -> Decimal:
    raw = _text(node, path)
    try:
        return Decimal(raw)
    except Exception:
        return Decimal('0')


class FacturXParser:
    """Parse Factur-X (CII EN16931) XML into a normalized dict."""

    def parse(self, xml_bytes: bytes) -> dict:
        try:
            root = ET.fromstring(xml_bytes)
        except ET.ParseError as exc:
            _logger.error("Factur-X XML parse error: %s", exc)
            return {}

        ttx = root.find('rsm:SupplyChainTradeTransaction', NS)
        agreement = ttx.find('ram:ApplicableHeaderTradeAgreement', NS) if ttx is not None else None
        settlement = ttx.find('ram:ApplicableHeaderTradeSettlement', NS) if ttx is not None else None
        summary = settlement.find('ram:SpecifiedTradeSettlementHeaderMonetarySummation', NS) if settlement is not None else None

        seller = agreement.find('ram:SellerTradeParty', NS) if agreement is not None else None
        buyer = agreement.find('ram:BuyerTradeParty', NS) if agreement is not None else None

        lines = []
        if ttx is not None:
            for line_el in ttx.findall('ram:IncludedSupplyChainTradeLineItem', NS):
                product = line_el.find('ram:SpecifiedTradeProduct', NS)
                delivery = line_el.find('ram:SpecifiedLineTradeDelivery', NS)
                line_settlement = line_el.find('ram:SpecifiedLineTradeSettlement', NS)
                line_agreement = line_el.find('ram:SpecifiedLineTradeAgreement', NS)
                lines.append({
                    'name': _text(product, 'ram:Name') if product is not None else '',
                    'quantity': float(_decimal(delivery, 'ram:BilledQuantity') if delivery is not None else Decimal('1')),
                    'price_unit': float(_decimal(line_agreement, 'ram:NetPriceProductTradePrice/ram:ChargeAmount') if line_agreement is not None else Decimal('0')),
                    'price_subtotal': float(_decimal(line_settlement, 'ram:SpecifiedTradeSettlementLineMonetarySummation/ram:LineTotalAmount') if line_settlement is not None else Decimal('0')),
                })

        doc = root.find('rsm:ExchangedDocument', NS)
        return {
            'invoice_number': _text(doc, 'ram:ID') if doc is not None else '',
            'invoice_date': _text(doc, 'ram:IssueDateTime/udt:DateTimeString') if doc is not None else '',
            'supplier': {
                'name': _text(seller, 'ram:Name') if seller is not None else '',
                'siret': _text(seller, 'ram:SpecifiedLegalOrganization/ram:ID') if seller is not None else '',
            },
            'customer': {
                'name': _text(buyer, 'ram:Name') if buyer is not None else '',
                'siret': _text(buyer, 'ram:SpecifiedLegalOrganization/ram:ID') if buyer is not None else '',
            },
            'currency': _text(settlement, 'ram:InvoiceCurrencyCode') if settlement is not None else 'EUR',
            'amount_untaxed': float(_decimal(summary, 'ram:LineTotalAmount') if summary is not None else Decimal('0')),
            'amount_tax': float(_decimal(summary, 'ram:TaxTotalAmount') if summary is not None else Decimal('0')),
            'amount_total': float(_decimal(summary, 'ram:GrandTotalAmount') if summary is not None else Decimal('0')),
            'lines': lines,
        }
