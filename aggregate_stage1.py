#!/usr/bin/env python3
"""
aggregate_stage1.py

Aggregates outputs from stage_1 pipeline across multiple interviews.

INPUT: Path to output/stage_1 parent directory and path to codebook.yaml
OUTPUT: aggregate_data.json and aggregate_report.md
"""

import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import yaml


def load_codebook(codebook_path: str) -> dict:
    """Load and parse codebook.yaml."""
    with open(codebook_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_all_codes_in_order(codebook: dict) -> list[str]:
    """Extract all leaf-level code IDs in codebook order."""
    codes = []
    for theme in codebook["themes"]:
        for code in theme["codes"]:
            codes.append(code["id"])
    return codes


def get_all_themes_in_order(codebook: dict) -> list[str]:
    """Extract all theme IDs in codebook order."""
    return [theme["id"] for theme in codebook["themes"]]


def code_to_theme(code: str) -> str:
    """Extract theme ID from a code (e.g., '1.b' -> '1')."""
    return code.split(".")[0]


def normalize_whitespace(text: str) -> str:
    """Normalize whitespace in text for duplicate detection."""
    return " ".join(text.split())


def discover_interview_folders(stage1_dir: Path) -> list[Path]:
    """Discover all interview subfolders (e.g., I01, I02, ...)."""
    return sorted([d for d in stage1_dir.iterdir() if d.is_dir()])


def health_check_interview(
    interview_dir: Path, codebook: dict, all_codes: list[str]
) -> tuple[bool, list[str]]:
    """
    Perform health checks on an interview's output files.
    Returns (is_valid, list_of_issues).
    """
    issues = []

    # Check pass2.json exists and has non-empty interpretations
    pass2_path = interview_dir / "pass2.json"
    if not pass2_path.exists():
        issues.append("pass2.json does not exist")
        return False, issues

    try:
        with open(pass2_path, "r", encoding="utf-8") as f:
            pass2 = json.load(f)
    except Exception as e:
        issues.append(f"pass2.json is invalid JSON: {e}")
        return False, issues

    if "interpretations" not in pass2 or not pass2["interpretations"]:
        issues.append("pass2.json has no interpretations array or it is empty")
        return False, issues

    # Check metadata.json exists
    metadata_path = interview_dir / "metadata.json"
    if not metadata_path.exists():
        issues.append("metadata.json does not exist")
        return False, issues

    try:
        with open(metadata_path, "r", encoding="utf-8") as f:
            metadata = json.load(f)
    except Exception as e:
        issues.append(f"metadata.json is invalid JSON: {e}")
        return False, issues

    # Check pass1_calls == number of themes in codebook
    pass1_calls = metadata.get("pass1_calls", -1)
    theme_count = len(codebook["themes"])
    if pass1_calls != theme_count:
        issues.append(
            f"pass1_calls ({pass1_calls}) != codebook theme count ({theme_count})"
        )

    # Check every entry in pass1_usage_per_theme has stop_reason == "end_turn"
    pass1_usage = metadata.get("pass1_usage_per_theme", [])
    for entry in pass1_usage:
        stop_reason = entry.get("stop_reason")
        theme_id = entry.get("theme_id", "?")
        if stop_reason != "end_turn":
            issues.append(
                f"Theme {theme_id} pass1 stop_reason is '{stop_reason}', not 'end_turn'"
            )

    # Check pass2_stop_reason == "end_turn" (if the field exists; if absent, treat as pass)
    pass2_usage_str = metadata.get("pass2_usage", "")
    if pass2_usage_str:
        # Extract stop_reason from the usage string if present
        # The format is a Usage(...) string; look for stop_reason in it
        if "stop_reason=" in str(pass2_usage_str):
            # If we find stop_reason in the string, check it
            if "stop_reason='end_turn'" not in str(pass2_usage_str):
                issues.append("pass2 stop_reason is not 'end_turn'")
        # If the key is absent, we pass (treat as pass per spec)

    return len(issues) == 0, issues


def aggregate_interviews(
    stage1_dir: Path, codebook: dict, all_codes: list[str]
) -> dict:
    """
    Aggregate data from all valid interviews.
    Returns a dict with all aggregated metrics.
    """
    interview_folders = discover_interview_folders(stage1_dir)

    included_interviews = []
    excluded_interviews = {}

    # Phase 1: Health checks
    for interview_dir in interview_folders:
        interview_id = interview_dir.name
        is_valid, issues = health_check_interview(interview_dir, codebook, all_codes)

        if is_valid:
            included_interviews.append(interview_dir)
        else:
            excluded_interviews[interview_id] = issues

    # Phase 2: Data collection from valid interviews
    # Maps: code -> { interview_id -> count }
    code_interview_counts = defaultdict(lambda: defaultdict(int))
    # Maps: theme -> { interview_id -> count }
    theme_interview_counts = defaultdict(lambda: defaultdict(int))
    # Maps: code -> { interview_id -> { grounding_type -> count } }
    grounding_per_code = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    # Total grounding counts per code
    grounding_totals = defaultdict(lambda: {"quote_text_only": 0, "quote_plus_inference": 0})
    # Duplicate citations: { interview_id -> { normalized_text -> list_of_codes } }
    citations_by_text = defaultdict(lambda: defaultdict(list))
    # Co-occurrence counter: { (code1, code2) -> count } where code1 < code2
    co_occurrences = defaultdict(int)
    # Unique speakers per code
    speakers_per_code = defaultdict(set)
    # Interview-level stats
    interview_stats = defaultdict(lambda: {"total_quotes": 0, "distinct_codes": set()})

    for interview_dir in included_interviews:
        interview_id = interview_dir.name

        # Load pass2.json for interpretations
        pass2_path = interview_dir / "pass2.json"
        with open(pass2_path, "r", encoding="utf-8") as f:
            pass2 = json.load(f)

        interpretations = pass2.get("interpretations", [])
        interview_stats[interview_id]["total_quotes"] = len(interpretations)

        # Process each interpretation
        for interp in interpretations:
            code = interp.get("code")
            theme_id = code_to_theme(code)
            speakers = interp.get("speakers", [])
            grounding = interp.get("interpretation_grounded_in", "")
            cited_text = interp.get("cited_text", "")

            # Count code
            code_interview_counts[code][interview_id] += 1
            # Count theme
            theme_interview_counts[theme_id][interview_id] += 1
            # Track grounding type
            if grounding in ["quote_text_only", "quote_plus_inference"]:
                grounding_per_code[code][interview_id][grounding] += 1
                grounding_totals[code][grounding] += 1

            # Track unique speakers
            for speaker in speakers:
                speakers_per_code[code].add(speaker)

            # Track distinct codes for this interview
            interview_stats[interview_id]["distinct_codes"].add(code)

            # Track citations for duplicate detection
            normalized_text = normalize_whitespace(cited_text)
            citations_by_text[interview_id][normalized_text].append(code)

    # Detect duplicate citations (same text, different codes) per interview
    duplicates_per_interview = defaultdict(list)
    for interview_id, text_to_codes in citations_by_text.items():
        for normalized_text, codes in text_to_codes.items():
            if len(codes) > 1:
                # Multiple codes reference the same text
                unique_codes = sorted(set(codes))
                for i, code1 in enumerate(unique_codes):
                    for code2 in unique_codes[i + 1 :]:
                        pair = (code1, code2) if code1 < code2 else (code2, code1)
                        co_occurrences[pair] += 1
                        if pair not in [d[0] for d in duplicates_per_interview[interview_id]]:
                            duplicates_per_interview[interview_id].append(
                                (pair, normalized_text[:100])
                            )  # Keep first 100 chars

    # Sort co-occurrences by frequency
    sorted_co_occurrences = sorted(
        co_occurrences.items(), key=lambda x: x[1], reverse=True
    )

    # Identify zero-quote codes across ALL included interviews
    zero_quote_codes = []
    for code in all_codes:
        if all(
            code_interview_counts[code].get(interview_dir.name, 0) == 0
            for interview_dir in included_interviews
        ):
            zero_quote_codes.append(code)

    # Calculate distinct code counts per interview
    for interview_id in interview_stats:
        num_distinct = len(interview_stats[interview_id]["distinct_codes"])
        interview_stats[interview_id]["num_distinct_codes"] = num_distinct
        interview_stats[interview_id]["total_codes_in_codebook"] = len(all_codes)

    return {
        "included_interviews": [d.name for d in included_interviews],
        "excluded_interviews": excluded_interviews,
        "code_interview_matrix": {
            code: {
                int_dir.name: code_interview_counts[code].get(int_dir.name, 0)
                for int_dir in included_interviews
            }
            for code in all_codes
        },
        "theme_interview_matrix": {
            theme_id: {
                int_dir.name: theme_interview_counts[theme_id].get(int_dir.name, 0)
                for int_dir in included_interviews
            }
            for theme_id in get_all_themes_in_order(codebook)
        },
        "grounding_per_code": {
            code: {
                int_dir.name: {
                    "quote_text_only": grounding_per_code[code][int_dir.name]["quote_text_only"],
                    "quote_plus_inference": grounding_per_code[code][int_dir.name]["quote_plus_inference"],
                }
                for int_dir in included_interviews
            }
            for code in all_codes
        },
        "grounding_totals": dict(grounding_totals),
        "duplicate_citations_by_pair": [
            {"code_pair": pair, "co_occurrence_count": count}
            for pair, count in sorted_co_occurrences
        ],
        "speakers_per_code": {
            code: sorted(list(speakers_per_code[code])) for code in all_codes
        },
        "interview_stats": {
            interview_id: {
                "total_quotes": interview_stats[interview_id]["total_quotes"],
                "num_distinct_codes": interview_stats[interview_id]["num_distinct_codes"],
                "total_codes_in_codebook": interview_stats[interview_id]["total_codes_in_codebook"],
            }
            for interview_id in sorted(interview_stats.keys())
        },
        "zero_quote_codes": zero_quote_codes,
    }


def generate_markdown_report(
    aggregated: dict, codebook: dict, all_codes: list[str]
) -> str:
    """Generate a human-readable markdown report from aggregated data."""
    lines = []

    lines.append("# Stage 1 Aggregation Report\n")

    # Summary
    lines.append("## Summary\n")
    num_included = len(aggregated["included_interviews"])
    num_excluded = len(aggregated["excluded_interviews"])
    lines.append(f"- **Included interviews:** {num_included}")
    lines.append(f"- **Excluded interviews:** {num_excluded}\n")

    # Excluded interviews with reasons
    if aggregated["excluded_interviews"]:
        lines.append("## Excluded Interviews\n")
        for interview_id, issues in aggregated["excluded_interviews"].items():
            lines.append(f"### {interview_id}")
            for issue in issues:
                lines.append(f"- {issue}")
            lines.append("")

    # Interview stats
    lines.append("## Interview Statistics\n")
    lines.append("| Interview | Total Quotes | Distinct Codes | % of Codebook |")
    lines.append("|-----------|--------------|----------------|---------------|")
    for interview_id, stats in aggregated["interview_stats"].items():
        total_quotes = stats["total_quotes"]
        distinct = stats["num_distinct_codes"]
        total = stats["total_codes_in_codebook"]
        pct = (distinct / total * 100) if total > 0 else 0
        lines.append(f"| {interview_id} | {total_quotes} | {distinct} | {pct:.1f}% |")
    lines.append("")

    # Code x Interview matrix
    lines.append("## Code × Interview Matrix\n")
    header = ["Code"] + aggregated["included_interviews"]
    lines.append("| " + " | ".join(header) + " |")
    lines.append("|" + "|".join(["-" * max(len(h), 8) for h in header]) + "|")

    for code in all_codes:
        row = [code]
        for interview_id in aggregated["included_interviews"]:
            count = aggregated["code_interview_matrix"][code].get(interview_id, 0)
            row.append(str(count))
        lines.append("| " + " | ".join(row) + " |")
    lines.append("")

    # Theme x Interview matrix
    lines.append("## Theme × Interview Matrix\n")
    header = ["Theme"] + aggregated["included_interviews"]
    lines.append("| " + " | ".join(header) + " |")
    lines.append("|" + "|".join(["-" * max(len(h), 8) for h in header]) + "|")

    for theme_id in get_all_themes_in_order(codebook):
        row = [theme_id]
        for interview_id in aggregated["included_interviews"]:
            count = aggregated["theme_interview_matrix"][theme_id].get(interview_id, 0)
            row.append(str(count))
        lines.append("| " + " | ".join(row) + " |")
    lines.append("")

    # Grounding type breakdown per code
    lines.append("## Grounding Type Breakdown (per Code)\n")
    header = ["Code", "Quote-Only", "Quote+Inference", "Total"]
    lines.append("| " + " | ".join(header) + " |")
    lines.append("|" + "|".join(["-" * max(len(h), 8) for h in header]) + "|")

    for code in all_codes:
        grounding = aggregated["grounding_totals"].get(code, {})
        quote_only = grounding.get("quote_text_only", 0)
        quote_plus = grounding.get("quote_plus_inference", 0)
        total = quote_only + quote_plus
        lines.append(f"| {code} | {quote_only} | {quote_plus} | {total} |")
    lines.append("")

    # Duplicate citations (co-occurrences)
    if aggregated["duplicate_citations_by_pair"]:
        lines.append("## Duplicate Citations (same text, different codes)\n")
        lines.append("| Code Pair | Co-occurrence Count |")
        lines.append("|-----------|---------------------|")
        for item in aggregated["duplicate_citations_by_pair"]:
            pair = item["code_pair"]
            count = item["co_occurrence_count"]
            pair_str = " ↔ ".join(pair)
            lines.append(f"| {pair_str} | {count} |")
        lines.append("")

    # Speakers per code
    lines.append("## Unique Speakers per Code\n")
    lines.append("| Code | Speakers |")
    lines.append("|------|----------|")
    for code in all_codes:
        speakers = aggregated["speakers_per_code"].get(code, [])
        if speakers:
            speaker_str = ", ".join(speakers)
            lines.append(f"| {code} | {speaker_str} |")
        else:
            lines.append(f"| {code} | (none) |")
    lines.append("")

    # Zero-quote codes
    if aggregated["zero_quote_codes"]:
        lines.append("## Codes with Zero Quotes\n")
        lines.append("The following codes had no quotes across ALL included interviews:\n")
        for code in aggregated["zero_quote_codes"]:
            lines.append(f"- {code}")
        lines.append("")

    return "\n".join(lines)


def main():
    if len(sys.argv) != 3:
        print(
            f"Usage: {sys.argv[0]} <path_to_output_stage1_dir> <path_to_codebook.yaml>"
        )
        sys.exit(1)

    stage1_dir = Path(sys.argv[1])
    codebook_path = Path(sys.argv[2])

    if not stage1_dir.exists():
        print(f"Error: {stage1_dir} does not exist")
        sys.exit(1)

    if not codebook_path.exists():
        print(f"Error: {codebook_path} does not exist")
        sys.exit(1)

    # Load codebook
    codebook = load_codebook(str(codebook_path))
    all_codes = get_all_codes_in_order(codebook)

    # Aggregate
    aggregated = aggregate_interviews(stage1_dir, codebook, all_codes)

    # Output aggregate_data.json
    output_data_path = stage1_dir / "aggregate_data.json"
    with open(output_data_path, "w", encoding="utf-8") as f:
        json.dump(aggregated, f, indent=2)
    print(f"Written: {output_data_path}")

    # Output aggregate_report.md
    report_markdown = generate_markdown_report(aggregated, codebook, all_codes)
    output_report_path = stage1_dir / "aggregate_report.md"
    with open(output_report_path, "w", encoding="utf-8") as f:
        f.write(report_markdown)
    print(f"Written: {output_report_path}")


if __name__ == "__main__":
    main()
