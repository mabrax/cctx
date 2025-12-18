"""Pytest configuration and fixtures for cctx tests."""

import os

# Set a fixed terminal width to prevent line wrapping issues in CI
# This must be set before any Rich imports
os.environ.setdefault("COLUMNS", "200")
os.environ.setdefault("LINES", "50")
# Disable Rich's terminal detection to ensure consistent output
os.environ.setdefault("TERM", "dumb")
