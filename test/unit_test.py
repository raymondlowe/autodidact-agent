"""
Main unit test runner for Autodidact Agent
Imports and runs tests from all major modules.
"""
import os
import sys
import unittest
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import main modules for testing
import backend.jobs as jobs
import backend.db as db
import utils.deep_research as deep_research

class TestJobs(unittest.TestCase):
    def test_clarify_topic(self):
        result = jobs.clarify_topic("Test topic", hours=2)
        self.assertIsInstance(result, list)
        self.assertTrue(len(result) > 0)

    def test_rewrite_topic(self):
        rewritten = jobs.rewrite_topic("Test topic", ["What is your goal?"], "To learn.")
        self.assertIsInstance(rewritten, str)
        self.assertTrue(len(rewritten) > 0)

    def test_deep_research_job_env(self):
        if not os.environ.get("OPENAI_API_KEY") and not os.environ.get("OPENROUTER_API_KEY"):
            self.skipTest("No API keys set, skipping deep research job test.")
        job_id = jobs.start_deep_research_job("Test topic", hours=1)
        self.assertIsInstance(job_id, str)
        self.assertTrue(len(job_id) > 0)

class TestDB(unittest.TestCase):
    def test_clean_job_id(self):
        job_id = "test\njob"
        cleaned = db.clean_job_id(job_id)
        self.assertNotIn("\n", cleaned)

class TestDeepResearch(unittest.TestCase):
    def test_lint(self):
        payload = '{"key": "value"}'
        result = deep_research.lint(payload)
        self.assertIsInstance(result, list)

if __name__ == "__main__":
    unittest.main()
