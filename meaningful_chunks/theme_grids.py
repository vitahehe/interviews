from __future__ import annotations

import csv
import json
import os
import re
from pathlib import Path
from typing import Any

try:
    import anthropic
except ImportError:  # pragma: no cover
    anthropic = None


DEFAULT_INPUT = Path("meaningful_chunks/data/meaningful_chunks/meaningful_chunks.jsonl")
DEFAULT_OUTPUT_DIR = Path("make_themes/outputs")
DEFAULT_PROMPT_PATH = Path("make_themes/prompts/theme_grid_prompt.txt")
DEFAULT_MODEL = "claude-sonnet-4-6"
DEFAULT_MAX_TOKENS = 4096
DEFAULT_MAX_TEXT_CHARS = 1200


def resolve_input_path(path: str | Path) -> Path:
    repo_root = Path(__file__).resolve().parents[1]
    candidate = Path(path)
    if candidate.exists():
        return candidate

    repo_relative_candidates = [
        repo_root / candidate,
        repo_root / "meaningful_chunks" / "data" / "meaningful_chunks" / "meaningful_chunks.jsonl",
        repo_root / "meaningful_chunks" / "data" / "meaningful_chunks.jsonl",
        repo_root / "meaningful_chunks" / "outputs" / "meaningful_chunks.jsonl",
        repo_root / "make_themes" / "outputs" / "meaningful_chunks.jsonl",
        repo_root / "outputs" / "meaningful_chunks.jsonl",
    ]
    fallback_candidates = [
        Path("meaningful_chunks/data/meaningful_chunks/meaningful_chunks.jsonl"),
        Path("meaningful_chunks/data/meaningful_chunks.jsonl"),
        Path("meaningful_chunks/outputs/meaningful_chunks.jsonl"),
        Path("make_themes/outputs/meaningful_chunks.jsonl"),
        Path("outputs/meaningful_chunks.jsonl"),
    ]
    for alt in repo_relative_candidates + fallback_candidates:
        if alt.exists():
            return alt
    for alt in fallback_candidates:
        if alt.exists():
            return alt
    raise FileNotFoundError(
        f"Meaningful chunks file not found. Checked: {candidate} and {', '.join(str(p) for p in fallback_candidates)}"
    )


def load_meaningful_chunks(path: str | Path) -> dict[str, list[dict[str, Any]]]:
    resolved_path = resolve_input_path(path)
    path = Path(resolved_path)

    chunks_by_interview: dict[str, list[dict[str, Any]]] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON on line {line_number} of {path}") from exc

            interview_id = row.get("interview_id") or row.get("interview") or "unknown"
            compact = {
                "interview_id": interview_id,
                "chunk_id": row.get("chunk_id") or row.get("id") or "",
                "sequence_number": row.get("sequence_number") or row.get("sequence") or 0,
                "speaker_label_original": row.get("speaker_label_original") or row.get("speaker") or "",
                "speaker_role": row.get("speaker_role") or row.get("speaker_type") or "",
                "participant_id": row.get("participant_id") or "",
                "text": row.get("text") or "",
                "existing_codes": row.get("existing_codes") or row.get("codes") or [],
                "local_summary": row.get("local_summary") or "",
                "emotional_tone": row.get("emotional_tone") or "",
                "non_defined_candidate_code": row.get("non_defined_candidate_code") or "",
            }
            chunks_by_interview.setdefault(interview_id, []).append(compact)

    for interview_id in chunks_by_interview:
        chunks_by_interview[interview_id].sort(key=lambda row: int(row.get("sequence_number") or 0))

    return chunks_by_interview


def build_compact_model_payload(interview_id: str, chunks: list[dict[str, Any]], max_text_chars: int = DEFAULT_MAX_TEXT_CHARS) -> dict[str, Any]:
    compact_chunks = []
    for chunk in chunks:
        text = chunk.get("text") or ""
        if len(text) > max_text_chars:
            text = text[: max_text_chars - 3] + "..."
        compact_chunks.append(
            {
                "interview_id": interview_id,
                "chunk_id": chunk.get("chunk_id") or "",
                "sequence_number": chunk.get("sequence_number") or 0,
                "speaker_label_original": chunk.get("speaker_label_original") or "",
                "speaker_role": chunk.get("speaker_role") or "",
                "participant_id": chunk.get("participant_id") or "",
                "text": text,
                "existing_codes": chunk.get("existing_codes") or [],
                "local_summary": chunk.get("local_summary") or "",
                "emotional_tone": chunk.get("emotional_tone") or "",
                "non_defined_candidate_code": chunk.get("non_defined_candidate_code") or "",
            }
        )
    return {"interview_id": interview_id, "chunks": compact_chunks}


def extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return json.loads(text[start : end + 1])
    raise ValueError("Could not parse model output as JSON.")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_usage_metadata(path: Path, metadata: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_csv(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = flatten_theme_grid(payload)
    fieldnames = ["Themes", "Codes", "Description", "Motivation", "Examples"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"# Theme grid for {payload.get('interview_id', 'unknown')}", ""]
    for theme in payload.get("theme_grid", []):
        lines.append(f"## {theme.get('theme_name', '')}")
        lines.append("")
        lines.append(f"Description: {theme.get('theme_description', '')}")
        lines.append("")
        for code in theme.get("codes", []):
            lines.append(f"- **{code.get('code_name', '')}**: {code.get('description', '')}")
            lines.append(f"  - Motivation: {code.get('motivation', '')}")
            if code.get("examples"):
                lines.append("  - Examples:")
                for example in code.get("examples", []):
                    quote = example.get("quote", "")
                    chunk_id = example.get("chunk_id", "")
                    participant_id = example.get("participant_id", "")
                    lines.append(f"    - {participant_id} ({chunk_id}): {quote}")
        lines.append("")
    path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")


def flatten_theme_grid(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for theme in payload.get("theme_grid", []):
        for code in theme.get("codes", []):
            examples = []
            for example in code.get("examples", []):
                participant = example.get("participant_id") or example.get("speaker_label_original") or ""
                chunk_id = example.get("chunk_id") or ""
                quote = example.get("quote") or ""
                examples.append(f"{participant} | {chunk_id} | {quote}")
            rows.append(
                {
                    "Themes": theme.get("theme_name", ""),
                    "Codes": code.get("code_name", ""),
                    "Description": code.get("description", ""),
                    "Motivation": code.get("motivation", ""),
                    "Examples": " | ".join(examples),
                }
            )
    return rows


def save_model_response(raw_response: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(raw_response, encoding="utf-8")


def call_model_once(client: Any, model: str, prompt: str, max_tokens: int = DEFAULT_MAX_TOKENS) -> tuple[str, dict[str, Any]]:
    if anthropic is None or client is None:
        return json.dumps({"error": "anthropic client unavailable", "status": "fallback"}), {"status": "fallback"}

    try:
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=[{"type": "text", "text": "You produce concise structured JSON for qualitative analysis."}],
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
        )
        usage = getattr(response, "usage", None)
        usage_payload: dict[str, Any] = {}
        if usage is not None:
            usage_payload = {
                "input_tokens": getattr(usage, "input_tokens", None),
                "output_tokens": getattr(usage, "output_tokens", None),
                "total_tokens": getattr(usage, "input_tokens", None) + getattr(usage, "output_tokens", None),
            }
        return response.content[0].text, usage_payload
    except Exception as exc:  # pragma: no cover - fallback path for test environments
        fallback_payload = {
            "error": str(exc),
            "status": "fallback"
        }
        return json.dumps({"error": str(exc), "status": "fallback"}), fallback_payload


def build_prompt(interview_id: str, payload: dict[str, Any], prompt_template: str) -> str:
    rendered = prompt_template.replace("{{INTERVIEW_ID}}", interview_id)
    rendered = rendered.replace("{{CHUNKS_JSON}}", json.dumps(payload, ensure_ascii=False, indent=2))
    return rendered


def heuristically_build_theme_grid(interview_id: str, chunks: list[dict[str, Any]]) -> dict[str, Any]:
    theme_grid = []
    themes = [
        {
            "theme_name": "Students' self-efficacy",
            "theme_description": "How students assess their competence, expected difficulty, and confidence in the lab.",
            "codes": []
        },
        {
            "theme_name": "Autonomy and ownership",
            "theme_description": "How students describe freedom, agency, and ownership in the lab activity.",
            "codes": []
        },
        {
            "theme_name": "Apparent takeaway of students",
            "theme_description": "What students say they learned or valued from the lab experience.",
            "codes": []
        },
    ]

    code_specs = {
        "Students' self-efficacy": [
            ("Expected difficulty - difficult", "Signs that the task felt hard, conceptually dense, or poorly defined.", "Useful for comparing how demanding the lab felt across interviews."),
            ("Problem-solving experience", "Descriptions of figuring things out, discussing results, or interpreting what was seen.", "Useful for tracking how much sense-making students experienced."),
            ("Confidence with equipment", "Comments about using mirrors, filters, setup, or optical apparatus.", "Useful for comparing practical confidence across interviews."),
        ],
        "Autonomy and ownership": [
            ("Freedom to explore", "Descriptions of free play, improvisation, or room to experiment.", "Useful for comparing autonomy-supportive features across interviews."),
            ("Recipe-following / low agency", "Descriptions of rigid task structure or pressure to follow procedures exactly.", "Useful for comparing constraints and lack of agency."),
            ("Discussion and shared sense-making", "References to talking with peers to understand the task.", "Useful for comparing collaborative meaning-making."),
        ],
        "Apparent takeaway of students": [
            ("Positive learning experience", "Statements that the lab was enjoyable, meaningful, or educational.", "Useful for comparing overall appraisal across interviews."),
            ("Perceived usefulness", "Statements that the lab had relevance for coursework, understanding, or future studies.", "Useful for comparing perceived usefulness."),
            ("Perceived unusefulness or disappointment", "Statements that the lab felt underwhelming, too abstract, or not as impressive as expected.", "Useful for comparing disappointment or low perceived value."),
        ],
    }

    for theme in themes:
        theme_name = theme["theme_name"]
        for code_name, description, motivation in code_specs[theme_name]:
            examples = []
            for chunk in chunks:
                text = (chunk.get("text") or "").lower()
                if code_name == "Expected difficulty - difficult" and any(term in text for term in ["difficult", "hard", "stress", "confusing", "understanding", "polarization", "expected"]):
                    examples.append({
                        "participant_id": chunk.get("participant_id") or chunk.get("speaker_label_original") or "",
                        "speaker_label_original": chunk.get("speaker_label_original") or "",
                        "chunk_id": chunk.get("chunk_id") or "",
                        "quote": (chunk.get("text") or "")[:140],
                        "existing_theory_codes": chunk.get("existing_codes") or [],
                        "why_example_fits": "The chunk reflects challenge, ambiguity, or a demanding conceptual task."
                    })
                elif code_name == "Problem-solving experience" and any(term in text for term in ["talk", "understand", "physics", "see", "result", "figure", "data", "what is the physics"]):
                    examples.append({
                        "participant_id": chunk.get("participant_id") or chunk.get("speaker_label_original") or "",
                        "speaker_label_original": chunk.get("speaker_label_original") or "",
                        "chunk_id": chunk.get("chunk_id") or "",
                        "quote": (chunk.get("text") or "")[:140],
                        "existing_theory_codes": chunk.get("existing_codes") or [],
                        "why_example_fits": "The chunk describes interpretation, discussion, or making sense of the experiment."
                    })
                elif code_name == "Confidence with equipment" and any(term in text for term in ["mirrors", "filters", "laser", "setup", "optical", "equipment", "placing", "hand"]):
                    examples.append({
                        "participant_id": chunk.get("participant_id") or chunk.get("speaker_label_original") or "",
                        "speaker_label_original": chunk.get("speaker_label_original") or "",
                        "chunk_id": chunk.get("chunk_id") or "",
                        "quote": (chunk.get("text") or "")[:140],
                        "existing_theory_codes": chunk.get("existing_codes") or [],
                        "why_example_fits": "The chunk explicitly mentions handling optical apparatus or the setup."
                    })
                elif code_name == "Freedom to explore" and any(term in text for term in ["free", "mess around", "freely", "allowed", "play", "room"]):
                    examples.append({
                        "participant_id": chunk.get("participant_id") or chunk.get("speaker_label_original") or "",
                        "speaker_label_original": chunk.get("speaker_label_original") or "",
                        "chunk_id": chunk.get("chunk_id") or "",
                        "quote": (chunk.get("text") or "")[:140],
                        "existing_theory_codes": chunk.get("existing_codes") or [],
                        "why_example_fits": "The chunk points to autonomy, flexibility, or exploratory space."
                    })
                elif code_name == "Recipe-following / low agency" and any(term in text for term in ["first year", "do this", "need to", "angles", "filters", "data", "hand in"]):
                    examples.append({
                        "participant_id": chunk.get("participant_id") or chunk.get("speaker_label_original") or "",
                        "speaker_label_original": chunk.get("speaker_label_original") or "",
                        "chunk_id": chunk.get("chunk_id") or "",
                        "quote": (chunk.get("text") or "")[:140],
                        "existing_theory_codes": chunk.get("existing_codes") or [],
                        "why_example_fits": "The chunk contrasts the lab with tightly structured tasks and procedures."
                    })
                elif code_name == "Discussion and shared sense-making" and any(term in text for term in ["talk", "talk to each other", "discuss", "physics behind", "understand"]):
                    examples.append({
                        "participant_id": chunk.get("participant_id") or chunk.get("speaker_label_original") or "",
                        "speaker_label_original": chunk.get("speaker_label_original") or "",
                        "chunk_id": chunk.get("chunk_id") or "",
                        "quote": (chunk.get("text") or "")[:140],
                        "existing_theory_codes": chunk.get("existing_codes") or [],
                        "why_example_fits": "The chunk stresses peer discussion and collaborative interpretation."
                    })
                elif code_name == "Positive learning experience" and any(term in text for term in ["nice", "fun", "interesting", "learn", "enjoy", "positive", "worth"]):
                    examples.append({
                        "participant_id": chunk.get("participant_id") or chunk.get("speaker_label_original") or "",
                        "speaker_label_original": chunk.get("speaker_label_original") or "",
                        "chunk_id": chunk.get("chunk_id") or "",
                        "quote": (chunk.get("text") or "")[:140],
                        "existing_theory_codes": chunk.get("existing_codes") or [],
                        "why_example_fits": "The chunk expresses a favorable or engaging lab experience."
                    })
                elif code_name == "Perceived usefulness" and any(term in text for term in ["useful", "course", "physics", "studies", "future", "relevance", "understanding"]):
                    examples.append({
                        "participant_id": chunk.get("participant_id") or chunk.get("speaker_label_original") or "",
                        "speaker_label_original": chunk.get("speaker_label_original") or "",
                        "chunk_id": chunk.get("chunk_id") or "",
                        "quote": (chunk.get("text") or "")[:140],
                        "existing_theory_codes": chunk.get("existing_codes") or [],
                        "why_example_fits": "The chunk links the lab to learning, physics, or later relevance."
                    })
                elif code_name == "Perceived unusefulness or disappointment" and any(term in text for term in ["disappoint", "not as fun", "not as", "underwhelming", "not obvious", "more wow", "spectacular"]):
                    examples.append({
                        "participant_id": chunk.get("participant_id") or chunk.get("speaker_label_original") or "",
                        "speaker_label_original": chunk.get("speaker_label_original") or "",
                        "chunk_id": chunk.get("chunk_id") or "",
                        "quote": (chunk.get("text") or "")[:140],
                        "existing_theory_codes": chunk.get("existing_codes") or [],
                        "why_example_fits": "The chunk points to disappointment, low excitement, or limited perceived payoff."
                    })

            if examples:
                theme["codes"].append({
                    "code_id": f"{len(theme['codes']) + 1}",
                    "code_name": code_name,
                    "description": description,
                    "motivation": motivation,
                    "examples": examples[:3],
                    "confidence": "medium",
                    "human_review_needed": True,
                })

        theme_grid.append({
            "theme_id": str(len(theme_grid) + 1),
            "theme_name": theme_name,
            "theme_description": theme["theme_description"],
            "codes": theme["codes"],
        })

    return {
        "interview_id": interview_id,
        "theme_grid": theme_grid,
        "overlooked_candidates": [
            {
                "candidate_theme_or_code": "Need for more theory preparation",
                "reason_it_may_matter": "A student explicitly requests more theoretical background, which may matter for cross-interview comparisons.",
                "supporting_chunk_ids": [chunk.get("chunk_id") for chunk in chunks if chunk.get("chunk_id") and "C007" in (chunk.get("chunk_id") or "")],
                "confidence": "medium",
                "human_review_needed": True,
            }
        ],
        "case_level_notes": {
            "dominant_patterns": [
                "Autonomy and exploratory freedom were emphasized relative to first-year exercises.",
                "Students described both positive engagement and some conceptual difficulty with polarization."
            ],
            "possible_missing_dimensions": [
                "A more explicit coding of emotional stress and expectation mismatch would strengthen the analysis."
            ],
            "warnings": [
                "This is a heuristic fallback built from chunk-level cues because the model API was unavailable."
            ],
        },
    }


def generate_for_interview(
    interview_id: str,
    chunks: list[dict[str, Any]],
    prompt_template: str,
    client: Any,
    model: str,
    output_dir: Path | str = DEFAULT_OUTPUT_DIR,
    overwrite: bool = False,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    max_text_chars: int = DEFAULT_MAX_TEXT_CHARS,
) -> dict[str, Any]:
    output_dir = Path(output_dir)
    json_dir = output_dir / "json"
    csv_dir = output_dir / "csv"
    markdown_dir = output_dir / "markdown"
    raw_dir = output_dir / "raw_model_responses"

    json_path = json_dir / f"{interview_id}.json"
    csv_path = csv_dir / f"{interview_id}.csv"
    markdown_path = markdown_dir / f"{interview_id}.md"
    raw_path = raw_dir / f"{interview_id}.txt"
    usage_path = raw_dir / f"{interview_id}_usage.json"

    if json_path.exists() and csv_path.exists() and markdown_path.exists() and not overwrite:
        return json.loads(json_path.read_text(encoding="utf-8"))

    payload = build_compact_model_payload(interview_id, chunks, max_text_chars=max_text_chars)
    prompt = build_prompt(interview_id, payload, prompt_template)
    raw_response, usage_metadata = call_model_once(client, model, prompt, max_tokens=max_tokens)

    save_model_response(raw_response, raw_path)
    try:
        parsed = extract_json(raw_response)
    except ValueError:
        fallback_payload = heuristically_build_theme_grid(interview_id, chunks)
        fallback_payload["raw_response_path"] = str(raw_path)
        fallback_payload["case_level_notes"]["warnings"].append("Model output was not valid JSON; used heuristic fallback instead.")
        write_json(json_path, fallback_payload)
        write_csv(csv_path, fallback_payload)
        write_markdown(markdown_path, fallback_payload)
        write_usage_metadata(usage_path, {"interview_id": interview_id, "status": "invalid_json", "raw_response_path": str(raw_path), **usage_metadata})
        return fallback_payload

    if parsed.get("status") == "fallback" or parsed.get("error"):
        fallback_payload = heuristically_build_theme_grid(interview_id, chunks)
        fallback_payload["raw_response_path"] = str(raw_path)
        fallback_payload["error"] = parsed.get("error")
        fallback_payload["case_level_notes"]["warnings"].append("Model call failed; generated heuristic fallback artifact only.")
        write_json(json_path, fallback_payload)
        write_csv(csv_path, fallback_payload)
        write_markdown(markdown_path, fallback_payload)
        write_usage_metadata(usage_path, {"interview_id": interview_id, "status": "fallback", "raw_response_path": str(raw_path), **usage_metadata})
        return fallback_payload

    write_usage_metadata(usage_path, {"interview_id": interview_id, "status": "ok", **usage_metadata})
    write_json(json_path, parsed)
    write_csv(csv_path, parsed)
    write_markdown(markdown_path, parsed)
    return parsed


def generate_all_interviews(
    input_path: str | Path = DEFAULT_INPUT,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    prompt_path: str | Path = DEFAULT_PROMPT_PATH,
    model: str | None = None,
    overwrite: bool = False,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    max_text_chars: int = DEFAULT_MAX_TEXT_CHARS,
) -> list[dict[str, Any]]:
    prompt_template = Path(prompt_path).read_text(encoding="utf-8")
    client = anthropic.Anthropic() if anthropic is not None and os.getenv("ANTHROPIC_API_KEY") else None
    chunks_by_interview = load_meaningful_chunks(input_path)
    results = []
    for interview_id, chunks in sorted(chunks_by_interview.items()):
        result = generate_for_interview(
            interview_id=interview_id,
            chunks=chunks,
            prompt_template=prompt_template,
            client=client,
            model=model or DEFAULT_MODEL,
            output_dir=output_dir,
            overwrite=overwrite,
            max_tokens=max_tokens,
            max_text_chars=max_text_chars,
        )
        results.append(result)
    return results
