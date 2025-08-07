from dataclasses import dataclass

from loguru import logger

from src.application.lean_processor import LeanProcessor, LeanProcessorResponse
from src.entity.conjecture import Conjecture
from src.entity.conjecture_eval_result import ConjectureEvalResult
from src.application.evaluator.KiminaPool import KiminaPool

@dataclass
class ConjectureEvaluator:
    try_remove_contexts: bool = False

    def __init__(self, kimina_proc: KiminaPool):
        self.kimina_proc = kimina_proc

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
                context_name="",
                iter_num=iter_num,
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
                context_name="",
                iter_num=-1,
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
                context_name="",
                iter_num=-1,
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
                context_name="",
                iter_num=-1,
            )

        return ConjectureEvalResult.new(
            conjecture=conjecture,
            already_exists=False,
            aesop_provable=False,
            error=None,
            goal=goal,
            proof=None,
            context_name="",
            iter_num=-1,
        )
    
    
    def evaluate(
        self,
        conjectures: list[Conjecture],
        context_name: str,
        iter_num: int,
    ) -> list[ConjectureEvalResult]:

        # -------------------- Stage 1: compilation only --------------------
        lean_snips = [cj.code for cj in conjectures]
        compile_res = self.kimina_proc.compile_only(lean_snips)

        stage1_pass = [
            idx for idx, r in enumerate(compile_res)
            if r["error"] is None and all(
                m["severity"] != "error" for m in r["response"]["messages"]
            )
        ]
        # keep track of indices that pass stage 2 ("exact?") so we can
        # attempt the final `aesop?` proof search.  Start with an empty list
        # and append to it as we identify conjectures that were not solved by
        # `exact?`.
        stage2_pass: list[int] = []

        # initialise results with failures
        results = [
            ConjectureEvalResult.new(
                conjecture=cj,
                passed=False,
                already_exists=False,
                aesop_provable=False,
                error="compile_failed" if i not in stage1_pass else None,
                goal=None,
                proof=None,
                context_name=context_name,
                iter_num=iter_num,
            )
            for i, cj in enumerate(conjectures)
        ]

        # -------------------- Stage 2: exact? ------------------------------
        if stage1_pass:
            exact_req  = [lean_snips[i] for i in stage1_pass]
            exact_res  = self.kimina_proc.exact_suggestion(exact_req)
            for local_idx, resp in enumerate(exact_res):
                global_idx = stage1_pass[local_idx]
                found = any(
                    m["severity"] == "info" and m["data"].startswith("Try this:")
                    for m in resp["response"]["messages"]
                )
                if found:
                    results[global_idx] = ConjectureEvalResult.new(
                        conjecture=conjectures[global_idx],
                        passed=False,
                        already_exists=True,
                        aesop_provable=False,
                        error=None,
                        goal=None,           # goal extraction can be added
                        proof="exact?",
                        context_name=context_name,
                        iter_num=iter_num,
                    )
                else:
                    stage2_pass.append(global_idx)
  
        # -------------------- Stage 3: aesop? ------------------------------
        if stage2_pass:
            aesop_req = [lean_snips[i] for i in stage2_pass]
            aesop_res = self.kimina_proc.aesop_suggestion(aesop_req)
            for local_idx, resp in enumerate(aesop_res):
                global_idx = stage2_pass[local_idx]
                proved = any(
                    m["severity"] == "info"
                    and m["data"].startswith("Try this:")
                    and "sorry" not in m["data"]
                    for m in resp["response"]["messages"]
                )
                results[global_idx] = ConjectureEvalResult.new(
                    conjecture=conjectures[global_idx],
                    passed=False if proved else True,
                    already_exists=False,
                    aesop_provable=proved,
                    error=None if proved else "aesop_failed",
                    goal=None,
                    proof="aesop?" if proved else None,
                    context_name=context_name,
                    iter_num=iter_num,
                )
   
        return results

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
