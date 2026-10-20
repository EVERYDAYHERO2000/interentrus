"""Load provider code independently of the Home Assistant runtime."""

import importlib.util
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "isp_providers",
    root / "custom_components/isp_balance/providers/__init__.py",
    submodule_search_locations=[str(root / "custom_components/isp_balance/providers")],
)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
