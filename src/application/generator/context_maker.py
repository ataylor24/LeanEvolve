from src.entity.conjecture_eval_result import ConjectureEvalResult


class ContextMaker:
    @staticmethod
    def make(context: str, eval_results: list[ConjectureEvalResult]) -> str:
        nontrivial_conjecture_statements = [
            eval_result.conjecture.statement
            for eval_result in eval_results
            if not eval_result.already_exists and eval_result.error is None
        ]
        context += "\n\n".join(nontrivial_conjecture_statements)
        return context, len(nontrivial_conjecture_statements) > 0
