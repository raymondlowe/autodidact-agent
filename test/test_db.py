# Example unit test for db module
import unittest
import backend.db as db

class TestDB(unittest.TestCase):
    def test_clean_job_id(self):
        job_id = "test\njob"
        cleaned = db.clean_job_id(job_id)
        assert "\n" not in cleaned

if __name__ == "__main__":
    unittest.main()
