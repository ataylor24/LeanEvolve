from src.application.evaluator.KiminaPool import KiminaPool
from src.application.fitness.llm_fitness_evaluator import LLMFitnessEvaluator
from textwrap import dedent
from typing import List, Tuple, Set, Dict, Any
from kimina_client.models import Snippet
import math
import json
from src.entity.conjecture_eval_result import ConjectureEvalResult
from ordered_set import OrderedSet

class FitnessEvaluator:
    def __init__(self, llm_model_name: str, llm_api_key: str, kimina_proc: KiminaPool):
        self.llm = LLMFitnessEvaluator(llm_model_name, llm_api_key)
        self.kimina_proc = kimina_proc
    
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
        diff   = scores.get("difficulty", 0)

        # Ill-typed caps (strongest)
        if flags.get("ill_typed", False):
            prov   = 0
            novelty = min(novelty, 0)
            diff    = min(diff, 0)

        # Restatement / trivial pattern caps
        if flags.get("restatement", False) or flags.get("trivial_pattern", False):
            novelty = min(novelty, 0)
            diff    = min(diff, 0)

        scores["novelty"] = self._qbin(novelty)
        scores["provability_estimate"] = self._qbin(prov)
        scores["difficulty"] = self._qbin(diff)
        return scores

    def _compute_overall(self, scores: Dict[str, int]) -> int:
        """overall = 0.40*novelty + 0.20*difficulty + 0.40*provability_estimate, quantized."""
        overall = (
            0.80 * scores["novelty"]
            + 0.10 * scores["difficulty"]
            + 0.10 * scores["provability_estimate"]
        )
        return self._qbin(overall)

    def evaluate_fitness(self, context: str, parent_code: str, results: List[ConjectureEvalResult]) -> List[Dict[str, Any]]:
        '''
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

        '''
        # ---------------- 1) forward provability via pass@k -------------------------
        passing_conjectures = []
        passing_idxs = OrderedSet()
        for i, result in enumerate(results):
            if result.passed:
                passing_conjectures.append(result.conjecture)
                passing_idxs.add(i)
            
        # ---------------- 3) LLM-judged metrics (new schema) -----------------------
        judged_items = self.llm.generate(context, parent_code, passing_conjectures)
        
        # Weights: keep simple/transparent. Adjust if needed.
        weights = {
            "llm_overall":        0.40,   # from LLM judged scores
            "verifiability":           0.60,   # from pass@k success
        }

        fitness_results: List[Dict[str, Any]] = []
        for i, conjecture_result in enumerate(results):
            # Merge flags (LLM + inverse proof)
            if i in passing_idxs:
                judged_conjecture = judged_items[passing_idxs.index(i)]
                flags = dict(judged_conjecture.get("flags", {})) 

                # Extract & sanitize scores (fill missing with 0)
                scores_in = judged_conjecture.get("scores", {})
                scores = {
                    "novelty": self._qbin(scores_in.get("novelty", 0)),
                    "provability_estimate": self._qbin(scores_in.get("provability_estimate", 0)),
                    "difficulty": self._qbin(scores_in.get("difficulty", 0)),
                }

                # Proof-based overrides to provability_estimate (as per pipeline logic)
                if conjecture_result.non_trivial_provable:
                    scores["provability_estimate"] = 100
                elif conjecture_result.non_trivial_neg_provable:
                    scores["provability_estimate"] = 0

                # Apply hard caps after proof overrides
                scores = self._apply_hard_caps(scores, flags)

                # Compute overall locally; then apply any residual overall caps
                overall_llm = self._compute_overall(scores)
                # Cap overall for ill-typed / likely_false / restatement/trivial per the spec
                if flags.get("ill_typed", False):
                    overall_llm = min(overall_llm, 0)
                if flags.get("restatement", False) or flags.get("trivial_pattern", False):
                    overall_llm = min(overall_llm, 0)

                verifiability = 1 if conjecture_result.non_trivial_provable or conjecture_result.non_trivial_neg_provable else 0
                # Fitness score composition
                score = 0.0
                score += (overall_llm / 100.0) * weights["llm_overall"]
                score += verifiability * weights["verifiability"]
                
                map_scores = {
                    "verifiability": verifiability,
                    "novelty": scores["novelty"],
                    "provability_estimate": scores["provability_estimate"],
                    "difficulty": scores["difficulty"],
                }

                fitness_results.append({
                    "fitness_score": score,
                    "map_scores": map_scores,
                    "verifiability": verifiability,
                    "llm_overall": overall_llm,
                    "llm_scores": scores,
                    "llm_flags": flags,
                    "justification": judged_conjecture.get("justification", ""),
                })
            else:
                fitness_results.append({
                    "fitness_score": 0.0,
                    "map_scores": None,
                    "verifiability": 0,
                    "llm_overall": None,
                    "llm_scores": None,
                    "llm_flags": None,
                    "justification": None,
                })
            
        with open("fitness_results.json", "a") as f:
            json.dump(fitness_results, f, indent=2)
            f.write("\n")

        return fitness_results