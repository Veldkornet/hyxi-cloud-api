# Dev Container

Opens this repo in a Python 3.14 shell with `uv` and `pre-commit` set up to
match CI (`.github/workflows/tests.yml`).

Unlike `ha-hyxi-cloud`'s dev container, there's no separate live service to
bring up here -- this is a plain library, tested with `pytest`, plus the
[Bruno](https://www.usebruno.com/) collection at `../dev_env/bruno/` for
exercising the real HYXI Open API by hand (see `../CONTRIBUTING.md`). The
Bruno VS Code extension is recommended below for opening that collection
without leaving the editor, but note Bruno itself doesn't run *in* this
container -- it talks to `open.hyxicloud.com` directly.

## How the pieces fit together

- **`devcontainer.json`**: a plain `image` + Python feature devcontainer (no
  `dockerComposeFile` -- nothing else to merge in). `.venv` is shadowed by
  its own named volume rather than sharing the repo's bind mount: `uv sync`
  running in this (Linux) container would otherwise silently overwrite a
  host-side `.venv` (macOS, say) with Linux binaries, breaking it outside
  the container afterward. This isn't hypothetical -- it happened during
  testing on `ha-hyxi-cloud`'s dev container, which is why this one has the
  fix from the start.
- **`postCreate.sh`**: installs `uv` (pinned to a specific version, https-
  only redirects), runs the same two-pass `uv sync` split as
  `tests.yml` -- third-party dependencies with `--no-build
  --no-install-project`, then this project itself with building allowed
  (trusted first-party code) -- and installs the repo's `pre-commit` hooks.
  `UV_LOCKED=1` comes from `devcontainer.json`'s `remoteEnv`.

## Using it

- **Running tests:** `uv run pytest tests/ -v`, same as CI.
- **Bruno:** open `../dev_env/bruno/` in the Bruno extension (or the desktop
  app), fill in your own `access_key`/`secret_key` in the `HYXi`
  environment, and run **Get Token** before anything else.

If you don't need any of this, working directly on your host with
`uv sync --extra test` still works exactly as before -- this dev container
is optional, not a replacement for that.
