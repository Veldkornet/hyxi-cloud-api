#!/usr/bin/env python3
"""Check that the package version in pyproject.toml and __init__.py are in sync."""

import re
import sys
from pathlib import Path


def main() -> None:
    """Verify that version declarations match across all API package files."""
    root = Path(__file__).parent.parent

    # 1. Read __init__.py version
    init_path = root / "src" / "hyxi_cloud_api" / "__init__.py"
    if not init_path.exists():
        print(f"Error: __init__.py not found at {init_path}")
        sys.exit(1)

    with init_path.open("r", encoding="utf-8") as f:
        init_content = f.read()

    init_version_match = re.search(
        r'^__version__\s*=\s*"(.*?)"', init_content, re.MULTILINE
    )
    init_version = init_version_match.group(1) if init_version_match else None

    # 2. Read pyproject.toml version
    pyproject_path = root / "pyproject.toml"
    if not pyproject_path.exists():
        print(f"Error: pyproject.toml not found at {pyproject_path}")
        sys.exit(1)

    with pyproject_path.open("r", encoding="utf-8") as f:
        pyproject_content = f.read()

    pyproject_version_match = re.search(
        r'^version\s*=\s*"(.*?)"', pyproject_content, re.MULTILINE
    )
    pyproject_version = (
        pyproject_version_match.group(1) if pyproject_version_match else None
    )

    if not init_version or not pyproject_version:
        print("Error: Could not extract versions.")
        print(f"  __init__.py version parsed: {init_version}")
        print(f"  pyproject.toml version parsed: {pyproject_version}")
        sys.exit(1)

    if init_version != pyproject_version:
        print("Package version mismatch:")
        print(f"  __init__.py: {init_version}")
        print(f"  pyproject.toml: {pyproject_version}")
        sys.exit(1)

    print("All package versions are in sync!")
    sys.exit(0)


if __name__ == "__main__":
    main()
