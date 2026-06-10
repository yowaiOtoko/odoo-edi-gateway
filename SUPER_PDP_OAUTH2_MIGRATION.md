# Super PDP OAuth2 Migration

## Issue Summary

The previous implementation used a static API key (`edi_super_pdp_api_key`) directly as a Bearer token. Super PDP actually requires **OAuth2 client credentials flow** to obtain a Bearer token via `/oauth2/token` before invoking protected endpoints.

## Changes Made

### 1. **Model Fields** (`odoo_edi_gateway/models/res_company.py`)

**Removed:**
- `edi_super_pdp_api_key` — static API key (incorrect auth method)

**Added:**
- `edi_super_pdp_client_id` — OAuth2 client ID
- `edi_super_pdp_client_secret` — OAuth2 client secret
- `edi_super_pdp_auth_url` — OAuth2 token endpoint base URL (default: `https://api.sandbox.super-pdp.tech`)
- `edi_super_pdp_base_url` — API base URL (updated default to `https://api.sandbox.super-pdp.tech/v1.beta`)
- `edi_super_pdp_access_token` — cached Bearer token (readonly)
- `edi_super_pdp_token_expiry` — token expiry datetime (readonly)

### 2. **Adapter** (`odoo_edi_gateway/adapters/super_pdp.py`)

**Key Changes:**
- New `_get_access_token()` method implements OAuth2 client credentials flow:
  - POST to `/oauth2/token` with `grant_type=client_credentials`
  - Caches token with expiry time, reuses if still valid
  - Automatically refreshes when expired
- Updated `_headers()` to use Bearer token from `_get_access_token()`
- Removed hardcoded `X-Sandbox` header
- Updated base URL defaults to match current Super PDP API

**OAuth2 Flow:**
```
POST /oauth2/token
{
  "grant_type": "client_credentials",
  "client_id": "<client_id>",
  "client_secret": "<client_secret>"
}
↓
Response: {"access_token": "...", "expires_in": 3600}
↓
Authorization: Bearer <access_token>
```

### 3. **UI Form** (`odoo_edi_gateway/views/res_company_views.xml`)

**Updated sections:**
- Grouped OAuth2 credentials (client_id, client_secret, auth_url, base_url)
- Added readonly token cache display
- Removed old API key field
- Reorganized form layout for clarity

### 4. **Validation** (`odoo_edi_gateway/adapters/__init__.py`)

Updated `get_adapter()` and `is_edi_configured()` to check for both `client_id` and `client_secret` instead of a single API key.

### 5. **Tests** (`odoo_edi_gateway/tests/test_super_pdp_adapter.py`)

**New tests:**
- `test_get_access_token_success` — verify OAuth2 token retrieval
- `test_get_access_token_missing_credentials` — verify error when credentials missing
- `test_get_access_token_cached_and_valid` — verify token caching
- Updated existing tests to mock OAuth2 flow

## Configuration Steps

In Odoo:

1. Navigate to **Settings > Companies > Edit Company**
2. Go to **EDI Gateway** tab
3. Select **SUPER PDP** as PDP Provider
4. Set **Sandbox Mode** if needed (default: True)
5. Under **SUPER PDP OAuth2 Credentials**, enter:
   - **Client ID** — from Super PDP account
   - **Client Secret** — from Super PDP account
   - **Auth URL** — typically `https://api.sandbox.super-pdp.tech` (sandbox) or `https://api.super-pdp.tech` (production)
   - **API Base URL** — typically `https://api.sandbox.super-pdp.tech/v1.beta` (sandbox) or `https://api.super-pdp.tech/v1.beta` (production)

Token caching is automatic—no manual intervention needed.

## API Endpoints

All requests now follow OAuth2 pattern:

- **Token Endpoint:** `POST {auth_url}/oauth2/token`
- **Invoice Submit:** `POST {base_url}/invoices`
- **Invoice Status:** `GET {base_url}/invoices/{id}/status`

Headers:
```
Authorization: Bearer <access_token>
Content-Type: application/json
Accept: application/json
```

## Migration from Old Config

If you have existing companies configured with the old `edi_super_pdp_api_key`:

1. The field will be removed in production
2. Reconfigure with new OAuth2 credentials (client_id/client_secret)
3. Token caching happens automatically on first use
