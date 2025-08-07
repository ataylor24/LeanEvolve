import re
from dataclasses import dataclass

from loguru import logger

from src.entity.conjecture import Conjecture


@dataclass
class ConjectureConverter:
    rename: bool = False

    def convert(self, conjecture_head: str, completion: str, meta: dict | None = None) -> list[Conjecture]:
        conjecture = _update_header(
            conjecture_head, _to_theorem(_update_footer(completion))
        )
        if self.rename:
            conjecture = _rename(conjecture)
        return [conjecture] if conjecture is not None else []


def _update_footer(code: str) -> str:
    lines = code.split(":=")
    code = lines[0] + ":= by\n"
    return code


def _to_theorem(code: str) -> Conjecture | None:
    try:
        code = re.sub(r"lemma", "theorem", code, count=1)
        idx = code.find("theorem")
        code = code[idx:] if idx != -1 else ""
        return Conjecture.new(code=code)
    except Exception as e:
        logger.warning(f"Error: {e}")
        logger.warning(f"Invalid statement: {code}")
        return None


def _update_header(head: str, conjecture: Conjecture | None) -> Conjecture | None:
    # if code starts with import, we need to remove the first import sentence
    # and replace it with updated import sentence
    if conjecture is None:
        return None
    if not conjecture.generation_successful:
        return conjecture
    conjecture.update_code(code=head + "\n" + conjecture.code)
    return conjecture


def _rename(conjecture: Conjecture | None) -> Conjecture | None:
    if conjecture is None:
        return None
    if not conjecture.generation_successful:
        return conjecture

    theorem_name = conjecture.name.split(".")[0] + "_ai"

    code = (
        conjecture.context
        + "theorem "
        + theorem_name
        + " "
        + " ".join(conjecture.statement.split()[2:])
        + "\n"
    )
    conjecture.update_code(code=code)
    return conjecture
