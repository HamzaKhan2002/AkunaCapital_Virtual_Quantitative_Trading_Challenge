"""
Run any existing mm2 harness against Market_Maker_3 without touching it.

    python as_mm3.py validate_mm2
    python as_mm3.py stress_mm2
    python as_mm3.py fuzz_edge_cases

Works because every harness does `from Market_Maker_2 import ...`; pre-seeding
sys.modules redirects that import to mm3.
"""
import os
import runpy
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import Market_Maker_3  # noqa: E402

sys.modules["Market_Maker_2"] = Market_Maker_3

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        raise SystemExit(2)
    sys.argv = sys.argv[1:]
    runpy.run_module(sys.argv[0], run_name="__main__")
