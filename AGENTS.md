# Notes for AI coding assistants

Repository facts for tools working on this client. People should start with [CONTRIBUTING.md](CONTRIBUTING.md); this file adds the conventions a change has to follow.

## What this is

An async Python client (`aiohttp`) for HYXI's OpenAPI: authentication, device discovery and polling, derived metrics, device control, push subscriptions and parsing pushed data. Its main user is the [ha-hyxi-cloud](https://github.com/Veldkornet/ha-hyxi-cloud) Home Assistant integration, which pins an exact version, so a breaking change only reaches it when it bumps the pin.

## Layout

- `src/hyxi_cloud_api/api.py`: the whole client, `HyxiApiClient`, with its errors (`HyxiAuthError`, `TokenRequestError`, and the nested `ControlError` and `SubscriptionError`) and its result types (`DiscoveryResult`, `Subscription`, `SubscribeResult`, `AuthorizationType`, `SubscriptionType`).
- `src/hyxi_cloud_api/__init__.py`: the public exports (`__all__`) and `__version__`.
- `tests/`: unit tests that answer the client's requests with mocks; no network access.

## Checks (exactly what CI runs)

```bash
uv sync --extra test
uv run pytest tests/ -p no:warnings --cov --cov-report=
uv run coverage report -m --fail-under=100
pre-commit run --files <changed files>
```

Coverage must stay at 100%. The pre-commit hooks include `mypy`, `pylint`, `vulture` and a check that exceptions are grouped the PEP 758 way (`except ValueError, TypeError:`).

## Conventions

- **Public API:** anything callers use is exported in `__init__.py`'s `__all__` and documented in the README. Prefer typed results (frozen dataclasses, enums) over HYXI's raw dicts, and document what each public method raises.
- **Breaking changes:** a change to a public method's return type or errors goes under "Behaviour Changes" in the release notes, with what callers have to change.
- **Logs:** never log keys, tokens, serial numbers or plant IDs as they are; mask identifiers with `_mask_id` and responses with `_sanitize_dict`.
- **Versions:** `__version__` in `__init__.py` is the only version; publishing a GitHub release puts the tag's version on PyPI (see CONTRIBUTING.md).
- **Comments and docstrings** describe what the code does now. History, issue or PR numbers and lint-rule citations belong in the commit message.
- **Issues and PRs are public:** no API keys, serial numbers or plant IDs in them.
