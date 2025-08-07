from src.entity.conjecture_eval_result import ConjectureEvalResult


class ContextMaker:
    @staticmethod
    def make(
        context: str, eval_results: list[ConjectureEvalResult]
    ) -> tuple[str, bool]:
        """update context with new conjectures.
        return: (updated context, whether new conjectures are found)
        """
        nontrivial_conjecture_statements = [
            eval_result.conjecture.sorry_statement
            for eval_result in eval_results
            if eval_result.passed and not eval_result.already_exists
        ]
        context += "\n\n".join(nontrivial_conjecture_statements)
        return context, len(nontrivial_conjecture_statements) > 0
