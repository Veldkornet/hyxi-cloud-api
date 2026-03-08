#!/bin/bash

# Get the directory where the script is located
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

ACTION=$1

case "$ACTION" in
  sync-git)
    echo "☁️  Fetching latest from GitHub..."
    git fetch --all

    echo "🏠 Updating local 'main'..."
    git checkout main
    git pull origin main

    echo "🛠️  Updating local 'dev'..."
    git checkout dev
    git pull origin dev

    echo "🔀 Merging 'main' into 'dev'..."
    if git merge main -m "chore: sync with main"; then
        echo "🚀 Pushing synced dev branch to GitHub..."
        git push origin dev
        echo "✅ Everything is up to date and in sync!"
    else
        echo "⚠️  CONFLICTS FOUND!"
        echo "Git couldn't auto-merge. Look at the red files in your sidebar."
        echo "Fix them, save, and commit to finish the sync manually."
        # We exit with an error code so the VS Code task shows a 'failed' notification
        exit 1
    fi
    ;;

  reset-dev)
    echo "☢️  Preparing to hard reset 'dev' to 'main'..."

    # Safety Check: Are there uncommitted changes?
    if ! git diff-index --quiet HEAD --; then
        echo "❌ ERROR: You have uncommitted changes! Commit them or stash them first."
        exit 1
    fi

    echo "☁️  Fetching latest from GitHub..."
    git fetch --all

    echo "🏠 Updating local 'main'..."
    git checkout main
    git pull origin main

    echo "🧹 Wiping 'dev' and matching it to 'main'..."
    git checkout dev
    git reset --hard main

    echo "🚀 Force-pushing clean 'dev' to GitHub..."
    git push origin dev --force

    echo "✨ 'dev' is now a clean mirror of 'main'. The ghosts are gone!"
    ;;
  ruff-check)
    echo "🔍 Running Ruff Check..."
    cd ..
    python3 -m ruff check .
    ;;
  ruff-format)
    echo "🧹 Running Ruff Format..."
    cd ..
    python3 -m ruff format .
    ;;
  ruff-fix)
    echo "🧹 Running Ruff Fix..."
    cd ..
    python3 -m ruff check . --fix
    ;;
  *)
    echo "Usage: $0 {sync-git|reset-dev|ruff-check|ruff-format|ruff-fix}"
    exit 1
    ;;

esac
