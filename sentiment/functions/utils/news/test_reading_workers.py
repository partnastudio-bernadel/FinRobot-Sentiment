import os
import json
import sys
import unittest
from unittest.mock import patch, MagicMock
import pandas as pd

# Ensure the sentiment directory is on the path
_sentinel_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _sentinel_dir not in sys.path:
    sys.path.insert(0, _sentinel_dir)

from functions.tools.edgar_tools import (
    get_cik_by_ticker,
    get_10k_metadata_by_year,
    extract_section_1a,
    extract_section_7,
    get_sec_user_agent
)
from functions.tools.transcript_tools import split_transcript, fetch_and_split_transcript
from functions.utils.logging.compliance_logger import log_compliance_event

class TestReadingWorkers(unittest.TestCase):

    def setUp(self):
        # Setup temporary directories/paths for logging tests
        self.temp_log_path = os.path.join(os.path.dirname(__file__), "test_compliance_audit.jsonl")
        if os.path.exists(self.temp_log_path):
            os.remove(self.temp_log_path)

    def tearDown(self):
        if os.path.exists(self.temp_log_path):
            os.remove(self.temp_log_path)

    # -----------------------------------------------------------------------
    # Edgar Tools Tests
    # -----------------------------------------------------------------------

    def test_get_sec_user_agent(self):
        with patch.dict(os.environ, {"SEC_EDGAR_USER_AGENT": "Test Agent Contact@test.com"}):
            self.assertEqual(get_sec_user_agent(), "Test Agent Contact@test.com")

    @patch("requests.get")
    def test_get_cik_by_ticker(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."},
            "1": {"cik_str": 789019, "ticker": "MSFT", "title": "Microsoft Corp."}
        }
        mock_get.return_value = mock_response

        cik = get_cik_by_ticker("AAPL")
        self.assertEqual(cik, "0000320193")

    @patch("requests.get")
    def test_get_10k_metadata_by_year(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "filings": {
                "recent": {
                    "form": ["10-Q", "10-K", "10-K"],
                    "filingDate": ["2024-05-01", "2024-10-31", "2023-10-27"],
                    "reportDate": ["2024-03-31", "2024-09-30", "2023-09-30"],
                    "accessionNumber": ["000-001", "000-002", "000-003"],
                    "primaryDocument": ["doc1.htm", "doc2.htm", "doc3.htm"]
                }
            }
        }
        mock_get.return_value = mock_response

        meta = get_10k_metadata_by_year("0000320193", 2024)
        self.assertEqual(meta["accession_number"], "000-002")
        self.assertEqual(meta["acc_no_no_hyphens"], "000002")

    def test_extract_section_1a(self):
        full_text = "TOC Section item 1A. Risk Factors text. " + ("A lot of descriptive text here about the risks of our company. " * 10) + " item 1B. Unresolved Staff Comments"
        extracted = extract_section_1a(full_text)
        self.assertIn("Risk Factors text", extracted)
        self.assertNotIn("Unresolved Staff Comments", extracted)

    def test_extract_section_7(self):
        full_text = "TOC Section item 7. Management's Discussion and Analysis. " + ("Financial details and tables representing executive reviews. " * 10) + " item 7A. Market Risk"
        extracted = extract_section_7(full_text)
        self.assertIn("Management's Discussion", extracted)
        self.assertNotIn("Market Risk", extracted)

    # -----------------------------------------------------------------------
    # Transcript Tools Tests
    # -----------------------------------------------------------------------

    def test_split_transcript_clean(self):
        content = "Executive presentations: We had a strong Q3. CEO: iPhone sales grew. Now, we will open the line for the Question-and-Answer Session. Analyst: Can you give more color? CEO: Yes."
        presentation, qa = split_transcript(content)
        self.assertIn("Executive presentations", presentation)
        self.assertIn("Question-and-Answer Session", qa)

    def test_split_transcript_fallback(self):
        content = "Full transcript with no separator matching any list headers."
        half_idx = len(content) // 2
        expected_pres = content[:half_idx].strip()
        expected_qa = content[half_idx:].strip()
        presentation, qa = split_transcript(content)
        self.assertEqual(presentation, expected_pres)
        self.assertEqual(qa, expected_qa)


    @patch("requests.get")
    def test_fetch_and_split_transcript(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {
                "symbol": "AAPL",
                "quarter": 3,
                "year": 2024,
                "content": "AAPL Q3 Call. CEO: Welcome. Questions and Answers. Analyst: Color? CEO: Good."
            }
        ]
        mock_get.return_value = mock_response

        # Set temporary API key
        with patch.dict(os.environ, {"FMP_API_KEY": "test_key"}):
            data = fetch_and_split_transcript("AAPL")
            self.assertEqual(data["meta"]["quarter"], 3)
            self.assertIn("Welcome", data["presentation"])
            self.assertIn("Questions and Answers", data["qa"])

    # -----------------------------------------------------------------------
    # Compliance Logger Tests
    # -----------------------------------------------------------------------

    def test_log_compliance_event(self):
        metadata = {"ticker": "AAPL", "drift": 0.18, "status": "APPROVED"}
        log_compliance_event("OVERRIDE", metadata, log_path=self.temp_log_path)
        
        self.assertTrue(os.path.exists(self.temp_log_path))
        with open(self.temp_log_path, "r") as f:
            lines = f.readlines()
            self.assertEqual(len(lines), 1)
            entry = json.loads(lines[0])
            self.assertEqual(entry["event_type"], "OVERRIDE")
            self.assertEqual(entry["ticker"], "AAPL")
            self.assertEqual(entry["drift"], 0.18)
            self.assertIn("logged_at", entry)

if __name__ == "__main__":
    unittest.main()
