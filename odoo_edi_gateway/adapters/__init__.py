from .base import PDPAdapter
from .super_pdp import SuperPDPAdapter

ADAPTER_REGISTRY = {
    'super_pdp': SuperPDPAdapter,
}


def get_adapter(company) -> PDPAdapter:
    provider = getattr(company, 'edi_pdp_provider', None)
    if not provider:
        return None
    cls = ADAPTER_REGISTRY.get(provider)
    if not cls:
        return None
    # Check for required config (example: API key for super_pdp)
    if provider == 'super_pdp':
        if not getattr(company, 'edi_super_pdp_api_key', None):
            return None
    return cls(company)

# Helper for config check
def is_edi_configured(company) -> bool:
    provider = getattr(company, 'edi_pdp_provider', None)
    if not provider:
        return False
    if provider == 'super_pdp':
        return bool(getattr(company, 'edi_super_pdp_api_key', None))
    return False
