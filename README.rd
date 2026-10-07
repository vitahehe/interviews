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


## Processing One Interview (I01)


Converts raw speaker-labeled transcript into structured turns (each with turn_id, speaker type, and text).

```bash
python pipeline/segment_transcript.py \
  --input transcription/test/Monday_20260223_Kvant1_lab_transcript.txt \
  --interview-id I01 \
  --output data/processed/Monday_20260223_Kvant1_lab_transcript.json
```

**Output:** `data/processed/Monday_20260223_Kvant1_lab_transcript.json`

Than, find evidence for each code in the codebook (Pass 1, citations-enabled), then interprets each quote (Pass 2, forced tool use). Produces three files per interview.

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

JUST stage 2:

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
Note for me: check alignment manually

Segmenting I01: transcription/test/Monday_20260223_Kvant1_lab_transcript.txt
Wrote 45 turns (25 student quote units) to data/processed/Monday_20260223_Kvant1_lab_transcript.json
Segmenting I02: transcription/test/PIQIP_Qinu_lab_andrea_1.txt
Wrote 17 turns (17 student quote units) to data/processed/PIQIP_Qinu_lab_andrea_1.json
Segmenting I03: transcription/test/PIQIP_Qinu_lab_andrea_2.txt
Wrote 68 turns (68 student quote units) to data/processed/PIQIP_Qinu_lab_andrea_2.json
Segmenting I04: transcription/test/PIQIP_Qinu_lab_bjarke_1.txt
Wrote 37 turns (37 student quote units) to data/processed/PIQIP_Qinu_lab_bjarke_1.json
Segmenting I05: transcription/test/PIQIP_Qinu_lab_bjarke_2.txt
Wrote 50 turns (50 student quote units) to data/processed/PIQIP_Qinu_lab_bjarke_2.json
Segmenting I06: transcription/test/PIQIP_Qinu_lab_julie_1.txt
Wrote 101 turns (101 student quote units) to data/processed/PIQIP_Qinu_lab_julie_1.json
Segmenting I07: transcription/test/Wednesday_20260225_Kvant1_lab_transcript.txt
Wrote 56 turns (31 student quote units) to data/processed/Wednesday_20260225_Kvant1_lab_transcript.json
Segmenting I08: transcription/test/kvant1_bjarke_3_transcript.txt
Wrote 16 turns (16 student quote units) to data/processed/kvant1_bjarke_3_transcript.json
Segmenting I09: transcription/test/kvant1_julie_1_transcript.txt
Wrote 45 turns (45 student quote units) to data/processed/kvant1_julie_1_transcript.json
Segmenting I10: transcription/test/kvant1_julie_2_transcript.txt
Wrote 79 turns (79 student quote units) to data/processed/kvant1_julie_2_transcript.json
Segmenting I11: transcription/test/kvant1_julie_3_transcript.txt
Wrote 49 turns (49 student quote units) to data/processed/kvant1_julie_3_transcript.json
Segmenting I12: transcription/test/kvant1_julie_4_transcript.txt
Wrote 79 turns (79 student quote units) to data/processed/kvant1_julie_4_transcript.json
Segmenting I13: transcription/test/qmemory_bjarke_1.txt
Wrote 32 turns (32 student quote units) to data/processed/qmemory_bjarke_1.json
Segmenting I14: transcription/test/qmemory_bjarke_2.txt
Wrote 42 turns (42 student quote units) to data/processed/qmemory_bjarke_2.json
Segmenting I15: transcription/test/qmemory_vita_1.txt
Wrote 40 turns (40 student quote units) to data/processed/qmemory_vita_1.json
Segmenting I16: transcription/test/qmemory_vita_2.txt
Wrote 37 turns (37 student quote units) to data/processed/qmemory_vita_2.json
Segmenting I17: transcription/test/qmemory_vita_3.txt
Wrote 50 turns (50 student quote units) to data/processed/qmemory_vita_3.json
✓ All interviews segmented!