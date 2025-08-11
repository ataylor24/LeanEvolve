from typing import cast

from openai import OpenAI
from openai.types.chat import (
    ChatCompletionSystemMessageParam,
    ChatCompletionUserMessageParam,
)
from pydantic import BaseModel

from src.entity.prompt import Prompt
from typing_extensions import Literal
from pydantic import BaseModel, Field, conint, confloat

MessageParam = ChatCompletionSystemMessageParam | ChatCompletionUserMessageParam


class ConjectureGPT:
    def __init__(self, model_name: str, api_key: str) -> None:
        self.model_name = model_name
        self.client = OpenAI(api_key=api_key)

    def ask(self, prompt: Prompt):
        """Send *prompt* and return structured JSON ({"operator": {…}, "conjectures": [...]})

        We rely on OpenAI structured JSON mode.  The schema expected from the
        LLM is:

        {
          "operator": {"name": "<operator id>", "description": "<optional>"},
          "conjectures": ["<Lean stmt 1>", "<Lean stmt 2>", …]
        }
        """

        class Operator(BaseModel):
            name: str
            description: str | None = None

        class Conjectures(BaseModel):
            operator: Operator
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
            reasoning_effort="medium",
        )
        parsed: Conjectures | None = completion.choices[0].message.parsed
        return parsed.model_dump() if parsed else {}
    
    def ask_fitness_check(self, prompt: Prompt):
        """
        Send *prompt* and return structured JSON with per-conjecture scores.

        Expected schema:
        {
        "mode": "parent" | "context",
        "judged_conjectures": [
            {
            "scores": {
                "novelty": 0-100,
                "provability_estimate": 0-100,
                "difficulty": 0-100
            },
            "flags": {
                "trivial_pattern": bool,
                "restatement": bool,
                "ill_typed": bool
            },
            "justification": "≤25 words…"
            }
        ]
        }
        """

        Score = conint(ge=0, le=100)

        class Scores(BaseModel):
            novelty: Score
            provability_estimate: Score
            difficulty: Score

        class Flags(BaseModel):
            trivial_pattern: bool
            restatement: bool
            ill_typed: bool

        class JudgedItem(BaseModel):
            scores: Scores
            flags: Flags
            justification: str = Field(max_length=180)

        class JudgeResponse(BaseModel):
            mode: Literal["parent", "context"]
            judged_conjectures: list[JudgedItem]
            


        messages: list[MessageParam] = []
        if prompt.system_prompt:
            messages.append(
                cast(ChatCompletionSystemMessageParam, {"role": "system", "content": prompt.system_prompt})
            )
        if prompt.user_prompt:
            messages.append(
                cast(ChatCompletionUserMessageParam, {"role": "user", "content": prompt.user_prompt})
            )

        completion = self.client.beta.chat.completions.parse(
            model=self.model_name,
            messages=messages,
            response_format=JudgeResponse,
            reasoning_effort="medium",
        )

        parsed: JudgeResponse | None = completion.choices[0].message.parsed
        return parsed.model_dump() if parsed else {}

