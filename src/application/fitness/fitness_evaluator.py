from src.application.fitness.prover import Prover
from src.application.generator.generator import Conjecture
from src.application.generator.converter import ConjectureConverter
from src.application.evaluator.KiminaPool import KiminaPool
from src.application.fitness.llm_fitness_evaluator import LLMFitnessEvaluator
from textwrap import dedent
from typing import List, Tuple, Set, Dict, Any
from kimina_client.models import Snippet
import math
import json

class FitnessEvaluator:
    def __init__(self, prover_model_name: str, llm_model_name: str, llm_api_key: str, kimina_proc: KiminaPool):
        self.prover = Prover(prover_model_name)
        self.llm = LLMFitnessEvaluator(llm_model_name, llm_api_key)
        self.kimina_proc = kimina_proc
        self.converter = ConjectureConverter()
        
    def _evaluate_proofs_passk(
        self,
        conjectures: List[Conjecture],                # theorem headers / full declarations
        proofs_per_conj: List[List[str]],     # k proof tails per statement[i]
        *,
        accept_sorry: bool = False,
    ) -> Tuple[Set[int], Set[int], Dict[int, int]]:
        """
        Returns:
        verified_idx:     set of i where ANY of the k proofs verified
        unverified_idx:   set of i where NONE verified
        best_idx:         map i -> j (the first j that verified), if any
        """
        results_grouped = self.kimina_proc.verify_proofs_passk(conjectures, proofs_per_conj)

        verified_idx: Set[int] = set()
        unverified_idx: Set[int] = set()
        best_idx: Dict[int, int] = {}

        for i, res_list in enumerate(results_grouped):
            any_ok = False
            for j, r in enumerate(res_list):
                if self._is_verified(r, accept_sorry=accept_sorry):
                    verified_idx.add(i)
                    best_idx[i] = j
                    any_ok = True
                    break
            if not any_ok:
                unverified_idx.add(i)
        return verified_idx, unverified_idx, best_idx

    def _is_verified(self, entry: dict, *, accept_sorry: bool = False) -> bool:

        if entry.get("error") is not None:
            return False

        msgs = entry.get("response", {}).get("messages", [])

        # Any hard Lean error ⇒ fail
        if any(m.get("severity") == "error" for m in msgs):
            return False

        # Optionally treat `sorry` warnings as failures
        if not accept_sorry:
            if any(
                m.get("severity") == "warning" and "declaration uses 'sorry'" in m.get("data", "")
                for m in msgs
            ):
                return False

        return True
    
    def _inverse_provability(
        self,
        conjectures: List[Conjecture],
    ) -> Tuple[Set[str], Set[str]]:
        """
        True  ↦  the *negation* (after push_neg) is provable
        False ↦  Lean failed or timed-out proving the negation
        """
        # 1) batch-rewrite all negations
        negated_forms = self.kimina_proc.batch_push_neg(conjectures)
                    
        negated_conjectures = [self.converter.convert(conjecture.context, neg_form)[0] for conjecture, neg_form in zip(conjectures, negated_forms)]

        # 2) k-proof attempt on the negations
        neg_proofs_k = self.prover.generate_k(negated_conjectures)  # defaults to self.prover.num_return_sequences

        # 3) evaluate pass@k
        neg_verified_idx, neg_unverified_idx, _ = self._evaluate_proofs_passk(
            negated_conjectures, neg_proofs_k, accept_sorry=False
        )
        with open("neg_proofs_k.json", "w") as f:
            json.dump(neg_proofs_k, f)
        return neg_verified_idx, neg_unverified_idx, neg_proofs_k
    
    def _qbin(self, x: float) -> int:
        """Clamp to [0,100] and quantize to nearest multiple of 5 (conservative: round down on .5)."""
        x = max(0.0, min(100.0, float(x)))
        # round to nearest 5 with .5 bias downward
        q = int(5 * math.floor((x / 5.0) + 0.499))
        return max(0, min(100, q))

    def _apply_hard_caps(self, scores: Dict[str, int], flags: Dict[str, bool]) -> Dict[str, int]:
        """Apply the hard rules/caps from the prompt to the score dict in-place and return it."""
        novelty = scores.get("novelty", 0)
        prov   = scores.get("provability_estimate", 0)
        depth  = scores.get("depth", 0)
        diff   = scores.get("difficulty", 0)

        # Ill-typed caps (strongest)
        if flags.get("ill_typed", False):
            prov   = 0
            novelty = min(novelty, 5)
            depth   = min(depth, 10)
            diff    = min(diff, 10)

        # Likely false (but well-typed) caps
        if flags.get("likely_false", False) and not flags.get("ill_typed", False):
            prov = min(prov, 30)

        # Restatement / trivial pattern caps
        if flags.get("restatement", False) or flags.get("trivial_pattern", False):
            novelty = min(novelty, 10)
            depth   = min(depth, 20)
            diff    = min(diff, 30)

        scores["novelty"] = self._qbin(novelty)
        scores["provability_estimate"] = self._qbin(prov)
        scores["depth"] = self._qbin(depth)
        scores["difficulty"] = self._qbin(diff)
        return scores

    def _compute_overall(self, scores: Dict[str, int]) -> int:
        """overall = 0.40*novelty + 0.30*depth + 0.20*difficulty + 0.10*provability_estimate, quantized."""
        overall = (
            0.40 * scores["novelty"]
            + 0.30 * scores["depth"]
            + 0.20 * scores["difficulty"]
            + 0.10 * scores["provability_estimate"]
        )
        return self._qbin(overall)

    def evaluate_fitness(self, context: str, parent_code: str, conjectures: List[Conjecture]) -> List[Dict[str, Any]]:
        # ---------------- 1) forward provability via pass@k -------------------------
        forward_proofs_k = self.prover.generate_k(conjectures)  # List[List[str]]
        verified_idx, unverified_idx, best_idx = self._evaluate_proofs_passk(
            conjectures, forward_proofs_k, accept_sorry=False
        )

        # ---------------- 2) inverse provability (negations) ------------------------
        likely_false_flags_by_i: Dict[int, bool] = {}
        if unverified_idx:
            unverified_list = [conjectures[i] for i in sorted(unverified_idx)]
            neg_verified_idx_subset, _, neg_proofs_k = self._inverse_provability(unverified_list)
            idx_map = {local_i: global_i for local_i, global_i in enumerate(sorted(unverified_idx))}
            for local_i in neg_verified_idx_subset:
                likely_false_flags_by_i[idx_map[local_i]] = True
        
        # ---------------- 3) LLM-judged metrics (new schema) -----------------------
        judged_items = self.llm.generate(context, parent_code, conjectures)
        
        # Weights: keep simple/transparent. Adjust if needed.
        weights = {
            "llm_overall":        0.40,   # from LLM judged scores
            "verified":           0.40,   # from pass@k success
            "negated_verified":  -0.40,   # from inverse proof success
        }

        fitness_results: List[Dict[str, Any]] = []
        for i, (judged_conjecture, conj) in enumerate(zip(judged_items, conjectures)):
            # Merge flags (LLM + inverse proof)
            flags = dict(judged_conjecture.get("flags", {}))  # copy
            flags["likely_false"] = flags.get("likely_false", False) or likely_false_flags_by_i.get(i, False)

            # Extract & sanitize scores (fill missing with 0)
            scores_in = judged_conjecture.get("scores", {})
            scores = {
                "novelty": self._qbin(scores_in.get("novelty", 0)),
                "provability_estimate": self._qbin(scores_in.get("provability_estimate", 0)),
                "depth": self._qbin(scores_in.get("depth", 0)),
                "difficulty": self._qbin(scores_in.get("difficulty", 0)),
            }

            # Proof-based overrides to provability_estimate (as per pipeline logic)
            is_verified = i in verified_idx
            is_neg_verified = bool(flags["likely_false"])
            if is_verified:
                scores["provability_estimate"] = 100
            elif is_neg_verified:
                scores["provability_estimate"] = 0

            # Apply hard caps after proof overrides
            scores = self._apply_hard_caps(scores, flags)

            # Compute overall locally; then apply any residual overall caps
            overall_llm = self._compute_overall(scores)
            # Cap overall for ill-typed / likely_false / restatement/trivial per the spec
            if flags.get("ill_typed", False):
                overall_llm = min(overall_llm, 20)
            if flags.get("likely_false", False) and not flags.get("ill_typed", False):
                overall_llm = min(overall_llm, 50)
            if flags.get("restatement", False) or flags.get("trivial_pattern", False):
                overall_llm = min(overall_llm, 40)

            # Fitness score composition
            score = 0.0
            score += (overall_llm / 100.0) * weights["llm_overall"]
            score += float(is_verified) * weights["verified"]
            score += float(is_neg_verified) * weights["negated_verified"]

            fitness_results.append({
                "fitness_score": score,
                "verified": is_verified,
                "negated_verified": is_neg_verified,
                # expose sanitized LLM metrics
                "novelty": scores["novelty"],
                "provability_estimate": scores["provability_estimate"],
                "depth": scores["depth"],
                "difficulty": scores["difficulty"],
                "overall": overall_llm,
                "flags": flags,
                "justification": judged_conjecture.get("justification", ""),
                "best_proof_k": (best_idx[i] if i in best_idx else None),
            })

        return fitness_results