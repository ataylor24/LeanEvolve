# prover.py
import torch
from transformers import AutoTokenizer
from vllm import LLM, SamplingParams
from typing import List, Sequence
from src.application.generator.generator import Conjecture

class Prover:
    def __init__(
        self,
        model_id: str,
        tensor_parallel_size: int = 2,
        max_tokens: int = 8192,
        num_return_sequences: int = 32,   # ← pick your default k
        gpu_memory_utilization: float = 0.75,
        temperature: float = 1.0,
        max_num_seqs: int | None = None,  # vLLM in-flight concurrency; None = auto
    ):
        self.tokenizer = AutoTokenizer.from_pretrained(model_id, use_fast=True)

        self.llm = LLM(
            model=model_id,
            device="cuda",
            dtype="float16",
            tensor_parallel_size=tensor_parallel_size,
            max_model_len=max_tokens,
            # NOTE: max_num_seqs controls in-flight concurrency, not "n".
            # If you know your batch size and k, you can set > batch_size*k
            # to avoid throttling; otherwise leave None.
            max_num_seqs=max_num_seqs,
            gpu_memory_utilization=gpu_memory_utilization,
        )
        self.max_tokens = max_tokens
        self.num_return_sequences = num_return_sequences
        self.temperature = temperature

    def _format_prompt(self, conjecture: Conjecture) -> str:
        # Keep the instruction minimal & deterministic. The model should output *only* the proof tail.
        # The caller will concatenate `statement` and this returned proof in verification.
        # return (
        #     "Complete the Lean 4 theorem by providing a *valid proof tail* that begins with `by`.\n\n"
        #     "Return only the proof (starting with `by`), no extra prose or code fences.\n\n"
        #     f"{conjecture.code}\n"
        # )
        prompt = """
        Complete the following Lean 4 code:

        ```lean4
        {}
        ```
        """.strip()
        return prompt.format(conjecture.code)

    def _to_chat_string(self, user_msg: str) -> str:
        # Build a chat-formatted string prompt. vLLM will accept raw strings.
        chat = [{"role": "user", "content": user_msg}]
        inputs = self.tokenizer.apply_chat_template(
            chat, tokenize=False, add_generation_prompt=False
        )
        inputs = inputs.replace(self.tokenizer.eos_token, "")
        return inputs

    @torch.inference_mode()
    def generate_k(
        self,
        conjectures: Sequence[Conjecture],
        k: int | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> List[List[str]]:
        """
        Returns: proofs_per_conjecture: List[List[str]]
                 proofs_per_conjecture[i] has length k and contains k proof tails for statements[i]
        """
        if k is None:
            k = self.num_return_sequences
        if temperature is None:
            temperature = self.temperature
        if max_tokens is None:
            max_tokens = self.max_tokens

        # Build prompts in one pass
        prompts = [self._to_chat_string(self._format_prompt(s)) for s in conjectures]

        # vLLM batched generation
        sampling = SamplingParams(
            max_tokens=max_tokens,
            temperature=temperature,
            n=k,
        )
        request_outputs = self.llm.generate(prompts, sampling_params=sampling)

        # Collect aligned outputs: request_outputs[i].outputs is list length k
        proofs_per_conjecture: List[List[str]] = []
        for ro in request_outputs:
            kth = [o.text.strip() for o in ro.outputs]  # preserve order 0..k-1
            proofs_per_conjecture.append(kth)
        return proofs_per_conjecture

    # Back-compat: single-statement path
    def prove_theorem(self, statement: str, k: int | None = None) -> List[str]:
        return self.generate_k([statement], k=k or self.num_return_sequences)[0]
