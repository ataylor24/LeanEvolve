import os
from pathlib import Path

REPL_ROOT = Path("repl")
MATHLIB_ROOT = REPL_ROOT / ".lake" / "packages" / "mathlib"
DATA_ROOT = Path("data").absolute()

DEFAULT_OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
