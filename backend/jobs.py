"""
Jobs module for Autodidact
Contains: clarifier agent, deep research wrapper, grader, and tutor nodes
"""

import json
import re
import time
from typing import Dict, List, Optional
import openai
from openai import OpenAI
from utils.config import CHAT_MODEL, load_api_key
from utils.deep_research import run_deep_research as deep_research_api


# Constants for retry logic
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds


def retry_api_call(func, *args, max_retries=MAX_RETRIES, **kwargs):
    """Retry API calls with exponential backoff"""
    last_error = None
    
    for attempt in range(max_retries):
        try:
            return func(*args, **kwargs)
        except openai.RateLimitError as e:
            wait_time = RETRY_DELAY * (2 ** attempt)
            print(f"Rate limit hit, waiting {wait_time} seconds...")
            time.sleep(wait_time)
            last_error = e
        except openai.APIError as e:
            if attempt < max_retries - 1:
                wait_time = RETRY_DELAY * (2 ** attempt)
                print(f"API error, retrying in {wait_time} seconds...")
                time.sleep(wait_time)
                last_error = e
            else:
                raise
        except Exception as e:
            # Don't retry on non-API errors
            raise
    
    # If we get here, all retries failed
    raise RuntimeError(f"Failed after {max_retries} attempts. Last error: {str(last_error)}")


def clarify_topic(topic: str, hours: Optional[int] = None) -> Dict:
    """
    Determine if topic needs clarification and generate questions if needed.
    
    Returns either:
    - {"need_clarification": true, "questions": ["Q1", "Q2", ...]}
    - {"need_clarification": false, "refined_topic": "..."}
    """
    
    clarification_prompt = '''
    You are an intelligent assistant preparing to conduct a deep research report. 
    Before proceeding, determine if clarification is needed.
    
    If the topic is specific enough (e.g., "Foundations of Statistical Learning", 
    "Bitcoin consensus mechanisms", "React hooks"), return:
    {"need_clarification": false, "refined_topic": "<exact topic provided>"}
    
    If the topic is too broad or ambiguous (e.g., "Modern World History", "Programming", 
    "Science"), ask up to 5 clarifying questions in a numbered list to help narrow down:
    - What aspect/subtopic they're most interested in
    - Their current knowledge level
    - Specific goals or applications
    - Time constraints or depth preferences
    
    Return format must be valid JSON:
    {"need_clarification": true, "questions": ["Q1", "Q2", ...]}
    or
    {"need_clarification": false, "refined_topic": "<refined version of topic>"}
    '''
    
    # Get API key
    api_key = load_api_key()
    if not api_key:
        raise ValueError("OpenAI API key not found. Please configure your API key in the sidebar.")
    
    # Create client
    client = OpenAI(api_key=api_key)
    
    # Prepare user message
    user_msg = f"Topic: {topic}"
    if hours:
        user_msg += f"\nUser wants to spend {hours} hours learning this."
    
    try:
        # Call OpenAI API with retry logic
        def make_clarifier_call():
            return client.chat.completions.create(
                model=CHAT_MODEL,
                messages=[
                    {"role": "system", "content": clarification_prompt},
                    {"role": "user", "content": user_msg}
                ],
                response_format={"type": "json_object"},
                temperature=0.7
            )
        
        response = retry_api_call(make_clarifier_call)
        
        # Parse response
        result = json.loads(response.choices[0].message.content)
        
        # Validate response format
        if "need_clarification" not in result:
            raise ValueError("Invalid response format from clarifier")
        
        if result["need_clarification"] and "questions" not in result:
            raise ValueError("Missing questions in clarification response")
        
        if not result["need_clarification"] and "refined_topic" not in result:
            result["refined_topic"] = topic
        
        return result
        
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Failed to parse clarifier response: {e}")
    except openai.AuthenticationError:
        raise RuntimeError("Invalid API key. Please check your OpenAI API key.")
    except openai.PermissionDeniedError:
        raise RuntimeError("API key doesn't have access to the required model.")
    except Exception as e:
        raise RuntimeError(f"Clarifier API call failed: {str(e)}")


def is_skip_response(response: str) -> bool:
    """Check if response is a non-answer using regex patterns"""
    skip_pattern = re.compile(r'^\s*(idk|i don\'t know|skip|na|n/a|none)\s*$', re.IGNORECASE)
    return bool(skip_pattern.match(response.strip()))


def process_clarification_responses(questions: List[str], responses: List[str]) -> str:
    """
    Process user responses to clarification questions and create refined topic
    """
    # Filter out skip responses
    valid_responses = []
    for i, (q, r) in enumerate(zip(questions, responses)):
        if not is_skip_response(r):
            valid_responses.append(f"Q: {q}\nA: {r}")
    
    if not valid_responses:
        return None  # No valid responses, use original topic
    
    # Get API key and create client
    api_key = load_api_key()
    if not api_key:
        raise ValueError("OpenAI API key not found")
    
    client = OpenAI(api_key=api_key)
    
    # Create prompt to refine topic based on responses
    refinement_prompt = """
    Based on the following clarification Q&A, create a refined, specific learning topic.
    
    Original topic and clarification Q&A:
    {qa_text}
    
    Return only the refined topic as a clear, specific statement.
    """
    
    qa_text = "\n\n".join(valid_responses)
    
    try:
        def make_refinement_call():
            return client.chat.completions.create(
                model=CHAT_MODEL,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that refines learning topics based on user input."},
                    {"role": "user", "content": refinement_prompt.format(qa_text=qa_text)}
                ],
                temperature=0.7
            )
        
        response = retry_api_call(make_refinement_call)
        return response.choices[0].message.content.strip()
        
    except Exception as e:
        raise RuntimeError(f"Failed to process clarification responses: {e}")


def run_deep_research_job(topic: str, hours: Optional[int] = None) -> Dict:
    """
    Wrapper for Deep Research API call with error handling and partial result recovery.
    Adapted from 02-topic-then-deep-research.py
    
    Returns:
        Dict with report_markdown, graph, and footnotes
    """
    # Get API key and create client
    api_key = load_api_key()
    if not api_key:
        raise ValueError("OpenAI API key not found. Please configure your API key.")
    
    client = OpenAI(api_key=api_key)
    
    try:
        # Call the deep research API
        result = deep_research_api(topic, client, hours)
        
        # Validate result has required fields
        if "report_markdown" not in result:
            # Try to salvage partial results
            if "graph" in result:
                result["report_markdown"] = f"# {topic}\n\n*Note: Report generation failed, but knowledge graph was created successfully.*"
            else:
                raise ValueError("Missing report_markdown in Deep Research result")
        
        if "graph" not in result:
            raise ValueError("Missing graph in Deep Research result")
        
        # Ensure graph has required structure
        if "nodes" not in result["graph"]:
            result["graph"]["nodes"] = []
        if "edges" not in result["graph"]:
            result["graph"]["edges"] = []
        
        if "footnotes" not in result:
            result["footnotes"] = {}  # Default to empty if missing
        
        # Validate nodes have learning objectives
        for node in result["graph"]["nodes"]:
            if "learning_objectives" not in node or not node["learning_objectives"]:
                # Generate placeholder objectives if missing
                node["learning_objectives"] = [
                    f"Understand the key concepts of {node['label']}",
                    f"Apply {node['label']} principles in practice",
                    f"Analyze relationships between {node['label']} and related topics",
                    f"Evaluate different approaches to {node['label']}",
                    f"Create solutions using {node['label']} knowledge"
                ]
        
        return result
        
    except openai.AuthenticationError:
        raise RuntimeError("Invalid API key. Please check your OpenAI API key.")
    except openai.PermissionDeniedError:
        raise RuntimeError("API key doesn't have access to Deep Research model.")
    except openai.RateLimitError:
        raise RuntimeError("Rate limit exceeded. Please try again in a few minutes.")
    except openai.APIError as e:
        raise RuntimeError(f"OpenAI API error: {str(e)}")
    except Exception as e:
        raise RuntimeError(f"Deep Research failed: {str(e)}") 