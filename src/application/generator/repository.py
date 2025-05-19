from src.constant import DATA_ROOT
from src.entity.conjecture import Conjecture

CONJECTURE_JSONL_FILE_PATH = DATA_ROOT / "conjecture.jsonl"


class ConjectureRepository:
    def save(self, conjectures: list[Conjecture]) -> None:
        with CONJECTURE_JSONL_FILE_PATH.open("a") as f:
            for conjecture in conjectures:
                f.write(conjecture.model_dump_json() + "\n")
