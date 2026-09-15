# Security Policy

## Reporting a vulnerability

Report privately via [GitHub Security Advisories][advisories] — please don't open a public issue.

[advisories]: https://github.com/edgar971/hermes-ollama-web/security/advisories/new

## Scope

This package sends your `OLLAMA_API_KEY` to the configured base URL and returns fetched web
content to a Hermes agent. Relevant properties:

- **The key is read from the environment only** — never logged, never written to disk, never
  included in an error message. Failures surface HTTP status plus a truncated response body.
- **`OLLAMA_WEB_BASE_URL` redirects where the key is sent.** Only point it at hosts you trust;
  it exists for proxies and self-hosted gateways.
- **Fetched page content is untrusted input.** It flows into an LLM's context, so prompt
  injection from a fetched page is a real risk. That threat is inherent to any web tool and is
  handled by Hermes (blocklists, SSRF gates, char budgets), not here.
- **No `eval`, no subprocess, no filesystem writes.** The package makes HTTPS requests and
  transforms JSON.

## Supported versions

The latest release on `main`. This is a small package — fixes ship forward, not backported.
