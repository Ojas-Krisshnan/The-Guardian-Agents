#!/usr/bin/env python3
"""
smoke_openai.py - Live API smoke test and end-to-end pipeline verification for OpenAI.

Enforces zero-exposure: Never logs, prints, or exposes the actual API key.
Uses safe synthetic data: Student: "Test Student", Concept: "Basic Algebra".
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Add project root to sys.path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from slice.budget import Budget
from slice.config import load_env, settings as get_settings
from slice.llm import Provider, complete, get_provider_config
from slice.store import Store
from synapse.agents.flow import diagnose, tailor_note
from synapse.schemas import (
    Attempt,
    CanonicalNote,
    ConceptNode,
    Diagnosis,
    NoteVersion,
    Test,
    TestQuestion,
)


def run_smoke_test():
    load_env()
    s = get_settings()

    print("=" * 60)
    print("PHASE 10: OPENAI LIVE API SMOKE TEST")
    print("=" * 60)

    # 1. Verify configuration without exposing secrets
    has_key = bool(s.openai_api_key or os.environ.get("OPENAI_API_KEY"))
    print(f"Provider: {s.provider}")
    print(f"Configured Model: {s.openai_model}")
    print(f"Base URL: {s.openai_base_url}")
    print(f"API Key Detected: {'[YES - SECURELY CONFIGURED]' if has_key else '[NO - NOT DETECTED]'}")

    if not has_key:
        print("\n[SKIP] OPENAI_API_KEY is not set in environment or .env.")
        print("To run live smoke test:")
        print("  1. Add OPENAI_API_KEY=your_key to .env (or export OPENAI_API_KEY)")
        print("  2. Set SLICE_PROVIDER=openai")
        print("  3. Run: python scripts/smoke_openai.py\n")
        return False

    # Force provider to openai for smoke test
    s_live = s
    if s.provider != "openai":
        from dataclasses import replace
        s_live = replace(s, provider="openai")

    cfg = get_provider_config(s_live)
    print(f"Resolved Provider Config: {cfg}")  # repr is safely masked

    db_path = ROOT / "scratch_smoke.db"
    if db_path.exists():
        try:
            db_path.unlink()
        except Exception:
            pass

    store = Store(str(db_path))
    run_id = store.create_run("openai_smoke")
    budget = Budget(store, run_id, s_live)

    # 2. Minimal real model request through slice/llm.py
    print("\nExecuting minimal model ping via slice.llm.complete()...")
    try:
        ping_res = complete(
            settings=s_live,
            budget=budget,
            messages=[{"role": "user", "content": "Respond with 'PONG' and nothing else."}],
            step="smoke_ping",
            timeout=30.0,
        )
        print(f"  -> Model Response: {ping_res.strip()!r}")
        print(f"  -> Tokens used so far: {budget.tokens_used()}")
    except Exception as e:
        print(f"  [FAIL] Minimal request failed: {type(e).__name__}: {e}")
        return False

    # 3. Real diagnosis agent call using safe synthetic student/test data
    print("\nExecuting Diagnosis Agent with synthetic student data (Basic Algebra)...")
    synthetic_test = Test(
        concept_id="algebra_basic",
        concept_name="Basic Algebra",
        questions=[
            TestQuestion(
                id="q_alg_1",
                text="Solve for x: 2x + 4 = 10",
                options=["x = 3", "x = 7", "x = 2", "x = 5"],
                correct_answer="x = 3",
                concept_id="algebra_basic",
            ),
            TestQuestion(
                id="q_alg_2",
                text="Solve for x: 3x - 6 = 9",
                options=["x = 5", "x = 1", "x = 3", "x = 9"],
                correct_answer="x = 5",
                concept_id="algebra_basic",
            ),
        ],
    )

    synthetic_attempt = Attempt(
        student_id="synthetic_student_01",
        test_id=synthetic_test.id,
        concept_id="algebra_basic",
        answers={
            "q_alg_1": "x = 7",  # Incorrect (added 4 instead of subtracting)
            "q_alg_2": "x = 5",  # Correct
        },
        score=1,
        total=2,
    )

    try:
        diag = diagnose(
            attempt=synthetic_attempt,
            test=synthetic_test,
            settings=s_live,
            budget=budget,
        )
        print("  -> Authoritative AI Diagnosis received successfully:")
        print(f"     Mastery Estimate: {diag.mastery_estimate}")
        print(f"     Trend: {diag.trend}")
        print(f"     Diagnosed Items: {len(diag.items)}")
        for it in diag.items:
            print(f"       - Q: {it.question_id} | Class: {it.classification} | Reason: {it.reason}")
        print(f"  -> Total tokens used: {budget.tokens_used()}")
    except Exception as e:
        print(f"  [FAIL] Diagnosis agent call failed: {type(e).__name__}: {e}")
        return False

    # 4. Phase 11: Real Note Tailoring Agent call using the generated diagnosis
    print("\n" + "=" * 60)
    print("PHASE 11: NOTE TAILORING AGENT LIVE VERIFICATION")
    print("=" * 60)
    canonical = CanonicalNote(
        concept_id="algebra_basic",
        markdown="# Basic Algebra\nLinear equations and balancing terms.",
        extracted_concepts=[ConceptNode(name="Basic Algebra", summary="Solving linear equations")],
    )

    try:
        note = tailor_note(
            student_id=synthetic_attempt.student_id,
            concept_id="algebra_basic",
            diagnosis=diag,
            canonical_note=canonical,
            settings=s_live,
            budget=budget,
        )
        print("  -> Personalized Study Note generated successfully:")
        print(f"     Concept: {note.concept_id}")
        print(f"     Version: {note.version}")
        print(f"     Linked Diagnosis ID: {note.diagnosis_id}")
        print(f"     Markdown preview (first 250 chars):\n{note.markdown[:250]}...\n")
        print(f"  -> Total tokens used: {budget.tokens_used()}")
    except Exception as e:
        print(f"  [FAIL] Note tailoring agent failed: {type(e).__name__}: {e}")
        return False

    print("=" * 60)
    print("SUCCESS: Full AI Pipeline Verified with Real OpenAI Provider!")
    print("=" * 60)
    store.close()
    try:
        db_path.unlink()
    except Exception:
        pass
    return True


if __name__ == "__main__":
    success = run_smoke_test()
    sys.exit(0 if success else 1)
