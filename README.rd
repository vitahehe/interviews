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
```

Use the interview ID values I01 and I02 to match the folders under [output/stage_1](output/stage_1).