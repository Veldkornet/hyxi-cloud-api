#!/usr/bin/env bash
# Runs once inside the devcontainer service after it's created. Mirrors
# .github/workflows/tests.yml's "Install dependencies" step as closely as
# possible so a passing local run means the same thing CI's run does.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

# Pinned rather than the bare .../uv/install.sh (always "latest"): a fixed
# version means what's installed here is the version this setup was last
# validated against, not whatever astral happens to be serving the moment
# someone opens the devcontainer. Bump deliberately, like a lockfile.
# --proto/--tlsv1.2 restrict curl to https-only redirects -- plain -L would
# silently follow a redirect to http.
curl --proto '=https' --tlsv1.2 -LsSf https://astral.sh/uv/0.12.3/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"

# The .venv named volume (see devcontainer.json's "mounts") is created
# root-owned by Docker on first use; postCreateCommand runs as the non-root
# `vscode` user, so hand the mount point over before `uv sync` writes into
# it. (Without a dedicated volume here, `uv sync` would instead write
# straight into the bind-mounted repo's .venv -- overwriting a host venv,
# e.g. macOS, with Linux binaries and breaking it outside the container.)
sudo chown -R "$(id -u):$(id -g)" .venv

# Same two-pass split tests.yml uses, for the same reason (see its own
# comment): third-party dependencies are installed with --no-build
# --no-install-project (refuses to build any of them from a source
# distribution, which would otherwise run that package's own build-backend
# code), then this project itself is installed separately, with building
# allowed -- trusted first-party code, no supply-chain concern in running
# our own build backend on our own checkout. UV_LOCKED=1 comes from
# devcontainer.json's `remoteEnv` (covers lifecycle scripts too, not just
# terminals), so both passes fail fast on lockfile drift like CI's do.
uv sync --extra test --no-build --no-install-project
uv sync --extra test

uv tool install pre-commit
pre-commit install
