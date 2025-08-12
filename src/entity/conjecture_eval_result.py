import uuid
from datetime import datetime
from typing import List

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
    passed_triviality_checks: bool
    non_trivial_provable: bool
    non_trivial_neg_provable: bool
    exact_provable: bool
    aesop_provable: bool
    error: LeanProcessorResponse | str | None
    verified_proofs: List[str] | None | str
    unverified_proofs: List[str] | None | str
    neg_verified_proofs: List[str] | None | str
    neg_unverified_proofs: List[str] | None | str
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
        passed_triviality_checks: bool,
        non_trivial_provable: bool,
        non_trivial_neg_provable: bool,
        exact_provable: bool,
        aesop_provable: bool,
        error: LeanProcessorResponse | None,
        verified_proofs: List[str] | str | None,
        unverified_proofs: List[str] | str | None,
        neg_verified_proofs: List[str] | str | None,
        neg_unverified_proofs: List[str] | str | None,
        context_name: str,
        iter_num: int,
    ):
        """Create a new instance of ConjectureEvalResult."""
        return cls(
            conjecture=conjecture,
            passed_triviality_checks=passed_triviality_checks,
            non_trivial_provable=non_trivial_provable,
            non_trivial_neg_provable=non_trivial_neg_provable,
            exact_provable=exact_provable,
            aesop_provable=aesop_provable,
            error=error,
            verified_proofs=verified_proofs,
            unverified_proofs=unverified_proofs,
            neg_verified_proofs=neg_verified_proofs,
            neg_unverified_proofs=neg_unverified_proofs,
            id=uuid.uuid4(),
            created_at=datetime.now(), 
            context_name=context_name,
            iter_num=iter_num,
        )
