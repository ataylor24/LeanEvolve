from src.application.generator.converter import ConjectureConverter
from src.application.generator.head_maker import ConjectureHeadMaker
from src.application.generator.llm import ConjectureGPT
from src.application.generator.prompt_maker import PromptMaker
from src.entity.conjecture import Conjecture
from src.entity.conjecture_eval_result import ConjectureEvalResult


class ConjectureGenerator:
    def __init__(
        self,
        model_name: str,
        api_key: str,
        rename: bool = False,
    ) -> None:
        self.llm = ConjectureGPT(model_name, api_key)
        self.prompt_maker = PromptMaker()
        self.head_maker = ConjectureHeadMaker()
        self.converter = ConjectureConverter(rename=rename)

    def generate(self, context: str, eval_results: list[ConjectureEvalResult] = []) -> list[Conjecture]:
        prompt = self.prompt_maker.make(context)
        head = self.head_maker.make(context, eval_results)
        completions = self.llm.ask(prompt)
        conjectures: list[Conjecture] = []
        for completion in completions:
            conjectures.extend(self.converter.convert(head, completion))

        return conjectures
