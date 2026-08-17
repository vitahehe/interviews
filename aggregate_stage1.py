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
    # Duplicate citations: { interview_id -> { normalized_text -> [(quote_id, code, full_text), ...] } }
    citations_by_text = defaultdict(lambda: defaultdict(list))
    # Cross-interview citations: { normalized_text -> list_of (interview_id, code, theme_id, quote_id) }
    cross_interview_citations = defaultdict(list)
    # Interview-level stats
    interview_stats = defaultdict(lambda: {"total_quotes": 0, "distinct_codes": set()})
    # Track citations with themes for per-interview analysis: { interview_id -> { normalized_text -> set_of_themes } }
    citations_with_themes = defaultdict(lambda: defaultdict(set))

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
            cited_text = interp.get("cited_text", "")
            quote_id = interp.get("quote_id", "")

            # Count code
            code_interview_counts[code][interview_id] += 1
            # Track distinct codes for this interview
            interview_stats[interview_id]["distinct_codes"].add(code)

            # Track citations for duplicate detection (within interview)
            normalized_text = normalize_whitespace(cited_text)
            citations_by_text[interview_id][normalized_text].append({
                "quote_id": quote_id,
                "code": code,
                "full_text": cited_text
            })
            
            # Track citations across interviews
            cross_interview_citations[normalized_text].append({
                "interview_id": interview_id,
                "code": code,
                "theme_id": theme_id,
                "quote_id": quote_id,
                "full_text": cited_text
            })
            
            # Track themes for this normalized text in this interview (for cross-theme analysis)
            citations_with_themes[interview_id][normalized_text].add(theme_id)

    # Detect duplicate citations (same text, different codes) per interview
    within_interview_duplicates = defaultdict(list)
    for interview_id, text_to_citations in citations_by_text.items():
        for normalized_text, citations in text_to_citations.items():
            if len(citations) > 1:
                # Multiple codes reference the same text within same interview
                # Get unique codes
                unique_codes = sorted(set(c["code"] for c in citations))
                if len(unique_codes) > 1:  # Only if different codes
                    within_interview_duplicates[interview_id].append({
                        "text": normalized_text[:200],
                        "full_text": citations[0]["full_text"],  # Store one full text
                        "codes": unique_codes,
                        "quote_ids": [c["quote_id"] for c in citations],
                        "count": len(citations)
                    })

    # Detect duplicate citations across interviews
    cross_interview_duplicates = []
    for normalized_text, citations in cross_interview_citations.items():
        # Get unique interviews for this text
        interviews_with_text = set(c["interview_id"] for c in citations)
        if len(interviews_with_text) > 1:
            # Same text appears in multiple interviews
            cross_interview_duplicates.append({
                "text": normalized_text[:200],
                "full_text": citations[0]["full_text"],
                "interviews": sorted(list(interviews_with_text)),
                "quote_ids": [c["quote_id"] for c in citations],
                "occurrences": len(citations)
            })

    # Identify zero-quote codes across ALL included interviews
    zero_quote_codes = []
    for code in all_codes:
        if all(
            code_interview_counts[code].get(interview_dir.name, 0) == 0
            for interview_dir in included_interviews
        ):
            zero_quote_codes.append(code)

    # Calculate distinct code counts per interview and cross-theme quotes
    cross_theme_quotes_per_interview = {}
    for interview_id in interview_stats:
        num_distinct = len(interview_stats[interview_id]["distinct_codes"])
        interview_stats[interview_id]["num_distinct_codes"] = num_distinct
        interview_stats[interview_id]["total_codes_in_codebook"] = len(all_codes)
        
        # Count quotes with same text across different themes in this interview
        cross_theme_count = 0
        for normalized_text, themes in citations_with_themes[interview_id].items():
            if len(themes) > 1:
                cross_theme_count += 1
        cross_theme_quotes_per_interview[interview_id] = cross_theme_count

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
        "within_interview_duplicates": dict(within_interview_duplicates),
        "cross_interview_duplicates": cross_interview_duplicates,
        "cross_theme_quotes_per_interview": cross_theme_quotes_per_interview,
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

    # Summary with total quotes and distinct codes
    lines.append("## Summary\n")
    num_included = len(aggregated["included_interviews"])
    num_excluded = len(aggregated["excluded_interviews"])
    total_all_quotes = sum(aggregated["interview_stats"][iid]["total_quotes"] 
                           for iid in aggregated["interview_stats"])
    distinct_codes_overall = set()
    for interview_id, stats in aggregated["interview_stats"].items():
        # Determine which codes have quotes in this interview
        codes_with_quotes = set()
        for code in all_codes:
            count = aggregated["code_interview_matrix"][code].get(interview_id, 0)
            if count > 0:
                codes_with_quotes.add(code)
        distinct_codes_overall.update(codes_with_quotes)
    
    lines.append(f"- **Included interviews:** {num_included}")
    lines.append(f"- **Excluded interviews:** {num_excluded}")
    lines.append(f"- **Total quotes across all interviews:** {total_all_quotes}")
    lines.append(f"- **Distinct codes with quotes:** {len(distinct_codes_overall)}/{len(all_codes)}\n")

    # Excluded interviews with reasons
    if aggregated["excluded_interviews"]:
        lines.append("## Excluded Interviews\n")
        for interview_id, issues in aggregated["excluded_interviews"].items():
            lines.append(f"### {interview_id}")
            for issue in issues:
                lines.append(f"- {issue}")
            lines.append("")

    # Interview stats with all codes (including empty)
    lines.append("## Interview Statistics\n")
    lines.append("| Interview | Total Quotes | Distinct Codes | Empty Codes | % of Codebook |")
    lines.append("|-----------|--------------|----------------|-------------|---------------|")
    for interview_id, stats in aggregated["interview_stats"].items():
        total_quotes = stats["total_quotes"]
        distinct = stats["num_distinct_codes"]
        total = stats["total_codes_in_codebook"]
        empty = total - distinct
        pct = (distinct / total * 100) if total > 0 else 0
        lines.append(f"| {interview_id} | {total_quotes} | {distinct} | {empty} | {pct:.1f}% |")
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

    lines.append("")

    # Within-Interview Duplicates
    if any(aggregated["within_interview_duplicates"].values()):
        lines.append("## Within-Interview Duplicate Citations (same text, different codes)\n")
        for interview_id in aggregated["included_interviews"]:
            duplicates = aggregated["within_interview_duplicates"].get(interview_id, [])
            if duplicates:
                lines.append(f"### {interview_id}\n")
                for dup in duplicates:
                    codes_str = ", ".join(dup["codes"])
                    quote_ids_str = ", ".join(dup["quote_ids"])
                    lines.append(f"**Codes:** {codes_str} | **Count:** {dup['count']}")
                    lines.append(f"**Quote IDs:** {quote_ids_str}")
                    lines.append(f"**Full Text:** {dup['full_text']}")
                    lines.append("")
    
    # Cross-Interview Duplicates
    if aggregated["cross_interview_duplicates"]:
        lines.append("## Cross-Interview Duplicate Citations (same text across interviews)\n")
        for dup in aggregated["cross_interview_duplicates"]:
            interviews_str = ", ".join(dup["interviews"])
            quote_ids_str = ", ".join(dup["quote_ids"])
            lines.append(f"**Interviews:** {interviews_str} | **Total Occurrences:** {dup['occurrences']}")
            lines.append(f"**Quote IDs:** {quote_ids_str}")
            lines.append(f"**Full Text:** {dup['full_text']}")
            lines.append("")
    
    # Per-Interview Cross-Theme Quotes
    lines.append("## Quotes Appearing Across Distinct Themes (per interview)\n")
    lines.append("| Interview | Shared Text Count |")
    lines.append("|-----------|-------------------|")
    for interview_id in sorted(aggregated["cross_theme_quotes_per_interview"].keys()):
        count = aggregated["cross_theme_quotes_per_interview"][interview_id]
        lines.append(f"| {interview_id} | {count} |")
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
