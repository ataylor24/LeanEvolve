# src/application/generator/prompt_maker.py
from __future__ import annotations
from src.entity.conjecture import Conjecture
from src.entity.prompt import Prompt
from src.entity.mutation import Mutation
from typing import List, Dict, Any

class PromptMaker:
    """
    Build the (system + user) prompt for ConjectureGPT.

    Parameters
    ----------
    context : str
        Lean source text (usually a module or file content).
    parent_code : str, optional
        An existing lemma / theorem that the LLM should mutate or extend.
    operator_hint : str | None, optional
        Name of the mutation operator to apply (Alpha‑Evolve style).

    Returns
    -------
    Prompt
        dataclass with .system_prompt and .user_prompt used by ConjectureGPT.
    """

    _SYSTEM_PROMPT = (
        "Please generate new theorems in Lean 4 format that are similar but not "
        "identical to each theorem provided in the text. For every theorem in "
        "the text, create a corresponding new theorem with slight variations. "
        "Do **not** include proofs, annotations, or imports. Each new theorem "
        "must begin with '```lean theorem' and end with ':= by```'. "
        "Use standard mathematical symbols (e.g. ∀, ∃, √) instead of Unicode "
        "escape sequences (e.g. \\u2200)."
    )
    
    # _EVOLVE_SYSTEM_PROMPT = (
    #     "You are “Lean‑Mutator‑GPT”, an assistant whose sole task is to invent AS MANY  **new Lean 4 theorem"
    #     "statements** AS POSSIBLE by *applying a specific **mutation operator*** to a *parent* statement that is"
    #     "supplied to you.\n"

    #     "INPUTS YOU WILL RECEIVE (always in this order)\n"
    #     "1. ## Original file:      – a truncated slice of Lean source code for context only, don’t copy!\n"
    #     "2. ## Parent statement:   – exactly one existing theorem or lemma in Lean 4 syntax.\n"
    #     "3. ## Mutation instruction:   – the name of a mutation operator (e.g. <weaken_result>,"
    #     "<upgrade_metric>, <symmetrize_indices>).  Apply **only** this operator.\n"

    #     "YOUR TASK\n"
    #     "• Produce **as many new theorem statements as possible** that are:\n"
    #     "  – syntactically valid Lean 4,\n"
    #     "  – compilable without extra imports,\n"
    #     "  – *semantically* related to the parent (the mutation operator’s intent must be obvious),\n"
    #     "  – **not identical** to any theorem already shown in the context.\n"

    #     "Respond with **one JSON object** and *nothing else*.\n"
    #     "The object **must exactly match** this schema:\n"

    #     "{"  # single JSON object, no outer list
    #     "  \"operator\": {"
    #     "    \"name\": \"<mutation operator>\","
    #     "    \"description\": \"<one-sentence description of the operator>\""
    #     "  },"
    #     "  \"conjectures\": ["
    #     "    \"<Lean theorem 1>\","
    #     "    \"... (as many as you can)\""
    #     "  ]"
    #     "}" 

    #     "CONSTRAINTS\n"
    #     "• No proofs, tactics, comments, or “sorry” – just the := by stub.\n"
    #     "• Use standard math symbols (∀, ∃, ≤, √) not Unicode escapes (e.g. \u2200).\n"
    #     "• Do not add open, import, or namespace lines.\n"
    #     "• Choose fresh, descriptive names (<NewName*>) to avoid clashes.\n"
    #     "• Keep each statement under 500 tokens.\n"
    #     "• Use standard mathematical symbols (e.g. ∀, ∃, √) instead of Unicode "
    #     "escape sequences (e.g. \\u2200).\n"

    #     "SCORING HINTS (used by an external evaluator)\n"
    #     "• Edits that introduce novel identifiers and increase reasoning depth score higher.\n"
    #     "• Statements that fail to type‑check score zero.\n"
        
    # )
    _EVOLVE_SYSTEM_PROMPT = (
        "You are “Lean-Mutator-GPT”, an assistant whose sole task is to invent AS MANY **new Lean 4 theorem "
        "statements** AS POSSIBLE by *applying exactly one specified mutation operator* to a *parent* statement "
        "that is supplied to you. Your goal is to generate **provable** and **Mathlib-friendly** lemmas: they should "
        "be routine consequences of the parent plus standard Mathlib facts (no new heavy theory).\n"
        "\n"
        "INPUTS YOU WILL RECEIVE (always in this order)\n"
        "1. ## Original file:      – a truncated slice of Lean source code for context only, don’t copy!\n"
        "2. ## Parent statement:   – exactly one existing theorem or lemma in Lean 4 syntax (binders show the ambient types).\n"
        "3. ## Mutation instruction:   – the name of ONE mutation operator (e.g. \<squarefree\_mul\_coprime\_iff>, "
        "\<arg\_right\_half\_plane\_bound>, \<cardinal\_collapse>, \<loewner\_monotone>). Apply **only** this operator.\n"
        "\n"
        "YOUR TASK\n"
        "• Produce **as many new theorem statements as possible** that are:\n"
        "  – syntactically valid Lean 4 and **type-checkable**,\n"
        "  – compilable **without extra imports**, assuming only what the parent’s context already imports,\n"
        "  – *semantically tied* to the parent (the operator’s intent must be obvious),\n"
        "  – **not identical** to any statement already shown in the Original file.\n"
        "• **Provability filter (mandatory):** Only emit statements that are straightforward consequences of the parent "
        "  together with standard Mathlib lemmas. If uncertain a statement is derivable, **do not include it**.\n"
        "\n"
        "Respond with **one JSON object** and *nothing else*.\n"
        "The object **must exactly match** this schema:\n"
        "\n"
        "{"
        "  \"operator\": {"
        "    \"name\": \"<mutation operator>\","
        "    \"description\": \"<one-sentence description of the operator>\""
        "  },"
        "  \"conjectures\": ["
        "    \"<Lean theorem 1>\","
        "    \"... (as many as you can)\""
        "  ]"
        "}"  # single JSON object, no outer list
        "\n"
        "CONSTRAINTS\n"
        "• No proofs, tactics, comments, or “sorry” – just the declaration with `:= by` stub.\n"
        "• Use standard math symbols (∀, ∃, ≤, √) **not** Unicode escapes (e.g. \u2200).\n"
        "• Do not add `open`, `import`, or `namespace` lines.\n"
        "• Choose fresh, descriptive names (e.g., <ParentName>*mut*\*) to avoid clashes.\n"
        "• Keep each statement under 500 tokens.\n"
        "• **Preserve the ambient universe and types** from the parent (if the parent is in ℕ, stay in ℕ; "
        "  if it’s `Matrix (Fin n) (Fin n) 𝕂`, keep the same shape n and 𝕂).\n"
        "• **Make all side-conditions explicit** so the statement is total and Lean-safe (e.g., `z ≠ 0` for division/Arg, "
        "  `Nat.Coprime m n` for multiplicative splits, bounds like `2 ≤ k` for powers).\n"
        "• **No hidden casts across domains.** If moving between ℕ, ℤ, ℝ, or ℂ, use explicit coercions/|·| and state the needed bounds.\n"
        "• **Do not introduce new structures or heavy theory** absent from the parent (avoid analytic continuation, "
        "  measure theory, independence results, deep spectral/PCF machinery, etc.). Prefer routine Tier-A facts.\n"
        "\n"
        "TIER-A OPERATOR BEHAVIOR (what to generate when relevant)\n"
        "• Algebra / Squarefree & radicals: equivalences (`Squarefree n ↔ radical n = n` over ℕ; use |n| over ℤ), "
        "  divisor-closure (`d ∣ n → Squarefree d`), product criteria with `Coprime`, radical multiplicativity under coprime, "
        "  “no square divides a square-free,” structure of divisors of `n^k` with `d = d₀*m^2`, and divisor/subset bijections.\n"
        "• Complex / Arg (principal branch): safe facts like `Arg (a*z) = Arg z` for real `a > 0`, `Arg (z⁻¹) = -Arg z`, "
        "  bounds on half-planes (`Re z > 0 → -π/2 < Arg z < π/2`), additive/subtractive laws on a fixed branch with explicit "
        "  non-cut conditions, and along a C¹ path γ avoiding 0: `d/dt Arg(γ(t)) = Im(γ'(t)/γ(t))`.\n"
        "• Cardinals (ZFC only): Cantor `κ < 2^κ`, König `κ^{cf κ} > κ`, collapses for sums/products/finite powers of infinite "
        "  cardinals, size of finite subsets/finite sequences, Hartogs bound, `κ × κ ≃ κ`. Avoid CH/GCH/PCF/Easton.\n"
        "• Symmetric/Hermitian matrices: Loewner transitivity, Sylvester inertia under congruence, PSD square-root existence "
        "  and monotonicity, Rayleigh bounds, Courant–Fischer characterizations, eigenvalues real for symmetric/Hermitian, "
        "  orthogonal/unitary diagonalization (when parent already fixes 𝕂 and finite dim), eigenvalue monotonicity under `A ≼ B`, "
        "  and `ρ(A) = ‖A‖₂` for symmetric.\n"
        "\n"
        "SAFETY CHECKLIST (apply before emitting each conjecture)\n"
        "1) **Types match** the parent’s binders; no free variables.\n"
        "2) **Totality:** all partial operations guarded (inverses/division require `≠ 0`).\n"
        "3) **Domains coherent:** ℤ vs ℕ (use |·| in ℤ), ℝ vs ℂ (don’t introduce IsROrC unless present).\n"
        "4) **Operator intent visible:** each statement is a clear instance of the given operator (not cosmetic renaming).\n"
        "5) **Lightweight proof path exists** using standard Mathlib lemmas likely available from the parent’s imports.\n"
        "\n"
        "SCORING HINTS (used by an external evaluator)\n"
        "• Parametric families (over indices/exponents/subspaces) score higher than singletons.\n"
        "• Deep but **routine** reasoning (equivalences, monotonicity, closure) scores higher than cosmetic rewrites.\n"
        "• Statements that fail to type-check score zero.\n"
    )


    def make(
        self,
        context: str,
        parent_code: str = "",
        elites: List[Dict[str, Mutation]] = [],
        ctx_mutations: dict[str, Mutation] = {},
        mutation: Mutation | None = None,
    ) -> Prompt:
        # ---------- build the user‑prompt ----------
        parts: list[str] = []

        # 1. original context (truncated to last 400 k chars as before)
        parts.append("## Original file:")
        parts.append(f"```lean\n{context[-400_000:]}\n```")

        # 2. optional parent snippet
        if parent_code:
            parts.append("\n## Parent statement to mutate:")
            parts.append(f"```lean\n{parent_code}\n```")

        # 3a. Elite examples to inspire mutations (operator + statement only)
        if elites:
            parts.append("\n## Elite examples (operator, description, theorem statements):")
            for e in elites[:10]:  # keep prompt bounded
                op_name = e.get("operator_id") or e.get("operator", {}).get("name", "<op>")
                # Try fitness_features->meta for description; else fallbacks
                meta = e.get("fitness_features", {})
                op_desc = meta.get("description") or e.get("operator", {}).get("description", "") or e.get("description", "")
                # Extract statement only (remove context/imports)
                lean_code = e.get("lean_code", "").split("theorem")
                stmt = ("theorem" + lean_code[-1]) if len(lean_code) > 1 else e.get("lean_code", "")
                # Safe-fence separate code block
                parts.append(f"### {op_name}: {op_desc}\n```lean\n{stmt}\n```")

        # 3b. operator instruction
        if mutation:
            if mutation.name == "_NOVEL_":
                parts.append("## Existing operators:")
                for op_id, op in ctx_mutations.items():
                    parts.append(f"### {op_id}: {op.name}: {op.description}")

                # ---------- NOVEL mutation prompt ----------
                parts.append(
                    "\n## Mutation instruction:\n"
                    "Invent **one brand-new mutation operator** that is *not* already listed in "
                    "the Existing or Elite operator sections.\n\n"
                    "**Hard constraints (MUST be satisfied):**\n"
                    "1. **Originality** – The `operator.name` must be unique and capture a genuinely "
                    "different transformation (no re-labelled duplicates, supersets, or subsets).\n"
                    "2. **Substantive change** – The operator must modify the logical *structure* of a "
                    "statement; it may not be a cosmetic edit (e.g. renaming variables, adding/removing "
                    "a tautology, or re-ordering premises).\n"
                    "3. **Non-triviality** – Conjectures produced by this operator should not be provable "
                    "immediately by tactics such as `exact`, `rfl`, `simp`, `ring`, `aesop`, etc.\n"
                    "4. **Distinct from other mutations** – Do not merely negate, dualise, or restrict an "
                    "existing operator unless the resulting behaviour is meaningfully new.\n\n"
                    "Take inspiration from the *style* and *depth* of the Elite operators above, but do "
                    "*not* replicate their mechanisms.\n\n"
                    f"Please apply the created mutation to the parent statement.\n"
                )
            else:
                parts.append(
                    f"\n## Mutation instruction:\n"
                    f"Please apply the mutation **<{mutation.name}>** "
                    f"to the parent statement.\n{mutation.name}: {mutation.description}"
                )
        # 4. closing cue for the LLM
        parts.append("\n## Your new theorem(s):")

        user_prompt = "\n".join(parts)  
        return Prompt(system_prompt=self._EVOLVE_SYSTEM_PROMPT, user_prompt=user_prompt)
    
    _FITNESS_CHECK_SYSTEM_PROMPT = (
        """
        You are Lean-Mutator-Judge. Evaluate conjectures produced by a mutation.
        Return ONLY valid JSON matching the schema below. No prose outside JSON.

        Scoring dimensions (0–100, use multiples of 5; be conservative and prefer the lower bin):
        - novelty:
        0 = restatement/vacuous rewrite; 50 = minor but real change; 100 = substantive structural/quantifier/hypothesis shift such that the conjecture is not present in parent/context.
        - provability_estimate:
        0 = very likely false/ill-typed; 30 = unclear with obstacles; 60 = probably true but nontrivial; 90 = very likely true under standard domain lemmas.
        - difficulty (estimated Lean/Aesop effort to prove):
        0 = one-liner by simp/linarith; 50 = short multi-step with standard lemmas; 80 = case splits or specialized algebraic facts; 100 = likely needs auxiliary lemmas or longer search.

        Flags (boolean): trivial_pattern, restatement, ill_typed.
        - trivial_pattern: the conjecture is a trivial pattern (e.g., ∧ True, syntactic restyle).
        - restatement: the conjecture is a restatement of the parent or of a conjecture in the context.
        - ill_typed: the conjecture is ill-typed.

        Justification: ≤25 words, cite concrete syntactic/semantic change and (if relevant) specific operators/lemmas.

        Output schema:
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

        Hard rules and caps (must enforce):
        - If ill_typed = true: set provability_estimate = 0; set novelty ≤ 5; set difficulty ≤ 10; justification must mention the type issue.
        - If restatement = true OR trivial_pattern = true: set novelty ≤ 10; set difficulty ≤ 30; justification must mention the restatement or trivial pattern.
        - If novelty ≥ 70, both restatement and trivial_pattern MUST be false and justification MUST reference a structural change (e.g., quantifier flip, new hypothesis, weakening/strengthening).
        - If justification cites only contraposition or direction-dropping of an existing iff, then novelty ≤ 40 and difficulty ≤ 50.
        - If the change is a pure rephrasing (e.g., x/y instead of arg x = arg y) without new reasoning burden, difficulty ≤ 40.
        - Do NOT fabricate proofs. If you cannot articulate a plausible lemma path, set provability_estimate ≤ 60 and difficulty ≥ depth.
        - Quantize all scores to {0,5,10,…,100}. When uncertain between bins, choose the lower one.

        Return JSON only. No trailing commas. No text outside JSON.

        """
    )
    
    def make_fitness_check(self, context: str, parent_code: str = "", conjectures: list[Conjecture] = []):
        # ---------- build the user‑prompt ----------
        # --- Select and trim the reference ---
        mode = "parent" if parent_code else "context"
        reference = (parent_code or "") if mode == "parent" else (context or "")
        reference = (reference or "")[:-400_000:]

        # --- Build USER PROMPT ---
        parts: list[str] = []
        parts.append("## Mode")
        parts.append(mode)
        parts.append("\n## Reference (Parent or Context Excerpt)")
        parts.append("```lean")
        parts.append(reference)
        parts.append("```")
        parts.append("\n## Conjectures to Judge")

        for i, cj in enumerate(conjectures, 1):
            parts.append(f"# id: c{i}")
            parts.append("```lean")
            parts.append(cj.context_and_statement)
            parts.append("```")

        user_prompt = "\n".join(parts)
    
        return Prompt(system_prompt=self._FITNESS_CHECK_SYSTEM_PROMPT, user_prompt=user_prompt)
