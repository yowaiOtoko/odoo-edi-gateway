# Odoo EDI Gateway

Provider-agnostic EDI gateway addon for Odoo 19, focused on French e-invoicing flows.

It currently supports:
- Outbound invoice submission to SUPER PDP
- Inbound invoice webhook ingestion and draft bill creation
- Lifecycle status synchronization (webhook + optional polling fallback)
- End-to-end audit logs for invoice state transitions

## Module Summary

- Name: `EDI Gateway`
- Technical module: `odoo_edi_gateway`
- Version: `19.0.1.0.0`
- License: `LGPL-3`
- Dependencies:
	- `account`
	- `queue_job`
- Python dependencies:
	- `factur-x`
	- `requests`
	- `cryptography`

## Key Features

### Outbound (Odoo -> PDP)
- Adds EDI fields on invoices (`account.move`):
	- `edi_state`, `edi_provider`, `edi_external_id`, `edi_sent_at`, `edi_last_error`, `edi_invoice_hash`
- Adds `Send EDI` button on posted invoices.
- Queues async sending job (`with_delay()._job_send_edi()`).
- Generates Factur-X PDF, computes an idempotency hash, and sends to PDP.
- Tracks state transitions and provider payloads in audit logs.

### Inbound (PDP -> Odoo)
- Public webhook endpoint for inbound documents:
	- `POST /edi/pdp/webhook/inbound`
- Stores inbound data in `edi.inbound.invoice`.
- Queues async parse/create job (`_job_process_inbound`).
- Parses XML and creates a draft vendor bill (`move_type = in_invoice`).

### Lifecycle Tracking
- Public webhook endpoint for lifecycle updates:
	- `POST /edi/pdp/webhook/lifecycle`
- Maps PDP statuses to internal EDI states (`sent`, `delivered`, `accepted`, `rejected`, `error`).
- Optional cron fallback polling (`_cron_poll_edi_status`) for in-flight invoices.

### Operations and Auditability
- Dedicated menu under Accounting:
	- `EDI Gateway / Inbound Invoices`
	- `EDI Gateway / Audit Logs`
- Audit model `edi.invoice.log` captures:
	- previous state, new state, payload sent, provider response, timestamp

## Data Models

### `account.move` extension
- Outbound lifecycle state machine with validation and queueing.
- Smart button to view EDI logs.

Internal outbound states:
- `draft`
- `validated`
- `queued`
- `sent`
- `delivered`
- `accepted`
- `rejected`
- `error`

### `edi.inbound.invoice`
- Stores inbound payload and processing lifecycle.
- Links to created invoice (`move_id`) after successful processing.

Inbound states:
- `received`
- `parsing`
- `parsed`
- `creating`
- `done`
- `error`

### `edi.invoice.log`
- Immutable audit trail of state transitions and provider exchanges.

### `res.company` configuration fields
- `edi_pdp_provider`
- `edi_super_pdp_api_key`
- `edi_super_pdp_base_url`
- `edi_super_pdp_sandbox`
- `edi_polling_enabled`
- `edi_polling_interval`
- `edi_webhook_secret`

## Webhooks

Both routes are `auth='none'` and require signature validation via adapter logic.

### Inbound webhook
- Route: `POST /edi/pdp/webhook/inbound`
- Company resolution:
	- header `X-Company-Id` or `X-Company-ID`
	- fallback: first company in database
- Signature header (SUPER PDP):
	- `X-SuperPDP-Signature`
- Expected payload fields:
	- `invoice_id` (or `id`)
	- XML content in `xml` or `facturx_xml`

### Lifecycle webhook
- Route: `POST /edi/pdp/webhook/lifecycle`
- Same company resolution and signature validation flow.
- Updates matching invoice by external id.

## SUPER PDP Adapter

Current provider implementation: `super_pdp`.

Behavior:
- Sends Factur-X document to `POST {base_url}/invoices`
- Polls status from `GET {base_url}/invoices/{external_id}/status`
- Uses HMAC SHA-256 signature validation for incoming webhooks
- Requires API key and webhook secret at company level

State mapping:
- `SUBMITTED -> sent`
- `DELIVERED -> delivered`
- `ACCEPTED -> accepted`
- `REJECTED -> rejected`
- `ERROR -> error`

## Installation

1. Place this addon in your Odoo addons path.
2. Ensure required modules are installed:
	 - `account`
	 - `queue_job`
3. Install Python dependencies in the Odoo runtime environment:

```bash
pip install factur-x requests cryptography
```

4. Update app list and install module `EDI Gateway`.

## Configuration

In Odoo, go to:
- Settings -> Companies -> (your company) -> `EDI Gateway` tab

Configure at minimum:
- PDP Provider: `SUPER PDP`
- SUPER PDP API Key
- SUPER PDP Base URL (sandbox or production)
- Webhook Signing Secret

Optional:
- Enable fallback polling
- Polling interval in minutes

## Typical Usage

### Outbound flow
1. Post a customer invoice.
2. Click `Send EDI`.
3. Job is queued and processed asynchronously.
4. Monitor EDI status and logs from invoice form.

### Inbound flow
1. PDP calls inbound webhook with signed payload.
2. Inbound record is created in `Inbound EDI Invoices`.
3. Processing job parses XML and creates draft vendor bill.
4. Review created invoice from inbound record.

## Cron Job

- Name: `EDI Gateway: Poll Invoice Status`
- Default state: disabled
- Interval: 15 minutes
- Purpose: fallback synchronization for sent/delivered invoices when polling is enabled per company

## Testing

Automated tests are included for:
- EDI service outbound/inbound behavior
- SUPER PDP adapter behavior and signature validation
- Factur-X parser extraction

Test files:
- `odoo_edi_gateway/tests/test_edi_service.py`
- `odoo_edi_gateway/tests/test_super_pdp_adapter.py`
- `odoo_edi_gateway/tests/test_facturx_parser.py`

Run tests with your Odoo test workflow, for example:

```bash
odoo-bin -d <test_db> -i odoo_edi_gateway --test-enable --stop-after-init
```

## Extending to Other PDPs

To add a new provider:
1. Implement adapter contract in `odoo_edi_gateway/adapters/`.
2. Register it in adapter registry.
3. Add provider-specific company config fields and UI if needed.
4. Keep webhook validation and status mapping explicit.

## Notes

- This module is a transport/lifecycle integration layer and does not replace Odoo accounting logic.
- In production, always enforce strong webhook secret management and network protections.

