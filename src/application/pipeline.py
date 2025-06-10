from src.application.evaluator import (
    ConjectureEvalResultRepository,
    ConjectureEvaluator,
)
from src.application.generator import ConjectureGenerator, ConjectureRepository
from src.application.generator.context_maker import ContextMaker
from src.application.lean_processor import LeanProcessor
from src.entity.conjecture_eval_result import ConjectureEvalResult


class ConjecturerPipeline:
    @staticmethod
    def run(
        model_name: str,
        api_key: str,
        contexts: list[str],
        max_iter: int = 1,
    ) -> None:
        generator = ConjectureGenerator(model_name, api_key)
        evaluator = ConjectureEvaluator()
        repository = ConjectureRepository()
        eval_repository = ConjectureEvalResultRepository()
        conjecture_eval_results: list[ConjectureEvalResult] = []

        for context in contexts:
            for _ in range(max_iter):
                print("Generating conjectures...")
                conjectures = generator.generate(context, conjecture_eval_results)
                print(f"Generated {len(conjectures)} conjectures")

                print("Saving conjectures...")
                repository.save(conjectures)
                print(f"Saved {len(conjectures)} conjectures to repository")

                print("Evaluating conjectures...")
                processors = [LeanProcessor(i) for i in range(len(conjectures))]
                results = evaluator.evaluate(processors, conjectures)
                print(f"Evaluated {len(results)} conjectures")

                print("Saving evaluation results...")
                eval_repository.save(results)
                print(f"Saved {len(results)} evaluation results to repository")

                print("Updating context...")
                conjecture_eval_results.extend(results)
                context, updated = ContextMaker.make(context, conjecture_eval_results)
                if not updated:
                    print("No new conjectures found")
                    break
                print("Updated context:\n...\n", context[-300:])
