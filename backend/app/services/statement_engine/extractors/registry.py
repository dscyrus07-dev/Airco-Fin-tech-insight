"""Default registry of the layouts available in this build."""
from ..extraction.registry import LayoutRegistry
from .hdfc.layout_spec import HDFC_LAYOUT_A

DEFAULT_REGISTRY = LayoutRegistry([HDFC_LAYOUT_A])
