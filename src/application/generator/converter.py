import re
from dataclasses import dataclass

from loguru import logger

from src.entity.conjecture import Conjecture


@dataclass
class ConjectureConverter:
    rename: bool = False

    def convert(self, conjecture_head: str, completion: str) -> list[Conjecture]:
        conjecture = _update_header(
            conjecture_head, _to_theorem(_update_footer(completion))
        )
        if self.rename:
            conjecture = _rename(conjecture)
        return [conjecture]


def _update_footer(code: str) -> str:
    lines = code.split(":=")
    code = lines[0] + ":= by\n"
    return code


def _to_theorem(code: str) -> Conjecture:
    try:
        code = re.sub(r"lemma", "theorem", code, count=1)
        idx = code.find("theorem")
        code = code[idx:] if idx != -1 else ""
        return Conjecture.new(code=code)
    except Exception as e:
        logger.warning(f"Error: {e}")
        logger.warning(f"Invalid statement: {code}")
        return Conjecture.new(code=code, generate_err=str(e))


def _update_header(head: str, conjecture: Conjecture) -> Conjecture:
    # if code starts with import, we need to remove the first import sentence
    # and replace it with updated import sentence
    if not conjecture.generation_successful:
        return conjecture
    conjecture.update_code(code=head + "\n" + conjecture.code)
    return conjecture


def _rename(conjecture: Conjecture) -> Conjecture:
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
