from __future__ import annotations
import argparse
import csv
import hashlib
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
import anthropic
from prompts import SYSTEM_PROMPT, build_user_prompt, BROAD_TOPICS

from dotenv import load_dotenv
import os

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")

api_key = os.getenv("ANTHROPIC_API_KEY")

if not api_key:
    raise EnvironmentError("ANTHROPIC_API_KEY is not set. Please set it before running this script.")


DEFAULT_INPUT_DIR = Path("transcription/test")
DEFAULT_OUTPUT_DIR = Path("annotation/outputs")
DEFAULT_MODEL = "claude-sonnet-4-6"
DEFAULT_MAX_TOKENS = 4000
DEFAULT_BATCH_SIZE = 20


def normalize_text(text: str) -> str:
    """Normalize line endings and remove excessive whitespace while preserving paragraphs."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def guess_speaker_type(speaker: str) -> str:
    """Guess whether a speaker is interviewer or student."""
    s = speaker.lower().strip()
    if any(token in s for token in ["interviewer", "interview", "teacher", "lecturer", "ta", "assistant", "bjarke"]):
        return "interviewer"
    if any(token in s for token in ["student", "participant", "pupil"]):
        return "student"
    return "unknown"


def split_into_speaker_blocks(text: str) -> list[dict[str, str]]:
    """
    Split a transcript into speaker blocks.

    If no speaker markers are detected, it falls back to paragraph chunks.
    """
    text = normalize_text(text)
    lines = text.split("\n")

    speaker_pattern = re.compile(
        r"^\s*(?P<speaker>"
        r"Interviewer|Interviewee|Moderator|Teacher|Lecturer|TA|Assistant|"
        r"Student\s*\d+|Participant\s*\d+|S\d+|P\d+|"
        r"[A-ZÆØÅČŠŽÁÉÍÓÚÝÄÖÜ][\wÆØÅæøåČŠŽčšžÁÉÍÓÚÝáéíóúýÄÖÜäöü .'-]{1,40}"
        r")\s*[:\-–]\s*(?P<content>.*)$"
    )

    blocks: list[dict[str, str]] = []
    current_speaker = "UNKNOWN"
    current_content: list[str] = []

    detected_speaker = False

    for line in lines:
        match = speaker_pattern.match(line)
        if match:
            detected_speaker = True
            if current_content:
                blocks.append({
                    "speaker": current_speaker.strip(),
                    "text": "\n".join(current_content).strip(),
                })
            current_speaker = match.group("speaker").strip()
            first_content = match.group("content").strip()
            current_content = [first_content] if first_content else []
        else:
            if line.strip():
                current_content.append(line.strip())
            else:
                # Preserve paragraph break inside the same speaker block.
                if current_content and current_content[-1] != "":
                    current_content.append("")

    if current_content:
        blocks.append({
            "speaker": current_speaker.strip(),
            "text": "\n".join(current_content).strip(),
        })

    if detected_speaker and blocks:
        return [b for b in blocks if b["text"]]

    #no speaker markers found, split by paragraphs.
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    return [{"speaker": "UNKNOWN", "text": p} for p in paragraphs]


def split_long_block(text: str, max_words: int = 220) -> list[str]:
    """
    Split long blocks into smaller chunks by sentence while avoiding tiny fragments.
    This keeps chunks interpretable for annotation.
    """
    words = text.split()
    if len(words) <= max_words:
        return [text.strip()]

    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    chunks = []
    current = []

    for sentence in sentences:
        tentative = " ".join(current + [sentence]).strip()
        if len(tentative.split()) <= max_words:
            current.append(sentence)
        else:
            if current:
                chunks.append(" ".join(current).strip())
            current = [sentence]

    if current:
        chunks.append(" ".join(current).strip())

    # If sentence splitting failed, fall back to word windows.
    final_chunks = []
    for chunk in chunks:
        if len(chunk.split()) <= max_words:
            final_chunks.append(chunk)
        else:
            w = chunk.split()
            for i in range(0, len(w), max_words):
                final_chunks.append(" ".join(w[i:i + max_words]))

    return [c for c in final_chunks if c.strip()]


def make_chunks(transcript_text: str, interview_id: str) -> list[dict[str, Any]]:
    """Create conservative transcript chunks with context windows."""
    blocks = split_into_speaker_blocks(transcript_text)
    raw_chunks: list[dict[str, Any]] = []

    chunk_number = 1
    for block in blocks:
        speaker = block["speaker"]
        speaker_type = guess_speaker_type(speaker)
        participant_id = speaker if speaker_type == "student" else ""

        for part in split_long_block(block["text"]):
            chunk_id = f"{interview_id}_C{chunk_number:04d}"
            raw_chunks.append({
                "interview_id": interview_id,
                "chunk_id": chunk_id,
                "speaker": speaker,
                "speaker_type": speaker_type,
                "participant_id": participant_id,
                "text": part,
            })
            chunk_number += 1


    chunks = []
    for i, chunk in enumerate(raw_chunks):
        previous_context = raw_chunks[i - 1]["text"][:500] if i > 0 else ""
        next_context = raw_chunks[i + 1]["text"][:500] if i < len(raw_chunks) - 1 else ""
        enriched = dict(chunk)
        enriched["previous_context"] = previous_context
        enriched["next_context"] = next_context
        chunks.append(enriched)

    return chunks


def batch_items(items: list[dict[str, Any]], batch_size: int) -> list[list[dict[str, Any]]]:
    """Split list into batches."""
    return [items[i:i + batch_size] for i in range(0, len(items), batch_size)]


def extract_json(text: str) -> dict[str, Any]:
    """
    Extract JSON from a model response.
    The prompt asks for pure JSON, but this fallback handles accidental wrapping.
    """
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = text[start:end + 1]
        return json.loads(candidate)

    raise ValueError("Could not parse model output as JSON.")


def call_claude_for_annotations(
    client: Any,
    model: str,
    batch: list[dict[str, Any]],
    temperature: float = 0.0,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> list[dict[str, Any]]:

    user_prompt = build_user_prompt(batch)

    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=[
            {
                "type": "text",
                "text": SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[
            {"role": "user", "content": user_prompt},
        ],
        temperature=temperature,
    )

    output_text = response.content[0].text

    parsed = extract_json(output_text)
    annotations = parsed.get("annotations", [])

    if not isinstance(annotations, list):
        raise ValueError("Model JSON did not contain a list under 'annotations'.")

    return annotations


def validate_and_complete_annotations(
    chunks: list[dict[str, Any]],
    annotations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Make sure every chunk has an annotation.
    If the model missed a chunk, create a conservative fallback annotation.
    """
    annotation_by_id = {
        ann.get("chunk_id"): ann
        for ann in annotations
        if isinstance(ann, dict) and ann.get("chunk_id")
    }

    completed = []
    for chunk in chunks:
        cid = chunk["chunk_id"]
        ann = annotation_by_id.get(cid)

        if ann is None:
            ann = {
                "chunk_id": cid,
                "broad_topics": ["OTHER_RELEVANT"],
                "confidence": 0.0,
                "theory_cues": ["model_missed_chunk"],
                "annotation_reason": "Fallback annotation: the model did not return an annotation for this chunk.",
                "valence": "unclear",
                "possible_tension": "human review needed because model missed this chunk",
                "human_review_needed": True,
            }

        broad_topics = ann.get("broad_topics", [])
        if not isinstance(broad_topics, list) or not broad_topics:
            broad_topics = ["OTHER_RELEVANT"]

        cleaned_topics = []
        for topic in broad_topics:
            if topic in BROAD_TOPICS and topic not in cleaned_topics:
                cleaned_topics.append(topic)

        if not cleaned_topics:
            cleaned_topics = ["OTHER_RELEVANT"]

        try:
            confidence = float(ann.get("confidence", 0.0))
        except (TypeError, ValueError):
            confidence = 0.0
        confidence = max(0.0, min(1.0, confidence))

        completed.append({
            **chunk,
            "broad_topics": cleaned_topics,
            "confidence": confidence,
            "theory_cues": ann.get("theory_cues", []),
            "annotation_reason": ann.get("annotation_reason", ""),
            "valence": ann.get("valence", "unclear"),
            "possible_tension": ann.get("possible_tension", "none"),
            "human_review_needed": bool(ann.get("human_review_needed", confidence < 0.6)),
        })

    return completed


def safe_filename(path: Path) -> str:
    """Create stable interview id from filename."""
    stem = re.sub(r"[^A-Za-z0-9_]+", "_", path.stem).strip("_")
    if not stem:
        digest = hashlib.sha1(str(path).encode()).hexdigest()[:8]
        stem = f"interview_{digest}"
    return stem


def write_chunks_csv(chunks: list[dict[str, Any]], path: Path) -> None:
    """Write raw chunks before annotation."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "interview_id",
        "chunk_id",
        "speaker",
        "speaker_type",
        "participant_id",
        "text",
        "previous_context",
        "next_context",
    ]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in chunks:
            writer.writerow({field: row.get(field, "") for field in fields})


def write_annotations_csv(rows: list[dict[str, Any]], path: Path) -> None:
    """Write annotated chunks as reviewable CSV."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "interview_id",
        "chunk_id",
        "speaker",
        "speaker_type",
        "participant_id",
        "text",
        "previous_context",
        "next_context",
        "broad_topics",
        "confidence",
        "theory_cues",
        "annotation_reason",
        "valence",
        "possible_tension",
        "human_review_needed",
    ]

    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            formatted = dict(row)
            formatted["broad_topics"] = "; ".join(row.get("broad_topics", []))
            formatted["theory_cues"] = "; ".join(row.get("theory_cues", [])) if isinstance(row.get("theory_cues"), list) else row.get("theory_cues", "")
            writer.writerow({field: formatted.get(field, "") for field in fields})


def write_annotations_jsonl(rows: list[dict[str, Any]], path: Path) -> None:
    """Write annotated chunks as JSONL for later pipeline stages."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def find_input_files(input_dir: Path, single_file: Path | None) -> list[Path]:
    """Find transcript files."""
    if single_file:
        if not single_file.exists():
            raise FileNotFoundError(f"File not found: {single_file}")
        return [single_file]

    if not input_dir.exists():
        raise FileNotFoundError(f"Input directory not found: {input_dir}")

    files = sorted(input_dir.glob("*.txt"))
    if not files:
        raise FileNotFoundError(f"No .txt files found in: {input_dir}")

    return files


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Broad AI-assisted annotation for laboratory physics interview transcripts."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT_DIR,
        help=f"Input folder containing .txt transcripts. Default: {DEFAULT_INPUT_DIR}",
    )
    parser.add_argument(
        "--file",
        type=Path,
        default=None,
        help="Optional single .txt transcript file to annotate.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Output folder. Default: {DEFAULT_OUTPUT_DIR}",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=DEFAULT_MODEL,
        help=f"Claude model name. Default: {DEFAULT_MODEL}",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help=f"Number of chunks per API call. Default: {DEFAULT_BATCH_SIZE}",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=DEFAULT_MAX_TOKENS,
        help=f"Max tokens for each Claude response. Default: {DEFAULT_MAX_TOKENS}",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only chunk transcripts and write all_chunks.csv; do not call the API.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_dir: Path = args.output
    output_dir.mkdir(parents=True, exist_ok=True)

    files = find_input_files(args.input, args.file)

    all_chunks: list[dict[str, Any]] = []
    all_annotated_rows: list[dict[str, Any]] = []

    print(f"Found {len(files)} transcript file(s).")

    for file_path in files:
        interview_id = safe_filename(file_path)
        print(f"\nReading: {file_path}")
        transcript_text = file_path.read_text(encoding="utf-8", errors="replace")
        chunks = make_chunks(transcript_text, interview_id)
        all_chunks.extend(chunks)
        print(f"Created {len(chunks)} chunks for {interview_id}.")

    chunks_csv = output_dir / "all_chunks.csv"
    write_chunks_csv(all_chunks, chunks_csv)
    print(f"\nSaved chunks: {chunks_csv}")

    if args.dry_run:
        print("Dry run complete. No API calls made.")
        return

    if anthropic is None:
        raise ImportError("The anthropic package is not installed. Run: pip install anthropic")

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise EnvironmentError("ANTHROPIC_API_KEY is not set. Please set it before running this script.")

    client = anthropic.Anthropic(api_key=api_key)

    for file_path in files:
        interview_id = safe_filename(file_path)
        interview_chunks = [c for c in all_chunks if c["interview_id"] == interview_id]
        interview_annotations: list[dict[str, Any]] = []

        print(f"\nAnnotating interview: {interview_id}")
        for idx, batch in enumerate(batch_items(interview_chunks, args.batch_size), start=1):
            print(f"  API batch {idx}: {len(batch)} chunks")
            model_annotations = call_claude_for_annotations(
                client=client,
                model=args.model,
                batch=batch,
                temperature=0.0,
                max_tokens=args.max_tokens,
            )
            completed = validate_and_complete_annotations(batch, model_annotations)
            interview_annotations.extend(completed)

        per_file_csv = output_dir / f"{interview_id}_broad_annotations.csv"
        write_annotations_csv(interview_annotations, per_file_csv)
        print(f"  Saved: {per_file_csv}")

        all_annotated_rows.extend(interview_annotations)

    all_csv = output_dir / "all_broad_annotations.csv"
    all_jsonl = output_dir / "all_broad_annotations.jsonl"

    write_annotations_csv(all_annotated_rows, all_csv)
    write_annotations_jsonl(all_annotated_rows, all_jsonl)

    metadata = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "input": str(args.input),
        "single_file": str(args.file) if args.file else None,
        "output": str(output_dir),
        "model": args.model,
        "batch_size": args.batch_size,
        "n_files": len(files),
        "n_chunks": len(all_chunks),
        "n_annotated_rows": len(all_annotated_rows),
        "stage": "broad_annotation",
    }
    (output_dir / "run_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    print("\nDone.")
    print(f"Saved combined CSV:   {all_csv}")
    print(f"Saved combined JSONL: {all_jsonl}")
    print(f"Saved metadata:       {output_dir / 'run_metadata.json'}")


if __name__ == "__main__":
    main()