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
from utils.deep_research import TOPIC_CLARIFYING_PROMPT, TOPIC_REWRITING_PROMPT


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


def clarify_topic(topic: str, hours: Optional[int] = None) -> List[str]:
    """
    Generate clarifying questions for a given topic using TOPIC_CLARIFYING_PROMPT.
    Always returns questions to ask the user.
    
    Args:
        topic: The learning topic
        hours: Optional number of hours the user wants to invest
        
    Returns:
        List of clarifying questions
    """
    print(f"\n[clarify_topic] Starting clarification for topic: '{topic}'")
    if hours:
        print(f"[clarify_topic] User wants to invest {hours} hours")
    
    # Get API key
    api_key = load_api_key()
    if not api_key:
        raise ValueError("OpenAI API key not found. Please configure your API key in the sidebar.")
    
    # Create client
    client = OpenAI(api_key=api_key)
    
    # Prepare user message
    user_msg = f"Topic: {topic}"
    if hours:
        user_msg += f"\nTime investment: {hours} hours"
    
    print(f"[clarify_topic] Using model: gpt-4o")
    print(f"[clarify_topic] User message: {user_msg}")
    
    try:
        # Call OpenAI API with retry logic
        def make_clarifier_call():
            return client.chat.completions.create(
                model="gpt-4o",  # Using gpt-4o as requested
                messages=[
                    {"role": "system", "content": TOPIC_CLARIFYING_PROMPT},
                    {"role": "user", "content": user_msg}
                ],
                temperature=0.7
            )
        
        print("[clarify_topic] Making API call...")
        response = retry_api_call(make_clarifier_call)
        
        # Extract the response content
        questions_text = response.choices[0].message.content.strip()
        print(f"[clarify_topic] Raw response:\n{questions_text}")
        
        # Parse the questions from the response
        # The response should be in bullet format, so we'll extract bullet points
        questions = []
        lines = questions_text.split('\n')
        for line in lines:
            line = line.strip()
            # Look for lines that start with bullets or numbers
            if line and (line.startswith('-') or line.startswith('•') or line.startswith('*') or 
                        (len(line) > 2 and line[0].isdigit() and line[1] in '.)')):
                # Clean up the bullet/number prefix
                question = re.sub(r'^[-•*\d.)\s]+', '', line).strip()
                if question:
                    questions.append(question)
        
        # If no bullets found, try to split by sentence-ending punctuation
        if not questions:
            print("[clarify_topic] No bullet points found, trying to split by sentences")
            sentences = re.split(r'[?!.]\s+', questions_text)
            questions = [s.strip() + '?' if not s.strip().endswith('?') else s.strip() 
                        for s in sentences if s.strip() and len(s.strip()) > 10]
        
        print(f"[clarify_topic] Extracted {len(questions)} questions")
        for i, q in enumerate(questions, 1):
            print(f"[clarify_topic]   Q{i}: {q}")
        
        return questions
        
    except openai.AuthenticationError:
        print("[clarify_topic] ERROR: Authentication failed")
        raise RuntimeError("Invalid API key. Please check your OpenAI API key.")
    except openai.PermissionDeniedError:
        print("[clarify_topic] ERROR: Permission denied")
        raise RuntimeError("API key doesn't have access to the required model.")
    except Exception as e:
        print(f"[clarify_topic] ERROR: {type(e).__name__}: {str(e)}")
        raise RuntimeError(f"Clarifier API call failed: {str(e)}")


def rewrite_topic(initial_topic: str, questions: List[str], user_answers: str) -> str:
    """
    Rewrite the topic based on clarifying questions and user answers.
    
    Args:
        initial_topic: The original topic from the user
        questions: List of clarifying questions that were asked
        user_answers: User's answers to all questions in a single string
        
    Returns:
        Rewritten, detailed topic instruction
    """
    print(f"\n[rewrite_topic] Starting topic rewriting")
    print(f"[rewrite_topic] Initial topic: '{initial_topic}'")
    print(f"[rewrite_topic] Number of questions: {len(questions)}")
    print(f"[rewrite_topic] User answers length: {len(user_answers)} chars")
    
    # Get API key and create client
    api_key = load_api_key()
    if not api_key:
        raise ValueError("OpenAI API key not found")
    
    client = OpenAI(api_key=api_key)
    
    # Format the content for the rewriting prompt
    formatted_content = f"""Initial topic: {initial_topic}

Clarifying questions:
"""
    for i, question in enumerate(questions, 1):
        formatted_content += f"{i}. {question}\n"
    
    formatted_content += f"\nUser's responses:\n{user_answers}"
    
    print(f"[rewrite_topic] Formatted content for API:\n{formatted_content}")
    print(f"[rewrite_topic] Using model: gpt-4o")
    
    try:
        def make_rewriter_call():
            return client.chat.completions.create(
                model="gpt-4o",  # Using gpt-4o as requested
                messages=[
                    {"role": "system", "content": TOPIC_REWRITING_PROMPT},
                    {"role": "user", "content": formatted_content}
                ],
                temperature=0.7
            )
        
        print("[rewrite_topic] Making API call...")
        response = retry_api_call(make_rewriter_call)
        
        # Extract the rewritten topic
        rewritten_topic = response.choices[0].message.content.strip()
        print(f"[rewrite_topic] Rewritten topic:\n{rewritten_topic}")
        
        return rewritten_topic
        
    except Exception as e:
        print(f"[rewrite_topic] ERROR: {type(e).__name__}: {str(e)}")
        raise RuntimeError(f"Failed to rewrite topic: {str(e)}")


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


# def run_deep_research_job(topic: str, hours: Optional[int] = None) -> Dict:
#     """
#     Wrapper for Deep Research API call with error handling and partial result recovery.
#     Adapted from 02-topic-then-deep-research.py
    
#     Returns:
#         Dict with report_markdown, graph, and footnotes
#     """
#     print(f"\n[run_deep_research_job] Starting deep research")
#     print(f"[run_deep_research_job] Topic: '{topic}'")
#     if hours:
#         print(f"[run_deep_research_job] Hours: {hours}")
    
#     # Get API key and create client
#     api_key = load_api_key()
#     if not api_key:
#         raise ValueError("OpenAI API key not found. Please configure your API key.")
    
#     client = OpenAI(api_key=api_key)
    
#     try:
#         # Call the deep research API
#         print("[run_deep_research_job] Calling deep research API...")
#         job_id = start_deep_research_job(topic, hours)

#         # Poll for completion
#         resp = poll_background_job(client, job_id)
        
#         if resp.status != "completed":
#             raise RuntimeError(f"Job ended with status {resp.status}")

#         # Extract the final assistant message
#         content_block = resp.output[-1].content[0]
#         result = wait_for_deep_research_out(job_id)
        
#         print("[run_deep_research_job] Deep research completed, validating results...")
        
#         # Validate result has required fields
#         if "report_markdown" not in result:
#             # Try to salvage partial results
#             if "graph" in result:
#                 result["report_markdown"] = f"# {topic}\n\n*Note: Report generation failed, but knowledge graph was created successfully.*"
#             else:
#                 raise ValueError("Missing report_markdown in Deep Research result")
        
#         if "graph" not in result:
#             raise ValueError("Missing graph in Deep Research result")
        
#         # Ensure graph has required structure
#         if "nodes" not in result["graph"]:
#             result["graph"]["nodes"] = []
#         if "edges" not in result["graph"]:
#             result["graph"]["edges"] = []
        
#         if "footnotes" not in result:
#             result["footnotes"] = {}  # Default to empty if missing
        
#         print(f"[run_deep_research_job] Found {len(result['graph']['nodes'])} nodes and {len(result['graph']['edges'])} edges")
        
#         # Validate nodes have learning objectives
#         for i, node in enumerate(result["graph"]["nodes"]):
#             if "learning_objectives" not in node or not node["learning_objectives"]:
#                 print(f"[run_deep_research_job] Warning: Node '{node.get('label', 'unknown')}' missing learning objectives, generating defaults")
#                 # Generate placeholder objectives if missing
#                 node["learning_objectives"] = [
#                     f"Understand the key concepts of {node['label']}",
#                     f"Apply {node['label']} principles in practice",
#                     f"Analyze relationships between {node['label']} and related topics",
#                     f"Evaluate different approaches to {node['label']}",
#                     f"Create solutions using {node['label']} knowledge"
#                 ]
        
#         print("[run_deep_research_job] Deep research validation complete")
#         return result
        
#     except openai.AuthenticationError:
#         print("[run_deep_research_job] ERROR: Authentication failed")
#         raise RuntimeError("Invalid API key. Please check your OpenAI API key.")
#     except openai.PermissionDeniedError:
#         print("[run_deep_research_job] ERROR: Permission denied")
#         raise RuntimeError("API key doesn't have access to Deep Research model.")
#     except openai.RateLimitError:
#         print("[run_deep_research_job] ERROR: Rate limit exceeded")
#         raise RuntimeError("Rate limit exceeded. Please try again in a few minutes.")
#     except openai.APIError as e:
#         print(f"[run_deep_research_job] ERROR: OpenAI API error: {str(e)}")
#         raise RuntimeError(f"OpenAI API error: {str(e)}")
#     except Exception as e:
#         print(f"[run_deep_research_job] ERROR: {type(e).__name__}: {str(e)}")
#         raise RuntimeError(f"Deep Research failed: {str(e)}") 


def start_deep_research_job(topic: str, hours: Optional[int] = None, oldAttemptSalvagedTxt: str = None, research_model: str = None) -> str:
    """
    Start a deep research job and return the job_id immediately.
    The job will run in the background on OpenAI's servers.
    
    Args:
        topic: The learning topic (already refined/rewritten)
        hours: Optional number of hours the user wants to invest
        
    Returns:
        str: The job ID for polling
    """
    print(f"\n[start_deep_research_job] Starting job for topic: '{topic}'")
    if hours:
        print(f"[start_deep_research_job] Hours: {hours}")
    
    # Get API key and create client
    api_key = load_api_key()
    if not api_key:
        raise ValueError("OpenAI API key not found. Please configure your API key.")
    
    client = OpenAI(api_key=api_key)
    
    try:
        # Import the DEVELOPER_PROMPT and model from deep_research module
        from utils.deep_research import DEVELOPER_PROMPT, DEEP_RESEARCH_MODEL

        research_model = research_model or DEEP_RESEARCH_MODEL
        print(f"[start_deep_research_job] Using model: {research_model}")
        
        # Prepare the user message with optional hours
        user_message = f"Topic: {topic}"
        if hours:
            user_message += f"\n\nTime user wants to invest to study: {hours} hours"
            target_nodes = min(max(hours * 2, 4), 40)
            user_message += f"\nTarget node count ≈ {target_nodes} (keep between {target_nodes - 2} and {target_nodes + 2})."
        user_message += "\nPlease follow the developer instructions."

        if oldAttemptSalvagedTxt:
            user_message += "\n\n"+oldAttemptSalvagedTxt
        
        print(f"[start_deep_research_job] User message: {user_message}")
        
        # Build input messages
        input_messages = [
            {
                "role": "developer",
                "content": [{"type": "input_text", "text": DEVELOPER_PROMPT}]
            },
            {
                "role": "user",
                "content": [{"type": "input_text", "text": user_message}]
            }
        ]

        # Tools configuration
        tools = [{"type": "web_search_preview"}]
        
        print("[start_deep_research_job] Submitting deep-research job...")
        resp = client.responses.create(
            model=research_model,
            background=True,
            input=input_messages,
            tools=tools,
            reasoning={"summary": "auto"},
        )
        
        job_id = resp.id
        print(f"[start_deep_research_job] Job submitted successfully with ID: {job_id}")
        
        return job_id
        
    except openai.AuthenticationError:
        print("[start_deep_research_job] ERROR: Authentication failed")
        raise RuntimeError("Invalid API key. Please check your OpenAI API key.")
    except openai.PermissionDeniedError:
        print("[start_deep_research_job] ERROR: Permission denied")
        raise RuntimeError("API key doesn't have access to Deep Research model.")
    except Exception as e:
        print(f"[start_deep_research_job] ERROR: {type(e).__name__}: {str(e)}")
        raise RuntimeError(f"Failed to start Deep Research job: {str(e)}") 


def test_job():
    print("test: run the jobs")
    api_key = load_api_key()
    if not api_key:
        raise ValueError("OpenAI API key not found. Please configure your API key.")

    client = OpenAI(api_key=api_key)

    from utils.deep_research import test_data, deep_research_output_cleanup

    input_data = test_data
    val = deep_research_output_cleanup(input_data, client)
    print(f"[test_job] Val: {val}")