import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from meaningful_chunks.theme_grids import build_compact_model_payload, flatten_theme_grid, generate_for_interview, load_meaningful_chunks


class ThemeGridUtilsTests(unittest.TestCase):
    def test_load_meaningful_chunks_normalizes_fields(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "meaningful_chunks.jsonl"
            rows = [
                {
                    "interview_id": "I01",
                    "chunk_id": "I01_C001",
                    "sequence_number": 1,
                    "speaker_label_original": "student 1",
                    "speaker_role": "participant",
                    "participant_id": "student 1",
                    "text": "I felt confident.",
                    "existing_codes": ["SE_Stress"],
                    "local_summary": "Confidence comment",
                    "emotional_tone": "confident",
                    "non_defined_candidate_code": "",
                },
                {
                    "interview_id": "I01",
                    "chunk_id": "I01_C002",
                    "sequence_number": 2,
                    "speaker_label_original": "Interviewer",
                    "speaker_role": "interviewer",
                    "participant_id": "",
                    "text": "What did you learn?",
                    "existing_codes": [],
                    "local_summary": "Question",
                    "emotional_tone": "neutral",
                    "non_defined_candidate_code": "",
                },
            ]
            input_path.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")

            chunks_by_interview = load_meaningful_chunks(input_path)

            self.assertEqual(list(chunks_by_interview.keys()), ["I01"])
            self.assertEqual(chunks_by_interview["I01"][0]["speaker_label_original"], "student 1")
            self.assertEqual(chunks_by_interview["I01"][0]["existing_codes"], ["SE_Stress"])

    def test_build_compact_model_payload_truncates_text(self):
        sample_chunks = [
            {
                "interview_id": "I01",
                "chunk_id": "I01_C001",
                "sequence_number": 1,
                "speaker_label_original": "student 1",
                "speaker_role": "participant",
                "participant_id": "student 1",
                "text": "x" * 400,
                "existing_codes": ["SE_Stress"],
                "local_summary": "confidence",
                "emotional_tone": "confident",
                "non_defined_candidate_code": "",
            }
        ]

        payload = build_compact_model_payload("I01", sample_chunks, max_text_chars=120)

        self.assertEqual(payload["interview_id"], "I01")
        self.assertIn("text", payload["chunks"][0])
        self.assertLessEqual(len(payload["chunks"][0]["text"]), 120)

    def test_flatten_theme_grid_creates_rows(self):
        sample_grid = {
            "interview_id": "I01",
            "theme_grid": [
                {
                    "theme_id": "1",
                    "theme_name": "Self-efficacy",
                    "codes": [
                        {
                            "code_id": "1.a",
                            "code_name": "Expected difficulty",
                            "description": "desc",
                            "motivation": "motivation",
                            "examples": [
                                {
                                    "participant_id": "student 1",
                                    "speaker_label_original": "student 1",
                                    "chunk_id": "I01_C001",
                                    "quote": "I felt confident",
                                    "existing_theory_codes": ["SE_Stress"],
                                    "why_example_fits": "Because it shows confidence",
                                }
                            ],
                        }
                    ],
                }
            ],
        }

        rows = flatten_theme_grid(sample_grid)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["Themes"], "Self-efficacy")
        self.assertEqual(rows[0]["Codes"], "Expected difficulty")

    def test_generate_for_interview_falls_back_when_api_is_unavailable(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {}, clear=True):
                chunks = [
                    {
                        "interview_id": "I01",
                        "chunk_id": "I01_C001",
                        "sequence_number": 1,
                        "speaker_label_original": "student 1",
                        "speaker_role": "participant",
                        "participant_id": "student 1",
                        "text": "This lab felt difficult and interesting.",
                        "existing_codes": [],
                        "local_summary": "Difficulty and interest",
                        "emotional_tone": "mixed",
                        "non_defined_candidate_code": "",
                    }
                ]

                result = generate_for_interview(
                    interview_id="I01",
                    chunks=chunks,
                    prompt_template="Prompt for {{INTERVIEW_ID}} with {{CHUNKS_JSON}}",
                    client=None,
                    model="test-model",
                    output_dir=tmpdir,
                    overwrite=True,
                )

                self.assertIn("theme_grid", result)
                self.assertGreaterEqual(len(result["theme_grid"]), 1)
                self.assertIn("case_level_notes", result)

    def test_generate_for_interview_writes_json_only_outputs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            chunks = [
                {
                    "interview_id": "I01",
                    "chunk_id": "I01_C001",
                    "sequence_number": 1,
                    "speaker_label_original": "student 1",
                    "speaker_role": "participant",
                    "participant_id": "student 1",
                    "text": "This lab felt difficult and interesting.",
                    "existing_codes": [],
                    "local_summary": "Difficulty and interest",
                    "emotional_tone": "mixed",
                    "non_defined_candidate_code": "",
                }
            ]

            generate_for_interview(
                interview_id="I01",
                chunks=chunks,
                prompt_template="Prompt for {{INTERVIEW_ID}} with {{CHUNKS_JSON}}",
                client=None,
                model="test-model",
                output_dir=tmpdir,
                overwrite=True,
            )

            self.assertTrue(Path(tmpdir, "json", "I01.json").exists())
            self.assertFalse(Path(tmpdir, "csv").exists())
            self.assertFalse(Path(tmpdir, "markdown").exists())
