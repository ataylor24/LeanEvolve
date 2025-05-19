from dataclasses import dataclass


@dataclass
class Prompt:
    system_prompt: str | None = None
    user_prompt: str | None = None
