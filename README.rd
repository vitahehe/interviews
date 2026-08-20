# Interview analysis workflow

This repository contains a small pipeline for turning raw interview transcripts into structured qualitative-analysis output. The current workflow is:

1. Segment a raw transcript into turns and sentence-level units.
2. Run a two-pass analysis with the Anthropic API using a codebook and prompt templates.
3. Write JSON outputs for each interview under the output directory.

## Repository contents

- [transcription/test](transcription/test): raw interview transcripts used as input.
- [pipeline/segment_transcript.py](pipeline/segment_transcript.py): converts a plain transcript into turn-level and sentence-level JSON structures.
- [pipeline/pipeline.py](pipeline/pipeline.py): runs Pass 1 and Pass 2 analysis and writes the result files.
- [pipeline/requirements.txt](pipeline/requirements.txt): Python dependencies for the pipeline.
- [codebook.yaml](codebook.yaml): the coding scheme used by the analysis.
- [prompts](prompts): system and pass-specific prompt templates.
- [data/processed](data/processed): processed interview JSON files produced by segmentation.
- [output/stage_1](output/stage_1): per-interview analysis outputs, including pass1.json, pass2.json, and metadata.json.

## How to run

1. Create and activate a Python environment.

```bash
cd /home/vita/projects/interviews
python -m venv .venv
source .venv/bin/activate
pip install -r pipeline/requirements.txt
```

2. Set your API key.

```bash
export ANTHROPIC_API_KEY=your_key_here
```

3. Segment one interview.

```bash
python pipeline/segment_transcript.py \
  --input transcription/test/Monday_20260223_Kvant1_lab_transcript.txt \
  --interview-id I01 \
  --output data/processed/Monday_20260223_Kvant1_lab_transcript.json
```

4. Run the analysis pipeline.

```bash
python pipeline/pipeline.py \
  --interview-id I01 \
  --processed data/processed/Monday_20260223_Kvant1_lab_transcript.json \
  --codebook codebook.yaml \
  --prompts-dir prompts \
  --outdir output/stage_1/I01


  python pipeline/pipeline.py \
  --interview-id I02 \
  --processed data/processed/Wednesday_20260225_Kvant1_lab_transcript.json \
  --codebook codebook.yaml \
  --prompts-dir prompts \
  --outdir output/stage_1/I02
```

Use the interview ID values I01 and I02 to match the folders under [output/stage_1](output/stage_1).



STAGE TWO, TRANS INTERVIEW ANALYSIS:

# Stage 1 Aggregator

Aggregates outputs from the Stage 1 pipeline across multiple interview folders, producing a comprehensive summary of coding patterns, themes, and speaker engagement.

## Usage

```bash
python aggregate_stage1.py <path_to_output_stage_1_dir> <path_to_codebook.yaml>
```

**Example:**
```bash
python aggregate_stage1.py output/stage_1 codebook.yaml
```

## Output Files

Two files are written to the `output/stage_1` directory:

### 1. `aggregate_data.json`
Machine-readable JSON file containing all aggregated metrics, suitable for downstream AI-assisted analysis. Includes:
- List of included and excluded interviews (with exclusion reasons)
- Code × interview count matrix
- Theme × interview count matrix
- Grounding type breakdown per code (quote-only vs. quote+inference)
- Duplicate citation pairs and co-occurrence counts
- Unique speakers per code
- Per-interview statistics

### 2. `aggregate_report.md`
Human-readable markdown report with formatted tables showing:
- Summary statistics
- Interview-level quote and code counts
- Code × interview matrix
- Theme × interview matrix
- Grounding type breakdown table
- Duplicate citations sorted by frequency
- Unique speakers per code
- Codes with zero quotes across all interviews


Algorithm Overview

### Phase 1: Discovery & Validation
1. Scan `output/stage_1/` for interview subdirectories (e.g., I01, I02, ...)
2. For each directory, run 5 health checks:
   - `pass2.json` exists with non-empty `interpretations` array
   - `metadata.json` exists and is valid JSON
   - `pass1_calls == len(codebook.themes)`
   - All entries in `pass1_usage_per_theme` have `stop_reason == "end_turn"`
   - `pass2_stop_reason == "end_turn"` (if field exists; absent = pass)
3. Separate interviews into `included` (passed all checks) and `excluded` (with reasons)

### Phase 2: Data Extraction & Aggregation
For each **included** interview, process `pass2.json` interpretations:

1. **Code × Interview Matrix**
   - Rows: all codes from codebook (in order), including those with 0 quotes
   - Columns: included interview IDs
   - Cell values: count of interpretations per code per interview

2. **Theme × Interview Matrix**
   - Rows: all themes from codebook (in order)
   - Columns: included interview IDs
   - Cell values: sum of counts for all codes under that theme

3. **Grounding Type Breakdown** (per code)
   - Track `interpretation_grounded_in` field: "quote_text_only" or "quote_plus_inference"
   - Aggregate per code per interview
   - Calculate totals across all included interviews

4. **Duplicate Citation Detection**
   - Normalize whitespace in each `cited_text`
   - Group interpretations by normalized text within each interview
   - When same text appears under multiple codes, record the code pair
   - Aggregate co-occurrence counts across all interviews
   - Sort pairs by frequency (descending)

5. **Unique Speakers per Code**
   - For each code, collect unique speaker names from all associated interpretations
   - Sort alphabetically

6. **Interview Statistics**
   - Total quote count (size of interpretations array)
   - Distinct codes triggered (unique codes with at least 1 quote)
   - Percentage of codebook covered

7. **Zero-Quote Codes**
   - Identify codes with 0 appearances across ALL included interviews
   - List separately for visibility


RUN AI PROMPT STAGE 2


   python pipeline/analyze_patterens.py \
  --stage1-dir output/stage_1 \
  --aggregate-data output/stage_1/aggregate_data.json \
  --codebook codebook.yaml \
  --prompts-dir prompts \
  --outdir outputs/stage_2 \
  --model claude-sonnet-5
