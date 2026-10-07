"""Compatibility re-export: the implementation is layout-neutral and lives in statement_engine.extraction.words."""
from ...extraction.words import *  # noqa: F401,F403
from ...extraction import words as _m

globals().update({k: getattr(_m, k) for k in dir(_m) if not k.startswith("__")})
