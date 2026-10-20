"""Run any mm2 harness against Market_Maker_6 (alias trick)."""
import os, runpy, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import Market_Maker_6
sys.modules["Market_Maker_2"] = Market_Maker_6
if __name__ == "__main__":
    sys.argv = sys.argv[1:]
    runpy.run_module(sys.argv[0], run_name="__main__")
