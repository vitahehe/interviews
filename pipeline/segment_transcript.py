"""
segment_transcript.py

Converts a raw, speaker-labeled interview transcript (.txt) into a list of
turns: [{"turn_id": "I01-T001", "speaker": "student 1", "text": "..."}, ...]

Why this exists as a separate, deterministic step (not left to the AI):
segmentation is a mechanical parsing task with a single correct answer given
the file's format. Doing it in code, once, and saving the result, means every
later pass1 call for this interview cites against the *same* fixed turn
indexing,  which is what makes citation offsets (start_block_index /
end_block_index, see Anthropic's Citations docs on custom content documents)
reliably map back to a specific turn every time.
"""

import argparse
import json
import re
from pathlib import Path

# Recognised speaker-label lines in this transcript format. Extend if a new
SPEAKER_LINE = re.compile(r"^(?:[Ss]tudent\s+\d+|Bjarke)$")


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
            # Ignore file-header lines that appear before any speaker is seen
            # (e.g. "Monday 20260223 Kvant1 lab.m4a, ..." and "level: bachelors").
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
        json.dumps({"interview_id": args.interview_id, "turns": turns}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"Wrote {len(turns)} turns to {args.output}")


if __name__ == "__main__":
    main()