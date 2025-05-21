import json


def pretty_print_jsonl(filename: str) -> None:
    with open(filename, encoding="utf-8") as f:
        for line in f:
            try:
                item = json.loads(line)
                if (
                    item["already_exists"] is False
                    and item["aesop_provable"] is False
                    and item["error"] is None
                ):
                    code = item["conjecture"]["code"].strip()
                    goal = item["goal"].strip()

                    print("-" * 80)
                    print("Code:")
                    print(code)
                    print("\nGoal:")
                    print(goal)
                    print("-" * 80)
                    print()
            except json.JSONDecodeError as e:
                print(f"Error decoding JSON: {e}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Pretty Print JSONL")
    parser.add_argument(
        "--filename",
        type=str,
        default="data/conjecture_eval_result.jsonl",
        help="The path to the JSONL file.",
    )
    args = parser.parse_args()
    pretty_print_jsonl(args.filename)
