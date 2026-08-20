"""
segment_transcript.py

Converts a raw, speaker-labeled interview transcript (.txt) into full
conversational turns. Student turns are the authoritative quote units for
Pass 1; interviewer turns remain available for human-readable reference.
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
def is_student_speaker(speaker: str) -> bool:
    return speaker.lower().startswith("student ")


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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="Raw transcript .txt path")
    ap.add_argument("--interview-id", required=True, help="e.g. I01")
    ap.add_argument("--output", required=True, help="Output .json path")
    args = ap.parse_args()

    raw = Path(args.input).read_text(encoding="utf-8")
    turns = segment(raw, args.interview_id)

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(
        json.dumps(
            {"interview_id": args.interview_id, "turns": turns},
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    student_turns = sum(is_student_speaker(turn["speaker"]) for turn in turns)
    print(f"Wrote {len(turns)} turns ({student_turns} student quote units) to {args.output}")


if __name__ == "__main__":
    main()