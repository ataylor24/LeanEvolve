from dataclasses import dataclass

from loguru import logger

from src.application.lean_processor import LeanProcessor, LeanProcessorResponse
from src.entity.conjecture import Conjecture
from src.entity.conjecture_eval_result import ConjectureEvalResult
from src.application.evaluator.KiminaPool import KiminaPool
from src.application.evaluator.prover import Prover
from src.application.generator.converter import ConjectureConverter
from typing import List, Tuple, Set, Dict


@dataclass
class ConjectureEvaluator:
    try_remove_contexts: bool = False

    def __init__(self, kimina_proc: KiminaPool, prover_model_name: str):
        self.kimina_proc = kimina_proc
        self.prover = Prover(prover_model_name)
        self.converter = ConjectureConverter()

    def _evaluate_proofs_passk(
        self,
        conjectures: List[Conjecture],                # theorem headers / full declarations
        proofs_per_conj: List[List[str]],     # k proof tails per statement[i]
        *,
        accept_sorry: bool = False,
    ) -> Tuple[Set[int], Set[int], Dict[int, List[str]]]:
        """
        Returns:
        verified_idx:     set of i where ANY of the k proofs verified
        unverified_idx:   set of i where NONE verified
        verified_proofs:  map i -> list of proofs that verified
        """
        results_grouped = self.kimina_proc.verify_proofs_passk(conjectures, proofs_per_conj)

        verified_idx: List[int] = []
        unverified_idx: List[int] = []
        verified_proofs: Dict[int, List[str]] = {}

        for i, res_list in enumerate(results_grouped):
            any_ok = False
            verified_proofs[i] = []
            for j, r in enumerate(res_list):
                if self._is_verified(r, accept_sorry=accept_sorry):
                    verified_idx.append(i)
                    verified_proofs[i].append(r)
                    any_ok = True
                    break
            if not any_ok:
                unverified_idx.append(i)
        return verified_idx, unverified_idx, verified_proofs

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
        neg_verified_idx, neg_unverified_idx, neg_verified_proofs = self._evaluate_proofs_passk(
            negated_conjectures, neg_proofs_k, accept_sorry=False
        )
        
        return neg_verified_idx, neg_unverified_idx, neg_verified_proofs
    
    def evaluate(
        self,
        conjectures: list[Conjecture],
        context_name: str,
        iter_num: int,
    ) -> list[ConjectureEvalResult]:

        # -------------------- Stage 1: compilation only --------------------
        conjecture_statements = [cj.code for cj in conjectures]
        compile_res = self.kimina_proc.compile_only(conjecture_statements)

        stage1_pass = [
            idx for idx, r in enumerate(compile_res)
            if r["error"] is None and all(
                m["severity"] != "error" for m in r["response"]["messages"]
            )
        ]
        
        stage2_pass: List[int] = []
        stage3_pass: List[int] = []
        # initialise results with failures
        results = [
            ConjectureEvalResult.new(
                conjecture=cj,
                passed=False,
                non_trivial_provable=False,
                non_trivial_neg_provable=False,
                exact_provable=False,
                aesop_provable=False,
                error="compile_failed" if i not in stage1_pass else None,
                proofs=None,
                context_name=context_name,
                iter_num=iter_num,
            )
            for i, cj in enumerate(conjectures)
        ]

        # -------------------- Stage 2: exact? ------------------------------
        if stage1_pass:
            exact_req  = [conjecture_statements[i] for i in stage1_pass]
            exact_res  = self.kimina_proc.exact_suggestion(exact_req)
            for local_idx, resp in enumerate(exact_res):
                global_idx = stage1_pass[local_idx]
                found = any(
                    m["severity"] == "info" and m["data"].startswith("Try this:")
                    for m in resp["response"]["messages"]
                )
                if found:
                    conjectures[global_idx].update_proof("exact?")
                    results[global_idx] = ConjectureEvalResult.new(
                        conjecture=conjectures[global_idx],
                        passed=False,
                        non_trivial_provable=False,
                        non_trivial_neg_provable=False,
                        exact_provable=True,
                        aesop_provable=False,
                        error=None,
                        proofs="exact?",
                        context_name=context_name,
                        iter_num=iter_num,
                    )
                else:
                    stage2_pass.append(global_idx)
  
        # -------------------- Stage 3: aesop? ------------------------------
        if stage2_pass:
            #TODO: add a check to verify that aesop's suggestion is valid
            
            aesop_req = [conjecture_statements[i] for i in stage2_pass]
            aesop_res = self.kimina_proc.aesop_suggestion(aesop_req)
            for local_idx, resp in enumerate(aesop_res):
                global_idx = stage2_pass[local_idx]
                proved = any(
                    m["severity"] == "info"
                    and m["data"].startswith("Try this:")
                    and "sorry" not in m["data"]
                    for m in resp["response"]["messages"]
                )
                if proved:
                    conjectures[global_idx].update_proof("aesop?")
                    results[global_idx] = ConjectureEvalResult.new(
                        conjecture=conjectures[global_idx],
                        passed=False,
                        non_trivial_provable=False,
                        non_trivial_neg_provable=False,
                        exact_provable=False,
                        aesop_provable=True,
                        error=None,
                        proofs="aesop?",
                        context_name=context_name,
                        iter_num=iter_num,
                        )
                else:
                    stage3_pass.append(global_idx)
        
        # -------------------- Stage 4: prove results ------------------------------
        if stage3_pass:
            conjectures_to_prove = [conjectures[i] for i in stage3_pass]
            forward_proofs_k = self.prover.generate_k(conjectures_to_prove)  # List[List[str]]
            verified_idx, unverified_idx, verified_proofs = self._evaluate_proofs_passk(
                conjectures_to_prove, forward_proofs_k, accept_sorry=False
            )
            for local_idx, proofs in zip(verified_idx, verified_proofs):
                global_idx = stage3_pass[local_idx]
                conjectures[global_idx].update_proof(proofs[0])
                results[global_idx] = ConjectureEvalResult.new(
                    conjecture=conjectures[global_idx],
                    passed=True,
                    non_trivial_provable=True,
                    non_trivial_neg_provable=False,
                    exact_provable=False,
                    aesop_provable=False,
                    error=None,
                    proofs=proofs,
                    context_name=context_name,
                    iter_num=iter_num,
                )

            # ---------------- 2) inverse provability (negations) ------------------------
          
            if unverified_idx:
                unverified_list = [conjectures_to_prove[i] for i in sorted(unverified_idx)]
                neg_verified_idx, neg_unverified_idx, neg_verified_proofs = self._inverse_provability(unverified_list)
            
                for local_idx, proofs in zip(neg_verified_idx, neg_verified_proofs):
                    global_idx = stage3_pass[unverified_idx[local_idx]]
                    conjectures[global_idx].update_proof(proofs[0])
                    results[global_idx] = ConjectureEvalResult.new(
                        conjecture=conjectures[global_idx],
                        passed=True,
                        non_trivial_provable=False,
                        non_trivial_neg_provable=True,
                        exact_provable=False,
                        aesop_provable=False,
                        error=None,
                        proofs=proofs,
                        context_name=context_name,
                        iter_num=iter_num,
                    )

                for local_idx in neg_unverified_idx:
                    global_idx = stage3_pass[unverified_idx[local_idx]]
                    conjectures[global_idx].update_proof("sorry")
                    results[global_idx] = ConjectureEvalResult.new(
                        conjecture=conjectures[global_idx],
                        passed=True,
                        non_trivial_provable=False,
                        non_trivial_neg_provable=False,
                        exact_provable=False,
                        aesop_provable=False,
                        error=None,
                        proofs=[],
                        context_name=context_name,
                        iter_num=iter_num,
                    )
                    
        return results

    @staticmethod
    def _try_remove_contexts(lean: LeanProcessor, conjecture: Conjecture) -> Conjecture:
        print_code = (
            conjecture.code.split(":=")[0]
            + ":= by sorry\n\n#print "
            + conjecture.name
            + "\n"
        )
        response = lean.exec(print_code)
        for message in response.messages:
            if message.severity == "info" and message.data.startswith("theorem "):
                statement = message.data.split(":=")[0] + ":= by\n"
                if "sorry" not in statement and not response.sorries:
                    return Conjecture.new(
                        code=conjecture.import_str + "\n\n" + statement
                    )

        return conjecture

