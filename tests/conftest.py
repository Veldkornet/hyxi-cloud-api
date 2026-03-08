"""Pytest configuration and setup."""

import sys
import os

# Adds the parent directory (your project root) to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
