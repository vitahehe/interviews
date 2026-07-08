import argparse
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
REPO_ROOT = Path(__file__).resolve().parents[1]

# Load API key from .env in the repository root
load_dotenv(REPO_ROOT / ".env")

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from meaningful_chunks.theme_grids import DEFAULT_INPUT, DEFAULT_OUTPUT_DIR, DEFAULT_PROMPT_PATH

DEFAULT_INPUT = Path("meaningful_chunks/data/meaningful_chunks/meaningful_chunks.jsonl")
DEFAULT_OUTPUT_DIR = Path("make_themes/outputs")
DEFAULT_PROMPT_PATH = Path("make_themes/prompts/theme_grid_prompt.txt")
DEFAULT_MODEL = "claude-sonnet-4-6"
DEFAULT_MAX_TOKENS = 4096
DEFAULT_MAX_TEXT_CHARS = 1200

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
    if not ANTHROPIC_API_KEY:
        print("ANTHROPIC_API_KEY is not set;ERRORRRRS", file=sys.stderr)


if __name__ == "__main__":
    main()


