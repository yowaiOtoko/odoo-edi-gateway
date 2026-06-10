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
    # Check for required config (OAuth2 credentials for super_pdp)
    if provider == 'super_pdp':
        client_id = getattr(company, 'edi_super_pdp_client_id', None)
        client_secret = getattr(company, 'edi_super_pdp_client_secret', None)
        if not client_id or not client_secret:
            return None
    return cls(company)

# Helper for config check
def is_edi_configured(company) -> bool:
    provider = getattr(company, 'edi_pdp_provider', None)
    if not provider:
        return False
    if provider == 'super_pdp':
        client_id = getattr(company, 'edi_super_pdp_client_id', None)
        client_secret = getattr(company, 'edi_super_pdp_client_secret', None)
        return bool(client_id and client_secret)
    return False
