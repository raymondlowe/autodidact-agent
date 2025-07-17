#!/usr/bin/env python3
"""
Test script to validate that job_id parameters are properly sanitized
to prevent "Invalid non-printable ASCII character in URL" errors.
"""

import sys
import os

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from unittest.mock import patch, MagicMock


def test_check_and_complete_job_sanitizes_job_id():
    """Test that check_and_complete_job uses clean_job_id in API calls"""
    print("Testing check_and_complete_job job_id sanitization...")
    
    from backend.db import check_and_complete_job
    
    # Mock the client and its methods
    mock_client = MagicMock()
    mock_job = MagicMock()
    mock_job.status = "in_progress"
    mock_client.responses.retrieve.return_value = mock_job
    
    # Test job_id with newline character
    dirty_job_id = "test-job-123\n"
    clean_job_id = "test-job-123"
    project_id = "test-project"
    
    with patch('utils.providers.create_client', return_value=mock_client):
        # Call the function
        result = check_and_complete_job(project_id, dirty_job_id)
        
        # Verify that the clean job ID was used in the API call
        mock_client.responses.retrieve.assert_called_once_with(clean_job_id)
        
        # Verify it was NOT called with the dirty job ID
        assert mock_client.responses.retrieve.call_args[0][0] == clean_job_id
        assert mock_client.responses.retrieve.call_args[0][0] != dirty_job_id
        
        print("✅ check_and_complete_job correctly uses sanitized job_id")


def test_check_job_sanitizes_job_id():
    """Test that check_job uses clean_job_id in API calls"""
    print("Testing check_job job_id sanitization...")
    
    from backend.db import check_job
    
    # Mock the client and its methods
    mock_client = MagicMock()
    mock_job = MagicMock()
    mock_job.status = "completed"
    mock_client.responses.retrieve.return_value = mock_job
    
    # Test job_id with newline character
    dirty_job_id = "test-job-456\n\r"
    clean_job_id = "test-job-456"
    
    with patch('utils.providers.create_client', return_value=mock_client):
        # Call the function
        result = check_job(dirty_job_id)
        
        # Verify that the clean job ID was used in the API call
        mock_client.responses.retrieve.assert_called_once_with(clean_job_id)
        
        # Verify it was NOT called with the dirty job ID
        assert mock_client.responses.retrieve.call_args[0][0] == clean_job_id
        assert mock_client.responses.retrieve.call_args[0][0] != dirty_job_id
        
        print("✅ check_job correctly uses sanitized job_id")


def test_job_id_cleaning_edge_cases():
    """Test various edge cases for job_id cleaning"""
    print("Testing job_id cleaning edge cases...")
    
    from backend.db import check_job
    
    mock_client = MagicMock()
    mock_job = MagicMock()
    mock_job.status = "failed"
    mock_client.responses.retrieve.return_value = mock_job
    
    test_cases = [
        ("job-id\n", "job-id"),           # trailing newline
        ("\njob-id", "job-id"),           # leading newline
        ("job\nid", "job\nid"),           # middle newline (should be preserved)
        ("  job-id  ", "job-id"),         # whitespace
        ("\t\njob-id\r\n\t", "job-id"),  # mixed whitespace and newlines
        ("", ""),                         # empty string
        (None, ""),                       # None value
    ]
    
    with patch('utils.providers.create_client', return_value=mock_client):
        for dirty_id, expected_clean_id in test_cases:
            mock_client.responses.retrieve.reset_mock()
            
            try:
                check_job(dirty_id)
                
                if expected_clean_id:  # Only check if we expect a non-empty ID
                    mock_client.responses.retrieve.assert_called_once_with(expected_clean_id)
                    actual_called_id = mock_client.responses.retrieve.call_args[0][0]
                    assert actual_called_id == expected_clean_id, f"Expected {expected_clean_id}, got {actual_called_id}"
                
            except Exception as e:
                if dirty_id is None or dirty_id == "":
                    # These cases might cause errors due to empty job_id, which is expected
                    continue
                else:
                    raise e
                    
    print("✅ job_id cleaning handles edge cases correctly")


def main():
    """Run all tests"""
    print("Running job_id sanitization tests...")
    print("=" * 50)
    
    try:
        test_check_and_complete_job_sanitizes_job_id()
        test_check_job_sanitizes_job_id()
        test_job_id_cleaning_edge_cases()
        
        print("\n" + "=" * 50)
        print("✅ All job_id sanitization tests passed!")
        print("\nThe fix should resolve the 'Invalid non-printable ASCII character in URL' error.")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()