"""
analyze_patterns.py

Stage 2, Step B: AI-assisted pattern-finding across already-aggregated,
already-verified Stage 1 evidence. Takes aggregate_data.json (Step A's
deterministic counts) plus the actual verified quotes from every included
interview's pass2.json, and asks the model to surface tensions,
contradictions, alignments, subtleties, and emerging patterns.

Design note: findings reference quotes by quote_id only. The model never
retypes quote text -- cited_text is spliced back in by this script after
the fact, the same anti-drift pattern used in run_pipeline.py's Pass 2.
This step trusts Step A's included_interviews list as the single source of
truth for which interviews are valid -- it does not re-run health checks.
"""

import argparse
import hashlib
import json
from pathlib import Path

import anthropic
import yaml
from dotenv import load_dotenv
load_dotenv()


def render(template: str, **kwargs) -> str:
    out = template
    for k, v in kwargs.items():
        out = out.replace("{{ " + k + " }}", str(v)).replace("{{" + k + "}}", str(v))
    return out


def load_all_quotes(stage1_dir: Path, included_interviews: list[str]) -> list[dict]:
    """Load every interpretation from every included interview's pass2.json,
    tagging each with its interview_id so cross-interview findings can
    reference where each quote came from."""
    quotes = []
    for interview_id in included_interviews:
        pass2_path = stage1_dir / interview_id / "pass2.json"
        with open(pass2_path, "r", encoding="utf-8") as f:
            pass2 = json.load(f)
        for interp in pass2.get("interpretations", []):
            quotes.append({**interp, "interview_id": interview_id})
    return quotes


def build_quotes_block(quotes: list[dict]) -> str:
    lines = []
    for q in quotes:
        lines.append(f"QUOTE_ID       → {q['quote_id']}")
        lines.append(f"INTERVIEW_ID   → {q['interview_id']}")
        lines.append(f"THEME          → {q.get('theme_id')}")
        lines.append(f"CODE           → {q.get('code')}")
        lines.append(f"FULL_QUOTE     → {q.get('cited_text', '').strip()}")
        lines.append(f"RATIONALE      → {q.get('rationale', '')}")
        lines.append("")
    return "\n".join(lines)

def build_aggregate_summary(aggregate_data: dict) -> str:
    """A compact, readable text rendering of the parts of aggregate_data.json
    relevant to pattern-finding -- not the full JSON dump, to keep the model
    focused on structure rather than re-parsing raw nested objects."""
    lines = []
    lines.append("Code counts per interview:")
    for code, per_interview in aggregate_data["code_interview_matrix"].items():
        counts = ", ".join(f"{i}={c}" for i, c in per_interview.items())
        lines.append(f"  {code}: {counts}")
    if aggregate_data.get("zero_quote_codes"):
        lines.append(f"Codes with zero quotes in ANY included interview: {', '.join(aggregate_data['zero_quote_codes'])}")
    if aggregate_data.get("duplicate_citations_by_pair"):
        lines.append("Codes whose quotes overlap (same quote satisfied both codes):")
        for item in aggregate_data["duplicate_citations_by_pair"]:
            pair = " & ".join(item["code_pair"])
            lines.append(f"  {pair}: {item['co_occurrence_count']} shared quote(s)")
    return "\n".join(lines)


FINDINGS_TOOL = {
    "name": "record_pattern_findings",
    "description": "Record cross-interview pattern findings from coded interview evidence.",
    "input_schema": {
        "type": "object",
        "properties": {
            "findings": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "finding_type": {
                            "type": "string",
                            "enum": ["tension", "contradiction", "alignment", "subtlety", "emerging_pattern", "irrelevant_pattern"],
                        },
                        "title": {"type": "string"},
                        "description": {"type": "string"},
                        "quote_ids": {"type": "array", "items": {"type": "string"}},
                        "themes_involved": {"type": "array", "items": {"type": "string"}},
                        "codes_involved": {"type": "array", "items": {"type": "string"}},
                        "confidence": {
                            "type": "string",
                            "enum": ["strong", "moderate", "speculative"],
                        },
                    },
                    "required": [
                        "finding_type", "title", "description",
                        "quote_ids", "themes_involved", "codes_involved", "confidence",
                    ],
                },
            }
        },
        "required": ["findings"],
    },
}


def run_pattern_analysis(client, model, system_prompt, prompt_template, aggregate_data, quotes):
    user_text = render(
        prompt_template,
        interview_count=len(aggregate_data["included_interviews"]),
        interview_ids=", ".join(aggregate_data["included_interviews"]),
        aggregate_summary=build_aggregate_summary(aggregate_data),
        quotes_block=build_quotes_block(quotes),
    )
    response = client.messages.create(
        model=model,
        max_tokens=16000,
        system=system_prompt,
        tools=[FINDINGS_TOOL],
        tool_choice={"type": "tool", "name": "record_pattern_findings"},
        messages=[{"role": "user", "content": user_text}],
    )

    stop_reason = getattr(response, "stop_reason", None)
    usage = getattr(response, "usage", {})

    for block in response.content:
        if getattr(block, "type", None) == "tool_use":
            return block.input.get("findings", []), usage, stop_reason

    return [], usage, stop_reason


def make_json_safe(obj):
    return json.loads(json.dumps(obj, default=str))


def generate_markdown_report(findings: list[dict]) -> str:
    lines = ["# Stage 2 — Cross-Interview Pattern Findings\n"]
    order = ["contradiction", "tension", "subtlety", "alignment", "emerging_pattern", "irrelevant_pattern"]
    for finding_type in order:
        matching = [f for f in findings if f["finding_type"] == finding_type]
        if not matching:
            continue
        lines.append(f"## {finding_type.replace('_', ' ').title()}\n")
        for f in matching:
            # Prepend any short warning lines for human reviewers when
            # checks added during quote-resolution flag inconsistencies.
            if not f.get("codes_involved_consistent", True):
                lines.append("⚠ codes_involved does not match cited quotes' actual codes -- see codes_involved_actual")
            if f.get("single_interview_only", False):
                lines.append("⚠ labeled as alignment but all supporting quotes are from a single interview")

            lines.append(f"**{f['title']}** (confidence: {f['confidence']})")
            lines.append(f["description"])
            if f.get("codes_involved") or f.get("themes_involved"):
                codes_str = ", ".join(f.get("codes_involved", [])) if f.get("codes_involved") else "(none)"
                themes_str = ", ".join(f.get("themes_involved", [])) if f.get("themes_involved") else "(none)"
                lines.append(f"Themes: {themes_str} | Codes: {codes_str}")
            lines.append("Supporting quotes:")
            for q in f["quotes"]:
                quote_display = f"[{q['quote_id']} | {q['interview_id']} | {q['code']}] {q['cited_text']}"
                lines.append(f"- {quote_display}")
            lines.append("")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage1-dir", required=True, help="e.g. outputs/stage_1")
    ap.add_argument("--aggregate-data", required=True, help="e.g. outputs/stage_1/aggregate_data.json")
    ap.add_argument("--codebook", required=True)
    ap.add_argument("--prompts-dir", required=True)
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--model", default="claude-sonnet-5")
    args = ap.parse_args()

    stage1_dir = Path(args.stage1_dir)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    aggregate_data = json.loads(Path(args.aggregate_data).read_text(encoding="utf-8"))
    codebook = yaml.safe_load(Path(args.codebook).read_text(encoding="utf-8"))

    prompts_dir = Path(args.prompts_dir)
    system_prompt = (prompts_dir / "system_prompt.md").read_text(encoding="utf-8")
    pattern_template = (prompts_dir / "stage2_pattern_prompt.md").read_text(encoding="utf-8")

    quotes = load_all_quotes(stage1_dir, aggregate_data["included_interviews"])
    quote_by_id = {q["quote_id"]: q for q in quotes}

    client = anthropic.Anthropic()
    findings, usage, stop_reason = run_pattern_analysis(
        client, args.model, system_prompt, pattern_template, aggregate_data, quotes
    )

    # Splice verified quote data back in by ID -- same anti-drift pattern as
    # run_pipeline.py's Pass 2. Flag (don't crash on) any quote_id the model
    # referenced that doesn't actually exist in our data.
    for finding in findings:
        resolved = []
        for qid in finding.get("quote_ids", []):
            q = quote_by_id.get(qid)
            if q is None:
                resolved.append({"quote_id": qid, "cited_text": "[UNRESOLVED quote_id -- not found in source data]", "interview_id": "?", "code": "?"})
            else:
                resolved.append({
                    "quote_id": qid,
                    "cited_text": q.get("cited_text"),
                    "interview_id": q.get("interview_id"),
                    "code": q.get("code"),
                })
        finding["quotes"] = resolved

        # Validate that the codes the model stated are actually present
        # on the resolved quotes. Preserve the model's original
        # `codes_involved` but record whether it matches the actual set
        # of codes observed on the cited quotes.
        stated_codes = set(finding.get("codes_involved", []))
        actual_codes = set(q["code"] for q in finding["quotes"] if q["code"] != "?")
        finding["codes_involved_consistent"] = (stated_codes == actual_codes)
        if stated_codes != actual_codes:
            finding["codes_involved_actual"] = sorted(actual_codes)

        # If a finding is typed as an "alignment", ensure we flag
        # when its supporting quotes actually come from a single
        # interview only.
        interview_ids_cited = set(q["interview_id"] for q in finding["quotes"] if q["interview_id"] != "?")
        finding["single_interview_only"] = (
            finding.get("finding_type") == "alignment" and len(interview_ids_cited) <= 1
        )

    (outdir / "pattern_findings.json").write_text(
        json.dumps({"findings": findings, "stop_reason": stop_reason}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    (outdir / "pattern_findings.md").write_text(
        generate_markdown_report(findings), encoding="utf-8"
    )

    def file_hash(p: Path) -> str:
        return hashlib.sha256(p.read_bytes()).hexdigest()[:16]

    metadata = {
        "model": args.model,
        "included_interviews": aggregate_data["included_interviews"],
        "aggregate_data_hash": file_hash(Path(args.aggregate_data)),
        "prompt_hash": file_hash(prompts_dir / "stage2_pattern_prompt.md"),
        "system_prompt_hash": file_hash(prompts_dir / "system_prompt.md"),
        "finding_count": len(findings),
        "stop_reason": stop_reason,
        "usage": make_json_safe(usage),
    }
    (outdir / "metadata.json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print(f"Done. {len(findings)} findings. Files written to {outdir}/")
    # This script always forces a tool choice; a stop_reason of
    # "tool_use" (or an explicit "end_turn") is expected. Anything
    # else (e.g. "max_tokens") should be treated as a potential
    # truncation and warned about.
    if stop_reason not in ("tool_use", "end_turn"):
        print(f"WARNING: stop_reason was '{stop_reason}' -- output may be truncated.")


if __name__ == "__main__":
    main()