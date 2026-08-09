# llm-rubric-eval

Weighted-rubric scoring of LLM responses with a **human-in-the-loop (HITL) gate**. Dependency-free (Python 3.8+, stdlib only).

Distilled from a multi-model pipeline I run for my own engineering work: several frontier models answer the same technical prompt, every answer is scored against a weighted 6-criteria rubric, and **nothing ships without explicit human approval** — a passing score is a recommendation, never a decision.

## The rubric

Default criteria (weights sum to 1.0, fully customizable per task):

| Criterion | Weight |
|---|---|
| technical_accuracy | 0.30 |
| completeness | 0.20 |
| code_quality | 0.20 |
| clarity | 0.10 |
| safety_compliance | 0.10 |
| conciseness | 0.10 |

`safety_compliance` is non-negotiable in my domain (industrial automation): an answer suggesting to bypass an interlock scores 0 there regardless of elegance.

## Usage

```bash
python rubric_eval.py examples/candidates.json            # ranked report + HITL gate
python rubric_eval.py examples/candidates.json --min 8.5  # stricter gate (exit 1 if none pass)
python rubric_eval.py examples/candidates.json --json     # machine-readable output
```

The included example scores three (anonymized) model answers to a Modbus RTU parsing task — including one that *looks* complete but swaps the CRC byte order, the kind of failure only domain evaluation catches.

## Design notes

- Input validation is strict: weights must sum to 1.0, scores must be 0–10, missing criteria fail loudly. Silent evaluation errors are worse than no evaluation.
- Exit codes make it pipeline-friendly: `0` = a candidate passed the gate (pending human approval), `1` = escalate to human review.
- The judge (human or LLM) lives **upstream**; this module is the deterministic scoring core, so the same scores always produce the same ranking.

## License

MIT — see [LICENSE](LICENSE).
