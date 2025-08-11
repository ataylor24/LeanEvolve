from pathlib import Path


def main(
    conjecturer_model_name: str,
    api_key: str,
    target_file_path: Path,
    max_iter: int,
    testing: bool,
    fitness_prover_model: str,
    fitness_llm_model: str,
) -> None:
    from src.application.pipeline import ConjecturerPipeline
    from src.entity.mathlib import MathlibFile

    with target_file_path.open("r") as f:
        mathlibs = [line.strip() for line in f.readlines()]
        contexts = [(MathlibFile(mathlib).content, mathlib) for mathlib in mathlibs]

    ConjecturerPipeline.run(conjecturer_model_name, api_key, contexts, max_iter, testing, fitness_prover_model, fitness_llm_model)

if __name__ == "__main__":
    import argparse
    import os

    from dotenv import load_dotenv

    load_dotenv()

    parser = argparse.ArgumentParser(description="Conjecturer CLI")
    parser.add_argument(
        "--conjecturer_model_name",
        type=str,
        default="o3",
        help="The name of the model to use for generation.",
    )
    parser.add_argument(
        "--api_key",
        type=str,
        default=os.getenv("OPENAI_API_KEY"),
        help="The API key for the model.",
    )
    parser.add_argument(
        "--fitness_prover_model",
        type=str,
        default="deepseek-ai/DeepSeek-Prover-V2-7B",
        help="Model name for the theorem prover used in fitness evaluation.",
    )
    parser.add_argument(
        "--fitness_llm_model",
        type=str,
        default="o4-mini",
        help="Model name for the LLM used to judge novelty, relevance and usefulness.",
    )
    parser.add_argument(
        "--target",
        type=str,
        default="./target_files_test.txt",
        help="The path to the target file.",
    )
    parser.add_argument(
        "--max_iter",
        type=int,
        default=5,
        help="The number of iterations to run.",
    )
    parser.add_argument(
        "--testing",
        action="store_true",
        help="Whether to run in testing mode.",
    )

    args = parser.parse_args()
    main(args.conjecturer_model_name, args.api_key, Path(args.target), args.max_iter, args.testing, args.fitness_prover_model, args.fitness_llm_model)
