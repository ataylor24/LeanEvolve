from src.entity.mathlib import MathlibFile


class ConjectureHeadMaker:
    def make(self, file: MathlibFile) -> str:
        context_set = set()
        context_list = []
        namespace_set = set()
        for line in file.content.split("\n"):
            if line.startswith("variable"):
                if line not in context_set:
                    context_list.append(line)
                    context_set.add(line)
            elif line.startswith("namespace"):
                namespaces = line.split(" ")[1:]
                for namespace in namespaces:
                    namespace_set.add(namespace)
        namespace_str = "open " + " ".join(namespace_set) if namespace_set else ""
        context_str = "\n".join(context_list)
        return (
            "\n\n".join(["import Mathlib\nimport Aesop", context_str, namespace_str])
            + "\n"
        )
