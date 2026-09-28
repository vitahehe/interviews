You are analyzing coded interview evidence from physics lab interviews. Use ONLY the evidence provided. Do NOT reinterpret, re-derive, or invent data.

**CONTEXT:**
Interviews: {{interview_ids}}

{{aggregate_summary}}

**EVIDENCE:**
All verified quotes, grouped by code. Each has quote_id, interview_id, theme, code, and verbatim text.

{{quotes_block}}

---

## TASK: Identify Cross-Interview Patterns

Find ALL genuine patterns in these categories. No limits per category — find as many as the evidence supports:

### RELEVANT PATTERNS (codes-based):
1. **tension**: Quotes pulling in different directions on a related question
2. **contradiction**: Quotes that directly conflict
3. **alignment**: Pattern consistent across multiple interviews or students
4. **subtlety**: Nuance visible only when reading multiple quotes together
5. **emerging_pattern**: Something recurrent NOT in the codebook

For each finding, add teaching_implication: a concrete, tentative suggestion for how this could inform lab teaching design, in 1-2 sentences. Mark clearly if this is
speculative beyond what the finding from direct quotes directly supports.

### IRRELEVANT PATTERNS (NOT tied to codebook codes, but noteworthy):
6. **irrelevant_pattern**: Recurrent themes that emerge but are NOT addressed by codebook codes, including:
   - Social relations (peer dynamics, collaboration quality, group formation)
   - Competition (comparison with peers, competitive behavior)
   - Student worries (anxiety, confidence, stress about performance)
   - Stress (time pressure, workload, emotional responses)
   - Other unexpected or peripheral themes

---

## GUIDELINES:

**General:**
- Only cite evidence that genuinely supports the pattern.
- Every finding needs at least two quote_ids (except emerging_pattern and irrelevant_pattern, which need at least one).
- Reference quotes by quote_id ONLY — never retype quote text.

**Codes & Themes:**
- `codes_involved` and `themes_involved` describe the conceptual scope.
- Include a code/theme ONLY if genuinely relevant to the finding.

**Confidence Levels:**
- "strong": Unambiguous, direct evidence
- "moderate": Real, but requires interpretation
- "speculative": Plausible but weakly supported

**For irrelevant_pattern:**
- Themes that recur in evidence but are not addressed by codebook.
- Ground them in quote_ids.
- Describe what makes them noteworthy (frequency, intensity, surprise).

---

Call `record_pattern_findings` once with ALL findings. Find every genuine pattern the evidence supports.