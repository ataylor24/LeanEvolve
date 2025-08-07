import json
import uuid
from datetime import datetime
from pathlib import Path

from src.constant import DATA_ROOT
from src.entity.conjecture_eval_result import ConjectureEvalResult

EVAL_RESULT_JSONL_FILE_PATH = DATA_ROOT / "conjecture_eval_result.jsonl"
NONTIVIAL_CONJECTURE_JSONL_FILE_PATH = DATA_ROOT / "grpo_problem.jsonl"


class ConjectureEvalResultRepository:
    """ConjectureEvalResultをjsonl形式で保存するリポジトリ"""

    def __init__(self, file_path: Path = EVAL_RESULT_JSONL_FILE_PATH):
        if not file_path.name.endswith(".jsonl"):
            raise ValueError("file_path must end with .jsonl")

        if not file_path.parent.exists():
            file_path.parent.mkdir(parents=True, exist_ok=True)
        if not file_path.exists():
            file_path.touch()

        self.file_path = file_path

    def save(self, results: list[ConjectureEvalResult]) -> None:
        """ConjectureEvalResultをjsonl形式で保存する"""
        with open(self.file_path, "a") as f:
            for result in results:
                f.write(
                    json.dumps(
                        {
                            "id": str(result.conjecture.id),
                            "already_exists": result.already_exists,
                            "aesop_provable": result.aesop_provable,
                            "goal": result.goal,
                            "proof": result.proof,
                            "error": (
                                None if result.error is None else (
                                    result.error if isinstance(result.error, str) else result.error.model_dump_json()
                                )
                            ),
                            "created_at": result.created_at.isoformat(),
                            "conjecture": result.conjecture.context_and_statement,
                            "context_name": result.context_name,
                        }
                    )
                    + "\n"
                )

        with NONTIVIAL_CONJECTURE_JSONL_FILE_PATH.open("a") as f:
            for result in results:
                if (
                    not result.already_exists
                    and not result.aesop_provable
                    and result.error is None
                ):
                    f.write(
                        json.dumps({"problem": result.conjecture.context_and_statement})
                        + "\n"
                    )

    def get_by_conjecture_id(
        self, conjecture_id: uuid.UUID
    ) -> ConjectureEvalResult | None:
        """ConjectureEvalResultをconjecture_idで取得する"""
        with open(self.file_path) as f:
            for line in f:
                result = ConjectureEvalResult.model_validate_json(line)
                if result.conjecture.id == conjecture_id:
                    return result
        return None

    def get_by_datetime(
        self,
        start_datetime: datetime | None = None,
        end_datetime: datetime | None = None,
    ) -> list[ConjectureEvalResult]:
        with open(self.file_path) as f:
            results = []
            for line in f:
                result = ConjectureEvalResult.model_validate_json(line)
                if start_datetime and result.created_at < start_datetime:
                    continue
                if end_datetime and result.created_at > end_datetime:
                    continue
                results.append(result)
            return results
