from dataclasses import dataclass

from loguru import logger

from src.application.lean_processor import LeanProcessor, LeanProcessorResponse
from src.entity.conjecture import Conjecture
from src.entity.conjecture_eval_result import ConjectureEvalResult


@dataclass
class ConjectureEvaluator:
    try_remove_contexts: bool = False

    def _eval_unit(
        self, lean: LeanProcessor, conjecture: Conjecture
    ) -> ConjectureEvalResult:
        if not conjecture.generation_successful:
            return ConjectureEvalResult.new(
                conjecture=conjecture,
                already_exists=False,
                aesop_provable=False,
                error=None,
                goal=None,
                proof=None,
            )
        if self.try_remove_contexts:
            conjecture = self._try_remove_contexts(lean, conjecture)

        goal, error = self._get_goal(lean, conjecture)
        if error:
            return ConjectureEvalResult.new(
                conjecture=conjecture,
                already_exists=False,
                aesop_provable=False,
                error=error,
                goal=None,
                proof=None,
            )

        exact_proof = self._check_by_exact(lean, conjecture)
        if exact_proof:
            return ConjectureEvalResult.new(
                conjecture=conjecture,
                already_exists=True,
                aesop_provable=False,
                error=None,
                goal=goal,
                proof=exact_proof,
            )

        aesop_proof = self._check_by_aesop(lean, conjecture)
        if aesop_proof:
            return ConjectureEvalResult.new(
                conjecture=conjecture,
                already_exists=False,
                aesop_provable=True,
                error=None,
                goal=goal,
                proof=aesop_proof,
            )

        return ConjectureEvalResult.new(
            conjecture=conjecture,
            already_exists=False,
            aesop_provable=False,
            error=None,
            goal=goal,
            proof=None,
        )

    def evaluate(
        self, leans: list[LeanProcessor], conjectures: list[Conjecture]
    ) -> list[ConjectureEvalResult]:
        return [
            self._eval_unit(lean, conjecture)
            for lean, conjecture in zip(leans, conjectures, strict=False)
        ]

    @staticmethod
    def _try_remove_contexts(lean: LeanProcessor, conjecture: Conjecture) -> Conjecture:
        print_code = (
            conjecture.code.split(":=")[0]
            + ":= by sorry\n\n#print "
            + conjecture.name
            + "\n"
        )
        response = lean.exec(print_code)
        for message in response.messages:
            if message.severity == "info" and message.data.startswith("theorem "):
                statement = message.data.split(":=")[0] + ":= by\n"
                if "sorry" not in statement and not response.sorries:
                    return Conjecture.new(
                        code=conjecture.import_str + "\n\n" + statement
                    )

        return conjecture

    @staticmethod
    def _get_goal(
        lean: LeanProcessor, conjecture: Conjecture
    ) -> tuple[str | None, LeanProcessorResponse | None]:
        """
        Get the goal of the conjecture.
        If the goal is not found, return None and the error response.
        If the goal is found, return the goal and None.
        """
        sorry_code = conjecture.context_and_statement.split(":=")[0] + ":= by sorry\n"
        response = lean.exec(sorry_code)
        for message in response.messages:
            if (
                message.severity == "warning"
                and message.data == "declaration uses 'sorry'"
            ):
                return response.sorries[0].goal, None

        return None, response

    @staticmethod
    def _check_by_exact(lean: LeanProcessor, conjecture: Conjecture) -> str | None:
        """
        If a proof of the conjecture can be found by "exact?", return the proof.
        Else return None.
        Novelty means a proof of the conjecture cannot be found by "exact?".
        """
        exact_code = conjecture.code + "  exact?\n"
        response = lean.exec(exact_code)
        for message in response.messages:
            if message.severity == "info" and message.data.startswith("Try this:"):
                logger.info("The conjecture can be proved by exact!")
                return message.data.split("Try this:")[1].strip()

        logger.info("The conjecture cannot be proved by exact.")
        return None

    @staticmethod
    def _check_by_aesop(lean: LeanProcessor, conjecture: Conjecture) -> str | None:
        """
        If a proof of the conjecture can be found by "aesop?", return the proof.
        Else return None.
        """
        aesop_code = conjecture.code + "  aesop?\n"
        response = lean.exec(aesop_code)
        for message in response.messages:
            if (
                message.severity == "info"
                and message.data.startswith("Try this:")
                and "sorry" not in message.data
            ):
                logger.info("The conjecture can be proved by aesop!")
                return message.data.split("Try this:")[1].strip()

        logger.info("The conjecture cannot be proved by aesop.")
        return None
