# Interview Analysis Pipeline Architecture

## Overview
Two-stage AI-assisted analysis with deterministic aggregation between stages.

---

## STAGE 1: Quote Extraction & Interpretation

### Input Data
- **Transcripts**: Raw text from interviews (e.g., `transcription/test/Monday_20260223_Kvant1_lab_transcript.txt`)
- **Codebook**: YAML with themes and codes (e.g., `codebook.yaml`)
- **Prompts**: System prompt + Pass 1 & Pass 2 prompts

### Pass 1: Segment-by-Theme
**What it does:**
- Reads transcript as a continuous text stream
- For EACH THEME in codebook, calls Claude with that theme + transcript
- Claude extracts text segments **relevant to that theme**
- Output: `pass1.json` with `segments` (one per theme)

**Quote Definition:**
- A **quote** is initially just a text **segment** extracted from the transcript (sentence, phrase, or short passage)
- It's identified by its theme, interview, and position in the transcript
- Stored in `pass1.json`

**AI Sees:**
```
System Prompt: [generic system instructions]
User Message:
  - Theme: "1" (e.g., "Difficulty & Problem-Solving")
  - Full Transcript Text
```

**Output Structure:**
```json
{
  "interview_id": "I01",
  "pass1_segments": [
    {
      "theme_id": "1",
      "segment_text": "student 2: More technical, I think..."
    }
  ]
}
```

---

### Pass 2: Interpret & Code
**What it does:**
- For EACH segment from Pass 1, Claude:
  - Adds **rationale** (why this segment matters)
  - Assigns a **code** (e.g., "1.b", "2.a")
  - Adds teaching implications
  - Specifies **grounding type** ("quote_text_only" vs "quote_plus_inference")
  
**Quote Final Form:**
- Now a **full interpretation object** with:
  - `quote_id`: Unique ID (e.g., `Monday_20260223_Kvant1_lab_transcript-Q001`)
  - `cited_text`: The original segment text
  - `code`: Single code assigned
  - `rationale`: Claude's explanation
  - `interview_id`: Which interview
  - All stored in `pass2.json`

**AI Sees:**
```
System Prompt: [generic]
User Message (for each segment):
  - Segment text
  - Theme context
  - Codebook codes for that theme
```

**Output Structure:**
```json
{
  "interview_id": "I01",
  "interpretations": [
    {
      "quote_id": "Monday_20260223_Kvant1_lab_transcript-Q001",
      "cited_text": "student 2: More technical, I think...",
      "code": "1.b",
      "theme_id": "1",
      "rationale": "...",
      "interpretation_grounded_in": "quote_text_only"
    }
  ]
}
```

### Quote Retrieval: Brute Force ✓
**Yes, it's locally brute-forced:**
```python
# In pass2.json, we iterate & store ALL quotes
# Then when we need a quote, we do local lookup by quote_id
quote_by_id = {q["quote_id"]: q for q in quotes}
q = quote_by_id.get(qid)  # <-- Local retrieval, no API call
```

---

## STAGE 1.5: Aggregation (Deterministic)

### What Happens Here
- **No AI involved** — this is pure Python logic
- Reads all `pass2.json` files from included interviews
- Counts codes per interview
- Tracks duplicate citations (same text, different codes)
- Tracks cross-theme overlaps

### Output: `aggregate_data.json`
```json
{
  "included_interviews": ["I01", "I02"],
  "code_interview_matrix": {
    "1.a": {"I01": 0, "I02": 0},
    "1.b": {"I01": 3, "I02": 0},
    ...
  },
  "within_interview_duplicates": {
    "I01": [
      {
        "codes": ["2.a", "3.b"],
        "quote_ids": ["Q007", "Q013"],
        "full_text": "..."
      }
    ]
  }
}
```

### Output: `aggregate_report.md`
Markdown table with:
- Interview stats (total quotes, distinct codes, empty codes)
- Code × Interview matrix
- Within-interview & cross-interview duplicates (with full text + quote_ids)

---

## STAGE 2: Cross-Interview Pattern Finding

### Input Data to AI
**Prompt Template with injected data:**

```
## CONTEXT (sent to API):

Interviews: I01, I02

### Aggregate Summary:
Code counts per interview:
  1.a: I01=0, I02=0
  1.b: I01=3, I02=0
  2.a: I01=5, I02=8
  ... (all codes)

### ALL QUOTES (sent to API):
QUOTE_ID       → Monday_20260223_Kvant1_lab_transcript-Q001
INTERVIEW_ID   → I01
THEME          → 1
CODE           → 1.b
FULL_QUOTE     → student 2: More technical, I think...
RATIONALE      → ...

QUOTE_ID       → Monday_20260223_Kvant1_lab_transcript-Q002
INTERVIEW_ID   → I01
THEME          → 1
CODE           → 1.b
FULL_QUOTE     → ...
RATIONALE      → ...

[... ALL 43 QUOTES ...]
```

### What AI Sees
1. **Aggregate summary** (code counts only, no quotes)
2. **All raw quotes** from all included interviews (quote_id, interview_id, code, theme, cited_text, rationale)
3. **Prompt instructions** asking to find:
   - Tensions, contradictions, alignments, subtleties
   - Emerging patterns (codes-based)
   - **Irrelevant patterns** (non-codebook themes)

### AI's Task
- **Output ONLY quote_ids** in findings (NOT quote text)
- Reference quotes by `quote_id` only
- Claude uses a **tool call** with structured JSON:
```json
{
  "findings": [
    {
      "finding_type": "alignment",
      "title": "...",
      "description": "...",
      "quote_ids": ["Monday_20260223_Kvant1_lab_transcript-Q007", "..."],
      "codes_involved": ["2.a"],
      "themes_involved": ["2"],
      "confidence": "strong"
    }
  ]
}
```

### Quote Retrieval: Local Post-Processing ✓
**After API response:**
```python
for finding in findings:
    for quote_id in finding["quote_ids"]:
        q = quote_by_id.get(quote_id)  # <-- Local lookup
        finding["quotes"].append({
            "quote_id": quote_id,
            "cited_text": q.get("cited_text"),
            "interview_id": q.get("interview_id"),
            "code": q.get("code")
        })
```

**Why this design?**
- Prevents AI from drifting/modifying quote text
- Keeps token count down (AI doesn't retype quotes)
- Ensures traceability (quote_id → original source)

---

## Summary: What's Sent to API

| Stage | Data Sent | Data NOT Sent |
|-------|-----------|---------------|
| Pass 1 | Full transcript text + current theme | Nothing else needed |
| Pass 2 | Each segment + theme + codebook codes | Other segments |
| Stage 2 | All 43 quotes + aggregate summary | Raw transcripts |

---

## Quote Flow Diagram

```
Transcript (raw text)
    ↓
Pass 1 (AI): Extract segments by theme
    ↓ (in pass1.json)
Pass 2 (AI): Interpret each segment → assign code, quote_id
    ↓ (in pass2.json)
Aggregation (Python): Count, detect duplicates
    ↓ (in aggregate_data.json + aggregate_report.md)
Stage 2 (AI): Find patterns, reference by quote_id only
    ↓ (tool call response)
Post-Processing (Python): Splice full quotes back in locally
    ↓ (in pattern_findings.json + pattern_findings.md)
Final Output: Markdown with full quotes, codes, interview_ids
```

---

## Cost & Efficiency

### Stage 1 Costs
- **Pass 1**: ~1 call per theme (fixed cost)
- **Pass 2**: ~N calls where N = number of segments (variable)

### Stage 2 Cost
- **1 API call** regardless of number of quotes
- All 43 quotes sent as context in single prompt
- Token usage: ~5000-8000 tokens for quotes block + aggregation + prompt

### Optimization: Anti-Drift Pattern
- AI never retypes quote text (quote_id only)
- All splicing happens locally after API call
- Prevents token waste on redundant quote text transmission

---

## Guarantees & Validations

### Stage 1 → Stage 2
✓ `quote_id` is authoritative (never changes)  
✓ `cited_text` is immutable after Pass 2  
✓ `code` & `theme_id` are fixed per quote  

### Stage 2 Post-Processing
✓ If quote_id not found in pass2.json, flag with `[UNRESOLVED]`  
✓ Validate `codes_involved` matches actual codes on cited quotes  
✓ Flag alignments that cite only single-interview quotes  

---

## File Structure Reference

```
output/stage_1/
  ├── I01/
  │   ├── pass1.json        # Segments by theme
  │   ├── pass2.json        # Interpreted quotes with codes
  │   └── metadata.json     # API usage, stop reasons
  ├── I02/
  │   ├── pass1.json
  │   ├── pass2.json
  │   └── metadata.json
  ├── aggregate_data.json   # Deterministic aggregation
  └── aggregate_report.md   # Human-readable summary

outputs/stage_2/
  ├── pattern_findings.json # AI findings + spliced quotes
  ├── pattern_findings.md   # Formatted report
  └── metadata.json         # Hashes, model, usage
```
## Cost Calculation

### Stage 1
- **Pass 1**: 1 call × (full transcript size) = ~500-2000 tokens
- **Pass 2**: 15 calls (one per segment) × ~300-500 tokens each = ~4500-7500 tokens
- **Total Stage 1**: ~5000-9500 tokens

### Stage 2
- **1 call** with all 43 quotes + context = ~6000-8000 tokens
- **No retrieval calls** (all local dict lookups)
- **Total Stage 2**: ~6000-8000 tokens

### Grand Total
- **API tokens**: ~11,000-17,500 tokens
- **Local operations**: Negligible CPU time (<1s)