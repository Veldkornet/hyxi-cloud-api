---
name: code-review
description: Project-specific checklist for reviewing pull requests to the hyxi-cloud-api async client library — async-only I/O, secret/PII masking in logs, PEP 758 exception style, auth-signing integrity, input validation/timeouts, GitHub Actions hardening, error surfacing, and the single source of truth for the package version. Use whenever reviewing a pull request or diff in this repository.
---

# Code Review: hyxi-cloud-api

This repo is an async Python client (`aiohttp`-based) for the HYXi Cloud API,
published to PyPI and consumed by the `ha-hyxi-cloud` Home Assistant
integration. When reviewing a PR, check the following in addition to general
correctness.

## 1. Async-only I/O
- All network calls go through the caller-supplied `aiohttp.ClientSession`.
- No blocking calls (`requests`, `time.sleep()`, blocking file/network I/O)
  anywhere in `src/`.

## 2. Secrets and PII never hit the logs in the clear
- Access Key / Secret Key (AK/SK) and any other credentials must never appear
  in a log line, even at debug level.
- Identifiers the library already masks before logging — serial numbers
  (`deviceSn`, `parentSn`, `batSn`), `plantId`, and IMEI (`gprsImei`) via
  SHA-256 (first 8 chars), and `plantAddress` via full `[REDACTED]` — must
  stay masked if the surrounding code changes. If a PR adds a new field that
  is similarly sensitive (another identifier or an address-like value),
  flag it if it isn't routed through the same masking path.
- Masking must stay deterministic (same input → same masked output) since
  parent/child device relationships are traced across log lines using it.

## 3. Exception style (PEP 758)
- Multiple exceptions in one `except` are comma-separated without
  surrounding parentheses, unless an `as` clause is present:
  `except ValueError, TypeError:` — not `except (ValueError, TypeError):`.
  This is enforced by Sourcery (`enforce-pep-758-exception-grouping`); flag
  new code that reintroduces the parenthesized form.

## 4. Auth signing must not be bypassed
- Requests are signed via `_generate_headers` (HMAC), with
  `_ensure_authenticated` / `_execute_with_auth_retry` handling
  token refresh and retry-on-auth-failure. New or changed request methods
  should route through that path rather than hand-rolling a request that
  skips signing or the retry logic.
- Access/refresh tokens are never passed to a logging call, at any level.

## 5. Robust input handling and timeouts
- Requests go through the internal helper that sets a default `timeout`
  (currently 15s) — flag a new call path that issues a raw `aiohttp` request
  bypassing it, since that can hang indefinitely.
- API response values are numeric fields that can arrive `None`,
  non-numeric, `NaN`, or malformed — parse them through a guarded
  conversion (`try`/`except`, as the codebase already does e.g. around
  metric parsing) rather than a bare `float()`/`int()` that turns one bad
  payload into an unhandled exception.
- Regional base-URL resolution should stay restricted to the known
  China/Europe/North America nodes rather than accepting an arbitrary
  caller-supplied host.

## 6. GitHub Actions workflow hardening
Only applies when a PR touches `.github/workflows/*`:
- New or modified `uses:` steps pin the action to a full 40-character commit
  SHA with a version comment (e.g. `actions/checkout@<sha> # v7.0.1`), not a
  tag or branch.
- New workflows include `step-security/harden-runner` as their first step
  with `egress-policy: block`.
- `GITHUB_TOKEN` permissions are explicitly declared and scoped to the
  minimum the job needs.

## 7. Error surfacing
- Control-command failures raise `HyxiApiClient.ControlError`; subscription
  failures raise `HyxiApiClient.SubscriptionError`. Check that new
  control/subscription methods raise the correct one rather than letting a
  raw `aiohttp` exception or a bare `Exception` escape.
- Don't swallow API error responses silently — surface them as one of the
  library's exception types so callers (including the HA integration) can
  handle them.

## 8. Version single source of truth
- `src/hyxi_cloud_api/__init__.py`'s `__version__` is the only place the
  package version is defined (`pyproject.toml` reads it dynamically). Flag
  a PR that hardcodes or duplicates a version string elsewhere.

## 9. Typing and lint
- `ruff` clean under this project's ruleset (pycodestyle, pyflakes, isort,
  pyupgrade, bugbear, bandit `S` rules, pep8-naming, pathlib `PTH`).
- `mypy` clean; the project targets Python 3.14+ typing.

## 10. Reuse, simplification, dead code
- Flag duplicated logic between similar methods (e.g. the various
  `set_mode_*` / `subscribe_*` methods) that should share a helper instead.
- Flag properties, helpers, or exception types no longer referenced anywhere
  after the change.
