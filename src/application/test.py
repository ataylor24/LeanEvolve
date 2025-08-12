import json
from typing import List
from src.application.generator.converter import ConjectureConverter
from src.application.generator.head_maker import ConjectureHeadMaker
from src.entity.conjecture import Conjecture
from src.entity.conjecture_eval_result import ConjectureEvalResult

def generate_test_statements(
    context: str,
    conjecture_eval_results: List[ConjectureEvalResult],
    num_cases: int = 10,
) -> List[Conjecture]:
    """Generate a list of ``Conjecture`` objects for testing.

    This helper is used in testing mode of the pipeline.  The converter returns a
    *list* of ``Conjecture`` objects (usually of length 1) so we flatten these
    into a single list before returning.  Down-stream evaluators expect a flat
    ``List[Conjecture]`` and will access the ``.code`` attribute, therefore we
    must not keep any nested list structure here.
    """
    converter = ConjectureConverter()
    head_maker = ConjectureHeadMaker()
    path = "/home/ataylor2/mathematical_reasoning/sketch-mutations/LeanConjecturer/test_data/conjectures.jsonl"
    head = head_maker.make(context, conjecture_eval_results)
    test_statements: list[Conjecture] = []
    with open(path, "r") as f:
        for i, line in enumerate(f):
            data = json.loads(line)
            # ``converter.convert`` returns ``list[Conjecture]`` — usually a
            # singleton list.  Use ``extend`` so that ``test_statements`` is a
            # flat list of ``Conjecture`` objects.
            test_statements.extend(
                converter.convert(head, data["conjecture"])
            )
            if i >= num_cases:
                break
    return test_statements

if __name__ == "__main__":
    test_statements = generate_test_statements(num_cases=10)
    print(test_statements)