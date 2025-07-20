"""
Jobs module for Autodidact
Contains: clarifier agent, deep research wrapper, grader, and tutor nodes
"""

import json
import re
import time
import logging
from typing import Dict, List, Optional
import openai
from openai import OpenAI
from utils.config import load_api_key, get_current_provider
from utils.providers import create_client, get_model_for_task, get_provider_info, ProviderError, get_api_call_params
from utils.deep_research import TOPIC_CLARIFYING_PROMPT, TOPIC_REWRITING_PROMPT

logger = logging.getLogger(__name__)


# Constants for retry logic
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds


def get_token_count(response) -> str:
    """
    Extract token count from API response, handling both object and dict formats.
    
    Args:
        response: API response object
        
    Returns:
        str: Token count as string or 'n/a' if not available
    """
    usage_info = getattr(response, 'usage', None)
    if usage_info:
        if hasattr(usage_info, 'total_tokens'):
            return str(usage_info.total_tokens)
        elif isinstance(usage_info, dict):
            return str(usage_info.get('total_tokens', 'n/a'))
    return 'n/a'


def retry_api_call(func, *args, max_retries=MAX_RETRIES, **kwargs):
    """Retry API calls with exponential backoff"""
    last_error = None
    for attempt in range(max_retries):
        try:
            return func(*args, **kwargs)
        except openai.RateLimitError as e:
            wait_time = RETRY_DELAY * (2 ** attempt)
            logger.warning(f"Rate limit hit, waiting {wait_time} seconds...")
            time.sleep(wait_time)
            last_error = e
        except openai.APIError as e:
            if attempt < max_retries - 1:
                wait_time = RETRY_DELAY * (2 ** attempt)
                logger.warning(f"API error, retrying in {wait_time} seconds...")
                time.sleep(wait_time)
                last_error = e
            else:
                raise
        except Exception as e:
            logger.error(f"Non-API error during API call: {type(e).__name__}: {str(e)}")
            raise
    logger.error(f"Failed after {max_retries} attempts. Last error: {str(last_error)}")
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
    logger.info(f"Starting clarification for topic: '{topic}'")
    if hours:
        logger.info(f"User wants to invest {hours} hours")

    # Create client using provider abstraction
    try:
        client = create_client()
    except ProviderError as e:
        logger.error(f"Provider configuration error: {str(e)}")
        raise ValueError(f"Provider configuration error: {str(e)}")

    # Prepare user message
    user_msg = f"Topic: {topic}"
    if hours:
        user_msg += f"\nTime investment: {hours} hours"

    logger.info(f"Using model: {get_model_for_task('chat')}")
    logger.debug(f"User message: {user_msg}")

    try:
        # Call API with retry logic using chat model
        def make_clarifier_call():
            params = get_api_call_params(
                model=get_model_for_task("chat"),
                messages=[
                    {"role": "system", "content": TOPIC_CLARIFYING_PROMPT},
                    {"role": "user", "content": user_msg}
                ],
                temperature=0.7
            )
            logger.info(f"[API CALL] Reason: Topic clarification | Model: {params.get('model')} | Provider: {get_provider_info(params.get('model', 'openai')).get('name', 'unknown')}")
            return client.chat.completions.create(**params)

        logger.info("Making API call for topic clarification...")
        response = retry_api_call(make_clarifier_call)
        meta = getattr(response, 'meta', None) or getattr(response, 'metadata', None) or {}
        logger.info(f"[API RETURN] Topic clarification complete | Model: {get_model_for_task('chat')} | Tokens: {get_token_count(response)} | Price: {meta.get('price', 'n/a')} | Meta: {meta}")

        # Extract the response content
        questions_text = response.choices[0].message.content.strip()
        logger.debug(f"Raw response:\n{questions_text}")

        # Parse the questions from the response
        questions = []
        lines = questions_text.split('\n')
        for line in lines:
            line = line.strip()
            if line and (line.startswith('-') or line.startswith('•') or line.startswith('*') or 
                        (len(line) > 2 and line[0].isdigit() and line[1] in '.)')):
                question = re.sub(r'^[-•*\d.)\s]+', '', line).strip()
                if question:
                    questions.append(question)

        if not questions:
            logger.info("No bullet points found, trying to split by sentences")
            sentences = re.split(r'[?!.]\s+', questions_text)
            questions = [s.strip() + '?' if not s.strip().endswith('?') else s.strip() 
                        for s in sentences if s.strip() and len(s.strip()) > 10]

        logger.info(f"Extracted {len(questions)} questions")
        for i, q in enumerate(questions, 1):
            logger.debug(f"Q{i}: {q}")

        return questions

    except openai.AuthenticationError:
        logger.error("Authentication failed")
        raise RuntimeError("Invalid API key. Please check your API key configuration.")
    except openai.PermissionDeniedError:
        logger.error("Permission denied")
        raise RuntimeError("API key doesn't have access to the required model.")
    except ProviderError as e:
        logger.error(f"Provider error: {str(e)}")
        raise RuntimeError(f"Provider configuration error: {str(e)}")
    except Exception as e:
        logger.error(f"Clarifier API call failed: {type(e).__name__}: {str(e)}")
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
    logger.info(f"Starting topic rewriting")
    logger.info(f"Initial topic: '{initial_topic}'")
    logger.info(f"Number of questions: {len(questions)}")
    logger.info(f"User answers length: {len(user_answers)} chars")
    
    # Create client using provider abstraction
    try:
        client = create_client()
    except ProviderError as e:
        raise ValueError(f"Provider configuration error: {str(e)}")
    
    # Format the content for the rewriting prompt
    formatted_content = f"""Initial topic: {initial_topic}

Clarifying questions:
"""
    for i, question in enumerate(questions, 1):
        formatted_content += f"{i}. {question}\n"
    
    formatted_content += f"\nUser's responses:\n{user_answers}"
    
    logger.debug(f"Formatted content for API:\n{formatted_content}")
    logger.info(f"Using model: {get_model_for_task('chat')}")
    
    try:
        def make_rewriter_call():
            params = get_api_call_params(
                model=get_model_for_task("chat"),
                messages=[
                    {"role": "system", "content": TOPIC_REWRITING_PROMPT},
                    {"role": "user", "content": formatted_content}
                ],
                temperature=0.7
            )
            logger.info(f"[API CALL] Reason: Topic rewriting | Model: {params.get('model')} | Provider: {get_provider_info(params.get('model', 'openai')).get('name', 'unknown')}")
            return client.chat.completions.create(**params)

        logger.info("Making API call for topic rewriting...")
        response = retry_api_call(make_rewriter_call)
        meta = getattr(response, 'meta', None) or getattr(response, 'metadata', None) or {}
        logger.info(f"[API RETURN] Topic rewriting complete | Model: {get_model_for_task('chat')} | Tokens: {get_token_count(response)} | Price: {meta.get('price', 'n/a')} | Meta: {meta}")
        
        # Extract the rewritten topic
        rewritten_topic = response.choices[0].message.content.strip()
        logger.info(f"Rewritten topic:\n{rewritten_topic}")
        
        return rewritten_topic
        
    except Exception as e:
        logger.error(f"ERROR: {type(e).__name__}: {str(e)}")
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
    
    # Create client using provider abstraction
    try:
        client = create_client()
    except ProviderError as e:
        raise ValueError(f"Provider configuration error: {str(e)}")
    
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
            params = get_api_call_params(
                model=get_model_for_task("chat"),
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that refines learning topics based on user input."},
                    {"role": "user", "content": refinement_prompt.format(qa_text=qa_text)}
                ],
                temperature=0.7
            )
            logger.info(f"[API CALL] Reason: Topic refinement | Model: {params.get('model')} | Provider: {get_provider_info(params.get('model', 'openai')).get('name', 'unknown')}")
            return client.chat.completions.create(**params)

        logger.info("Making API call for topic refinement...")
        response = retry_api_call(make_refinement_call)
        meta = getattr(response, 'meta', None) or getattr(response, 'metadata', None) or {}
        logger.info(f"[API RETURN] Topic refinement complete | Model: {get_model_for_task('chat')} | Tokens: {get_token_count(response)} | Price: {meta.get('price', 'n/a')} | Meta: {meta}")
        return response.choices[0].message.content.strip()
        
    except Exception as e:
        raise RuntimeError(f"Failed to process clarification responses: {e}")


# def run_deep_research_job(topic: str, hours: Optional[int] = None) -> Dict:
#     """
#     Wrapper for Deep Research API call with error handling and partial result recovery.
#     Adapted from 02-topic-then-deep-research.py
    
#     Returns:
#         Dict with report_markdown, graph, and resources
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
        
#         if "resources" not in result:
#             result["resources"] = {}  # Default to empty if missing
        
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
    For OpenAI: Uses background jobs that run on their servers.
    For Perplexity: Creates a pseudo job_id and executes immediately (may take 4-5 minutes).
    
    Args:
        topic: The learning topic (already refined/rewritten)
        hours: Optional number of hours the user wants to invest
        
    Returns:
        str: The job ID for polling (OpenAI) or pseudo-ID for immediate execution (Perplexity)
    """
    logger.info(f"[API CALL] Reason: Start deep research | Topic: {topic} | Hours: {hours if hours else 'n/a'}")
    if hours:
        logger.info(f"User wants to invest {hours} hours")
    
    # Create client using provider abstraction
    try:
        client = create_client()
        current_provider = get_current_provider()
    except ProviderError as e:
        raise ValueError(f"Provider configuration error: {str(e)}")
    
    try:
        # Import the DEVELOPER_PROMPT from deep_research module
        from utils.deep_research import DEVELOPER_PROMPT
        
        # Get the appropriate model for deep research
        try:
            research_model = research_model or get_model_for_task("deep_research")
        except ProviderError:
            # Fallback to chat model if deep research not available
            logger.info(f"Deep research model not available for {current_provider}, using chat model")
            research_model = research_model or get_model_for_task("chat")
        
        logger.info(f"Using provider: {current_provider}")
        logger.info(f"Using model: {research_model}")
        
        # Check if this provider supports deep research features
        provider_info = get_provider_info(current_provider)
        supports_deep_research = provider_info.get("supports_deep_research", False)
        
        # Prepare the user message with optional hours
        user_message = f"Topic: {topic}"
        if hours:
            user_message += f"\n\nTime user wants to invest to study: {hours} hours"
            target_nodes = min(max(hours * 2, 4), 40)
            user_message += f"\nTarget node count ≈ {target_nodes} (keep between {target_nodes - 2} and {target_nodes + 2})."
        user_message += "\nPlease follow the developer instructions."

        if oldAttemptSalvagedTxt:
            user_message += "\n\n"+oldAttemptSalvagedTxt
        
        logger.debug(f"User message: {user_message}")
        
        # Handle different provider approaches
        if current_provider == "openai" and supports_deep_research:
            # OpenAI approach: Use background jobs with responses.create()
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
            
            logger.info("Submitting OpenAI deep-research background job...")
            resp = client.responses.create(
                model=research_model,
                background=True,
                input=input_messages,
                tools=tools,
                reasoning={"summary": "auto"},
            )
            meta = getattr(resp, 'meta', None) or getattr(resp, 'metadata', None) or {}
            logger.info(f"[API RETURN] Deep research job submitted | Model: {research_model} | Job ID: {resp.id} | Tokens: {get_token_count(resp)} | Price: {meta.get('price', 'n/a')} | Meta: {meta}")
            
            job_id = resp.id
            # Clean the job ID in case it contains control characters
            from backend.db import clean_job_id
            cleaned_job_id = clean_job_id(job_id)
            logger.info(f"OpenAI job submitted successfully with ID: {cleaned_job_id}")
            
            return cleaned_job_id
            
        elif current_provider == "openrouter" and "perplexity" in research_model.lower():
            # Perplexity approach: Run in a background thread, immediately return job ID
            logger.info("Using Perplexity Sonar Deep Research (background thread)...")
            import uuid, threading, json
            from pathlib import Path
            pseudo_job_id = f"perplexity-{str(uuid.uuid4())[:8]}"
            from utils.config import PERPLEXITY_DEEP_RESEARCH_TIMEOUT
            temp_dir = Path.home() / '.autodidact' / 'temp_responses'
            temp_dir.mkdir(parents=True, exist_ok=True)
            temp_file = temp_dir / f"{pseudo_job_id}.json"

            # Write initial status as 'queued'
            with open(temp_file, 'w') as f:
                json.dump({
                    "status": "queued",
                    "content": None,
                    "model": research_model,
                    "provider": current_provider
                }, f)

            def run_perplexity_job():
                try:
                    long_timeout_client = openai.OpenAI(
                        api_key=client.api_key,
                        base_url=client.base_url,
                        timeout=PERPLEXITY_DEEP_RESEARCH_TIMEOUT
                    )
                    logger.info(f"[API CALL] Reason: Perplexity deep research | Model: {research_model} | Provider: {current_provider} | Job ID: {pseudo_job_id}")
                    response = long_timeout_client.chat.completions.create(
                        model=research_model,
                        messages=[
                            {"role": "system", "content": DEVELOPER_PROMPT},
                            {"role": "user", "content": user_message}
                        ],
                        temperature=0.7,
                        timeout=PERPLEXITY_DEEP_RESEARCH_TIMEOUT
                    )
                    meta = getattr(response, 'meta', None) or getattr(response, 'metadata', None) or {}
                    logger.info(f"[API RETURN] Perplexity deep research complete | Model: {research_model} | Job ID: {pseudo_job_id} | Tokens: {get_token_count(response)} | Price: {meta.get('price', 'n/a')} | Meta: {meta}")
                    response_content = response.choices[0].message.content
                    with open(temp_file, 'w') as f:
                        json.dump({
                            "status": "completed",
                            "content": response_content,
                            "model": research_model,
                            "provider": current_provider
                        }, f)
                    logger.info(f"Completed and stored result for {pseudo_job_id}")
                except Exception as e:
                    with open(temp_file, 'w') as f:
                        json.dump({
                            "status": "failed",
                            "content": str(e),
                            "model": research_model,
                            "provider": current_provider
                        }, f)
                    logger.error(f"[API RETURN] Perplexity deep research failed | Model: {research_model} | Job ID: {pseudo_job_id} | Error: {e}")

            threading.Thread(target=run_perplexity_job, daemon=True).start()
            logger.info(f"Perplexity job {pseudo_job_id} started in background thread.")
            return pseudo_job_id
            
        else:
            # Fallback approach: Use regular chat completion
            logger.info(f"[API CALL] Reason: Fallback chat completion | Model: {research_model} | Provider: {current_provider}")
            params = get_api_call_params(
                model=research_model,
                messages=[
                    {"role": "system", "content": DEVELOPER_PROMPT},
                    {"role": "user", "content": user_message}
                ],
                temperature=0.7
            )
            response = client.chat.completions.create(**params)
            meta = getattr(response, 'meta', None) or getattr(response, 'metadata', None) or {}
            logger.info(f"[API RETURN] Fallback chat completion complete | Model: {research_model} | Tokens: {get_token_count(response)} | Price: {meta.get('price', 'n/a')} | Meta: {meta}")
            
            # Generate a pseudo job ID and store response
            import uuid
            pseudo_job_id = f"chat-{str(uuid.uuid4())[:8]}"
            
            # Store the response temporarily
            from pathlib import Path
            temp_dir = Path.home() / '.autodidact' / 'temp_responses'
            temp_dir.mkdir(parents=True, exist_ok=True)
            temp_file = temp_dir / f"{pseudo_job_id}.json"
            
            import json
            with open(temp_file, 'w') as f:
                json.dump({
                    "status": "completed",
                    "content": response.choices[0].message.content,
                    "model": research_model,
                    "provider": current_provider
                }, f)
            
            return pseudo_job_id
        
    except openai.AuthenticationError:
        logger.error("Authentication failed")
        raise RuntimeError("Invalid API key. Please check your API key configuration.")
    except openai.PermissionDeniedError:
        logger.error("Permission denied")
        raise RuntimeError("API key doesn't have access to the required model.")
    except openai.APITimeoutError:
        logger.error("Request timeout")
        raise RuntimeError("Deep research request timed out. Perplexity requests can take 4-5 minutes.")
    except ProviderError as e:
        logger.error(f"Provider error: {str(e)}")
        raise RuntimeError(f"Provider configuration error: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error: {type(e).__name__}: {str(e)}")
        raise RuntimeError(f"Failed to start research job: {str(e)}") 


def test_job():
    print("test: run the jobs")
    try:
        client = create_client()
    except ProviderError as e:
        raise ValueError(f"Provider configuration error: {str(e)}")

    from utils.deep_research import test_data, deep_research_output_cleanup

    input_data = test_data
    val = deep_research_output_cleanup(input_data, client)
    print(f"[test_job] Val: {val}")