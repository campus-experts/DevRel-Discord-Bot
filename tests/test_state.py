import json
import tempfile
import unittest
from pathlib import Path

from utils.state import load_state, save_state


class StateTests(unittest.TestCase):
    def test_load_state_returns_empty_when_file_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state_path = Path(tmp) / "state.json"
            self.assertEqual(load_state(state_path), {})

    def test_save_state_creates_file_and_loads_back(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state_path = Path(tmp) / "nested" / "state.json"
            expected = {"youtube_last_digest_date": "2026-05-06"}
            save_state(expected, state_path)
            self.assertEqual(load_state(state_path), expected)

    def test_save_state_merges_existing_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state_path = Path(tmp) / "state.json"
            state_path.write_text(json.dumps({"blog_last_digest_date": "2026-05-01"}))

            save_state({"youtube_last_digest_date": "2026-05-06"}, state_path)
            merged = load_state(state_path)

            self.assertEqual(merged["blog_last_digest_date"], "2026-05-01")
            self.assertEqual(merged["youtube_last_digest_date"], "2026-05-06")


if __name__ == "__main__":
    unittest.main()
