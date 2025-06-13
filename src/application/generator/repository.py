import json

from src.constant import DATA_ROOT
from src.entity.conjecture import Conjecture

CONJECTURE_JSONL_FILE_PATH = DATA_ROOT / "conjecture.jsonl"
NONTIVIAL_CONJECTURE_JSONL_FILE_PATH = DATA_ROOT / "nontrivial_conjecture.jsonl"


class ConjectureRepository:
    def save(self, conjectures: list[Conjecture]) -> None:
        with CONJECTURE_JSONL_FILE_PATH.open("a") as f:
            for conjecture in conjectures:
                f.write(
                    json.dumps(
                        {
                            "id": str(conjecture.id),
                            "conjecture": conjecture.context_and_statement,
                            "generate_err": conjecture.generate_err,
                            "created_at": conjecture.created_at.isoformat(),
                        }
                    )
                    + "\n"
                )
