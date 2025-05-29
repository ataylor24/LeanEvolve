from src.entity.conjecture import Conjecture


class ContextMaker:
    @staticmethod
    def make(conjectures: list[Conjecture]) -> str:
        context = conjectures[0].context
        context += "\n\n".join([conjecture.statement for conjecture in conjectures if conjecture.generation_successful])
        return context
