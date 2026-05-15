from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SendResult:
    success: bool
    external_id: Optional[str] = None
    error: Optional[str] = None
    raw_response: dict = field(default_factory=dict)


@dataclass
class StatusResult:
    success: bool
    edi_state: Optional[str] = None
    error: Optional[str] = None
    raw_response: dict = field(default_factory=dict)


class PDPAdapter(ABC):
    """Abstract base for all PDP provider adapters."""

    def __init__(self, company):
        self.company = company

    @abstractmethod
    def send_invoice(self, facturx_pdf: bytes, invoice_hash: str, metadata: dict) -> SendResult:
        """Submit a Factur-X invoice to the PDP.

        Returns SendResult with external_id on success.
        """

    @abstractmethod
    def get_status(self, external_id: str) -> StatusResult:
        """Poll the PDP for the current lifecycle state of an invoice."""

    @abstractmethod
    def validate_webhook(self, headers: dict, body: bytes) -> bool:
        """Return True if webhook signature is valid."""
