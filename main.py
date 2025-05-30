from pathlib import Path


def main(
    model_name: str,
    api_key: str,
    target_file_path: Path,
    max_iter: int,
) -> None:
    from src.application.pipeline import ConjecturerPipeline
    from src.entity.mathlib import MathlibFile

    with target_file_path.open("r") as f:
        lines = f.readlines()
    contexts: list[str] = []
    for line in lines:
        file_path = line.strip()
        if not file_path:
            continue
        file = MathlibFile(file_path)
        contexts.append(file.content)

    ConjecturerPipeline.run(model_name, api_key, contexts, max_iter)


if __name__ == "__main__":
    import argparse
    import os

    from dotenv import load_dotenv

    load_dotenv()

    parser = argparse.ArgumentParser(description="Conjecturer CLI")
    parser.add_argument(
        "--model_name",
        type=str,
        default="o3-mini",
        help="The name of the model to use for generation.",
    )
    parser.add_argument(
        "--api_key",
        type=str,
        default=os.getenv("OPENAI_API_KEY"),
        help="The API key for the model.",
    )
    parser.add_argument(
        "--target",
        type=str,
        default="data/inter_closure_exercise.lean",
        help="The path to the target file.",
    )
    parser.add_argument(
        "--max_iter",
        type=int,
        default=10,
        help="The number of iterations to run.",
    )

    args = parser.parse_args()
    main(args.model_name, args.api_key, Path(args.target), args.max_iter)
