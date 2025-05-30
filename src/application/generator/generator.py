from src.application.generator.context_maker import ContextMaker
from src.application.generator.converter import ConjectureConverter
from src.application.generator.head_maker import ConjectureHeadMaker
from src.application.generator.llm import ConjectureGPT
from src.application.generator.prompt_maker import PromptMaker
from src.entity.conjecture import Conjecture
from src.entity.mathlib import MathlibFile


class ConjectureGenerator:
    def __init__(
        self,
        model_name: str,
        api_key: str,
    ) -> None:
        self.llm = ConjectureGPT(model_name, api_key)
        self.prompt_maker = PromptMaker()
        self.head_maker = ConjectureHeadMaker()
        self.converter = ConjectureConverter(rename=True)

    def generate(self, content: str) -> list[Conjecture]:
        prompt = self.prompt_maker.make(content)
        head = self.head_maker.make(content)
        completions = self.llm.ask(prompt)
        conjectures: list[Conjecture] = []
        for completion in completions:
            conjectures.extend(self.converter.convert(head, completion))

        return conjectures
