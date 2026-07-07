#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from meaningful_chunks.theme_grids import DEFAULT_INPUT, DEFAULT_OUTPUT_DIR, DEFAULT_PROMPT_PATH, generate_all_interviews


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate one theme-grid JSON/CSV/Markdown file per interview from meaningful chunks.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="Path to the meaningful chunks JSONL file.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="Directory for generated outputs.")
    parser.add_argument("--prompt", type=Path, default=DEFAULT_PROMPT_PATH, help="Path to the prompt template.")
    parser.add_argument("--model", type=str, default=None, help="Model name to use; defaults to the repository default.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing outputs for interviews.")
    parser.add_argument("--max-tokens", type=int, default=4096, help="Maximum output tokens for the model call.")
    parser.add_argument("--max-text-chars", type=int, default=1200, help="Maximum number of characters to send for each chunk text.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY is not set; continuing with heuristic fallback outputs.", file=sys.stderr)
    generate_all_interviews(
        input_path=args.input,
        output_dir=args.output_dir,
        prompt_path=args.prompt,
        model=args.model,
        overwrite=args.overwrite,
        max_tokens=args.max_tokens,
        max_text_chars=args.max_text_chars,
    )


if __name__ == "__main__":
    main()
