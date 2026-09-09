# Interview Qualitative Analysis Pipeline

A two-stage pipeline for automated qualitative coding of physics-lab student interviews. Transcripts are segmented, coded against a predefined codebook using Claude's API with citations-enabled retrieval, interpreted with structured reasoning, aggregated across multiple interviews, and analyzed for cross-interview patterns.

## Pipeline Overview

```
Raw Transcript
    ↓
[Stage 1: Per-Interview Analysis]
    ├─ Segment: raw transcript → turns
    ├─ Pass 1: find evidence in student turns (citations-enabled)
    └─ Pass 2: interpret each quote (forced tool use)
    ↓
Per-Interview Outputs (pass1.json, pass2.json, metadata.json)
    ↓
[Stage 2: Cross-Interview Aggregation & Analysis]
    ├─ Aggregate: validate + consolidate all interviews
    └─ Pattern Finding: identify cross-interview themes (forced tool use)
    ↓
Aggregated Reports (aggregate_data.json, aggregate_report.md)
Cross-Interview Findings (pattern_findings.json, pattern_findings.md)
```

See [PIPELINE_DETAILS.md](PIPELINE_DETAILS.md) for comprehensive technical documentation of every component, constraint, and design decision.


### 1. Set up environment

```bash
cd /home/vita/projects/interviews
python -m venv .venv
source .venv/bin/activate
pip install -r pipeline/requirements.txt
export ANTHROPIC_API_KEY=your_key_here
```

## Processing One Interview (I01)

This section walks through the complete pipeline for interview I01, from raw transcript to final outputs.

### Step 1: Segment the raw transcript

Converts raw speaker-labeled transcript into structured turns (each with turn_id, speaker type, and text).

```bash
python pipeline/segment_transcript.py \
  --input transcription/test/Monday_20260223_Kvant1_lab_transcript.txt \
  --interview-id I01 \
  --output data/processed/Monday_20260223_Kvant1_lab_transcript.json
```

**Output:** `data/processed/Monday_20260223_Kvant1_lab_transcript.json`

### Step 2: Run Stage 1 analysis (Pass 1 + Pass 2)

Finds evidence for each code in the codebook (Pass 1, citations-enabled), then interprets each quote (Pass 2, forced tool use). Produces three files per interview.

```bash
python pipeline/pipeline.py \
  --interview-id I01 \
  --processed data/processed/Monday_20260223_Kvant1_lab_transcript.json \
  --codebook codebook.yaml \
  --prompts-dir prompts \
  --outdir output/stage_1/I01 \
  --model claude-sonnet-5
```

**Outputs:**
- `output/stage_1/I01/pass1.json` — all evidence found (quotes + turn IDs)
- `output/stage_1/I01/pass2.json` — all interpretations (rationale + teaching implications)
- `output/stage_1/I01/metadata.json` — timing, usage, hashes, validation info

## Processing Additional Interviews

To run the same pipeline for a different interview, repeat Steps 1–2 with a different input file and interview ID. Example for interview I03:

### Step 1: Segment I03

```bash
python pipeline/segment_transcript.py \
  --input transcription/test/kvant1_julie_1_transcript.txt \
  --interview-id I03 \
  --output data/processed/kvant1_julie_1_transcript.json
```

### Step 2: Analyze I03

```bash
python pipeline/pipeline.py \
  --interview-id I03 \
  --processed data/processed/kvant1_julie_1_transcript.json \
  --codebook codebook.yaml \
  --prompts-dir prompts \
  --outdir output/stage_1/I03 \
  --model claude-sonnet-5
```

## Stage 2: Cross-Interview Aggregation & Pattern Finding

Run these after processing at least one interview (or multiple for meaningful aggregation).

### Step 1: Aggregate all valid interviews

Validates all interviews in `output/stage_1/`, creates consolidated code × interview matrices, detects duplicate citations, and generates summary statistics.

```bash
python aggregate_stage1.py output/stage_1 codebook.yaml
```

**Outputs:**
- `output/stage_1/aggregate_data.json` — machine-readable metrics (matrices, counts, exclusion reasons)
- `output/stage_1/aggregate_report.md` — human-readable summary tables

### Step 2: Find cross-interview patterns

Uses aggregate metrics and all verified quotes to surface tensions, contradictions, alignments, and emerging patterns via AI-assisted analysis.

```bash
python pipeline/analyze_patterens.py \
  --stage1-dir output/stage_1 \
  --aggregate-data output/stage_1/aggregate_data.json \
  --codebook codebook.yaml \
  --prompts-dir prompts \
  --outdir outputs/stage_2 \
  --model claude-sonnet-5
```

**Outputs:**
- `outputs/stage_2/pattern_findings.json` — structured findings (tensions, contradictions, alignments, etc.)
- `outputs/stage_2/pattern_findings.md` — human-readable report with supporting quotes

## File Structure

- **[pipeline/segment_transcript.py](pipeline/segment_transcript.py)** — Turn-level segmentation
- **[pipeline/pipeline.py](pipeline/pipeline.py)** — Stage 1: Pass 1 + Pass 2 analysis
- **[aggregate_stage1.py](aggregate_stage1.py)** — Stage 2, Step 1: validation & aggregation
- **[pipeline/analyze_patterens.py](pipeline/analyze_patterens.py)** — Stage 2, Step 2: pattern finding
- **[codebook.yaml](codebook.yaml)** — Coding scheme (themes and codes)
- **[prompts/](prompts/)** — Prompt templates (system, pass1, pass2, stage2)
- **[data/processed/](data/processed/)** — Segmented interviews (input to Stage 1)
- **[output/stage_1/](output/stage_1/)** — Per-interview and aggregate outputs
- **[outputs/stage_2/](outputs/stage_2/)** — Cross-interview pattern findings
- **[transcription/test/](transcription/test/)** — Raw interview transcripts

For detailed documentation of how each component works, design constraints, and how the model is guided at every stage, see [PIPELINE_DETAILS.md](PIPELINE_DETAILS.md).

---

## Quick Start: Stage 1 Only (Segment & Analyze All Interviews)

Process all transcripts in `transcription/test/` automatically without typing filenames:

```bash
counter=0; for file in transcription/test/*.txt; do \
  counter=$((counter + 1)); \
  interview_id=$(printf "I%02d" $counter); \
  filename=$(basename "$file" .txt); \
  echo "Processing $interview_id: $file"; \
  python pipeline/segment_transcript.py \
    --input "$file" \
    --interview-id "$interview_id" \
    --output "data/processed/${filename}.json" && \
  python pipeline/pipeline.py \
    --interview-id "$interview_id" \
    --processed "data/processed/${filename}.json" \
    --codebook codebook.yaml \
    --prompts-dir prompts \
    --outdir "output/stage_1/${interview_id}" \
    --model claude-sonnet-5 || break; \
done && echo "✓ Stage 1 complete!"
```

**What this does:**
- Finds all `.txt` files in `transcription/test/`
- Assigns interview IDs: I01, I02, I03, etc.
- Segments each transcript
- Runs Stage 1 analysis (Pass 1 + Pass 2) for each
- Stops on error (safe mode)

---

## Complete End-to-End (All Stages, All Interviews)

After Stage 1 completes, run Stage 2 (aggregation + pattern finding):

```bash
python aggregate_stage1.py output/stage_1 codebook.yaml && \
python pipeline/analyze_patterens.py \
  --stage1-dir output/stage_1 \
  --aggregate-data output/stage_1/aggregate_data.json \
  --codebook codebook.yaml \
  --prompts-dir prompts \
  --outdir outputs/stage_2 \
  --model claude-sonnet-5 && \
echo "✓ All stages complete! Results in output/stage_1/ and outputs/stage_2/"
```

