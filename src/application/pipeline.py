from src.application.evaluator import (
    ConjectureEvalResultRepository,
    ConjectureEvaluator,
)
from src.application.generator import ConjectureGenerator, ConjectureRepository
from src.application.lean_processor import LeanProcessor
from src.entity.mathlib import MathlibFile


class ConjecturerPipeline:
    @staticmethod
    def run(
        model_name: str,
        api_key: str,
        files: list[MathlibFile],
    ) -> None:
        generator = ConjectureGenerator(model_name, api_key)
        evaluator = ConjectureEvaluator()
        repository = ConjectureRepository()
        eval_repository = ConjectureEvalResultRepository()

        for file in files:
            print(f"Generating conjectures for {file.file_path}...")
            conjectures = generator.generate(file)
            print(f"Generated {len(conjectures)} conjectures for {file.file_path}")

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
