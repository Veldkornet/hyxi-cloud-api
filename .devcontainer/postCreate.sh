#!/usr/bin/env bash
# Runs once inside the devcontainer service after it's created. Mirrors
# .github/workflows/tests.yml's "Install dependencies" step as closely as
# possible so a passing local run means the same thing CI's run does.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

# Download the release archive and verify it against astral's own published
# checksum, rather than piping install.sh through sh: pinning a version in
# the install.sh URL (astral.sh/uv/<version>/install.sh) does NOT pin or
# verify the *installer script's own content* -- only the release binaries
# it goes on to fetch are checksummed internally. This step checks exactly
# what it's about to run. Bump UV_VERSION deliberately, like a lockfile.
UV_VERSION="0.12.3"
case "$(uname -m)" in
  x86_64) UV_TARGET="x86_64-unknown-linux-gnu" ;;
  aarch64) UV_TARGET="aarch64-unknown-linux-gnu" ;;
  *)
    echo "error: unsupported architecture $(uname -m) for pinned uv install" >&2
    exit 1
    ;;
esac
UV_ASSET="uv-${UV_TARGET}.tar.gz"
UV_RELEASE_URL="https://github.com/astral-sh/uv/releases/download/${UV_VERSION}"

uv_tmpdir="$(mktemp -d)"
trap 'rm -rf "$uv_tmpdir"' EXIT
# --proto/--tlsv1.2 restrict curl to https-only redirects -- plain -L would
# silently follow a redirect to http.
curl --proto '=https' --tlsv1.2 -LsSf "$UV_RELEASE_URL/$UV_ASSET" -o "$uv_tmpdir/$UV_ASSET"
curl --proto '=https' --tlsv1.2 -LsSf "$UV_RELEASE_URL/$UV_ASSET.sha256" -o "$uv_tmpdir/$UV_ASSET.sha256"
(cd "$uv_tmpdir" && sha256sum -c "$UV_ASSET.sha256")

mkdir -p "$HOME/.local/bin"
tar -xzf "$uv_tmpdir/$UV_ASSET" -C "$uv_tmpdir"
mv "$uv_tmpdir/uv-$UV_TARGET/uv" "$uv_tmpdir/uv-$UV_TARGET/uvx" "$HOME/.local/bin/"

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
uv sync --extra test  # NOSONAR: this pass is specifically the trusted-first-party-build step the comment above describes -- --no-build would defeat its purpose

# pre-commit is a locked test dependency (pyproject.toml), not `uv tool
# install`'s unversioned "whatever's latest on PyPI right now" -- `uv run`
# uses the project's own locked venv instead of uv's separate, unpinned
# tool store. `uv run --no-build` was tried here and doesn't work: its
# implicit sync re-validates the *whole* environment against the flag,
# including this project's own editable install, which has no wheel and
# always needs building -- same root cause as the NOSONAR above, verified
# by actually hitting the resulting error, not assumed.
uv run pre-commit install  # NOSONAR: see comment -- --no-build is incompatible with this project's own editable install
