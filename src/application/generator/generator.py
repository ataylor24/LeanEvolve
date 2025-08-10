"""ConjectureGenerator – produce Lean conjectures via LLM"""

from __future__ import annotations

import json, pathlib, uuid
from pathlib import Path
from typing import List, Optional, Dict, Any

from src.application.generator.converter import ConjectureConverter
from src.application.generator.head_maker import ConjectureHeadMaker
from src.application.generator.llm import ConjectureGPT
from src.application.generator.prompt_maker import PromptMaker
from src.entity.conjecture import Conjecture
from src.entity.conjecture_eval_result import ConjectureEvalResult
from src.entity.mutation import Mutation
from src.application import mutation_utils


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

    def generate(
        self,
        context_id: str,
        context: str,
        eval_results: Optional[List[ConjectureEvalResult]] = None,
        elites: List[Dict[str, Mutation]] = [],
        ctx_mutations: dict[str, Mutation] = {},
        mutation: Optional[Mutation] = None,
        *,
        parent_code: str = "",
        operator_hint: Optional[str] = None,
    ) -> tuple[List[Conjecture], str]:

        eval_results = eval_results or []

        prompt = self.prompt_maker.make(
            context=context,
            parent_code=parent_code,
            mutation=mutation,
            elites=elites,
            ctx_mutations=ctx_mutations,
        )
        head = self.head_maker.make(context, eval_results)

        resp_obj = self.llm.ask(prompt)
        try:
            chosen_op = resp_obj["operator"]["name"]
            desc = resp_obj["operator"].get("description", "") or ""
            if chosen_op not in ctx_mutations:
                # Persist into mutations.json via mutation_utils API
                mutation_utils.add_op(context_id, chosen_op, desc)
                ctx_mutations[chosen_op] = {"name": chosen_op, "description": desc}
        except (KeyError, TypeError):
            malformed_dir = Path("malformed_json")
            malformed_dir.mkdir(exist_ok=True)
            fname = malformed_dir / f"{uuid.uuid4()}.json"
            fname.write_text(json.dumps(resp_obj, indent=2))
            raise ValueError(f"Malformed LLM response (saved to {fname}).") from None

        conjectures: List[Conjecture] = []
        chosen_op = mutation.name if isinstance(mutation, Mutation) else resp_obj["operator"]["name"]
        op_desc = mutation.description if isinstance(mutation, Mutation) else resp_obj["operator"]["description"]
        for stmt in resp_obj["conjectures"]:
            conjectures.extend(
                self.converter.convert(
                    head,
                    stmt,
                    meta={"operator": chosen_op, "description": op_desc},
                )
            )

        return conjectures, chosen_op
