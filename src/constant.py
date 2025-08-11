import os
from pathlib import Path

REPL_ROOT = Path("repl")
MATHLIB_ROOT = REPL_ROOT / ".lake" / "packages" / "mathlib"
DATA_ROOT = Path("data").absolute()
# Store mutations per-run inside the shared data directory so the top-level
# version stays untouched.
GLOBAL_MUTATION_FILE = str("mutations.json")
LOCAL_MUTATION_FILE = str(DATA_ROOT / "mutations.json")
DEFAULT_OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
