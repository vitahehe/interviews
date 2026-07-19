"""
segment_transcript.py

Converts a raw, speaker-labeled interview transcript (.txt) into:
  - turns: full conversational turns (kept for human-readable reference)
  - sentences: sentence-level units, each tagged with its parent turn_id and
    speaker — these become the citable content blocks for Pass 1.

Why sentence-level, not turn-level: Anthropic's citations mechanism can only
point at a whole content block, never a substring within one. Splitting to
sentence level lets a citation land on the specific clause that matters.

Why this is still a separate, deterministic step (not left to the AI):
sentence splitting has a mechanically-defined answer given punctuation --
keep this reliable and free, save the model's attention for judgment calls.
"""

import argparse
import json
import re
from pathlib import Path

SPEAKER_LINE = re.compile(r"^(?:[Ss]tudent\s+\d+|Bjarke)$")

# Splits after a sentence-ending punctuation mark, only where followed by
# whitespace -- deliberately does NOT split inside "..." itself (no
# whitespace between the dots), but does split after "..." once followed by
# a space, and after a normal ".", "?", or "!".
SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+")


def segment(raw_text: str, interview_id: str) -> list[dict]:
    lines = raw_text.splitlines()
    turns: list[dict] = []
    current_speaker = None
    current_lines: list[str] = []

    def flush():
        if current_speaker is not None:
            text = "\n".join(current_lines).strip()
            if text:
                turns.append(
                    {
                        "turn_id": f"{interview_id}-T{len(turns) + 1:03d}",
                        "speaker": current_speaker,
                        "text": text,
                    }
                )

    for line in lines:
        stripped = line.strip()
        if SPEAKER_LINE.match(stripped):
            flush()
            current_speaker = stripped
            current_lines = []
        else:
            if current_speaker is not None:
                current_lines.append(line)
    flush()
    return turns


def split_into_sentences(turns: list[dict]) -> list[dict]:
    """Flatten turns into sentence-level citable units."""
    sentences: list[dict] = []
    for turn in turns:
        raw_pieces = SENTENCE_BOUNDARY.split(turn["text"])
        pieces = [p.strip() for p in raw_pieces if p.strip()]
        if not pieces:
            continue
        for i, piece in enumerate(pieces, start=1):
            sentences.append(
                {
                    "sentence_id": f"{turn['turn_id']}-S{i:02d}",
                    "turn_id": turn["turn_id"],
                    "speaker": turn["speaker"],
                    "text": piece,
                }
            )
    return sentences


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def verify_no_data_loss(turns: list[dict], sentences: list[dict]) -> None:
    """Reconstructs each turn from its sentences and confirms nothing was
    dropped in the split. Whitespace differences are ignored (splitting
    necessarily changes spacing), but every word must survive."""
    by_turn: dict[str, list[str]] = {}
    for s in sentences:
        by_turn.setdefault(s["turn_id"], []).append(s["text"])

    for turn in turns:
        original = _normalize(turn["text"])
        reconstructed = _normalize(" ".join(by_turn.get(turn["turn_id"], [])))
        if reconstructed != original:
            print(
                f"WARNING: possible data loss/alteration in {turn['turn_id']}\n"
                f"  original:      {original!r}\n"
                f"  reconstructed: {reconstructed!r}"
            )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="Raw transcript .txt path")
    ap.add_argument("--interview-id", required=True, help="e.g. I01")
    ap.add_argument("--output", required=True, help="Output .json path")
    args = ap.parse_args()

    raw = Path(args.input).read_text(encoding="utf-8")
    turns = segment(raw, args.interview_id)
    sentences = split_into_sentences(turns)
    verify_no_data_loss(turns, sentences)

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(
        json.dumps(
            {"interview_id": args.interview_id, "turns": turns, "sentences": sentences},
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    print(f"Wrote {len(turns)} turns / {len(sentences)} sentences to {args.output}")


if __name__ == "__main__":
    main()