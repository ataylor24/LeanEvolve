# src/application/kimina_client_pool.py
from __future__ import annotations
from typing import List, Dict
from src.application.generator.generator import Conjecture
from kimina_client import KiminaClient                # kimina HTTP client
from kimina_client.models import Snippet
import os
import re
from textwrap import dedent

class KiminaPool:
    """
    Wrap a single Lean4Client and expose three batched helpers:
        • compile_only      – Lean kernel, no tactics
        • exact_suggestion  – append 'exact?' and compile
        • aesop_suggestion  – append 'aesop?' and compile
    """

    def __init__(
        self,
        base_url: str | None = None,
        timeout: int = 120,
        num_proc: int = 16,
        batch_size: int = 32,
    ):
        """Thin wrapper around :class:`Lean4Client` with sensible defaults.

        Parameters
        ----------
        base_url : str | None
            Base URL of the kimina-lean-server, including scheme & port.  If
            *None*, the environment variable ``KIMINA_SERVER_URL`` is honoured
            (if present); otherwise we default to ``http://localhost:12332``
            which is the port used by the bundled Lean server implementation.
        timeout : int
            Request timeout forwarded to the underlying client (seconds).
        num_proc : int
            *Unused for now* – placeholder for future pool parallelism.
        batch_size : int
            Batch size forwarded to the map-elites evaluator (not yet used).
        """

        if base_url is None:
            base_url = os.getenv("KIMINA_SERVER_URL", "http://localhost")
        print(f"Using Kimina server at {base_url}")
        self._client  = KiminaClient(api_url=base_url)
        self._timeout = timeout
        self._num_proc = num_proc
        self._batch_size = batch_size

    # ------------------- NEW analysis helper -------------------
    def analyze_statement(self, code: str):
        """Forward a single Lean statement to the /analyze endpoint.

        This is used by src.application.descriptors to obtain parser-aware
        features for MAP-Elites.
        """
        return self._client.analyze_statement(code, timeout=self._timeout)

    # ------------ low‑level RPC helpers -----------------
    def _verify_batch(self, items: List[Dict]) -> List[Dict]:
        """Return the list of results from a Kimina `/check` call.

        Kimina-client >=0.6.0 returns a `CheckResponse` object with a
        `.results` attribute instead of the old `dict` payload.  To stay
        backward-compatible we support both shapes.
        """
        resp = self._client.check(items, timeout=self._timeout, batch_size=self._batch_size, max_workers=self._num_proc, debug=True)
        # Newer kimina_client returns a dataclass-like object
        from kimina_client.models import backward_response_from_repl
        if hasattr(resp, "results"):
            # Convert each `ReplResponse` to the old backward-compatible dict shape
            converted = []
            for r in resp.results:
                d = backward_response_from_repl(r)
                # Ensure keys exist so older code using "['error']" doesn't crash
                if "error" not in d:
                    d["error"] = None
                if "response" not in d or d["response"] is None:
                    d["response"] = {"messages": []}
                converted.append(d)
            return converted  # type: ignore[attr-defined]
        # Older versions returned a plain dict list already
        return resp["results"]

    # ------------ public helpers -----------------------
    def compile_only(self, snippets: List[str]) -> List[Dict]:
        req = [Snippet(id=str(i), code=f"{s.rstrip()} sorry") for i, s in enumerate(snippets)]
        return self._verify_batch(req)

    def exact_suggestion(self, snippets: List[str]) -> List[Dict]:
        req = [Snippet(id=str(i), code=f"{s.rstrip()} exact?\n") for i, s in enumerate(snippets)]
        return self._verify_batch(req)

    def aesop_suggestion(self, snippets: List[str]) -> List[Dict]:
        req = [Snippet(id=str(i), code=f"{s.rstrip()} aesop?\n") for i, s in enumerate(snippets)]
        return self._verify_batch(req)
    
    def _split_imports_and_rest(self, text: str) -> tuple[str, str]:
        """Return (imports_block, rest_block) from the beginning of `text`."""
        lines = text.splitlines()
        i = 0
        while i < len(lines) and lines[i].lstrip().startswith("import "):
            i += 1
        return "\n".join(lines[:i]).strip(), "\n".join(lines[i:]).strip()

    def _dedup_imports(self, *blocks: str) -> str:
        """Deduplicate import lines while preserving order."""
        seen, out = set(), []
        for blk in blocks:
            for ln in blk.splitlines():
                l = ln.strip()
                if l.startswith("import ") and l not in seen:
                    seen.add(l); out.append(l)
        return "\n".join(out)
    
    def _parse_decl_header(self, stmt: str) -> tuple[str | None, str | None]:
        """
        Parse the first declaration keyword and name from a Lean statement header.

        Returns (keyword, name). For `example`, name will be None.
        Recognizes: theorem|lemma|def|example.
        """
        # Named decls: theorem/lemma/def <name> ...
        m = re.search(r"^\s*(theorem|lemma|def)\s+([A-Za-z_][A-Za-z0-9_\.]*)\b", stmt, flags=re.M)
        if m:
            return m.group(1), m.group(2)
        # `example` has no name
        m = re.search(r"^\s*example\b", stmt, flags=re.M)
        if m:
            return "example", None
        return None, None
    
    def batch_push_neg(self, conjectures: List[Conjecture]) -> List[str]:
        items = []
        for idx, conj in enumerate(conjectures):
            # 1) Put ALL imports at the very top
            ctx_imports, ctx_rest = self._split_imports_and_rest(conj.context)
            top_imports = self._dedup_imports(
                "import Lean", "import Mathlib", "import Aesop", ctx_imports
            )

            kw, parsed_name = self._parse_decl_header(conj.sorry_statement)
            orig_name = parsed_name or getattr(conj, "name", None) or f"anon_{idx}"

            # Preserve theorem/lemma if your converter supports both; otherwise normalize.
            emit_kw = kw if kw in ("theorem", "lemma") else "theorem"
            neg_name = f"neg_{orig_name}"
            # 2) Build snippet: imports -> set_option -> opens -> rest-of-context
            #    -> theorem (with sorry) -> helper -> #eval
            lean_snippet = dedent(f"""
            {top_imports}

            -- We rely on Lean's Meta + Tactic APIs and mathlib's `push_neg`.
            open Classical
            open Lean Elab Tactic

            {ctx_rest}

            /- The conjecture we will inspect (it is okay if it has `sorry`) -/
            {conj.sorry_statement}

            /-- Push negation through a proposition `ty` and return the rewritten type. -/
            def _pushNegExpr (ty : Lean.Expr) : Lean.Meta.MetaM Lean.Expr := do
            -- Create a goal with target `ty`, then run `push_neg` on that goal.
            let gExpr ← Lean.Meta.mkFreshExprMVar ty
            let g     := gExpr.mvarId!
            -- Run parsed tactic syntax via Lean.Elab.runTactic; it returns (List MVarId × Term.State).
            let (gs, _) ← Lean.Elab.runTactic g (← `(tactic| open Classical in push_neg))
            let g' := gs.headD g
            -- Get the (instantiated) type of the resulting goal and return it.
            let ty'  ← Lean.MVarId.getType g'
            let ty'' ← Lean.instantiateMVars ty'
            pure ty''

            -- Use #eval! because the file contains a sorry-proof.
            #eval! Lean.Meta.MetaM.run' do
            -- Look up the original constant and build `¬ P` where `P` is its type
            let P    ← Lean.Meta.inferType (← Lean.Meta.mkConstWithFreshMVarLevels ``{orig_name})
            let notP := Lean.mkApp (Lean.mkConst ``Not) P
            let e'   ← _pushNegExpr notP
            -- Pretty print the resulting expression and emit a single-line declaration
            let fmt  ← Lean.PrettyPrinter.ppExpr e'
            let out := "{emit_kw} {neg_name} : " ++ fmt.pretty ++ " := by\\n"
            IO.println out
            """).strip()

            items.append(Snippet(id=str(idx), code=lean_snippet))

        # --- single RPC round-trip ------------------------------------------------
        results = self._verify_batch(items)

        # --- extract the `info` messages sent by the #eval ------------------------
        rewritten: List[str] = []
        for r, snip in zip(results, items):
            msgs = r.get("response", {}).get("messages", [])
            info_msg = next((m["data"].strip() for m in msgs if m.get("severity") == "info"), None)
            if info_msg is None:
                # keep first lines for quick diagnosis if needed
                head = "\n".join(snip.code.splitlines())
                raise RuntimeError(
                    f"push_neg failed for id={r.get('custom_id') or r.get('id')}   messages={msgs}\n"
                    f"--- snippet head ---\n{head}\n"
                )
            rewritten.append(info_msg)
        return rewritten

    def verify_proofs_passk(
        self,
        conjectures: List[Conjecture],
        proofs_per_conj: List[List[str]],
    ) -> List[List[Dict]]:
        """
        For each statement[i] and each proof tail proofs_per_conj[i][j], we build:

            code = f"{statement}\n{proof_tail}\n"

        We send ONE batched Kimina /check call with Snippet ids "{i}:{j}".
        We return results grouped & aligned as a list[ list[ dict ] ] so that
        results[i][j] corresponds to proofs_per_conj[i][j].
        """
        assert len(conjectures) == len(proofs_per_conj), \
            "conjectures and proofs_per_conj must be the same length"

        # Flat list of Snippets with composite IDs "i:j"
        items: List[Snippet] = []
        for i, (conj, proofs) in enumerate(zip(conjectures, proofs_per_conj)):
            s = conj.code.rstrip()
            for j, prf in enumerate(proofs):
                tail = prf.strip()
                code = f"{s}\n{tail}\n"   # keep a newline at end
                items.append(Snippet(id=f"{i}:{j}", code=code))

        # One RPC
        flat_results = self._verify_batch(items)  # List[Dict], order preserved by client

        # Group back into [ [ Dict ] ]
        grouped: List[List[Dict]] = [ [ ] for _ in range(len(conjectures)) ]
        id_re = re.compile(r"^(\d+):(\d+)$")
        for r in flat_results:
            cid = r.get("custom_id") or r.get("id")
            m = id_re.match(str(cid))
            if not m:
                # Ensure we don't silently mis-assign
                raise RuntimeError(f"Unexpected custom_id shape: {cid}")
            i, j = int(m.group(1)), int(m.group(2))
            # Pad if needed (should not happen, but defensive)
            while len(grouped[i]) <= j:
                grouped[i].append({})
            grouped[i][j] = r
        return grouped
