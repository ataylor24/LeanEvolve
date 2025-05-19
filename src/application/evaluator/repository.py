import uuid
from datetime import datetime
from pathlib import Path

from src.constant import DATA_ROOT
from src.entity.conjecture_eval_result import ConjectureEvalResult

EVAL_RESULT_JSONL_FILE_PATH = DATA_ROOT / "conjecture_eval_result.jsonl"


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
                f.write(result.model_dump_json() + "\n")

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
