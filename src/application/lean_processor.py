import json
import re
import subprocess
from typing import Any

from loguru import logger

from src.constant import DATA_ROOT, REPL_ROOT
from src.entity.lean_response import LeanProcessorResponse


def _camel_to_snake(name: str) -> str:
    """Convert camelCase or PascalCase to snake_case."""
    s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


def _convert_keys_to_snake_case(obj: Any):
    """Recursively convert all dictionary keys to snake_case."""
    if isinstance(obj, dict):
        return {
            _camel_to_snake(k): _convert_keys_to_snake_case(v) for k, v in obj.items()
        }
    elif isinstance(obj, list):
        return [_convert_keys_to_snake_case(i) for i in obj]
    else:
        return obj


class LeanProcessor:
    def __init__(self, process: int = 0):
        self._file_path = DATA_ROOT / "tmp" / f"Verify{process}.lean"
        self._file_path.parent.mkdir(parents=True, exist_ok=True)
        self._file_path.touch(exist_ok=True)

    def exec(self, content: str) -> LeanProcessorResponse:
        with open(self._file_path, "w") as f:
            f.write(content)

        command = (
            f'echo \'{{"path": "{self._file_path}", "allTactics": true}}\''
            "| lake exe repl"
        )
        work_dir = REPL_ROOT
        result = subprocess.run(command, cwd=work_dir, shell=True, capture_output=True)
        if result.returncode != 0:
            raise ValueError("Verification failed. result: ", result)

        logger.debug("Lean result: ", result.stdout.decode("utf-8"))
        parsed_result = _convert_keys_to_snake_case(
            json.loads(result.stdout.decode("utf-8"))
        )
        return LeanProcessorResponse.from_dict(parsed_result)

    @classmethod
    def new(cls, idx: int) -> "LeanProcessor":
        return cls(idx)
