from src.entity.conjecture_eval_result import ConjectureEvalResult


class ConjectureHeadMaker:
    def make(self, content: str, eval_results: list[ConjectureEvalResult]) -> str:
        context_set = set()
        context_list = []
        namespace_set = set()
        for line in content.split("\n"):
            if line.startswith("variable"):
                if line not in context_set:
                    context_list.append(line)
                    context_set.add(line)
            elif line.startswith("open"):
                namespaces = line.split(" ")[1:]
                for namespace in namespaces:
                    namespace_set.add(namespace)
        namespace_str = "open " + " ".join(namespace_set) if namespace_set else ""
        context_str = "\n".join(context_list)
        return (
            "\n\n".join(["import Mathlib\nimport Aesop", context_str, namespace_str])
            + "\n"
            + "\n".join(
                [
                    eval_result.conjecture.sorry_statement
                    for eval_result in eval_results
                    if not eval_result.already_exists and eval_result.error is None
                ]
            )
        )
