#!/usr/bin/env python3
"""Compatibility entry point for the common, non-destructive configurator."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from deploy import configure
if __name__ == '__main__':
    configure()
