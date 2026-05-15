Below is a technical PRD (internal engineering specification) for your Odoo module:

Project: odoo-edi-gateway Scope: Odoo-only module (Odoo 19) Goal: Architecture + implementation spec for send/receive/lifecycle e-invoicing via PDP (SUPER PDP initially, but provider-agnostic)

📘 PRD — Odoo EDI Gateway (Send + Receive + Lifecycle)

1. Introduction

The Odoo EDI Gateway is a modular Odoo 19 addon that enables full electronic invoice lifecycle management in compliance with the French 2026–2027 e-invoicing reform.

It provides:





Outbound invoice transmission (Odoo → PDP)



Inbound invoice reception (PDP → Odoo)



Full lifecycle tracking (sent, delivered, accepted, rejected, error)



Provider abstraction layer (SUPER PDP first, extensible to other PDPs)



Factur-X generation and validation pipeline

The module is designed as a transport + lifecycle layer, not a replacement for Odoo accounting.

2. Goals

Primary goals





Enable Odoo to comply with French e-invoicing obligations (2026–2027)



Support invoice sending and reception via PDPs



Track full invoice lifecycle with reliable state synchronization



Provide a provider-agnostic EDI abstraction layer



Ensure async, reliable processing with retries and audit logs

Secondary goals





Support multiple PDP providers in the future



Ensure compatibility with OCA EDI ecosystem



Reduce integration effort for Odoo integrators

3. Non-goals





No accounting engine replacement (Odoo remains source of truth)



No payment processing



No UI redesign of invoicing screens



No direct Chorus Pro implementation (handled via PDP abstraction)



No custom ERP logic outside invoice domain

4. Users & personas

4.1 Primary users





Small and medium businesses using Odoo 19



Accounting teams issuing and receiving invoices

4.2 Secondary users





Odoo integrators



Accounting firms managing multiple clients



SaaS platforms embedding Odoo

5. Functional requirements

5.1 Outbound invoice sending (Odoo → PDP)

FR-1: Invoice submission





User validates an invoice in Odoo



System generates Factur-X document



Invoice is queued for transmission

FR-2: Factur-X generation





Must generate:





PDF/A-3



Embedded XML (Factur-X EN16931 compliant)



Based on OCA EDI patterns

FR-3: Transmission





Send invoice to configured PDP provider (default: SUPER PDP)



Store external invoice ID



Mark invoice as sent

FR-4: Retry mechanism





Automatic retry on failure



Exponential backoff



Dead-letter state after max retries

5.2 Inbound invoice reception (PDP → Odoo)

FR-5: Webhook ingestion





Expose secure endpoint:





/edi/pdp/webhook/inbound



Accept invoice payloads from PDP

FR-6: Invoice ingestion





Store raw invoice payload (XML + metadata)



Persist inbound record in staging table

FR-7: Parsing





Parse Factur-X / UBL formats



Extract:





supplier



customer



lines



taxes



totals

FR-8: Invoice creation





Create Odoo draft invoice (account.move)



Link inbound record to created invoice

5.3 Lifecycle tracking (core requirement)

FR-9: State machine

Each invoice must follow:

draft
→ validated
→ queued
→ sent
→ delivered
→ accepted
→ rejected
→ error


FR-10: State synchronization





Update states from:





PDP responses



webhooks



polling fallback (optional)

FR-11: Audit trail





Log every state transition



Store:





timestamp



payload



provider response

5.4 PDP abstraction layer

FR-12: Provider interface

All PDP providers must implement:





send_invoice()



get_status()



validate_webhook()

FR-13: Super PDP implementation (initial)





REST API integration



webhook support



Factur-X payload submission

FR-14: Multi-provider readiness

System must allow:





per-company PDP configuration



provider switching without invoice redesign

5.5 Async processing

FR-15: Queue system





Use queue_job (OCA standard)



All outbound transmissions are async

FR-16: Idempotency





Prevent duplicate invoice submission



Use unique invoice hash + external ID mapping

6. Data model

6.1 account.move extension

Fields:





edi_state



edi_provider



edi_external_id



edi_last_error



edi_sent_at

6.2 inbound invoice model

edi.inbound.invoice
- external_id
- raw_xml
- raw_pdf
- parsed_data (json)
- state
- move_id (linked invoice)


6.3 audit log

edi.invoice.log
- move_id
- event_type
- old_state
- new_state
- payload
- created_at


7. System architecture

7.1 High-level flow

           OUTBOUND FLOW
Odoo Invoice
   ↓
Factur-X Generator
   ↓
Queue Job
   ↓
PDP Adapter (SUPER PDP)
   ↓
PDP API
   ↓
Lifecycle updates (webhook)

--------------------------------

           INBOUND FLOW
PDP
   ↓
Webhook endpoint
   ↓
Inbound staging table
   ↓
Parser (Factur-X / UBL)
   ↓
Odoo invoice creation


8. Design considerations

8.1 Separation of concerns





Accounting logic ≠ EDI logic



EDI logic isolated in gateway module



PDP providers isolated in adapters

8.2 Resilience





All external calls async



Retry policies mandatory



Webhook failures must not block invoices

8.3 Compliance

Must support:





EN16931 standard



Factur-X format



French e-invoicing lifecycle tracking

9. Technical considerations

Stack assumptions





Odoo 19 Community



Python 3.11+



OCA:





account_edi



queue_job



Factur-X tools

External dependencies





SUPER PDP API (initial provider)



Future PDP providers (Chorus, etc.)

10. Success metrics





≥ 99% invoice delivery success rate



< 2 min average transmission time



0 lost invoices (idempotency guaranteed)



100% lifecycle traceability



webhook processing latency < 5 seconds

11. Open questions





Should inbound invoice auto-post or stay in draft?



Should multi-PDP routing be tenant-configurable?



Should fallback polling be mandatory or optional?



Should invoice validation be strict or advisory?

🚀 Summary

You are essentially building:

A full EDI middleware layer inside Odoo 19

This module becomes:





a PDP abstraction layer



a lifecycle engine



a Factur-X transport system



a compliance bridge for French 2026–2027 reform



