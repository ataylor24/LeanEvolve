from typing import Any

from loguru import logger
from pydantic import BaseModel


class Pos(BaseModel):
    line: int
    column: int

    @classmethod
    def from_dict(cls, data: dict) -> "Pos":
        return cls(line=data["line"], column=data["column"])


class Message(BaseModel):
    severity: str
    pos: Pos
    data: str
    end_pos: Pos | None

    @classmethod
    def from_dict(cls, d: dict) -> "Message":
        return cls(
            severity=d["severity"],
            pos=Pos.from_dict(d["pos"]),
            data=d["data"],
            end_pos=Pos.from_dict(d["end_pos"]) if d.get("end_pos") else None,
        )


class Tactic(BaseModel):
    used_constants: list[str]
    tactic: str
    proof_state: int
    pos: Pos
    goals: str
    end_pos: Pos | None

    @classmethod
    def from_dict(cls, d: dict) -> "Tactic":
        return cls(
            used_constants=d["used_constants"],
            tactic=d["tactic"],
            proof_state=d["proof_state"],
            pos=Pos.from_dict(d["pos"]),
            goals=d["goals"],
            end_pos=Pos.from_dict(d["end_pos"]) if d.get("end_pos") else None,
        )


class Sorry(BaseModel):
    proof_state: int
    pos: Pos
    goal: str
    end_pos: Pos | None

    @classmethod
    def from_dict(cls, d: dict) -> "Sorry":
        return cls(
            proof_state=d["proof_state"],
            pos=Pos.from_dict(d["pos"]),
            goal=d["goal"],
            end_pos=Pos.from_dict(d["end_pos"]) if d.get("end_pos") else None,
        )


class LeanProcessorResponse(BaseModel):
    messages: list[Message]
    tactics: list[Tactic]
    sorries: list[Sorry]

    @classmethod
    def from_dict(cls, result: dict[str, Any]) -> "LeanProcessorResponse":
        messages, tactics, sorries = [], [], []
        for key, lst in result.items():
            logger.debug(f"{key}: {lst}")
            if key not in ["messages", "tactics", "sorries", "env"]:
                logger.warning(f"Unknown key in LeanProcessorResponse: {key}")
            if key == "messages":
                messages = [Message.from_dict(messages) for messages in lst]
            elif key == "tactics":
                tactics = [Tactic.from_dict(tactic) for tactic in lst]
            elif key == "sorries":
                sorries = [Sorry.from_dict(sorry) for sorry in lst]
        return cls(messages=messages, tactics=tactics, sorries=sorries)
