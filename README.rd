# Interviews qualitative analysis workflow

This repository supports a lightweight qualitative-analysis pipeline for interview transcripts.

## Purpose

The workflow is organized around three stages:

1. Transcription input
2. Annotation of transcript chunks
3. Meaningful-chunk selection and per-interview theme-grid generation

The current implementation is designed to work as follows:

- Put raw interview transcripts in [transcription]
- Run annotation on one or more transcripts from [annotation]
- Use the resulting chunk-level evidence to build a meaningful-chunk evidence file in [meaningful_chunks]
- Generate one per-interview theme grid in [make_themes]

## Main folders

- [transcription](transcription): raw interview transcripts
- [annotation](annotation): transcript chunking and broad annotation logic
- [meaningful_chunks](meaningful_chunks): meaningful-chunk loading and evidence preparation
- [make_themes](make_themes): per-interview theme-grid generation, CSV/JSON/Markdown export, and prompt templates

## How to run

### 1. Annotation

Run annotation on a transcript file:

```bash
cd /workspaces/interviews
export ANTHROPIC_API_KEY=your_key_here
python annotation/annotate.py --file transcription/test/Monday_20260223_Kvant1_lab_transcript.txt --output annotation/outputs
```

### 2. Create meaningful-chunk input

The repository expects a JSONL file with meaningful-chunk evidence. A compact example is already prepared under [meaningful_chunks/data](meaningful_chunks/data).

### 3. Generate theme grids

Run the theme-grid generator:

```bash
cd /workspaces/interviews
python make_themes/scripts/generate_interview_theme_grids.py --input meaningful_chunks/data/meaningful_chunks.jsonl --output-dir make_themes/outputs/interview_theme_grids
```

## Notes on the current implementation

- The theme-grid generator is intentionally evidence-oriented: each theme code is supported by short chunk-level examples.
- The generated outputs are stored in [make_themes/outputs/interview_theme_grids](make_themes/outputs/interview_theme_grids).
