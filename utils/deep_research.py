"""
Deep Research module for Autodidact
Refactored from 02-topic-then-deep-research.py
"""

import json
import time
from typing import Dict, Optional
import openai
from openai import OpenAI
from utils.config import DEEP_RESEARCH_MODEL, DEEP_RESEARCH_POLL_INTERVAL

# After we get the user's topic & time investment preferences, this prompt is used to ask clarifying questions to the user
TOPIC_CLARIFYING_PROMPT = """
You will be given a short topic that a user wants to learn alongside the time they want to invest. Your job is NOT to answer it or complete the task, but instead to ask clarifying questions that would help you or another researcher to understand what exactly the user wants to learn.

GUIDELINES:
1. **Focus on Learning Scope & Learner Profile**
- Ask what *specific aspect* of the topic interests them (breadth vs. depth, technical vs. conceptual).  
- Ask about their **background knowledge** (novice, hobbyist, intermediate, expert).  
- Ask their **preferred learning outcomes** (e.g., “explain to a peer”, “implement a demo”, “pass an exam”).
- Consider what information would change the structure, depth, or direction for the specialized learning plan.
- Ask about each one *explicitly*, even if it feels obvious or typical.

2. **Do Not Invent Preferences**
- If the user did not mention a preference, *do not assume it*. Ask about it clearly and neutrally.

3. **Use the First Person**
- Phrase your questions from the perspective of the assistant or researcher talking to the user (e.g., “Could you clarify...” or “Do you have a preference for...”)

4. **Use a Bulleted List if Multiple Questions**
- If there are multiple open questions, list them clearly in bullet format for readability.

5. **Avoid Overasking**
- Prioritize the 3–6 questions that would most reduce ambiguity or scope creep. You don’t need to ask *everything*, just the most pivotal unknowns.

6. **Include Examples Where Helpful**
- If asking about preferences, briefly list examples to help the user answer. For e.g. media formats they prefer could be textbook chapters, videos, blogposts, etc.

7. **Format for Conversational Use**
- The output should sound helpful and conversational—not like a form. Aim for a natural tone while still being precise.
"""

# This prompt will be passed the user's topic, clarifying questions, and their responses.
# It will be used to rewrite the topic into a more specific and detailed topic instruction, which will finally be passed into the deep research prompt.
TOPIC_REWRITING_PROMPT = """
You will be given an initial topic by the user, followed by clarifying questions, followed by the user's responses. Your job is to rewrite these into a concise detailed topic instruction.

GUIDELINES:
1. **Maximize Specificity and Detail**
- Include all known user preferences and explicitly list key attributes or dimensions to consider.
- It is of utmost importance that all details from the user are included in the instructions.

2. **Fill in Unstated But Necessary Dimensions as Open-Ended**
- If certain attributes are essential for a meaningful output but the user has not provided them, explicitly state that they are open-ended or default to no specific constraint.

3. **Avoid Unwarranted Assumptions**
- If the user has not provided a particular detail, do not invent one.
- Instead, state the lack of specification and guide the researcher to treat it as flexible or accept all possible options.

4. **Use the First Person**
- Phrase the request from the perspective of the user.
"""


# Updated developer prompt to include learning objectives
DEVELOPER_PROMPT = """
You are a “Deep-Research Curriculum Architect” with the goal of making the optimal learning syllabus for motivated autodidacts  on the topic user asks of you

TASK 1 – RESOURCES  
• Identify 10–15 authoritative, learner-friendly resources suitable for motivated autodidacts on the specified topic.
• Return them as a JSON array **resources** with:  
  { "rid", "title", "type", "url", "date", "scope" }  
  – type ∈ {book | paper | video | interactive | article}.  
  – scope = one-sentence summary.

TASK 2 – GRAPH  
• Build a directed-acyclic knowledge graph with **≈ 2 nodes for every hour of study time stated by the user (minimum 8, maximum 40), ±2 nodes allowed**.  
• Each node must be teachable in ~30 min (split >45 min concepts, merge <15 min).  
• Node schema:  
  {
    "id": "kebab-case",                  // unique  
    "title": "human-readable",  
    "prerequisites": ["id1","id2","id3"],// ≤3; omit if none  
    "objectives": [                      // 5–7, Bloom verbs, ≤12 words
      "Explain …", "Calculate …"
    ],
    "sections": [                        // pointers into resources
      { "rid": "mastering_bitcoin_2e", "loc": "Ch.8 §Difficulty" }
    ]
  }

HARD CONSTRAINTS  
• Graph acyclic; ≥10 % roots (no prerequisites) and ≥15 % leaves (no dependants).  
• Every prerequisite **must exactly match an “id” that appears in this JSON**.  
• Use only `rid` values present in **resources**.  
• Return **one valid JSON object** with keys `"resources"` and `"nodes"`.  
• Any non-JSON text will be discarded.
"""


def poll_background_job(client: OpenAI, job_id: str) -> Dict:
    """Poll until a background deep-research job is complete."""
    while True:
        job = client.responses.retrieve(job_id)
        status = job.status
        if status in ("completed", "failed", "cancelled", "expired"):
            return job
        print(f"[{time.strftime('%H:%M:%S')}] Job {job_id} → {status} …")
        time.sleep(DEEP_RESEARCH_POLL_INTERVAL)


def run_deep_research(topic: str, client: OpenAI, hours: Optional[int] = None, existing_job_id: Optional[str] = None) -> Dict:
    """
    Run Deep Research on a topic
    
    Args:
        topic: The learning topic
        client: OpenAI client instance
        hours: Optional number of hours the user wants to invest
        existing_job_id: Optional job ID to retrieve results from
    
    Returns:
        Dict with report_markdown, graph, and footnotes
    """
    print(f"\n[run_deep_research] Starting deep research")
    print(f"[run_deep_research] Topic: '{topic}'")
    print(f"[run_deep_research] Hours: {hours}")
    print(f"[run_deep_research] Existing job ID: {existing_job_id}")
    
    # If we have an existing job ID, just retrieve results
    if existing_job_id:
        print("[run_deep_research] Retrieving existing job results...")
        job = client.responses.retrieve(existing_job_id)
        content_block = job.output[-1].content[0]
    else:
        # Prepare the user message with optional hours
        user_message = f"Topic: {topic}"
        if hours:
            user_message += f"\nTarget study time: {hours} hours"
            target_nodes = min(max(hours * 2, 8), 40)
            user_message += f"\nTarget node count ≈ {target_nodes} (keep between {target_nodes - 2} and {target_nodes + 2})."
        user_message += "\nPlease follow the developer instructions."
        
        print(f"[run_deep_research] User message prepared: {user_message}")
        
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
        tools = [
            {"type": "web_search_preview"},
            # {
            #   "type": "code_interpreter",
            #   "container": {
            #     "type": "auto",
            #     "file_ids": []
            #   }
            # }
          ]
        
        print("messages", input_messages)

        # FIXME remove this later
        # FIXME make it use the data format according to the new prompt
        raise Exception("stop")

        print("Submitting deep-research job …")
        resp = client.responses.create(
            model=DEEP_RESEARCH_MODEL,
            background=True,
            input=input_messages,
            tools=tools,
            reasoning={"summary": "auto"},
        )

        # Poll for completion
        resp = poll_background_job(client, resp.id)
        
        if resp.status != "completed":
            raise RuntimeError(f"Job ended with status {resp.status}")

        # Extract the final assistant message
        content_block = resp.output[-1].content[0]
    
    if content_block.type != "output_text":
        raise RuntimeError("Unexpected content block type")
    
    # Parse JSON response
    try:
        data = json.loads(content_block.text)
        return data
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Failed to parse JSON response: {e}")


def extract_graph_and_footnotes(deep_research_result: Dict) -> tuple[Dict, Dict]:
    """
    Extract graph and footnotes from Deep Research result
    
    Returns:
        (graph_dict, footnotes_dict)
    """
    graph = deep_research_result.get("graph", {})
    footnotes = deep_research_result.get("footnotes", {})
    
    return graph, footnotes 