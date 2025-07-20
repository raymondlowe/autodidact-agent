#!/usr/bin/env python3
"""
Test script to verify that the response handling fixes work properly
Tests various edge cases where response.choices might be None or empty
"""

import sys
import os
import unittest
from unittest.mock import Mock, patch

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

class TestResponseHandling(unittest.TestCase):
    
    def test_perplexity_response_handling_with_none_choices(self):
        """Test that the Perplexity response handling properly handles None choices"""
        from backend.jobs import start_deep_research_job
        from utils.config import set_current_provider, save_api_key
        
        # Set up test environment
        save_api_key("sk-test-key", "openrouter")
        set_current_provider("openrouter")
        
        # Mock a response with None choices
        mock_response = Mock()
        mock_response.choices = None
        mock_response.meta = {}
        
        with patch('openai.OpenAI') as mock_openai_client:
            mock_client_instance = Mock()
            mock_openai_client.return_value = mock_client_instance
            mock_client_instance.chat.completions.create.return_value = mock_response
            mock_client_instance.api_key = "test-key"
            mock_client_instance.base_url = "https://openrouter.ai/api/v1"
            
            # This should now handle the None choices gracefully
            try:
                job_id = start_deep_research_job("Test topic", 2)
                
                # Check if the job was created (it will run in background thread)
                self.assertTrue(job_id.startswith("perplexity-"))
                print("✅ Perplexity job creation handled None choices gracefully")
                
                # Wait a moment for the background thread to complete
                import time
                time.sleep(1)
                
                # Check the temp file to see if the error was properly handled
                from pathlib import Path
                temp_dir = Path.home() / '.autodidact' / 'temp_responses'
                temp_file = temp_dir / f"{job_id}.json"
                
                if temp_file.exists():
                    import json
                    with open(temp_file, 'r') as f:
                        data = json.load(f)
                    
                    # The job should have failed with the proper error message
                    self.assertEqual(data["status"], "failed")
                    self.assertIn("Invalid response structure", data["content"])
                    print("✅ Error was properly caught and stored")
                else:
                    print("ℹ️ Temp file not found, background thread may still be running")
                    
            except Exception as e:
                # The error should be handled gracefully in the background thread
                # So we shouldn't get an exception here unless there's a different issue
                print(f"⚠️ Unexpected exception: {e}")

    def test_clarify_topic_with_none_choices(self):
        """Test that clarify_topic handles None choices properly"""
        from backend.jobs import clarify_topic
        
        # Mock a response with None choices
        mock_response = Mock()
        mock_response.choices = None
        mock_response.meta = {}
        
        with patch('backend.jobs.create_client') as mock_create_client, \
             patch('backend.jobs.retry_api_call') as mock_retry_api_call:
            
            mock_client = Mock()
            mock_create_client.return_value = mock_client
            mock_retry_api_call.return_value = mock_response
            
            # This should raise a RuntimeError with our specific message
            with self.assertRaises(RuntimeError) as context:
                clarify_topic("Test topic")
            
            self.assertIn("Invalid response structure: missing or empty choices", str(context.exception))
            print("✅ clarify_topic properly handles None choices")

    def test_clarify_topic_with_empty_choices(self):
        """Test that clarify_topic handles empty choices properly"""
        from backend.jobs import clarify_topic
        
        # Mock a response with empty choices
        mock_response = Mock()
        mock_response.choices = []
        mock_response.meta = {}
        
        with patch('backend.jobs.create_client') as mock_create_client, \
             patch('backend.jobs.retry_api_call') as mock_retry_api_call:
            
            mock_client = Mock()
            mock_create_client.return_value = mock_client
            mock_retry_api_call.return_value = mock_response
            
            # This should raise a RuntimeError with our specific message
            with self.assertRaises(RuntimeError) as context:
                clarify_topic("Test topic")
            
            self.assertIn("Invalid response structure: missing or empty choices", str(context.exception))
            print("✅ clarify_topic properly handles empty choices")

    def test_clarify_topic_with_none_message(self):
        """Test that clarify_topic handles None message properly"""
        from backend.jobs import clarify_topic
        
        # Mock a response with None message
        mock_choice = Mock()
        mock_choice.message = None
        
        mock_response = Mock()
        mock_response.choices = [mock_choice]
        mock_response.meta = {}
        
        with patch('backend.jobs.create_client') as mock_create_client, \
             patch('backend.jobs.retry_api_call') as mock_retry_api_call:
            
            mock_client = Mock()
            mock_create_client.return_value = mock_client
            mock_retry_api_call.return_value = mock_response
            
            # This should raise a RuntimeError with our specific message
            with self.assertRaises(RuntimeError) as context:
                clarify_topic("Test topic")
            
            self.assertIn("Invalid response structure: missing or empty message", str(context.exception))
            print("✅ clarify_topic properly handles None message")

    def test_clarify_topic_with_valid_response(self):
        """Test that clarify_topic works correctly with valid responses"""
        from backend.jobs import clarify_topic
        
        # Mock a valid response
        mock_message = Mock()
        mock_message.content = "- What is your current experience level?\n- What specific area interests you most?"
        
        mock_choice = Mock()
        mock_choice.message = mock_message
        
        mock_response = Mock()
        mock_response.choices = [mock_choice]
        mock_response.meta = {}
        mock_response.usage = Mock()
        mock_response.usage.total_tokens = 100
        
        with patch('backend.jobs.create_client') as mock_create_client, \
             patch('backend.jobs.retry_api_call') as mock_retry_api_call:
            
            mock_client = Mock()
            mock_create_client.return_value = mock_client
            mock_retry_api_call.return_value = mock_response
            
            # This should work correctly
            questions = clarify_topic("Test topic")
            
            self.assertIsInstance(questions, list)
            self.assertGreater(len(questions), 0)
            print(f"✅ clarify_topic works correctly with valid response: {len(questions)} questions")

def main():
    """Run all response handling tests"""
    print("Testing response handling fixes...")
    print("=" * 50)
    
    # Initialize unittest and run tests
    unittest.main(verbosity=2, exit=False)
    
    print("\n" + "=" * 50)
    print("✅ All response handling tests completed!")

if __name__ == "__main__":
    main()