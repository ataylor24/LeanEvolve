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
        conjectures: Dict[int, Conjecture],                # theorem headers / full declarations
        proofs_per_conj: Dict[int, List[str]],     # k proof tails per statement[i]
        *,
        accept_sorry: bool = False,
        testing: bool = False,
    ) -> Tuple[Set[int], Set[int], Dict[int, Dict[str, List[str]]]]:
        """
        Returns:
        verified_idx:     set of i where ANY of the k proofs verified
        unverified_idx:   set of i where NONE verified
        verified_proofs:  map i -> list of proofs that verified
        """
        results_grouped = self.kimina_proc.verify_proofs_passk(conjectures, proofs_per_conj)

        verified_idx: Set[int] = set()
        unverified_idx: Set[int] = set()
        proofs: Dict[int, Dict[str, List[str]]] = {}

        # `results_grouped` and `proofs_per_conj` are aligned by LOCAL indices 0..n-1
        for i, res_list in enumerate(results_grouped):
            proof_idx = i
            any_ok = False
            proofs[proof_idx] = {}
            proofs[proof_idx]["verified"] = []
            proofs[proof_idx]["unverified"] = []
            for r, proof in zip(res_list, proofs_per_conj[proof_idx]):
                if self._is_verified(r, accept_sorry=accept_sorry):
                    verified_idx.add(proof_idx)
                    proofs[proof_idx]["verified"].append(proof)
                    any_ok = True
                else:
                    proofs[proof_idx]["unverified"].append(proof)
            if not any_ok:
                unverified_idx.add(proof_idx)
                
        return verified_idx, unverified_idx, proofs

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
        conjectures: Dict[int, Conjecture],
        testing: bool = False,
    ) -> Tuple[Set[str], Set[str]]:
        """
        True  ↦  the *negation* (after push_neg) is provable
        False ↦  Lean failed or timed-out proving the negation
        """
        # 1) batch-rewrite all negations
        negated_forms = self.kimina_proc.batch_push_neg(conjectures)
                    
        negated_conjectures = {idx: self.converter.convert(conjectures[idx].context, neg_form)[0] for idx, neg_form in zip(conjectures.keys(), negated_forms)}

        # 2) k-proof attempt on the negations
        neg_proofs_k = self.prover.generate_k(negated_conjectures)  # defaults to self.prover.num_return_sequences

        # 3) evaluate pass@k
        neg_verified_idx, neg_unverified_idx, neg_proofs = self._evaluate_proofs_passk(
            negated_conjectures, neg_proofs_k, accept_sorry=False, testing=testing
        )
        
        return neg_verified_idx, neg_unverified_idx, neg_proofs
    
    def evaluate(
        self,
        conjectures: list[Conjecture],
        context_name: str,
        iter_num: int,
        testing: bool = False,
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
                passed_triviality_checks=False,
                non_trivial_provable=False,
                non_trivial_neg_provable=False,
                exact_provable=False,
                aesop_provable=False,
                error="compile_failed" if i not in stage1_pass else None,
                verified_proofs=None,
                unverified_proofs=None,
                neg_verified_proofs=None,
                neg_unverified_proofs=None,
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
                if found and not testing:
                    conjectures[global_idx].update_proof("exact?")
                    results[global_idx] = ConjectureEvalResult.new(
                        conjecture=conjectures[global_idx],
                        passed_triviality_checks=False,
                        non_trivial_provable=False,
                        non_trivial_neg_provable=False,
                        exact_provable=True,
                        aesop_provable=False,
                        error=None,
                        verified_proofs="exact?",
                        unverified_proofs=None,
                        neg_verified_proofs=None,
                        neg_unverified_proofs=None,
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
                if proved and not testing:
                    conjectures[global_idx].update_proof("aesop?")
                    results[global_idx] = ConjectureEvalResult.new(
                        conjecture=conjectures[global_idx],
                        passed_triviality_checks=False,
                        non_trivial_provable=False,
                        non_trivial_neg_provable=False,
                        exact_provable=False,
                        aesop_provable=True,
                        error=None,
                        verified_proofs="aesop?",
                        unverified_proofs=None,
                        neg_verified_proofs=None,
                        neg_unverified_proofs=None,
                        context_name=context_name,
                        iter_num=iter_num,
                        )
                else:
                    stage3_pass.append(global_idx)
        
        # -------------------- Stage 4: prove results ------------------------------
        if stage3_pass:
            # Build a LOCAL index map 0..n-1 -> global idx in `stage3_pass`
            conjectures_to_prove = {local_i: conjectures[global_i] for local_i, global_i in enumerate(stage3_pass)}
            forward_proofs_k = self.prover.generate_k(conjectures_to_prove)  # Dict[int, List[str]] keyed by local indices
            verified_idx, unverified_idx, proofs = self._evaluate_proofs_passk(
                conjectures_to_prove, forward_proofs_k, accept_sorry=False, testing=testing
            )
            print(f"PROVED {len(verified_idx)} / {len(stage3_pass)} CONJECTURES")
            global_indices = []
            for conj_idx in proofs.keys():
                global_idx = stage3_pass[conj_idx]  # conj_idx is local
                global_indices.append(global_idx)
                if proofs[conj_idx]["verified"]:
                    shortest_proof = min(proofs[conj_idx]["verified"], key=len)
                    conjectures[global_idx].update_proof(shortest_proof)
                else:
                    conjectures[global_idx].update_proof("sorry")
                
                provable = len(proofs[conj_idx]["verified"]) > 0
                results[global_idx] = ConjectureEvalResult.new(
                    conjecture=conjectures[global_idx],
                    passed_triviality_checks=True,
                    non_trivial_provable=provable,
                    non_trivial_neg_provable=False,
                    exact_provable=False,
                    aesop_provable=False,
                    error=None,
                    verified_proofs=proofs[conj_idx]["verified"],
                    unverified_proofs=proofs[conj_idx]["unverified"],
                    neg_verified_proofs=None,
                    neg_unverified_proofs=None,
                    context_name=context_name,
                    iter_num=iter_num,
                )

            # ---------------- 2) inverse provability (negations) ------------------------
          
            if unverified_idx:
                # Reindex the unverified subset to contiguous local indices 0..m-1
                sorted_unverified = sorted(list(unverified_idx))
                reindexed_unverified = {local_i: conjectures_to_prove[orig_i] for local_i, orig_i in enumerate(sorted_unverified)}
                reindexed_to_orig = {local_i: orig_i for local_i, orig_i in enumerate(sorted_unverified)}

                _, _, neg_proofs = self._inverse_provability(reindexed_unverified, testing=testing)
                
                for conj_idx in neg_proofs.keys():
                    orig_local_idx = reindexed_to_orig[conj_idx]
                    global_idx = stage3_pass[orig_local_idx]
                    global_indices.append(global_idx)
                    if neg_proofs[conj_idx]["verified"]:
                        shortest_proof = min(neg_proofs[conj_idx]["verified"], key=len)
                        conjectures[global_idx].update_proof(shortest_proof)
                    else:
                        conjectures[global_idx].update_proof("sorry")
                        
                    neg_provable = len(neg_proofs[conj_idx]["verified"]) > 0
                    results[global_idx] = ConjectureEvalResult.new(
                        conjecture=conjectures[global_idx],
                        passed_triviality_checks=True,
                        non_trivial_provable=False,
                        non_trivial_neg_provable=neg_provable,
                        exact_provable=False,
                        aesop_provable=False,
                        error=None,
                        verified_proofs=proofs[orig_local_idx]["verified"],
                        unverified_proofs=proofs[orig_local_idx]["unverified"],
                        neg_verified_proofs=neg_proofs[conj_idx]["verified"],
                        neg_unverified_proofs=neg_proofs[conj_idx]["unverified"],
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

