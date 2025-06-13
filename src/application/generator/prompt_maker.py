from src.entity.prompt import Prompt


class PromptMaker:
    def make(self, context: str) -> Prompt:
        system_prompt = (
            "Please generate new theorems in Lean 4 format that are similar "
            "but not identical to each theorem provided in the text "
            "as many as possible. "
            "For each theorem in the text, generate a corresponding new theorem "
            "with slight variations in content. "
            "Do not include proofs, annotations, or imports. "
            "The new theorems begin with '```lean theorem', not any annotions. "
            "They should end with ':= by```'. "
            "Additionally, please use standard mathematical symbols "
            "(e.g., ∀, ∃, √) "
            "instead of Unicode escape sequences (e.g., \u2200).\n"
        )
        user_prompt = "## Original file:\n"
        user_prompt += f"```lean\n{context[-400000:]}\n```\n"
        return Prompt(system_prompt, user_prompt)
