You are analyzing coded interview evidence across multiple interviews from
the same physics lab course, already extracted and verified in a prior
stage. Your task is to identify genuine cross-interview patterns -- not to
re-derive counts, which are provided below and already computed correctly.

Aggregate counts across {{interview_count}} interviews ({{interview_ids}}):
{{aggregate_summary}}

Below are all verified quotes from these interviews, grouped by code. Each
quote has a quote_id, interview_id, theme, code, the verbatim quote, and the
prior interpretation notes.

{{quotes_block}}

Using only this evidence, identify findings in these categories:
- tension: two or more quotes pulling in different directions on a related
  question, whether within one interview or across interviews
- contradiction: a stronger case where quotes appear to directly conflict
- alignment: a pattern consistent across multiple interviews or students
- subtlety: a nuance visible only when reading multiple quotes together,
  not evident from any single quote or from the counts alone
- emerging_pattern: something the original codebook does not have a code
  for, but that recurs across the evidence

For each finding, call record_pattern_findings once with the full list.
Reference supporting evidence ONLY by quote_id -- do not retype or
paraphrase quote text into your description; describe the pattern itself
and let the quote_ids carry the evidence. Every finding must cite at least
two quote_ids, except emerging_pattern findings which need at least one.
Assign a confidence level: "strong" if quotes are unambiguous and directly
support the finding, "moderate" if the case is real but relies on some
interpretation, "speculative" if it's a plausible but weakly-supported
observation. Do not manufacture findings to fill a quota -- if the evidence
does not support a category, omit it.