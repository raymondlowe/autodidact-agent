# Example unit test for jobs module
import unittest
import backend.jobs as jobs

class TestJobs(unittest.TestCase):
    def test_clarify_topic(self):
        result = jobs.clarify_topic("Test topic", hours=2)
        self.assertIsInstance(result, list)
        self.assertTrue(len(result) > 0)

if __name__ == "__main__":
    unittest.main()
