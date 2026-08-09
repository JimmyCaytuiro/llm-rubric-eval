#!/usr/bin/env python3
"""
rubric_eval.py — Weighted-rubric evaluation of LLM responses, with
human-in-the-loop (HITL) gating.

Distilled from a multi-model pipeline I run for my own engineering work: several models
answer the same prompt, each answer is scored against a weighted rubric,
and nothing ships without explicit human approval. This module is the
scoring core, dependency-free, usable standalone or as a library.

Usage:
    python rubric_eval.py examples/candidates.json           # score + report
    python rubric_eval.py examples/candidates.json --min 7.0 # gate threshold

Input format (JSON):
    {
      "task": "short description of the prompt/task",
      "rubric": {"criterion_name": weight, ...},   # weights sum to 1.0
      "candidates": [
        {"model": "model-a", "scores": {"criterion_name": 0-10, ...},
         "notes": "free-form evaluator notes"},
        ...
      ]
    }

Assumptions:
    - Scores are 0-10 per criterion, assigned by a human evaluator or an
      LLM judge (upstream of this module).
    - Weights are validated to sum to 1.0 (tolerance 1e-6).
"""

import argparse
import json
import sys
from pathlib import Path

# Default rubric: the 6 criteria I use for technical-answer evaluation.
DEFAULT_RUBRIC = {
    "technical_accuracy": 0.30,
    "completeness":       0.20,
    "code_quality":       0.20,
    "clarity":            0.10,
    "safety_compliance":  0.10,
    "conciseness":        0.10,
}


class RubricError(ValueError):
    pass


def validate_rubric(rubric: dict) -> None:
    if not rubric:
        raise RubricError("Rubric is empty")
    bad = {k: w for k, w in rubric.items()
           if not isinstance(w, (int, float)) or w < 0}
    if bad:
        raise RubricError(f"Invalid weights (must be numbers >= 0): {bad}")
    total = sum(rubric.values())
    if abs(total - 1.0) > 1e-6:
        raise RubricError(f"Weights must sum to 1.0 (got {total:.4f})")


def score_candidate(scores: dict, rubric: dict) -> float:
    """Weighted total on a 0-10 scale. Missing criteria raise, extra warn."""
    missing = set(rubric) - set(scores)
    if missing:
        raise RubricError(f"Candidate missing scores for: {sorted(missing)}")
    for crit, val in scores.items():
        if crit not in rubric:
            continue
        try:
            num = float(val)
        except (TypeError, ValueError):
            raise RubricError(f"Score must be a number: {crit}={val!r}") from None
        if not 0 <= num <= 10:
            raise RubricError(f"Score out of range 0-10: {crit}={val}")
    return sum(float(scores[c]) * w for c, w in rubric.items())


def evaluate(data: dict) -> dict:
    rubric = data.get("rubric") or DEFAULT_RUBRIC
    validate_rubric(rubric)
    candidates = data.get("candidates", [])
    if not candidates:
        raise RubricError("No candidates to evaluate")

    results = []
    for cand in candidates:
        total = score_candidate(cand.get("scores", {}), rubric)
        results.append({
            "model": cand.get("model", "unknown"),
            "total": round(total, 3),
            "scores": cand.get("scores", {}),
            "notes": cand.get("notes", ""),
        })
    results.sort(key=lambda r: r["total"], reverse=True)
    return {"task": data.get("task", ""), "rubric": rubric, "ranking": results}


def report(result: dict, min_score: float) -> int:
    print(f"Task: {result['task']}\n")
    print(f"{'RANK':<5}{'MODEL':<22}{'TOTAL':>6}   GATE")
    winner = result["ranking"][0]
    for i, r in enumerate(result["ranking"], 1):
        gate = "PASS" if r["total"] >= min_score else "below threshold"
        print(f"{i:<5}{r['model']:<22}{r['total']:>6.2f}   {gate}")

    print("\nPer-criterion breakdown (winner):")
    for crit, w in result["rubric"].items():
        s = float(winner["scores"][crit])
        print(f"  {crit:<20} {s:>5.1f} x {w:.2f} = {s * w:.2f}")

    # HITL gate: even a passing score is a *recommendation*, not a decision.
    if winner["total"] >= min_score:
        print(f"\nRECOMMENDATION: '{winner['model']}' ({winner['total']:.2f}) "
              f">= threshold {min_score}. Pending HUMAN APPROVAL before use.")
        return 0
    print(f"\nNO candidate reached threshold {min_score}. "
          f"Best: '{winner['model']}' at {winner['total']:.2f}. Escalate to human review.")
    return 1


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", type=Path, help="JSON file with rubric + candidates")
    ap.add_argument("--min", type=float, default=7.0,
                    help="minimum weighted score to pass the gate (default 7.0)")
    ap.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = ap.parse_args()

    try:
        data = json.loads(args.input.read_text(encoding="utf-8"))
    except OSError as exc:
        sys.exit(f"ERROR: cannot read {args.input}: {exc}")
    except json.JSONDecodeError as exc:
        sys.exit(f"ERROR: {args.input} is not valid JSON: {exc}")

    try:
        result = evaluate(data)
    except RubricError as exc:
        sys.exit(f"ERROR: {exc}")

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        sys.exit(0)
    sys.exit(report(result, args.min))


if __name__ == "__main__":
    main()
