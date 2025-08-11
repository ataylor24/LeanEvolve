import json, pathlib
from typing import Dict, Any

from src.constant import LOCAL_MUTATION_FILE, GLOBAL_MUTATION_FILE
from src.entity.mutation import Mutation

_LOCAL_MUTATION_FILE = pathlib.Path(LOCAL_MUTATION_FILE)
_GLOBAL_MUTATION_FILE = pathlib.Path(GLOBAL_MUTATION_FILE)
# Ensure parent directory exists (e.g. `data/`) so read/write succeeds even on fresh checkouts.
_LOCAL_MUTATION_FILE.parent.mkdir(parents=True, exist_ok=True)
_RAW: Dict[str, Any] = json.loads(_GLOBAL_MUTATION_FILE.read_text()) if _GLOBAL_MUTATION_FILE.exists() else {}

def _ensure_ctx(ctx: str) -> Dict[str, Any]:
    if ctx not in _RAW:
        _RAW[ctx] = {}
    return _RAW[ctx]


def get_ctx_ops(context_id: str) -> Dict[str, Mutation]:
    """Return operator map for this context: {op_id: {name, description}}.

    Supports two schemas in the JSON:
      - { "mutations": [ {"name":..., "description":...}, ... ], ... }
      - top-level pairs "op_name": "description" for convenience.
    """
    ctx_data = _RAW.get(context_id, {})
    ops: Dict[str, Mutation] = {}

    # List-based entries
    for op_name, op_desc in ctx_data.items():
        ops[op_name] = Mutation(name=op_name, description=op_desc)

    return ops


def add_op(context_id: str, name: str, description: str) -> None:
    """Append a new operator to the context and persist to disk."""
    ctx = _ensure_ctx(context_id)
    ctx[name] = description
    _LOCAL_MUTATION_FILE.write_text(json.dumps(_RAW, indent=2, ensure_ascii=False))