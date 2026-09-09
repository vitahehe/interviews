# Interview Qualitative Analysis Pipeline — Technical Details

## System Overview

This document provides comprehensive technical documentation for every component of the interview analysis pipeline, including how data flows through the system, how the AI model is constrained at each stage, what validation checks are performed, and the design rationale behind key decisions.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│ STAGE 1: PER-INTERVIEW ANALYSIS                                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ PHASE 1: SEGMENTATION                                       │   │
│  │ (pipeline/segment_transcript.py)                            │   │
│  │                                                              │   │
│  │  Input:  Raw transcript (speaker-labeled .txt)              │   │
│  │  Output: JSON with turns (turn_id, speaker, text)           │   │
│  │                                                              │   │
│  │  • Speaker recognition: "Student N" or "Bjarke"            │   │
│  │  • Turn = complete speaker monologue until next speaker     │   │
│  │  • Student turns are citation units; interviewer turns      │   │
│  │    are context only                                          │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                            ↓                                          │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ PHASE 2: PASS 1 — EVIDENCE RETRIEVAL                        │   │
│  │ (pipeline/pipeline.py :: run_pass1)                         │   │
│  │                                                              │   │
│  │  Input:  Segmented turns + codebook                         │   │
│  │  Output: JSON with quoted evidence (quotes, turn_ids)       │   │
│  │                                                              │   │
│  │  • One API call per THEME in codebook                       │   │
│  │  • Model searches for evidence in student turns only        │   │
│  │  • Uses CITATIONS-ENABLED RETRIEVAL (no paraphrasing)       │   │
│  │  • Returns: matched code IDs + cited text                   │   │
│  │  • Validation: stop_reason must be "end_turn"              │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                            ↓                                          │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ PHASE 3: PASS 2 — INTERPRETATION                            │   │
│  │ (pipeline/pipeline.py :: run_pass2)                         │   │
│  │                                                              │   │
│  │  Input:  All quotes from Pass 1                             │   │
│  │  Output: JSON with interpretations                          │   │
│  │          (rationale, teaching_implication, etc.)            │   │
│  │                                                              │   │
│  │  • Single API call (all quotes at once)                     │   │
│  │  • Uses FORCED TOOL USE (schema-guaranteed output)          │   │
│  │  • Model interprets each quote independently                │   │
│  │  • Output fields:                                            │   │
│  │    - rationale: why quote matches code                      │   │
│  │    - why_interesting: pedagogical relevance                 │   │
│  │    - teaching_implication: actionable insight               │   │
│  │    - interpretation_grounded_in: "quote_only" or            │   │
│  │      "quote_plus_inference"                                  │   │
│  │  • Quote text is NOT retyped; reinserted post-hoc           │   │
│  │  • Validation: stop_reason must be "end_turn"              │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                            ↓                                          │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ OUTPUTS: 3 files per interview                              │   │
│  │  • pass1.json       (evidence + turn IDs)                   │   │
│  │  • pass2.json       (interpretations + source quotes)       │   │
│  │  • metadata.json    (timing, usage, hashes, validation)     │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                       │
└─────────────────────────────────────────────────────────────────────┘
                                  ↓
┌─────────────────────────────────────────────────────────────────────┐
│ STAGE 2: CROSS-INTERVIEW AGGREGATION & PATTERN ANALYSIS             │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ STEP 1: AGGREGATION & HEALTH CHECKS                         │   │
│  │ (aggregate_stage1.py)                                        │   │
│  │                                                              │   │
│  │  Input:  All output/stage_1/I*/ folders + codebook          │   │
│  │  Output: aggregate_data.json + aggregate_report.md          │   │
│  │                                                              │   │
│  │  Health Checks (Phase 1):                                    │   │
│  │    1. pass2.json exists with non-empty interpretations      │   │
│  │    2. metadata.json exists and is valid JSON                │   │
│  │    3. pass1_calls == codebook theme count                   │   │
│  │    4. All Pass 1 calls have stop_reason="end_turn"         │   │
│  │    5. Pass 2 has stop_reason="end_turn" (if present)       │   │
│  │    → Separates into INCLUDED vs EXCLUDED interviews         │   │
│  │                                                              │   │
│  │  Aggregation (Phase 2):                                      │   │
│  │    • Code × Interview Matrix                                 │   │
│  │      (rows=codes, columns=interviews, values=counts)         │   │
│  │    • Theme × Interview Matrix                                │   │
│  │      (rows=themes, columns=interviews, values=sums)          │   │
│  │    • Grounding Type Breakdown                                │   │
│  │      (quote_only vs quote_plus_inference per code)           │   │
│  │    • Duplicate Citation Detection                            │   │
│  │      (same quote text matched to multiple codes)             │   │
│  │    • Unique Speakers per Code                                │   │
│  │      (alphabetically sorted)                                 │   │
│  │    • Per-Interview Statistics                                │   │
│  │      (total quotes, distinct codes, coverage %)              │   │
│  │    • Zero-Quote Codes                                        │   │
│  │      (codes not found in any included interview)             │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                            ↓                                          │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ STEP 2: CROSS-INTERVIEW PATTERN FINDING                     │   │
│  │ (pipeline/analyze_patterens.py :: run_pattern_analysis)     │   │
│  │                                                              │   │
│  │  Input:  aggregate_data.json + all verified quotes          │   │
│  │  Output: pattern_findings.json + pattern_findings.md        │   │
│  │                                                              │   │
│  │  • Model receives: aggregate summary + all quotes            │   │
│  │  • Uses FORCED TOOL USE for structured findings             │   │
│  │  • Surfaces findings across interviews:                      │   │
│  │    - tensions (conflicting perspectives)                     │   │
│  │    - contradictions (explicit disagreements)                 │   │
│  │    - alignments (consistent patterns)                        │   │
│  │    - subtleties (nuanced observations)                       │   │
│  │    - emerging_patterns (novel themes)                        │   │
│  │    - irrelevant_patterns (to be discarded)                   │   │
│  │  • References quotes by ID only (text reinserted post-hoc)   │   │
│  │  • Validation: stop_reason must be "end_turn"              │   │
│  │  • Post-processing:                                          │   │
│  │    - Resolves quote text and metadata                        │   │
│  │    - Flags single-interview-only findings                    │   │
│  │    - Flags code mismatches in findings                       │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                            ↓                                          │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ OUTPUTS: 2 files for all interviews                         │   │
│  │  • pattern_findings.json (structured findings + quotes)     │   │
│  │  • pattern_findings.md   (human-readable report)            │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                       │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Component Details

### Stage 1: Per-Interview Analysis

#### 1. Segmentation (segment_transcript.py)

**Responsibility:** Convert raw, speaker-labeled interview transcripts into structured turn-level JSON.

**Input Format:**
```
Speaker labels (one per line, standalone):
  - "Student 1", "Student 2", ..., "Student N" (students)
  - "Bjarke" (interviewer)

Speaker content:
  - Everything after speaker label until next speaker label
  - Preserves original line breaks and formatting
```

**How Chunks Are Defined:**
- **Turn** = complete speaker monologue
  - Starts after a speaker label
  - Ends before the next speaker label
  - Example: I01-T001 (Interview 01, Turn 001)
  - Speaker labels are extracted and preserved exactly as given
  
- **Student Turn** = turn spoken by a student
  - This becomes the **citable unit** in Pass 1
  - Interviewer turns are kept for context but not quotable
  - Rationale: Interview answers are the evidence; interviewer prompts are scaffolding

**Output Structure:**
```json
{
  "interview_id": "I01",
  "turns": [
    {
      "turn_id": "I01-T001",
      "speaker": "Student 1",
      "text": "I think the experiment was interesting because..."
    },
    ...
  ]
}
```

**Validation:**
- Confirms speaker lines match regex: `^(Student \d+|Bjarke)$` (case-insensitive)
- Counts total turns and student-only turns
- Outputs summary: `"Wrote 47 turns (28 student quote units) to ..."`

---

#### 2. Pass 1: Evidence Retrieval (pipeline.py :: run_pass1)

**Responsibility:** Find evidence for each code in the codebook by searching student turns.

**Key Design Principle: Citations-Enabled Retrieval**
- Model uses Anthropic's citation mechanism to directly quote from the provided document
- Model CANNOT paraphrase or approximate quotes
- Eliminates hallucination of "evidence" that doesn't exist in the transcript
- Prevents the model from forcing marginal matches

**Input:**
- Codebook (themes with codes, descriptions, and motivations)
- Segmented turns
- System prompt (core constraints: "never state a quote supports a code unless drawn from transcript"; "if no part supports it, say so explicitly")
- Pass 1 prompt template

**Processing:**
1. For each THEME in codebook (sequentially):
   - Model receives: theme description, all codes in theme, all student turns
   - Model outputs: for each code in order:
     - Marker: `[[CODE:X.Y]]` (code ID)
     - Either: direct citations (using citation mechanism), or `[[NONE]]` (no evidence)
   
2. **Student-Turn-Only Citation Document:**
   - Only student turns are included as citable content blocks
   - Interviewer turns are NOT citable
   - Each block = one complete student turn
   - Rationale: interview quality data is student response; interviewer moves are procedural

3. **AI Constraint: Citation-Based Retrieval:**
   - System prompt: "Never state that a quote supports a code unless the quote is drawn directly from the provided transcript document. Do not paraphrase or summarize transcript speech as if it were a quote."
   - API enforces: `"citations": {"enabled": true}` on the custom content document
   - Model must use Anthropic's citation mechanism (`[start_block_index, end_block_index]`)
   - No paraphrasing allowed; no "approximately" matches

4. **Output Parsing:**
   - Extract citations from response content blocks
   - Map citation indices to original student turn IDs and speaker names
   - Assign quote_id (e.g., I01-Q001, I01-Q002, ...)
   - Store: `{quote_id, code, cited_text, turn_ids, speakers, theme_id}`

**Output: pass1.json**
```json
{
  "interview_id": "I01",
  "quotes": [
    {
      "quote_id": "I01-Q001",
      "theme_id": "1",
      "code": "1.a",
      "cited_text": "I thought it would be easy, but there were some tricky parts.",
      "turn_ids": ["I01-T005"],
      "speakers": ["Student 1"]
    },
    ...
  ],
  "codes_with_no_quotes": ["2.b", "3.a"]
}
```

**Validation (via metadata.json):**
- `pass1_calls` must equal `codebook theme count` (one call per theme)
- `pass1_usage_per_theme[*].stop_reason` must all be `"end_turn"`
- If stop_reason is `"max_tokens"` or `"tool_use"`, interview is marked EXCLUDED

**Token Usage Tracking:**
- Per-theme usage (input tokens, output tokens, cache hits)
- Aggregated across all themes
- Stored in metadata for auditing and cost analysis

---

#### 3. Pass 2: Interpretation (pipeline.py :: run_pass2)

**Responsibility:** For each quote found in Pass 1, record structured interpretative analysis.

**Key Design Principle: Forced Tool Use**
- Model outputs a single tool call with all interpretations at once
- Tool schema is enforced by API; model cannot deviate
- Guarantees output matches expected JSON structure exactly
- No post-processing needed to normalize or re-parse model output

**Input:**
- All quotes from Pass 1 (with code metadata)
- Codebook (for code descriptions and names)
- System prompt (same as Pass 1: emphasis on grounding in provided text)
- Pass 2 prompt template

**Processing:**
1. Build **quotes block** with all Pass 1 quotes formatted for the model:
   ```
   - quote_id: I01-Q001
     code: 1.a (Expected difficulty - easy)
     speakers: Student 1
     quote: "I thought it would be easy..."
   
   - quote_id: I01-Q002
     ...
   ```

2. Call API with:
   - `tool_choice={"type": "tool", "name": "record_interpretation"}` (forced)
   - `max_tokens=18000` (larger for complex reasoning)
   - `messages=[{"role": "user", "content": user_text}]`

3. **Model Constraints** (via system prompt + tool schema):
   - Rationale: must explain why the quote supports the code
   - Why_interesting: must connect to teaching/learning context
   - Teaching_implication: must be actionable (not vague)
   - Interpretation_grounded_in: must classify as "quote_text_only" or "quote_plus_inference"
     - "quote_text_only": everything is explicitly in the quote
     - "quote_plus_inference": includes reasonable inference from context

4. **Quote Text Anti-Drift Pattern:**
   - Model NEVER retypes or regenerates quote text
   - Input to Pass 2: `{quote_id, cited_text, code, ...}`
   - Model output: `{quote_id, rationale, why_interesting, teaching_implication, interpretation_grounded_in}`
   - Post-processing: re-attach original `cited_text` to each interpretation
   - Rationale: if model re-typed quotes, drift/hallucination could occur; sourcing from Pass 1 guarantees accuracy

5. **Output Parsing:**
   - Extract tool_use block from response
   - Verify stop_reason is "end_turn" or "tool_use"
   - Merge interpretations with original quote metadata

**Output: pass2.json**
```json
{
  "interview_id": "I01",
  "interpretations": [
    {
      "quote_id": "I01-Q001",
      "rationale": "Student explicitly states prior expectation that course would be easy.",
      "why_interesting": "Prior self-efficacy beliefs shape engagement and motivation; comparing expectations to actual experience helps understand learning gains.",
      "teaching_implication": "Could survey students upfront about difficulty expectations; if many underestimate, may need scaffolding or clearer learning objectives.",
      "interpretation_grounded_in": "quote_text_only",
      "cited_text": "I thought it would be easy...",
      "code": "1.a",
      "theme_id": "1",
      "speakers": ["Student 1"],
      "turn_ids": ["I01-T005"]
    },
    ...
  ]
}
```

**Validation (via metadata.json):**
- `pass2_usage.stop_reason` must be "end_turn" or "tool_use"
- If stop_reason is "max_tokens", interview is marked EXCLUDED
- Timing: records Pass 1 time and Pass 2 time separately

---

#### 4. Metadata & Integrity Checks (pipeline.py)

**Purpose:** Track pipeline execution, enable reproducibility, and flag incomplete/invalid results.

**Metadata Contents:**
```json
{
  "interview_id": "I01",
  "model": "claude-sonnet-5",
  "codebook_hash": "a1b2c3d4e5f6g7h8",         // SHA256 first 16 chars
  "pass1_prompt_hash": "x1y2z3w4v5u6t7s8",      // ensures prompt version
  "pass2_prompt_hash": "...",
  "system_prompt_hash": "...",
  "pass1_calls": 5,                             // should equal codebook theme count
  "pass1_usage_per_theme": [
    {
      "theme_id": "1",
      "usage": {
        "input_tokens": 2840,
        "output_tokens": 312,
        "cache_creation_input_tokens": 0,
        "cache_read_input_tokens": 0
      },
      "stop_reason": "end_turn"  // CRITICAL: must be "end_turn"
    },
    ...
  ],
  "pass2_usage": {
    "input_tokens": 8921,
    "output_tokens": 3401,
    "cache_creation_input_tokens": 0,
    "cache_read_input_tokens": 0
  },
  "timing_seconds": {
    "pass1": 42.15,
    "pass2": 28.33
  },
  "quote_count": 47,
  "codes_with_no_quotes": ["2.b", "3.a", ...]
}
```

**Hash-Based Integrity:**
- Codebook, prompts, and system message are hashed
- If prompts change, hash changes → data is linked to specific prompt version
- Enables auditing: "which version of the prompt produced this result?"

---

### Stage 2: Cross-Interview Aggregation & Analysis

#### 1. Aggregation & Health Checks (aggregate_stage1.py)

**Responsibility:** Consolidate outputs from multiple interviews, validate integrity, and produce cross-interview matrices and summary statistics.

**Phase 1: Discovery & Health Checks**

Process:
1. Scan `output/stage_1/` for subdirectories (e.g., I01, I02, I03)
2. For each directory, run 5 health checks:

   **Check 1:** pass2.json exists with non-empty interpretations array
   - Ensures the interview has at least one code match
   - Issue: "pass2.json does not exist" or "has no interpretations array or it is empty"

   **Check 2:** metadata.json exists and is valid JSON
   - Ensures metadata was written successfully
   - Issue: "metadata.json does not exist" or "is invalid JSON: ..."

   **Check 3:** pass1_calls == len(codebook["themes"])
   - Ensures one API call per theme (all themes were processed)
   - Issue: "pass1_calls (4) != codebook theme count (5)"

   **Check 4:** All entries in pass1_usage_per_theme have stop_reason == "end_turn"
   - Ensures all theme passes completed normally (no max_tokens, tool_use, etc.)
   - Issue: "Theme 3 pass1 stop_reason is 'max_tokens', not 'end_turn'"

   **Check 5:** pass2_stop_reason == "end_turn" (if field exists)
   - Ensures Pass 2 completed normally
   - Issue: "pass2 stop_reason is not 'end_turn'"

3. Separate interviews:
   - **INCLUDED:** passed all 5 checks
   - **EXCLUDED:** failed any check, with reasons listed

**Output Sections:**
```json
{
  "included_interviews": ["I01", "I03"],
  "excluded_interviews": {
    "I02": ["pass1_calls (3) != codebook theme count (5)"]
  },
  ...
}
```

---

**Phase 2: Aggregation**

**Matrix 1: Code × Interview Matrix**
- Rows: all codes from codebook (in order), including those with 0 quotes
- Columns: included interview IDs (sorted)
- Values: count of interpretations per code per interview
- Purpose: shows which codes are active across which interviews

```
         I01  I03
1.a       5    2
1.b       0    3
1.c       1    1
2.a       2    0
...
```

**Matrix 2: Theme × Interview Matrix**
- Rows: all themes from codebook (in order)
- Columns: included interview IDs
- Values: sum of all codes within each theme per interview
- Purpose: high-level overview of theme activity

```
         I01  I03
1        6    6
2        8    4
3        3    2
...
```

**Grounding Type Breakdown (per code)**
- For each code, count interpretations by grounding type:
  - "quote_text_only": interpretation requires only the quote text
  - "quote_plus_inference": interpretation requires background knowledge or reasoning
- Output:
  ```
  {
    "1.a": {
      "quote_only": 5,
      "quote_plus_inference": 2,
      "total": 7
    },
    ...
  }
  ```
- Purpose: distinguishes data-driven vs. interpretive findings

**Duplicate Citation Detection**
- Within each interview, normalize whitespace in cited_text
- Group interpretations by normalized text
- When same text appears under multiple codes → record code pair
- Aggregate co-occurrence counts across all interviews
- Output:
  ```json
  {
    "code_pair": ["1.a", "2.b"],
    "co_occurrence_count": 3,
    "examples": [
      {
        "interview_id": "I01",
        "cited_text": "..."
      }
    ]
  }
  ```
- Purpose: identifies quotes that satisfy multiple codes (potential coding overlap)

**Unique Speakers per Code**
- For each code, collect all unique speaker names from interpretations
- Sort alphabetically
- Output:
  ```json
  {
    "1.a": ["Student 1", "Student 2", "Student 3"],
    "1.b": ["Student 1"],
    ...
  }
  ```
- Purpose: shows which students contributed evidence for each code

**Per-Interview Statistics**
- Total quote count (size of interpretations array)
- Distinct codes triggered (unique codes with at least 1 quote)
- Percentage of codebook covered (distinct codes / total codes in codebook)
- Output:
  ```json
  {
    "I01": {
      "total_quotes": 47,
      "distinct_codes": 18,
      "coverage_percent": 75.0
    },
    ...
  }
  ```
- Purpose: summary statistics for each interview's coding completeness

**Zero-Quote Codes**
- Codes that appear 0 times across ALL included interviews
- Output:
  ```json
  {
    "zero_quote_codes": ["2.d", "3.b", "4.a"]
  }
  ```
- Purpose: identifies under-sampled aspects of the codebook

---

**Outputs:**

1. **aggregate_data.json** (machine-readable, for Stage 2 Step 2)
   ```json
   {
     "included_interviews": [...],
     "excluded_interviews": {...},
     "code_interview_matrix": {...},
     "theme_interview_matrix": {...},
     "grounding_breakdown": {...},
     "duplicate_citations_by_pair": [...],
     "unique_speakers_per_code": {...},
     "interview_stats": {...},
     "zero_quote_codes": [...]
   }
   ```

2. **aggregate_report.md** (human-readable summary)
   - Summary statistics (interview count, total quotes, distinct codes)
   - Formatted tables for code × interview, theme × interview
   - Grounding type percentages
   - Duplicate citation pairs (sorted by frequency)
   - Unique speakers per code
   - Codes with zero quotes

---

#### 2. Cross-Interview Pattern Finding (analyze_patterens.py)

**Responsibility:** Use AI to surface tensions, contradictions, alignments, and emerging themes across multiple interviews.

**Key Design Principle: Forced Tool Use + Quote Deduplication**
- Model generates findings as a single tool call
- Findings reference quotes by ID only (no text generation)
- Text is spliced back post-hoc from verified Pass 1 quotes
- Prevents quote drift and ensures all cited evidence is traceable

**Input:**
- aggregate_data.json (matrices, counts, statistics)
- All verified quotes from all included interviews (loaded from each interview's pass2.json)
- System prompt
- Stage 2 pattern prompt template

**Processing:**

1. **Load All Verified Quotes**
   - For each included interview: load pass2.json
   - Append interview_id to each quote for cross-interview tracking
   - Result: list of all {quote_id, interview_id, code, cited_text, rationale, ...}

2. **Build Model Input:**

   **Aggregate Summary Block:**
   - Code × interview matrix (text representation)
   - Zero-quote codes
   - Duplicate citation pairs
   - Rationale: model sees consolidated view of patterns

   **Quotes Block:**
   - All quotes with metadata:
     ```
     QUOTE_ID       → I01-Q001
     INTERVIEW_ID   → I01
     THEME          → 1
     CODE           → 1.a
     FULL_QUOTE     → "I thought it would be easy..."
     RATIONALE      → "Student explicitly states..."
     ```
   - Model reads verbatim from this block (no regeneration)

3. **Model Constraints** (via FINDINGS_TOOL schema):

   **Finding Type Enumeration:**
   - `tension`: perspectives that pull in different directions (not necessarily contradictory)
   - `contradiction`: explicit disagreements or incompatible statements
   - `alignment`: consistent patterns across multiple interviews
   - `subtlety`: nuanced observations requiring careful interpretation
   - `emerging_pattern`: novel themes not previously anticipated
   - `irrelevant_pattern`: to be discarded (model may flag false patterns)

   **Required Output Fields (tool schema enforces):**
   ```
   {
     "finding_type": "enum[tension|contradiction|alignment|subtlety|emerging_pattern|irrelevant_pattern]",
     "title": "string (1-10 words)",
     "description": "string (2-3 sentences)",
     "quote_ids": ["I01-Q001", "I03-Q005", ...],
     "themes_involved": ["1", "2", ...],
     "codes_involved": ["1.a", "2.b", ...],
     "confidence": "enum[strong|moderate|speculative]"
   }
   ```

   **AI Constraints:**
   - quote_ids: model must reference only IDs from the provided quotes list
   - themes_involved, codes_involved: must be extracted from quotes' theme/code fields
   - confidence: model must justify confidence based on evidence (# quotes, consistency, etc.)
   - description: must explicitly reference the findings, not just restate codes

4. **Output Parsing & Post-Processing:**
   - Extract tool_use block
   - For each finding, resolve quote_ids back to full quote objects
   - Splice in cited_text, speakers, turn_ids
   - Validate:
     - All quote_ids exist in the verified quotes list
     - codes_involved matches actual codes in cited quotes (flag if mismatch)
     - If all quotes are from single interview: flag as "single_interview_only" (not cross-interview)
   - Output: updated finding with full quote details

   **Post-Processing Checks:**
   ```python
   # For each finding:
   if len(set([q.interview_id for q in quotes])) == 1:
       finding["single_interview_only"] = True
   
   if set(finding.codes_involved) != set([q.code for q in quotes]):
       finding["codes_involved_consistent"] = False
       finding["codes_involved_actual"] = sorted(set([q.code for q in quotes]))
   ```

5. **Validation:**
   - stop_reason must be "end_turn" or "tool_use"
   - All quote_ids must exist
   - Findings are deduplicated (by title + key structure)

---

**Output: pattern_findings.json**
```json
{
  "interview_count": 2,
  "included_interviews": ["I01", "I03"],
  "findings": [
    {
      "finding_type": "tension",
      "title": "Self-Efficacy vs. Actual Difficulty Experience",
      "description": "Students who expected the lab to be easy initially encountered unexpected challenges. This creates tension between prior beliefs and actual experience, which may influence motivation and engagement.",
      "quote_ids": ["I01-Q005", "I03-Q018"],
      "quotes": [
        {
          "quote_id": "I01-Q005",
          "interview_id": "I01",
          "code": "1.a",
          "cited_text": "I thought it would be easy...",
          "speakers": ["Student 1"],
          "rationale": "Student explicitly states..."
        },
        ...
      ],
      "themes_involved": ["1"],
      "codes_involved": ["1.a", "1.c"],
      "confidence": "strong",
      "single_interview_only": false,
      "codes_involved_consistent": true
    },
    ...
  ]
}
```

---

**Output: pattern_findings.md**

Human-readable report organized by finding type:

```markdown
# Stage 2 — Cross-Interview Pattern Findings

## Contradiction

**Student Accountability vs. External Factors** (confidence: strong)
Some students attribute learning outcomes to their own effort, while others emphasize instructor guidance or experimental difficulty.

Themes: 2, 3 | Codes: 2.a, 3.a

Supporting quotes:
- [I01-Q001 | I01 | 2.a] "I figured it out myself by trying different approaches"
- [I03-Q045 | I03 | 3.a] "The instructions could have been clearer"

...

## Alignment

**Positive Experience Across Students** (confidence: moderate)
Multiple students report enjoying collaborative aspects of the lab.

...
```

---

## Features & Design Rationale

### 1. Citations-Enabled Retrieval (Pass 1)

**What it does:**
- Anthropic API enforces that model quotes from provided document
- Model uses citation mechanism (`[start_block_index, end_block_index]`)
- Model cannot rephrase or approximate

**Why:**
- Prevents hallucination: model cannot invent "evidence"
- Prevents forced matches: model explicitly says "[[NONE]]" when no match
- Maintains data fidelity: all quotes are verbatim from transcript
- Auditable: every quote can be traced to specific turn ID

**Constraint Applied:**
```python
doc = {
    "type": "document",
    "source": {
        "type": "content",
        "content": [
            {"type": "text", "text": f"{turn['speaker']}: {turn['text']} "}
            for turn in student_turns
        ]
    },
    "title": "Interview transcript",
    "citations": {"enabled": True}  # CONSTRAINT
}
```

---

### 2. Forced Tool Use (Pass 2 & Stage 2 Step 2)

**What it does:**
- Anthropic API enforces that model outputs one tool call
- Tool schema defines exact output structure
- Model cannot deviate from schema

**Why:**
- Guarantees output format: no parsing errors, no surprises
- Consistent structure: all interpretations have rationale, why_interesting, etc.
- Schema-as-constraint: tool definition IS the validation rule
- Post-processing is minimal: trust the output structure

**Constraint Applied:**
```python
response = client.messages.create(
    model=model,
    tools=[INTERPRETATION_TOOL],
    tool_choice={"type": "tool", "name": "record_interpretation"},  # CONSTRAINT
    messages=[...]
)
```

---

### 3. Quote Versioning (Anti-Drift Pattern)

**What it does:**
- Pass 1 retrieves and stores quote text
- Pass 2 references quotes by ID only, does NOT regenerate text
- Text is re-attached from Pass 1 after interpretation
- Stage 2 references quote IDs; text is looked up from Stage 1 data

**Why:**
- Prevents quote drift: if model regenerated quotes, small changes could accumulate
- Ensures traceability: every quote text is sourced from segmented transcript
- Immutability: quote text is fixed after Pass 1 and never modified

**Implementation:**
```python
# Pass 2 input to model:
# {quote_id: "I01-Q001", code: "1.a", ...}  # NO cited_text

# Pass 2 model output:
# {quote_id: "I01-Q001", rationale: "...", ...}  # NO cited_text

# Pass 2 post-processing:
for interp in interpretations:
    source_quote = quote_by_id.get(interp["quote_id"], {})
    interp["cited_text"] = source_quote.get("cited_text")
```

---

### 4. Health Checks & Integrity Validation

**What it does:**
- 5 checks per interview before inclusion
- Separates INCLUDED vs EXCLUDED interviews
- Flags partial or compromised runs

**Why:**
- Reproducibility: ensures all included data meets quality bar
- Traceability: exclusion reasons are recorded for audit
- Safety: prevents analysis of incomplete runs
- Transparency: human reviewer can see what was excluded and why

**Check Specifics:**
```
✓ pass2.json exists with interpretations
✓ metadata.json exists and is valid
✓ pass1_calls == codebook theme count (all themes processed)
✓ All Pass 1 calls have stop_reason="end_turn" (completed normally)
✓ Pass 2 has stop_reason="end_turn" (completed normally, if present)
```

---

### 5. File Hashing for Reproducibility

**What it does:**
- SHA256 hashes of codebook, prompts, and system message
- Stored in metadata.json

**Why:**
- Audit trail: links data to specific prompt version
- Reproducibility: if you have the same files + same model + same prompts → same results
- Change tracking: if prompt is updated, hash changes → old data is linked to old version
- Debugging: if results seem wrong, can check which prompt was used

**Implementation:**
```python
metadata = {
    "codebook_hash": hashlib.sha256(Path(codebook).read_bytes()).hexdigest()[:16],
    "pass1_prompt_hash": hashlib.sha256(...).hexdigest()[:16],
    "pass2_prompt_hash": hashlib.sha256(...).hexdigest()[:16],
    "system_prompt_hash": hashlib.sha256(...).hexdigest()[:16],
}
```

---

### 6. Token Usage & Cost Tracking

**What it does:**
- Records input tokens, output tokens, and cache hits per Pass 1 call
- Records total usage for Pass 2 and Stage 2 Step 2
- Tracks timing (seconds per pass)

**Why:**
- Cost auditing: can calculate API expenses
- Performance monitoring: identifies slow passes
- Cache optimization: track when prompt caching reduces tokens
- Budgeting: plan future analysis based on historical costs

**Data Captured:**
```json
{
  "input_tokens": 2840,
  "output_tokens": 312,
  "cache_creation_input_tokens": 0,
  "cache_read_input_tokens": 0
}
```

---

## Data Flow & Traceability

### Tracing a Single Quote

1. **Source:** raw transcript line (e.g., "Student 1: I thought it would be easy...")
2. **After Segmentation:** stored in turn (turn_id=I01-T005, speaker=Student 1, text="...")
3. **Pass 1 Retrieval:** cited via Anthropic citations mechanism
4. **Pass 1 Output:** quote_id=I01-Q001, cited_text="...", turn_ids=[I01-T005], speakers=[Student 1]
5. **Pass 2 Input:** referenced by quote_id only (text NOT regenerated)
6. **Pass 2 Output:** interpretation with quote_id, rationale, teaching_implication, etc.
7. **Pass 2 Post-Processing:** cited_text re-attached from quote_by_id lookup
8. **Aggregation:** interpretations counted in code × interview matrix
9. **Duplicate Detection:** normalized text "i thought it would be easy..." grouped with other similar quotes
10. **Stage 2 Input:** included in quotes_block verbatim
11. **Stage 2 Finding:** referenced by quote_id in pattern findings
12. **Stage 2 Output:** full quote details (text, speakers, rationale, etc.) included in final markdown report

**Verification:** Any quote in final output can be traced back to:
- Exact turn in segmented JSON
- Exact line in raw transcript
- Interpretation stored in Pass 2
- Health checks that validated the interview

---

## Exclusion & Validation Scenarios

### Scenario 1: Interview Excluded in Aggregation

```json
{
  "included_interviews": ["I01"],
  "excluded_interviews": {
    "I03": [
      "pass1_calls (3) != codebook theme count (5)"
    ]
  }
}
```

**Interpretation:** Interview I03 ran only 3 Pass 1 calls instead of 5, meaning 2 themes were not processed. Likely causes:
- API error mid-run (e.g., timeout)
- Incomplete pipeline run
- Bug in pipeline code

**Action:** Rerun `python pipeline/pipeline.py` for I03.

---

### Scenario 2: Quote Referenced in Finding But Not Found

```python
if quote_id not in quote_by_id:
    # Post-processing catches this
    logging.warning(f"Finding references unknown quote_id: {quote_id}")
```

**Prevention:** Stage 2 only uses quote_ids that exist in pass2.json files (verified during load_all_quotes).

---

### Scenario 3: Code Mismatch in Finding

```json
{
  "finding": {
    "quote_ids": ["I01-Q001", "I03-Q045"],
    "codes_involved": ["2.a"],
    "codes_involved_consistent": false,
    "codes_involved_actual": ["1.a", "2.a"]
  }
}
```

**Interpretation:** Model claimed finding is about code 2.a, but actually involves both 1.a and 2.a. This is flagged for human review.

**Prevention:** Post-processing checks and flags these mismatches:
```python
model_codes = set(finding.get("codes_involved", []))
actual_codes = set(q["code"] for q in quotes)
if model_codes != actual_codes:
    finding["codes_involved_consistent"] = False
    finding["codes_involved_actual"] = sorted(actual_codes)
```

---

## System Prompt & AI Constraints

### System Prompt (system_prompt.md)

Core constraints applied to all API calls:

1. **Evidence-Based Only:**
   - "Never state that a quote supports a code unless the quote is drawn directly from the provided transcript document."
   - "Do not paraphrase or summarize transcript speech as if it were a quote."

2. **Explicit Negation:**
   - "If no part of the transcript supports a code, say so explicitly. Do not force a marginal or weak match to fill in an answer."

3. **Speaker Identity:**
   - "Speaker labels ('student 1', 'student 2', 'student 3', 'Bjarke') must be preserved exactly as given; do not guess a speaker's identity beyond the label provided."

4. **Quote Integrality:**
   - "When citing a student turn, cite the complete turn as provided. Do not force a code onto a turn that only weakly or vaguely relates to it."

---

### Pass 1 Prompt (pass1_prompt.md)

Instructs model to:
1. Go through student turns one by one
2. For each code (in order):
   - Output marker: `[[CODE:X.Y]]`
   - If supported: cite using citation mechanism
   - If not: output `[[NONE]]`
3. Do not retype quotes; use citation mechanism

---

### Pass 2 Prompt (pass2_prompt.md)

Provides quotes and instructs model to interpret each. Rationale field should explain code match. Teaching_implication should be actionable. Grounding field should classify quote_only vs. quote_plus_inference.

---

### Stage 2 Prompt (stage2_pattern_prompt.md)

Instructs model to:
1. Examine all quotes across all interviews
2. Identify patterns by type (tension, contradiction, alignment, etc.)
3. Reference quotes by ID only (model does not retype quotes)
4. Classify confidence (strong, moderate, speculative) with justification
5. Ensure findings span multiple interviews (for alignments/contradictions)

---

## Error Handling & Recovery

### Pass 1 Incomplete (< N themes processed)

```
Detected: pass1_calls (3) != codebook theme count (5)
Action: Interview marked EXCLUDED in aggregation
Recovery: Rerun pipeline.py for that interview
```

### Pass 2 Incomplete (stop_reason != "end_turn")

```
Detected: metadata.pass2_usage.stop_reason = "max_tokens"
Action: Interview marked EXCLUDED in aggregation
Recovery: Increase max_tokens for Pass 2 and rerun
```

### Aggregation Phase 1 (all interviews excluded)

```
Detected: included_interviews = []
Action: aggregate_data.json and aggregate_report.md are generated but empty/minimal
Recovery: Debug why all interviews failed health checks; fix and rerun
```

### Stage 2 Quote Lookup Failure

```
Detected: quote_id not in quote_by_id
Action: Logged as warning; finding is not generated
Recovery: Ensure Stage 2 uses aggregate_data.json from same aggregation run; ensure all pass2.json files are present
```

---

## Summary of AI Constraints

| Stage | Component | Constraint Type | Implementation |
|-------|-----------|-----------------|-----------------|
| 1 | Pass 1 | Citations-enabled retrieval | API parameter: `citations.enabled=true` |
| 1 | Pass 1 | No paraphrasing | System prompt + citation mechanism |
| 1 | Pass 2 | Forced tool use | API parameter: `tool_choice={type:tool, name:...}` |
| 1 | Pass 2 | Schema-guaranteed output | INTERPRETATION_TOOL definition |
| 1 | Pass 2 | Quote immutability | Quote text sourced from Pass 1, never regenerated |
| 2 | Aggregation | Health checks | 5-check validation gate |
| 2 | Pattern Finding | Forced tool use | API parameter: `tool_choice={type:tool, name:...}` |
| 2 | Pattern Finding | Quote traceability | Quote IDs referenced, text looked up post-hoc |
| All | All | Reproducibility | File hashes + metadata tracking |
| All | All | Auditability | All API calls logged with usage, timing, stop_reason |

---

## Extending the Pipeline

### Adding a New Code to the Codebook

1. Edit `codebook.yaml`: add new code to appropriate theme
2. Rerun `pipeline/pipeline.py` for all interviews
   - Pass 1 will search for evidence for the new code
   - Pass 2 will interpret any new quotes
3. Run `python aggregate_stage1.py` to regenerate matrices
4. Run `python pipeline/analyze_patterens.py` to re-analyze patterns

### Adjusting a Prompt

1. Edit prompt file (e.g., `prompts/pass1_prompt.md`)
2. Hash will change automatically (stored in metadata)
3. Rerun `pipeline/pipeline.py` for all interviews
   - Old data remains with old hash; new runs have new hash
   - Can compare results across prompt versions if needed
4. Rerun aggregation and pattern finding

### Changing the Model

```bash
python pipeline/pipeline.py \
  ... \
  --model claude-opus-5  # instead of claude-sonnet-5
```

- Usage and timing may differ
- Metadata will record the model name and hashes
- Results are comparable if prompts and codebook are identical

---

## Conclusion

This pipeline implements a **constrained, auditable, reproducible** system for qualitative analysis. Every stage:
- Uses API constraints to prevent hallucination or forcing
- Tracks metadata (hashes, timing, usage, stop_reason)
- Applies health checks to ensure quality
- Traces data back to source (raw transcript)
- Produces human-readable and machine-readable outputs

The design prioritizes **evidence-based interpretation**, **schema guarantees**, and **end-to-end traceability**.
