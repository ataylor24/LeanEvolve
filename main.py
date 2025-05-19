from pathlib import Path


def main(
    model_name: str,
    api_key: str,
    target_file_path: Path,
) -> None:
    from src.application.pipeline import ConjecturerPipeline
    from src.entity.mathlib import MathlibFile

    # ファイルを読み込む
    with target_file_path.open("r") as f:
        lines = f.readlines()
    files: list[MathlibFile] = []
    for line in lines:
        file_path = line.strip()
        if not file_path:
            continue
        file = MathlibFile(file_path)
        files.append(file)

    # パイプラインを実行する
    ConjecturerPipeline.run(model_name, api_key, files)


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
        "--target_file_path",
        type=str,
        default="target_files.txt",
        help="The path to the target file.",
    )

    args = parser.parse_args()
    main(args.model_name, args.api_key, Path(args.target_file_path))
