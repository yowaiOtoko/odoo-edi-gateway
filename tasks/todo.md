# TODO

- [x] Inspect SUPER PDP adapter failure path
- [x] Update token retrieval to support OAuth2 client credentials in Authorization header
- [x] Correct default SUPER PDP sandbox/production hostnames
- [x] Add regression tests for token request format and modern host defaults
- [x] Run targeted tests for SUPER PDP adapter

# Review

- Implemented OAuth2 token retrieval with standards-compliant Basic auth header first, then legacy body-credential fallback.
- Updated default sandbox domains from super-pdp.tech to superpdp.tech in runtime defaults and company field defaults.
- Added adapter-level URL normalization so existing saved super-pdp.tech values are transparently upgraded at runtime.
- Added tests covering header-based token request, legacy URL normalization, and fallback behavior when header auth is rejected.
- Verification: VS Code diagnostics are clean for modified files; `python3 -m compileall odoo_edi_gateway` succeeded.
- Note: direct test execution via `runTests` found no runnable tests in this environment, and `pytest` is not installed locally.
