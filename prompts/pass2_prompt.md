You are given a set of quotes already verified as coming directly from
interview transcripts, each tagged with the code it was matched to. Do not
alter, shorten, or re-quote the text of any quote. For each quote, call the
`record_interpretation` tool once with:

- quote_id (as given)
- rationale: why this quote fits its assigned code, in 1-2 sentences,
  referring only to what the quote itself says
- why_interesting: what is notable about this quote for understanding student
  experience, in 1-2 sentences
- interpretation_grounded_in: "quote_text_only" if your rationale relies
  strictly on the quote's wording, or "quote_plus_inference" if it involves
  reading between the lines.

Quotes:
{{ quotes_block }}