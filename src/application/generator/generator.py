"""ConjectureGenerator – produce Lean conjectures via LLM"""

from __future__ import annotations

import json, pathlib, uuid
from pathlib import Path
from typing import List, Optional

from src.application.generator.converter import ConjectureConverter
from src.application.generator.head_maker import ConjectureHeadMaker
from src.application.generator.llm import ConjectureGPT
from src.application.generator.prompt_maker import PromptMaker
from src.entity.conjecture import Conjecture
from src.entity.conjecture_eval_result import ConjectureEvalResult

_MUTATION_FILE = pathlib.Path("mutations.json")
if _MUTATION_FILE.exists():
    # context_id -> { op_name -> description }
    _MUTATIONS: dict[str, dict[str, str]] = json.loads(_MUTATION_FILE.read_text())
else:
    _MUTATIONS = {}

def get_ctx_ops(context_id: str) -> dict[str, str]:
    """Return (and create) the operator map for this context."""
    return _MUTATIONS.setdefault(context_id, {})

def save_all() -> None:
    """Persist all contexts' mutations."""
    _MUTATION_FILE.write_text(json.dumps(_MUTATIONS, indent=2))


class ConjectureGenerator:
    """
    Thin wrapper around PromptMaker/LLM that now supports:
        • optional parent_code (few‑shot seed)
        • optional operator_hint (mutation to apply)
    """

    def __init__(
        self,
        model_name: str,
        api_key: str,
        rename: bool = False,
    ) -> None:
        self.llm = ConjectureGPT(model_name, api_key)
        self.prompt_maker = PromptMaker()
        self.head_maker = ConjectureHeadMaker()
        self.converter = ConjectureConverter(rename=rename)

        # Expose the whole catalogue if callers want to inspect it
        self.mutations = _MUTATIONS

    def generate(
        self,
        context_id: str,
        context: str,
        eval_results: Optional[List[ConjectureEvalResult]] = None,
        *,
        parent_code: str = "",
        operator_hint: Optional[str] = None,
    ) -> tuple[List[Conjecture], str]:

        eval_results = eval_results or []

        prompt = self.prompt_maker.make(
            context=context,
            parent_code=parent_code,
            operator_hint=operator_hint,
        )
        head = self.head_maker.make(context, eval_results)

        resp_obj = self.llm.ask(prompt)
        try:
            chosen_op = resp_obj["operator"]["name"]
            desc = resp_obj["operator"].get("description", "") or ""
            ctx_ops = get_ctx_ops(context_id)

            if chosen_op not in ctx_ops:
                ctx_ops[chosen_op] = desc
                save_all()
        except (KeyError, TypeError):
            malformed_dir = Path("malformed_json")
            malformed_dir.mkdir(exist_ok=True)
            fname = malformed_dir / f"{uuid.uuid4()}.json"
            fname.write_text(json.dumps(resp_obj, indent=2))
            raise ValueError(f"Malformed LLM response (saved to {fname}).") from None

        conjectures: List[Conjecture] = []
        op_desc = get_ctx_ops(context_id).get(chosen_op, "")
        for stmt in resp_obj["conjectures"]:
            conjectures.extend(
                self.converter.convert(
                    head,
                    stmt,
                    meta={"operator": chosen_op, "description": op_desc},
                )
            )

        return conjectures, chosen_op
