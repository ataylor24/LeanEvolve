from src.application.evaluator import (
    ConjectureEvalResultRepository,
    ConjectureEvaluator,
)
from src.application.generator import ConjectureGenerator, ConjectureRepository
from src.application.generator.context_maker import ContextMaker
from src.entity.conjecture_eval_result import ConjectureEvalResult
from src.application import program_db, sampler, map_archive
from src.application.fitness.fitness_evaluator import FitnessEvaluator
import pickle, pathlib
from src.application.evaluator.KiminaPool import KiminaPool
from src.application.test import generate_test_statements
from src.entity.mutation import Mutation   
from src.application import mutation_utils


class ConjecturerPipeline:
    @staticmethod
    def run(
        model_name: str,
        api_key: str,
        contexts: list[str],
        max_iter: int = 1,
        testing: bool = False,
        fitness_prover_model: str = "deepseek-ai/DeepSeek-Prover-v2",
        fitness_llm_model: str = "o4-mini",
        
    ) -> None:
        kimina_proc = KiminaPool("http://localhost", timeout=120, num_proc=16, batch_size=32)
        generator = ConjectureGenerator(model_name, api_key)
        evaluator = ConjectureEvaluator(kimina_proc, fitness_prover_model)
        repository = ConjectureRepository()
        eval_repository = ConjectureEvalResultRepository()
        fitness_evaluator = FitnessEvaluator(llm_model_name=fitness_llm_model, llm_api_key=api_key, kimina_proc=kimina_proc)
        
        # Initialise MAP archive with default config; you can tune prune thresholds here
        cfg = map_archive.MapConfig()
        map_archive.init_archive(cfg)
        step = 0
        
        for context, context_id in contexts:
            if testing:
                print(f"TESTING pipeline for context: {context_id}")
            else:
                print(f"Running pipeline for context: {context_id}")
            
            ctx_ops = mutation_utils.get_ctx_ops(context_id)
            ctx_op_ids = list(ctx_ops.keys())
            
            conjecture_eval_results: list[ConjectureEvalResult] = []
            for iter_num in range(max_iter):
                print(f"--------------------------------Iteration {iter_num}--------------------------------")
                # Optional: reset island elites each iteration if configured
                if cfg.reset_each_iter:
                    map_archive.clear_all_elites()
                # Periodically prune underperforming/stale elites
                map_archive.prune_underperformers()

                elites = map_archive.get_all_elites()
                parents = sampler.choose_parents(k=1) or []
                parent_code = parents[0]["lean_code"] if parents else ""
                step += 1
                
                op_id = sampler.choose_operator(ctx_op_ids, step)
                print(f"Generating conjectures via operator <{op_id}>...")
                if not testing:
                    conjectures, chosen_op = generator.generate(context_id, context,
                                                    conjecture_eval_results,
                                                    elites=elites,
                                                    ctx_mutations=ctx_ops,
                                                    mutation=ctx_ops.get(op_id),
                                                    parent_code=parent_code,
                                                    operator_hint=op_id)
                    print("Saving conjectures...")
                    repository.save(conjectures)
                    print(f"Saved {len(conjectures)} conjectures to repository")
                else:
                    print("Generating test conjectures...")
                    conjectures = generate_test_statements(context, conjecture_eval_results, num_cases=10)
                    chosen_op = "test"

                
                print("Evaluating conjectures...")
                results = evaluator.evaluate(conjectures, context_id, iter_num)
                print(f"Evaluated {len(results)} conjectures")
                if not testing:
                    print("Saving evaluation results...")
                    eval_repository.save(results)
                    print(f"Saved {len(results)} evaluation results to repository")

                print("Updating context...")
                conjecture_eval_results.extend(results)
                context, updated = ContextMaker.make(context, conjecture_eval_results, iter_num)
                if not updated:
                    print("No new conjectures found")
                    continue
                
                print("Evaluating fitness...")
                fitness_results = fitness_evaluator.evaluate_fitness(context,
                        parent_code, results)
                for fitness, result, conjecture in zip(fitness_results, results, conjectures):
                    print(f"Fitness: {fitness}")
                    record = {
                        "parent_id": parents[0]["id"] if parents else None,
                        "id": str(result.id),
                        "iter_num": result.iter_num,
                        "context": context_id,
                        "operator_id": chosen_op,
                        "lean_code": conjecture.code,
                        # Reward should correlate with success; use normalized fitness_score for DB
                        "validity": float(result.passed),
                        "verifiable": fitness["verifiability"],
                        "fitness_score": fitness["fitness_score"],
                        "fitness_features": fitness,
                        "map_scores": fitness["map_scores"],
                    }
                    if not testing:
                        print("Updating program database...")
                        program_db.append(record)
                        # Use fitness_score as the operator reward (not inverted 'passed')
                        sampler.update_operator_stats(chosen_op, float(record["fitness_score"]))
                        # --- MAP-Elites style archive update ---
                        map_archive.update_elites(record)
                if not testing:
                    print("Archiving MAP-Elites...")
                    # Persist MAP archive to disk
                    map_archive.persist()
                else:
                    print("Not archiving in testing mode...")