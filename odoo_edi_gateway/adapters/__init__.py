from .base import PDPAdapter
from .super_pdp import SuperPDPAdapter

ADAPTER_REGISTRY = {
    'super_pdp': SuperPDPAdapter,
}


def get_adapter(company) -> PDPAdapter:
    provider = company.edi_pdp_provider
    cls = ADAPTER_REGISTRY.get(provider)
    if not cls:
        raise ValueError(f"Unknown PDP provider: {provider}")
    return cls(company)
