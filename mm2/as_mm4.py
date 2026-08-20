"""Run any mm2 harness against Market_Maker_4 (alias trick, see as_mm3.py)."""
import os
import runpy
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import Market_Maker_4  # noqa: E402

sys.modules["Market_Maker_2"] = Market_Maker_4

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        raise SystemExit(2)
    sys.argv = sys.argv[1:]
    runpy.run_module(sys.argv[0], run_name="__main__")
