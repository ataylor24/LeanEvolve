import uuid
from datetime import datetime

from pydantic import BaseModel

from src.application.lean_processor import LeanProcessorResponse
from src.entity.conjecture import Conjecture


class ConjectureEvalResult(BaseModel):
    """
    ConjectureEvalResult is a dataclass
    that represents the result of evaluating a conjecture.

    Attributes:
        conjecture (Conjecture): The conjecture that was evaluated.
        is_valid (bool): Indicates whether the conjecture is valid.
        already_exists (bool): Indicates whether the conjecture already exists.
        aesop_provable (bool): Indicates whether the conjecture is provable by Aesop.
        error (LeanProcessorResponse | str | None):
        The error response from the Lean processor, if any.
        proof (str | None): The proof of the conjecture, if available.
        id (uuid.UUID): Unique identifier for the result.
        created_at (datetime): Timestamp when the result was created.
    """

    conjecture: Conjecture
    passed: bool
    already_exists: bool
    aesop_provable: bool
    error: LeanProcessorResponse | str | None
    goal: str | None
    proof: str | None
    id: uuid.UUID
    created_at: datetime
    context_name: str
    iter_num: int

    @property
    def is_valid(self) -> bool:
        """Check if the conjecture is valid."""
        return self.conjecture.generation_successful and self.error is None

    @classmethod
    def new(
        cls,
        conjecture: Conjecture,
        passed: bool,
        already_exists: bool,
        aesop_provable: bool,
        error: LeanProcessorResponse | None,
        goal: str | None,
        proof: str | None,
        context_name: str,
        iter_num: int,
    ):
        """Create a new instance of ConjectureEvalResult."""
        return cls(
            conjecture=conjecture,
            passed=passed,
            already_exists=already_exists,
            aesop_provable=aesop_provable,
            error=error,
            goal=goal,
            proof=proof,
            id=uuid.uuid4(),
            created_at=datetime.now(), 
            context_name=context_name,
            iter_num=iter_num,
        )
