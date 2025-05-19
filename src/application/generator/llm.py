from typing import cast

from openai import OpenAI
from openai.types.chat import (
    ChatCompletionSystemMessageParam,
    ChatCompletionUserMessageParam,
)
from pydantic import BaseModel

from src.entity.prompt import Prompt

MessageParam = ChatCompletionSystemMessageParam | ChatCompletionUserMessageParam


class ConjectureGPT:
    def __init__(self, model_name: str, api_key: str) -> None:
        self.model_name = model_name
        self.client = OpenAI(api_key=api_key)

    def ask(self, prompt: Prompt) -> list[str]:
        class Conjectures(BaseModel):
            conjectures: list[str]

        messages: list[MessageParam] = []
        if prompt.system_prompt:
            messages.append(
                cast(
                    ChatCompletionSystemMessageParam,
                    {"role": "system", "content": prompt.system_prompt},
                )
            )
        if prompt.user_prompt:
            messages.append(
                cast(
                    ChatCompletionUserMessageParam,
                    {"role": "user", "content": prompt.user_prompt},
                )
            )

        completion = self.client.beta.chat.completions.parse(
            model=self.model_name,
            messages=messages,
            response_format=Conjectures,
        )
        conjectures: Conjectures | None = completion.choices[0].message.parsed
        return conjectures.conjectures if conjectures else []
