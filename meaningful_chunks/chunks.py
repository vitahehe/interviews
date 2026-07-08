"""
meaningful_chunks/chunks.py =
MEANINGFUL CHUNK SELECTION.

Takes the broad annotations produced by Stage 1 (annotation/annotate.py)
and narrows the full transcript-preserving pool down to analytically meaningful
evidence chunks for SELF_DETERMINATION, SELF_EFFICACY, and VALUE_MOTIVATION
(plus high-confidence OTHER_RELEVANT material).

Design:
- Stage 2a (this always runs): deterministic, rule-based filtering on the
  confidence/topic/human_review_needed fields Stage 1 already produced. Free,
  instant, fully reproducible, fully auditable.
- Stage 2b (--adjudicate flag, optional): only the "borderline" pool — chunks
  with a theory-relevant label but insufficient Stage 1 confidence — gets a
  second, focused look from Claude. This keeps AI's role scoped to genuine
  judgment calls instead of re-deciding chunks Stage 1 already settled.
- Nothing is silently discarded. Excluded and rejected chunks are always
  written to their own files for audit.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path
from typing import Any

try:
    import anthropic
except ImportError:
    anthropic = None


CORE_TOPICS = {"SELF_DETERMINATION", "SELF_EFFICACY", "VALUE_MOTIVATION"}
SECONDARY_TOPICS = {"OTHER_RELEVANT"}
CONTEXT_TOPIC = "CONTEXT_ONLY"

DEFAULT_INPUT = Path("/home/vita/projects/interviews/annotation/outputs/all_broad_annotations.jsonl")
DEFAULT_OUTPUT_DIR = Path("chunks/outputs")

DEFAULT_CORE_THRESHOLD = 0.5        # matches Stage 1's "plausible evidence" band
DEFAULT_SECONDARY_THRESHOLD = 0.65  # higher bar: OTHER_RELEVANT is a catch-all

DEFAULT_MODEL = "claude-sonnet-4-6"
DEFAULT_MAX_TOKENS = 2048
ADJUDICATION_BATCH_SIZE = 10


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_jsonl(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_csv(rows: list[dict[str, Any]], path: Path, fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            formatted = dict(row)
            for key in ("broad_topics", "theory_cues"):
                if isinstance(formatted.get(key), list):
                    formatted[key] = "; ".join(formatted[key])
            writer.writerow({field: formatted.get(field, "") for field in fields})


def classify_chunk(row: dict[str, Any], core_threshold: float, secondary_threshold: float) -> str:
    """Deterministic Stage 2a tier assignment: 'confirmed', 'borderline', or 'excluded'."""
    topics = set(row.get("broad_topics", []))
    confidence = float(row.get("confidence", 0.0))
    needs_review = bool(row.get("human_review_needed", False))

    if not topics or topics == {CONTEXT_TOPIC}:
        return "excluded"

    if topics & CORE_TOPICS:
        return "confirmed" if (confidence >= core_threshold and not needs_review) else "borderline"

    if topics & SECONDARY_TOPICS:
        return "confirmed" if (confidence >= secondary_threshold and not needs_review) else "borderline"

    # Unknown/unexpected topic combination: never silently drop, send for review.
    return "borderline"


def run_stage_2a(rows, core_threshold, secondary_threshold):
    confirmed, borderline, excluded = [], [], []
    for row in rows:
        tier = classify_chunk(row, core_threshold, secondary_threshold)
        enriched = {**row, "stage2_tier": tier}
        {"confirmed": confirmed, "borderline": borderline, "excluded": excluded}[tier].append(enriched)
    return confirmed, borderline, excluded


ADJUDICATION_SYSTEM_PROMPT = """
<role>
You are doing analytic gatekeeping for Stage 2 of a qualitative interview-analysis
pipeline studying physics-lab students' motivation, using Self-Determination
Theory, Self-Efficacy Theory, and Expectancy-Value Theory.
</role>

<context>
Each chunk you are given already received a tentative topic label in Stage 1
(broad annotation), but with low confidence or a human-review flag, meaning it
was NOT automatically accepted as solid evidence. Your job is a single, more
careful re-judgment: given the full chunk text and its previous/next context,
decide whether it is genuinely usable as an evidence chunk for a researcher
doing thematic analysis, or too vague, off-topic, or purely contextual.
</context>

<rules>
- Do not invent new topics. Only confirm, narrow, or reject the topics the
  chunk already carries.
- Include if, on closer reading, the chunk gives specific, interpretable
  evidence related to autonomy/competence/relatedness/motivation quality
  (Self-Determination), task-specific capability beliefs (Self-Efficacy), or
  expectancy/value/cost judgments about the lab (Value-Motivation).
- Exclude if the chunk is generic, purely procedural, too vague to support a
  specific claim, or its apparent relevance depends entirely on the context
  fields rather than the chunk text itself.
- When genuinely unsure, prefer include with a lower revised_confidence rather
  than excluding outright — this stage still tolerates some over-inclusion,
  just less than Stage 1 did.
- Do not omit any chunk_id from your response.
</rules>

<output_format>
Return ONLY a single valid JSON object, no markdown fences, no extra text:

{
  "decisions": [
    {
      "chunk_id": "string",
      "decision": "include | exclude",
      "final_topics": ["SELF_DETERMINATION"],
      "revised_confidence": 0.0,
      "reasoning": "one sentence"
    }
  ]
}
</output_format>
""".strip()


def build_adjudication_user_prompt(batch: list[dict[str, Any]]) -> str:
    payload = [
        {
            "chunk_id": row["chunk_id"],
            "speaker_type": row.get("speaker_type", ""),
            "text": row.get("text", ""),
            "previous_context": row.get("previous_context", ""),
            "next_context": row.get("next_context", ""),
            "stage1_broad_topics": row.get("broad_topics", []),
            "stage1_confidence": row.get("confidence", 0.0),
            "stage1_annotation_reason": row.get("annotation_reason", ""),
            "stage1_possible_tension": row.get("possible_tension", ""),
        }
        for row in batch
    ]
    chunks_json = json.dumps(payload, indent=2, ensure_ascii=False)
    return f"""<chunks_for_review>
{chunks_json}
</chunks_for_review>

Make one include/exclude decision per chunk above, following <rules> and
<output_format> in the system prompt.""".strip()


def extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return json.loads(text[start:end + 1])
    raise ValueError("Could not parse model output as JSON.")


def batch_items(items: list[dict], batch_size: int) -> list[list[dict]]:
    return [items[i:i + batch_size] for i in range(0, len(items), batch_size)]


def adjudicate_borderline(client, model, borderline, max_tokens=DEFAULT_MAX_TOKENS):
    """Stage 2b: send only the borderline pool to Claude for a focused second judgment."""
    accepted, rejected = [], []

    for idx, batch in enumerate(batch_items(borderline, ADJUDICATION_BATCH_SIZE), start=1):
        print(f"  Adjudication batch {idx}: {len(batch)} chunks")
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=[{"type": "text", "text": ADJUDICATION_SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": build_adjudication_user_prompt(batch)}],
            temperature=0.0,
        )
        parsed = extract_json(response.content[0].text)
        decisions = {d["chunk_id"]: d for d in parsed.get("decisions", []) if d.get("chunk_id")}

        for row in batch:
            cid = row["chunk_id"]
            decision = decisions.get(cid)
            enriched = dict(row)

            if decision is None:
                # Model missed it: keep, flagged for human review rather than silently dropping.
                enriched["stage2_decision"] = "include"
                enriched["stage2_reasoning"] = "Model did not return a decision; defaulted to include for human review."
                enriched["human_review_needed"] = True
                accepted.append(enriched)
                continue

            enriched["stage2_decision"] = decision.get("decision", "include")
            enriched["stage2_reasoning"] = decision.get("reasoning", "")
            if decision.get("final_topics"):
                enriched["broad_topics"] = decision["final_topics"]
            try:
                enriched["confidence"] = float(decision.get("revised_confidence", row.get("confidence", 0.0)))
            except (TypeError, ValueError):
                pass

            (accepted if enriched["stage2_decision"] == "include" else rejected).append(enriched)

    return accepted, rejected


CSV_FIELDS = [
    "interview_id", "chunk_id", "speaker", "speaker_type", "participant_id",
    "text", "previous_context", "next_context", "broad_topics", "confidence",
    "theory_cues", "annotation_reason", "valence", "possible_tension",
    "human_review_needed", "stage2_tier", "stage2_decision", "stage2_reasoning",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stage 2: select analytically meaningful chunks from Stage 1 output.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--core-threshold", type=float, default=DEFAULT_CORE_THRESHOLD)
    parser.add_argument("--secondary-threshold", type=float, default=DEFAULT_SECONDARY_THRESHOLD)
    parser.add_argument(
        "--adjudicate", action="store_true",
        help="Send the borderline pool to Claude for a focused second judgment. "
             "Without this flag, the script only does the free deterministic split.",
    )
    parser.add_argument("--model", type=str, default=DEFAULT_MODEL)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows = read_jsonl(args.input)
    print(f"Loaded {len(rows)} annotated chunks from {args.input}")

    confirmed, borderline, excluded = run_stage_2a(rows, args.core_threshold, args.secondary_threshold)
    print(f"Confirmed: {len(confirmed)} | Borderline: {len(borderline)} | Excluded (context-only): {len(excluded)}")

    args.output.mkdir(parents=True, exist_ok=True)
    write_jsonl(excluded, args.output / "excluded_context_only.jsonl")
    write_csv(excluded, args.output / "excluded_context_only.csv", CSV_FIELDS)

    if not args.adjudicate:
        write_jsonl(confirmed, args.output / "meaningful_chunks.jsonl")
        write_csv(confirmed, args.output / "meaningful_chunks.csv", CSV_FIELDS)
        write_jsonl(borderline, args.output / "borderline_chunks_for_review.jsonl")
        write_csv(borderline, args.output / "borderline_chunks_for_review.csv", CSV_FIELDS)
        print("\nDone (no AI adjudication run).")
        print(f"  Confirmed meaningful chunks: {args.output / 'meaningful_chunks.jsonl'}")
        print(f"  Borderline chunks awaiting review: {args.output / 'borderline_chunks_for_review.jsonl'}")
        return

    if anthropic is None:
        raise ImportError("The anthropic package is not installed. Run: pip install anthropic")
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise EnvironmentError("ANTHROPIC_API_KEY is not set.")

    client = anthropic.Anthropic()
    print(f"\nAdjudicating {len(borderline)} borderline chunks with {args.model}...")
    accepted, rejected = adjudicate_borderline(client, args.model, borderline)
    print(f"  Adjudication result: {len(accepted)} included, {len(rejected)} excluded")

    final_meaningful = confirmed + accepted
    write_jsonl(final_meaningful, args.output / "meaningful_chunks.jsonl")
    write_csv(final_meaningful, args.output / "meaningful_chunks.csv", CSV_FIELDS)
    write_jsonl(rejected, args.output / "excluded_after_adjudication.jsonl")
    write_csv(rejected, args.output / "excluded_after_adjudication.csv", CSV_FIELDS)

    print("\nDone.")
    print(f"  Final meaningful chunks ({len(final_meaningful)}): {args.output / 'meaningful_chunks.jsonl'}")
    print(f"  Excluded after adjudication ({len(rejected)}): {args.output / 'excluded_after_adjudication.jsonl'}")


if __name__ == "__main__":
    main()