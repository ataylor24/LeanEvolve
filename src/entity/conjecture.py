import uuid
from datetime import datetime

from pydantic import BaseModel, field_validator


class Conjecture(BaseModel):
    code: str
    generate_err: str | None
    id: uuid.UUID
    created_at: datetime

    @field_validator("code")
    @classmethod
    def _validate_code(cls, code: str):
        if not code.endswith(":= by\n"):
            raise ValueError("Invalid Conjecture: code must end with `:= by\n`")
        return code

    @property
    def generation_successful(self) -> bool:
        return self.generate_err is None

    @property
    def context(self) -> str:
        return self.code.split("theorem")[0]

    @property
    def statement(self) -> str:
        return "theorem" + self.code.split("theorem")[-1]

    @property
    def context_and_statement(self) -> str:
        return self.context + self.statement

    @property
    def sorry_statement(self) -> str:
        return self.statement + "  sorry\n"

    @property
    def name(self) -> str:
        return self.statement.split(" ")[1]

    @property
    def import_str(self) -> str:
        sentence = ""
        for line in self.code.split("\n"):
            if line.startswith("import"):
                sentence += line + "\n"
            else:
                break
        return sentence.strip()

    @classmethod
    def new(cls, code: str, generate_err: str | None = None):
        return cls(
            code=code,
            generate_err=generate_err,
            id=uuid.uuid4(),
            created_at=datetime.now(),
        )

    def update_code(self, code: str):
        validated_code = self.__class__._validate_code(code)
        self.code = validated_code
