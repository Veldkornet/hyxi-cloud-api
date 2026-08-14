# Contributing to hyxi-cloud-api

Thanks for considering a contribution! This library exists mainly to power the
[HYXi Cloud Home Assistant Integration](https://github.com/Veldkornet/ha-hyxi-cloud),
but it's usable standalone in any Python 3.14+ project.

## 🛠️ Development Setup

1. **Fork and Clone:** create a branch from `main`.
2. **Environment:** Open the repo in the [dev container](.devcontainer/) (VS
   Code "Reopen in Container", or GitHub Codespaces) for a ready-to-go
   Python 3.14 + `uv` + `pre-commit` setup, plus the Bruno extension for the
   collection below -- see `.devcontainer/README.md`. Not required:
   `uv sync --extra test` on your own machine works just as well.
3. **Install:** `uv sync --extra test` gets you a `.venv` with the runtime
   dependencies (`aiohttp`) plus the test extras (`pytest`, `pytest-asyncio`,
   `hypothesis`, `pytest-cov`).
4. **Pre-commit:** install the hooks (`ruff`, `mypy`, `pylint`, `vulture`,
   `codespell`, `gitleaks`, `shellcheck`, and a custom
   [PEP 758](https://peps.python.org/pep-0758/) exception-grouping check --
   see `.pre-commit-config.yaml`) with `pre-commit install`.
5. **Coding Standards:** [Ruff](https://github.com/astral-sh/ruff) for
   linting/formatting; this project targets Python 3.14 and prefers the
   PEP 758 comma-separated exception syntax (`except ValueError, TypeError:`)
   over parenthesized grouping -- the `check-exception-parentheses`
   pre-commit hook enforces this.

## 🧪 Testing

`uv run pytest tests/ -v` matches what CI runs. CI installs dependencies in
two passes -- third-party packages with `--no-build --no-install-project`
(refuses to build any of them from source, which would otherwise run that
package's own build backend) and this project itself separately, with
building allowed (trusted first-party code, no supply-chain concern in
running our own build backend on our own checkout):

```bash
uv sync --extra test --no-build --no-install-project
uv sync --extra test
```

Plain `uv sync --extra test` also works locally; the split only matters for
CI's stricter posture.

## 🌐 Testing Against the Real API: Bruno

`dev_env/bruno/` is a [Bruno](https://www.usebruno.com/) collection covering
the HYXI Open API endpoints this library wraps -- useful for exploring the
API directly, or reproducing an issue outside of Python before deciding
whether the bug is in this client or the API itself.

- **Opening it:** install Bruno, then "Open Collection" and point it at
  `dev_env/bruno/`.
- **Credentials:** the `HYXi` environment (`dev_env/bruno/environments/HYXi.yml`)
  declares `access_key` and `secret_key` as secret variables with no value
  committed. Fill in your own [developer API credentials](https://open.hyxicloud.com)
  in Bruno's environment editor after opening the collection -- they're
  stored locally by Bruno, never written back into the committed file.
- **Auth flow:** run the **Get Token** request first; the other requests
  read the resulting token from a runtime variable and will error clearly
  ("No token found! Run the 'Get Token' request first.") if you skip it.
- Requests that need a specific plant or device populate
  `active_plant_id` / `active_device_sn` automatically from an earlier
  response (e.g. **Query List of Plants**, **Query Devices at that Plant**)
  rather than expecting a hardcoded value.

## 🔖 Releasing

`src/hyxi_cloud_api/__init__.py`'s `__version__` is the single source of
truth for the package version (`pyproject.toml` reads it dynamically via
`tool.setuptools.dynamic`). Publishing a GitHub Release triggers
`ci-cd.yml`'s `publish` job, which pushes to PyPI over OIDC (no stored
token) using the release's tag name.

## ⚖️ License

By contributing, you agree that your contributions will be licensed under
the project's **MIT License**.
