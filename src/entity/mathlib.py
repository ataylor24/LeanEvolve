import re

from src.constant import MATHLIB_ROOT


class MathlibFile:
    def __init__(self, file_path: str):
        if not self.is_valid(file_path):
            raise ValueError("invalid file path: " + file_path)
        self.file_path = file_path

        self.__content: str | None = None

    def __hash__(self):
        return hash(self.file_path)

    @property
    def content(self) -> str:
        if not self.__content:
            lean_file_path = (
                MATHLIB_ROOT / self.file_path.replace(".", "/")
            ).with_suffix(".lean")
            with lean_file_path.open() as f:
                self.__content = f.read()

        return self.__content

    @property
    def import_header(self) -> str:
        return f"import {self.file_path}"

    @staticmethod
    def is_valid(dot_file_path: str) -> bool:
        pattern = re.compile(r"^Mathlib(?:\.[A-Z][A-Za-z0-9]*)*$")
        if not pattern.match(dot_file_path):
            return False

        lean_file_path = (MATHLIB_ROOT / dot_file_path.replace(".", "/")).with_suffix(
            ".lean"
        )
        return lean_file_path.exists()
