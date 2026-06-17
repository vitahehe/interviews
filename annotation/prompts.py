"""
prompts.py

Prompt definitions for Stage 1 of the hybrid AI/human interview-analysis workflow:
BROAD ANNOTATION.

The goal is to preserve the whole transcript while assigning broad, theory-guided
topic labels to each chunk:

- SELF_DETERMINATION
- SELF_EFFICACY
- VALUE_MOTIVATION
- OTHER_RELEVANT
- CONTEXT_ONLY

The definitions below are adapted for a physics laboratory course context from:
1. Ryan & Deci, Self-Determination Theory:
   autonomy, competence, relatedness, intrinsic motivation, controlled motivation.
2. Bandura, Self-Efficacy:
   task-specific belief in capability; persistence, effort, obstacles; mastery,
   vicarious/peer modelling, social persuasion, stress/anxiety.
3. Eccles/Wigfield Expectancy-Value Theory:
   expectancy of success, ability beliefs, intrinsic value, utility value,
   attainment/identity value, and perceived costs.
"""

from __future__ import annotations


BROAD_TOPICS = [
    "SELF_DETERMINATION",
    "SELF_EFFICACY",
    "VALUE_MOTIVATION",
    "OTHER_RELEVANT",
    "CONTEXT_ONLY",
]


SYSTEM_PROMPT = """
You are assisting with qualitative analysis of interviews from a laboratory physics course.

Your task is BROAD ANNOTATION ONLY.

You are NOT producing final thematic codes.
You are NOT selecting only the best evidence.
You are NOT summarizing the interview.
You are NOT discarding ambiguous material.

The purpose of this stage is to preserve the transcript while assigning broad,
theory-guided topic labels that will later be used for meaningful chunk selection,
topic-pool creation, and AI-assisted theme discovery.

A chunk may receive multiple labels.
Prefer over-inclusion to under-inclusion.
If a chunk is ambiguous but may be relevant, label it with the possible topic and use low confidence.
If a chunk contains tension, contradiction, hesitation, uncertainty, disagreement, or minority views,
preserve this in the annotation fields.
Always annotate every chunk.
"""


BROAD_TOPIC_DEFINITIONS = """
BROAD TOPIC DEFINITIONS FOR PHYSICS LAB INTERVIEWS

1. SELF_DETERMINATION

Use this label when the chunk relates to whether the lab supports or frustrates
students' autonomy, competence, relatedness, or quality of motivation.

Theoretical lens:
Self-Determination Theory asks whether the learning environment supports basic
psychological needs:
- autonomy: feeling ownership, choice, agency, meaningful control;
- competence: feeling capable, effective, able to understand or act;
- relatedness: feeling socially supported, safe, included, respected;
and whether motivation feels intrinsic, identified, controlled, pressured, or absent.

In a physics laboratory course, look for:
- "We could decide how to approach it."
- "I liked having freedom."
- "We just followed instructions."
- "There was no room to think."
- "After trying, I understood how to do it."
- "I had no idea what I was doing."
- "My group helped me."
- "The TA made it safe to ask."
- "I did not want to ask."
- "Others took over."
- "It was exciting."
- "I wanted to understand what was happening."
- "I only cared about the report, grade, deadline."
- "It was cool to see the effect."
- "I finally saw the physics."

Possible theory cues:
Autonomy supported; Autonomy frustrated; Competence supported; Competence frustrated;
Relatedness supported; Relatedness frustrated; Intrinsic interest; Controlled motivation;
Wonder motivation; Ownership; Feeling abandoned; Feeling over-directed.


2. SELF_EFFICACY

Use this label when the chunk relates to students' task-specific belief that they
can perform actions required in experimental physics.

Theoretical lens:
Self-efficacy is not general confidence or self-esteem. It is a person's belief
that they can perform specific actions needed to produce desired outcomes.
Efficacy expectations influence whether people start an action, how much effort
they invest, and how long they persist when obstacles appear.

In a physics laboratory course, look for:
- confidence or lack of confidence handling apparatus, sensors, alignment, optics,
  electronics, measurement devices, software, or equipment;
- confidence fitting, plotting, interpreting uncertainty, analysing data;
- confidence troubleshooting or diagnosing why something does not work;
- confidence connecting theory to what appears in the lab;
- success after struggle;
- failure as learning;
- failure interpreted as incompetence;
- peer modelling: "I saw another student do it, so I thought I could";
- social encouragement from TA, teacher, or peers;
- stress, anxiety, embarrassment, fear of asking, time pressure, or feeling exposed
  when these affect students' belief in their capability.

Possible theory cues:
Equipment/experimental self-efficacy; Data-analysis self-efficacy;
Troubleshooting self-efficacy; Theory-lab connection self-efficacy;
Mastery experience; Success after struggle; Failure as learning;
Failure as incompetence; Peer modelling; Social encouragement;
Stress/anxiety affecting efficacy.


3. VALUE_MOTIVATION

Use this label when the chunk relates to what value students attach to the lab,
whether they expect success, whether they think the task is worth doing, and what
costs they perceive.

Theoretical lens:
Expectancy-Value Theory asks:
- Do students believe they can succeed?
- Do students believe the task is worth doing?
- What kind of value do they attach to the task?
- What costs do they experience?

In a physics laboratory course, look for:
- expectancy of success: "I thought I could/couldn't do well";
- ability belief: "I am good/bad at labs", "I am not an experimental person";
- intrinsic value: interest, enjoyment, curiosity, fascination;
- utility value: usefulness for future career, research, exams, skills, thesis work;
- attainment/identity value: "This is what physicists do", "This fits/does not fit me";
- time cost: "Too many hours", workload, deadlines;
- emotional cost: stress, anxiety, embarrassment, frustration;
- identity cost: "It made me feel I am not suited for physics";
- low perceived value: "I did not see the point";
- value shift: "At first I hated it, but later I understood why it mattered."

Possible theory cues:
Expectancy of success; Ability belief; Intrinsic value; Utility value;
Attainment value; Identity relevance; Time cost; Emotional cost; Identity cost;
Low perceived value; Value shift; Worth-the-effort tension.


4. OTHER_RELEVANT

Use this label when the chunk may matter for later interpretation but does not
clearly fit the three main topics. Examples:
- course logistics that explain later comments;
- assessment structure;
- group composition;
- teacher/course design details;
- lab format details;
- comments about curriculum context;
- relevant background that may explain a student's later claim.


5. CONTEXT_ONLY

Use this label when the chunk mainly provides background, transition, short
interviewer framing, factual setup, or administrative information and does not
itself contain analytic material.

Important:
A chunk can be both CONTEXT_ONLY and another label only if it contains context plus
a small but relevant signal. Otherwise, use CONTEXT_ONLY alone.
"""


ANNOTATION_INSTRUCTIONS = """
ANNOTATION INSTRUCTIONS

For each chunk, return one annotation object.

Required fields for each chunk:
- chunk_id: exactly as provided.
- broad_topics: list containing one or more of:
  SELF_DETERMINATION, SELF_EFFICACY, VALUE_MOTIVATION, OTHER_RELEVANT, CONTEXT_ONLY.
- confidence: number from 0.0 to 1.0.
  Use high confidence only when the label is clear.
  Use low or medium confidence when the chunk is ambiguous but potentially relevant.
- theory_cues: short list of relevant cues, for example:
  ["Autonomy frustrated", "Competence uncertainty"].
- annotation_reason: one or two sentences explaining why the broad label was assigned.
- valence: one of "positive", "negative", "mixed", "unclear", "not_applicable".
  Valence refers to the student's experience in relation to the label, not whether the statement is good writing.
- possible_tension: short string describing contradiction, ambiguity, hesitation, disagreement,
  or "none".
- human_review_needed: true or false.
  Use true for low confidence, subtle meaning, possible contradiction, unclear speaker,
  or anything that may be theoretically important but ambiguous.

Rules:
- Annotate EVERY chunk.
- Do not omit chunks.
- Do not invent evidence not present in the chunk.
- Keep labels broad.
- Do not create final thematic codes.
- Prefer preserving possible evidence over excluding it.
- It is acceptable for one chunk to have several broad topics.
- If the interviewer asks a question that frames a theory-relevant issue, label it as CONTEXT_ONLY
  or OTHER_RELEVANT unless the wording itself matters for interpretation.
"""


def build_user_prompt(batch: list[dict]) -> str:
    """
    Build the user prompt for one batch of transcript chunks.

    batch should be a list of dictionaries with:
    - chunk_id
    - speaker
    - speaker_type
    - participant_id
    - text
    - previous_context
    - next_context
    """
    return f"""
{BROAD_TOPIC_DEFINITIONS}

{ANNOTATION_INSTRUCTIONS}

Return ONLY valid JSON in this exact shape:

{{
  "annotations": [
    {{
      "chunk_id": "string",
      "broad_topics": ["SELF_DETERMINATION"],
      "confidence": 0.0,
      "theory_cues": ["string"],
      "annotation_reason": "string",
      "valence": "positive | negative | mixed | unclear | not_applicable",
      "possible_tension": "string",
      "human_review_needed": true
    }}
  ]
}}

Here are the chunks to annotate:

{batch}
""".strip()
