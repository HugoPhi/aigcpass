"""Unified skill root directory locator.

All scripts should import ROOT from this module instead of duplicating
_find_root() logic. This ensures correct path resolution regardless of
where the skill is installed or what the current working directory is.
"""
import os as _os

# _root.py lives in script/, so its parent directory is the skill root.
ROOT = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
