first STAGES:

1. Transcripts
you have a folder called transcripts, throw in your transcribed interviews. It would be amazing to have a seperate .rd file 
that sumamrizes which symbols did you use for scilences, confusions, annoyance etc. 
If you did any local coding, be free to pus it in this folder.  each interview-= specific file name
any other thing you did with it, throw it here:)

2. annotation of data. You can find more detaild explanation and methodology of creating this step on the shared Miro board.
This is the current prompy, please change the symbol table based on your transcription process. 
The outputs of mlls can be found in annotation folder. Let me know if you see anything that you think requires change!!!

PROMPT:

You are assisting with qualitative annotation of a semi-guided group interview about a laboratory-based physics course.
The input is a raw transcript in .txt format. The transcript contains speaker labels such as "student 1", "student 2", etc,  and "NAME OF INTERVIEWER". The interview may include unfinished sentences, repetition, hesitation, informal language, and long turns.

Your task is NOT to produce final themes.
Your task is NOT to identify contradictions or tensions.
Your task is to produce a loss-minimizing (using FULL TEXT OF THE interview), sequence-preserving annotation of the full interview.

MAIN GOAL:
Chunk the entire interview into meaning units while preserving every word of the original transcript. Each chunk should keep track of:
- the order of the interview,
- who is speaking,
- what they said,
- whether the speaker is interviewer or participant,
- which defined codes apply,
- memo information.

IMPORTANT PRINCIPLES:
1. Preserve all interview material.
2. Every spoken part of the transcript must appear in exactly one chunk.
3. Do not skip interviewer questions, filler, hesitation, confusion, repetition, or unclear parts.
4. Do not rewrite ANYTHING. 
5. Track speaker labels exactly as they appear.
6. Maintain sequence: first this was said, then that was said.
7. Allow overlapping codes.
8. A chunk may receive zero, one, or multiple codes.
9. Use ONLY the codes listed in the DEFINED CODEBOOK below.
10. Do not invent new formal codes. If a chunk does not fit any defined code, leave "codes": [] and describe it in the memo field "non_defined_candidate_code".
11. Do NOT mark contradictions or tensions in this stage, Do NOT create themes, Do NOT summarize the whole interview, Do NOT infer psychological states beyond the transcript.
12. If uncertain, mark "human_review_needed": true.

CHUNKING RULES:
- Chunk by meaning unit, not by fixed length.
- A meaning unit is the smallest coherent piece of speech that expresses one idea, experience, comparison, explanation, or question.
- Keep interviewer questions as chunks too.
- If one speaker turn contains several analytically different ideas, split it into multiple chunks.
- If several short lines belong together and express one idea, they may be combined into one chunk.
- Never combine speech from different speakers into one chunk.
- Each chunk must have a "sequence_number" so the order of the interview is preserved.
- Each chunk must have a "chunk_id" such as "I01_C001", "I01_C002", etc.

SPEAKER RULES:
- Preserve the original speaker label in "speaker_label_original".
- Classify "NAME OF INTERVIEWER" as "interviewer".
- Classify "student 1", "student 2", etc. as "participant".
- If gender or education rank is not stated in the transcript, write "unknown".
- Do not guess gender or education rank from names or wording.

SYMBOL TABLE:
Use this symbol table if these markers appear:
- "..." = hesitation, pause, unfinished thought
- "???" = confusion, unclear speech, or unintelligible part
- "[laughs]" = general laughter
- "[silence]" = silence
- "[overlap]" = overlapping speech
- "[inaudible]" = cannot hear
- "[translated]" = translated text
- "[emphasis]" = strongly felt point
- "[uncertain]" = not sure/questioning
- "[agreement]" = other speakers agree

DEFINED CODEBOOK:

SDT codes:
- SDT_Autonomy_supported
- SDT_Autonomy_frustrated
- SDT_Competence_supported
- SDT_Competence_frustrated
- SDT_Relatedness_supported
- SDT_Relatedness_frustrated
- SDT_Intrinsic_interest
- SDT_Controlled_motivation
- SDT_Wonder_motivation

Self-efficacy codes:
- SE_Equipment_experimental_self_efficacy
- SE_Data_analysis_self_efficacy
- SE_Troubleshooting_self_efficacy
- SE_Theory_laboratory_connection_self_efficacy
- SE_Success_after_struggle
- SE_Failure_as_learning
- SE_Failure_as_incompetence
- SE_Peer_modelling
- SE_Social_encouragement
- SE_Stress

Expectancy–Value Theory codes:
- EVT_Expectancy_of_success
- EVT_Ability_belief
- EVT_Intrinsic_value
- EVT_Utility_value
- EVT_Attainment_value
- EVT_Cost_time
- EVT_Cost_emotional
- EVT_Cost_identity
- EVT_Low_perceived_value
- EVT_Value_shift

Communities of Practice codes:
- CP_Authentic_practice
- CP_Artificial_school_task
- CP_Legitimate_start_participation
- CP_Illegitimate_participation
- CP_Movement_toward_participation
- CP_Fixed_participation
- CP_Recognition_by_others
- CP_Identity_positioning
- CP_Boundary_or_no_boundary_between_lab_and_theory

CODE INTERPRETATION GUIDE:

SDT:
Use SDT_Autonomy_supported when students describe freedom, choice, agency, free play, deciding how to approach the task.
Use SDT_Autonomy_frustrated when students describe being over-directed, constrained, having no room to think, or only following instructions.
Use SDT_Competence_supported when students describe understanding, learning, becoming capable, or succeeding.
Use SDT_Competence_frustrated when students describe confusion, not knowing what they were doing, feeling lost, or depending on others.
Use SDT_Relatedness_supported when students describe support, safe interaction, useful group work, or help from peers/TA/teacher.
Use SDT_Relatedness_frustrated when students describe not wanting to ask, being ignored, others taking over, or feeling unsupported.
Use SDT_Intrinsic_interest when students describe interest, curiosity, enjoyment, wanting to understand.
Use SDT_Controlled_motivation when students describe motivation mainly from report, grade, deadline, obligation, or hand-in.
Use SDT_Wonder_motivation when students describe seeing the physics, excitement, coolness, beauty, or fascination with an effect.

Self-efficacy:
Use SE_Equipment_experimental_self_efficacy for confidence or lack of confidence with apparatus, mirrors, lasers, sensors, alignment, physical setup, filters, beam splitters, or experimental handling.
Use SE_Data_analysis_self_efficacy for confidence or lack of confidence with fitting, plotting, uncertainty, data interpretation, software, or analysis.
Use SE_Troubleshooting_self_efficacy for diagnosing problems, figuring out why something does not work, adjusting setup.
Use SE_Theory_laboratory_connection_self_efficacy for confidence explaining how theory appears in the lab.
Use SE_Success_after_struggle when success follows initial struggle.
Use SE_Failure_as_learning when mistakes/errors helped understanding.
Use SE_Failure_as_incompetence when errors made the student feel incapable, bad, or unsuited.
Use SE_Peer_modelling when the student gains confidence by watching peers.
Use SE_Social_encouragement when TA/peer support increases confidence.
Use SE_Stress when there are traces of anxiety, time pressure, fear of asking, embarrassment, panic, or stress.

Expectancy–Value Theory:
Use EVT_Expectancy_of_success when students describe whether they thought they could or could not succeed.
Use EVT_Ability_belief when students describe themselves as good/bad at labs, physics, experiments, theory, analysis, or similar.
Use EVT_Intrinsic_value when students describe interest, enjoyment, curiosity, or intellectual satisfaction.
Use EVT_Utility_value when students describe usefulness for future career, research, exams, skills, or later studies.
Use EVT_Attainment_value when students connect the lab to identity, becoming a physicist, or what physicists do.
Use EVT_Cost_time when students mention too many hours, workload, deadlines, or time burden.
Use EVT_Cost_emotional when students mention stress, anxiety, embarrassment, frustration, incompetence, or emotional burden.
Use EVT_Cost_identity when students say or imply the experience made them feel not suited for physics/labs.
Use EVT_Low_perceived_value when students say they did not see the point.
Use EVT_Value_shift when students describe changing value over time, e.g. first disliked it, later understood why it mattered.

Communities of Practice:
Use CP_Authentic_practice when students say the lab felt like real physics, research, authentic experimentation, or actual scientific practice.
Use CP_Artificial_school_task when students say it felt like recipe-following, report production, or artificial school work.
Use CP_Legitimate_start_participation when students felt allowed to be beginners, try things, learn gradually, or experiment without already knowing everything.
Use CP_Illegitimate_participation when students felt judged, excluded, not allowed to try, or not treated as legitimate participants.
Use CP_Movement_toward_participation when students become more active over time.
Use CP_Fixed_participation when students remain observers, note-takers, passive helpers, or stuck in one limited role.
Use CP_Recognition_by_others when TA, teacher, or peers treat the student as capable.
Use CP_Identity_positioning when students say things like "I am more theoretical", "I am not a lab person", "I like experiments", or otherwise position themselves.
Use CP_Boundary_or_no_boundary_between_lab_and_theory when students treat theory and experiment as separate worlds, or describe connecting them.

MEMO RULES:
Each chunk must include a memo object with:
- "local_summary": short description of what is being said in this chunk.
- "emotional_tone": tone based on what is said and transcript markers, e.g. neutral, curious, excited, hesitant, frustrated, uncertain, confident, reflective.
- "unsaid_or_implicit_signal": cautious note about what may be implied, but only if grounded in the text.
- "non_defined_candidate_code": if the excerpt does not fit defined codes but may still be analytically useful, propose a plain-language candidate code here. This is not a formal code.
- "followup_needed": true/false.
- "followup_question": if followup_needed is true, write a question that would clarify the point.
- "human_review_needed": true/false.
- "ai_uncertainty_note": explain uncertainty if human_review_needed is true.

OUTPUT FORMAT:
Return valid JSON only. No markdown. No commentary outside JSON.

Use exactly this structure:

{
  "interview_id": "I01",
  "source_file": "transcripts_raw/interview_01.txt",
  "participant_metadata": [
    {
      "participant_id": "student 1",
      "speaker_label_original": "student 1",
      "gender": "unknown",
      "education_rank": "unknown",
      "role": "participant",
      "notes": ""
    }
  ],
  "symbol_table": {
    "...": "hesitation, pause, unfinished thought",
    "???": "confusion, unclear speech, or unintelligible part",
    "[laughs]": "laughter",
    "[silence]": "silence",
    "[overlap]": "overlapping speech",
    "[inaudible]": "cannot hear",
    "[translated]": "translated text"
  },
  "chunks": [
    {
      "chunk_id": "I01_C001",
      "sequence_number": 1,
      "speaker_label_original": "",
      "speaker_role": "",
      "participant_id": "",
      "gender": "unknown",
      "education_rank": "unknown",
      "language": "English",
      "text": "",
      "codes": [],
      "memo": {
        "local_summary": "",
        "emotional_tone": "",
        "unsaid_or_implicit_signal": "",
        "non_defined_candidate_code": "",
        "followup_needed": false,
        "followup_question": "",
        "human_review_needed": false,
        "ai_uncertainty_note": ""
      }
    }
  ]
}

FINAL SELF-CHECK BEFORE RETURNING JSON:
1. Does every spoken part of the transcript appear in exactly one chunk?
2. Are chunks in the same order as the original transcript?
3. Is each speaker tracked correctly?
4. Are all codes from the allowed codebook?
5. Are overlapping codes allowed where appropriate?
6. Are no contradictions, tensions, or final themes identified?
7. Are interviewer questions preserved?
8. Are uncertain parts flagged for human review?