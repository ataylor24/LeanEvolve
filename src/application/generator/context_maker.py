from src.entity.conjecture_eval_result import ConjectureEvalResult


class ContextMaker:
    @staticmethod
    def make(
        context: str, eval_results: list[ConjectureEvalResult], iter_num: int
    ) -> tuple[str, bool]:
        """update context with new conjectures.
        return: (updated context, whether new conjectures are found)
        """
        nontrivial_conjecture_statements = [
            eval_result.conjecture.proof
            for eval_result in eval_results
            if eval_result.passed and not (eval_result.exact_provable or eval_result.aesop_provable)
        ]
        context += f"\n\n/-ITERATION {iter_num}-/\n\n"
        context += "\n\n".join(nontrivial_conjecture_statements)
        return context, len(nontrivial_conjecture_statements) > 0
