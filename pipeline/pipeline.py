"""
run_pipeline.py

Stage 1 pipeline: for one interview, runs
  Pass 1 (retrieval, citations-enabled, one call per theme)
  Pass 2 (interpretation, schema-guaranteed via forced tool use)
and writes exactly three files:
  <outdir>/pass1.json
  <outdir>/pass2.json
  <outdir>/metadata.json
"""

import argparse
import hashlib
import json
import re
import time
from pathlib import Path

import anthropic
import yaml
from dotenv import load_dotenv
load_dotenv()

CODE_MARKER = re.compile(r"\[\[CODE:([\w.]+)\]\]")
NONE_MARKER = "[[NONE]]"


def load_codebook(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def render(template: str, **kwargs) -> str:
    out = template
    for k, v in kwargs.items():
        out = out.replace("{{ " + k + " }}", str(v)).replace("{{" + k + "}}", str(v))
    return out


def codes_block_for_theme(theme: dict) -> str:
    lines = []
    for code in theme["codes"]:
        lines.append(f"- {code['id']} {code['name']}")
        lines.append(f"  Description: {code['description'].strip()}")
        lines.append(f"  Why this matters: {code['motivation'].strip()}")
    return "\n".join(lines)


def is_student_speaker(speaker: str) -> bool:
    return speaker.lower().startswith("student ")


def build_custom_content_document(turns: list[dict]) -> tuple[dict, list[dict]]:
    """Build one citable content block per student turn.

    Interviewer turns remain in the processed transcript but are excluded
    from the citation document, making full student turns the quote units.
    """
    student_turns = [turn for turn in turns if is_student_speaker(turn["speaker"])]
    return {
        "type": "document",
        "source": {
            "type": "content",
            "content": [
                {"type": "text", "text": f"{turn['speaker']}: {turn['text']} "}
                for turn in student_turns
            ],
        },
        "title": "Interview transcript",
        "context": "Student interview transcript, one content block per complete student turn.",
        "citations": {"enabled": True},
    }, student_turns


def parse_pass1_response(content_blocks, turns: list[dict], theme_id: str) -> list[dict]:
    quotes = []
    current_code = None
    for block in content_blocks:
        if getattr(block, "type", None) != "text":
            continue
        text = block.text
        for m in CODE_MARKER.finditer(text):
            current_code = m.group(1)
        citations = getattr(block, "citations", None)
        if citations:
            for c in citations:
                start = getattr(c, "start_block_index", None)
                end = getattr(c, "end_block_index", None)
                # end_block_index is exclusive, so the range maps directly to
                # the student-turn citation blocks.
                cited_sentences = (
                    [turns[i] for i in range(start, end)]
                    if start is not None and end is not None and 0 <= start <= end <= len(turns)
                    else []
                )
                turn_ids = [turn["turn_id"] for turn in cited_sentences]
                speakers = sorted({turn["speaker"] for turn in cited_sentences})
                quotes.append(
                    {
                        "theme_id": theme_id,
                        "code": current_code,
                        "cited_text": getattr(c, "cited_text", None),
                        "turn_ids": turn_ids,
                        "speakers": speakers,
                    }
                )
    return quotes


def run_pass1(client, model, turns, theme, system_prompt, pass1_template):
    doc, student_turns = build_custom_content_document(turns)
    user_text = render(
        pass1_template,
        theme_name=theme["name"],
        theme_note=(f" ({theme['note']})" if theme.get("note") else ""),
        codes_block=codes_block_for_theme(theme),
        code_count=len(theme["codes"]),
    )
    response = client.messages.create(
        model=model,
        max_tokens=10000,
        system=system_prompt,
        messages=[
            {"role": "user", "content": [doc, {"type": "text", "text": user_text}]}
        ],
    )
    quotes = parse_pass1_response(response.content, student_turns, theme["id"])
    return quotes, response.usage, response.stop_reason


INTERPRETATION_TOOL = {
    "name": "record_interpretation",
    "description": "Record the interpretive analysis for one already-verified quote.",
    "input_schema": {
        "type": "object",
        "properties": {
            "interpretations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "quote_id": {"type": "string"},
                        "rationale": {"type": "string"},
                        "why_interesting": {"type": "string"},
                        "teaching_implication": {"type": "string"},
                        "interpretation_grounded_in": {
                            "type": "string",
                            "enum": ["quote_text_only", "quote_plus_inference"],
                        },
                    },
                    "required": [
                        "quote_id", "rationale", "why_interesting",
                        "teaching_implication", "interpretation_grounded_in",
                    ],
                },
            }
        },
        "required": ["interpretations"],
    },
}


def run_pass2(client, model, system_prompt, pass2_template, quotes_with_ids, codebook):
    code_lookup = {c["id"]: c for theme in codebook["themes"] for c in theme["codes"]}
    quotes_block_lines = []
    for q in quotes_with_ids:
        code_meta = code_lookup.get(q["code"], {})
        quotes_block_lines.append(
            f"- quote_id: {q['quote_id']}\n"
            f"  code: {q['code']} ({code_meta.get('name', 'unknown')})\n"
            f"  speakers: {', '.join(q['speakers'])}\n"
            f"  quote: \"{q['cited_text']}\""
        )
    user_text = render(pass2_template, quotes_block="\n".join(quotes_block_lines))

    response = client.messages.create(
        model=model,
        max_tokens=18000,
        system=system_prompt,
        tools=[INTERPRETATION_TOOL],
        tool_choice={"type": "tool", "name": "record_interpretation"},
        messages=[{"role": "user", "content": user_text}],
    )

    stop_reason = response.stop_reason
    for block in response.content:
        if getattr(block, "type", None) == "tool_use":
            return block.input.get("interpretations", []), response.usage, stop_reason
    return [], response.usage, stop_reason


def make_json_safe(obj):
    return json.loads(json.dumps(obj, default=str))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--interview-id", required=True)
    ap.add_argument("--processed", required=True)
    ap.add_argument("--codebook", required=True)
    ap.add_argument("--prompts-dir", required=True)
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--model", default="claude-sonnet-5")
    args = ap.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    turns = json.loads(Path(args.processed).read_text(encoding="utf-8"))["turns"]
    codebook = load_codebook(args.codebook)

    prompts_dir = Path(args.prompts_dir)
    system_prompt = (prompts_dir / "system_prompt.md").read_text(encoding="utf-8")
    pass1_template = (prompts_dir / "pass1_prompt.md").read_text(encoding="utf-8")
    pass2_template = (prompts_dir / "pass2_prompt.md").read_text(encoding="utf-8")

    client = anthropic.Anthropic()

    all_quotes = []
    pass1_usage_log = []
    t0 = time.time()
    for theme in codebook["themes"]:
        quotes, usage, stop_reason = run_pass1(client, args.model, turns, theme, system_prompt, pass1_template)
        all_quotes.extend(quotes)
        pass1_usage_log.append({"theme_id": theme["id"], "usage": make_json_safe(usage), "stop_reason": stop_reason})

    for i, q in enumerate(all_quotes, start=1):
        q["quote_id"] = f"{args.interview_id}-Q{i:03d}"

    codes_with_quotes = {q["code"] for q in all_quotes}
    codes_with_no_quotes = [
        c["id"] for theme in codebook["themes"] for c in theme["codes"]
        if c["id"] not in codes_with_quotes
    ]

    pass1_output = {
        "interview_id": args.interview_id,
        "quotes": all_quotes,
        "codes_with_no_quotes": codes_with_no_quotes,
    }
    (outdir / "pass1.json").write_text(
        json.dumps(pass1_output, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    t1 = time.time()

    interpretations, pass2_usage, pass2_stop_reason = run_pass2(
        client, args.model, system_prompt, pass2_template, all_quotes, codebook
    )

    quote_by_id = {q["quote_id"]: q for q in all_quotes}
    pass2_output = {"interview_id": args.interview_id, "interpretations": []}
    for interp in interpretations:
        source_quote = quote_by_id.get(interp["quote_id"], {})
        pass2_output["interpretations"].append(
            {
                **interp,
                "cited_text": source_quote.get("cited_text"),
                "code": source_quote.get("code"),
                "theme_id": source_quote.get("theme_id"),
                "speakers": source_quote.get("speakers"),
                "turn_ids": source_quote.get("turn_ids"),
            }
        )
    (outdir / "pass2.json").write_text(
        json.dumps(pass2_output, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    t2 = time.time()

    def file_hash(p: Path) -> str:
        return hashlib.sha256(p.read_bytes()).hexdigest()[:16]

    metadata = {
        "interview_id": args.interview_id,
        "model": args.model,
        "codebook_hash": file_hash(Path(args.codebook)),
        "pass1_prompt_hash": file_hash(prompts_dir / "pass1_prompt.md"),
        "pass2_prompt_hash": file_hash(prompts_dir / "pass2_prompt.md"),
        "system_prompt_hash": file_hash(prompts_dir / "system_prompt.md"),
        "pass1_calls": len(codebook["themes"]),
        "pass1_usage_per_theme": pass1_usage_log,
        "pass2_usage": make_json_safe(pass2_usage),
        "timing_seconds": {"pass1": round(t1 - t0, 2), "pass2": round(t2 - t1, 2)},
        "quote_count": len(all_quotes),
        "codes_with_no_quotes": codes_with_no_quotes,
    }
    (outdir / "metadata.json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print(f"Done. {len(all_quotes)} quotes found. Files written to {outdir}/")


if __name__ == "__main__":
    main()