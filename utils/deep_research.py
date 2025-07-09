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


# Updated developer prompt to include learning objectives
DEVELOPER_PROMPT = """
You are a "Deep Research + Graph Builder" agent.

Goal
====
Given a user-supplied learning topic (and optional PDFs / URLs), you must:

1. Investigate the topic thoroughly (use web_search_preview, code_interpreter, and
   any attached files).
2. Write a concise but comprehensive report in Markdown, with inline citations
   like "…text [^1]".
3. Build a prerequisite knowledge graph (DAG) and return it as *valid JSON*.

Output format (MUST ADHERE)
---------------------------
```json
{
  "report_markdown": "<full markdown report here>",
  "graph": {
    "nodes": [
      {
        "id": "string",                // kebab-case, unique
        "label": "string",             // human-readable concept
        "summary": "1–2 sentences",
        "study_time_minutes": 30,      // always 30 unless truly unavoidable
        "source_citations": [1,3],     // footnote numbers from the report
        "learning_objectives": [       // 5-7 specific, measurable objectives
          "Explain the difference between supervised and unsupervised learning",
          "Calculate bias and variance for a given model",
          "Apply k-fold cross-validation to evaluate a classifier",
          "Implement gradient descent for linear regression",
          "Identify when regularization is needed and choose between L1/L2"
        ]
      }
    ],
    "edges": [
      {
        "source": "id",                // prerequisite
        "target": "id",                // depends-on
        "confidence": 0.0-1.0,
        "rationale": "short reason",
        "source_citations": [2]
      }
    ]
  },
  "footnotes": {
    "1": {"title":"...", "url":"..."},
    "2": {"title":"...", "url":"..."}
  }
}
```

Structural rules
	1.	The graph is a DAG, not a linear list.
	2.	Create an edge only if concept A must be learned before B.
	3.	Aim for 2–4 independent threads (disjoint roots).
	4.	≥ 25 % of nodes must have no prerequisites (roots) and ≥ 25 % must have
no dependants (leaves).
	5.	Average branching factor ≥ 1.3 (some nodes point to ≥ 2 children).
	6.	Each node should be teachable in ≈ 30 minutes. If a concept exceeds
45 min, split it; if < 15 min, merge upward.

Additional rules for learning objectives:
- Each node must have 5-7 learning objectives
- Objectives should be specific and measurable (use action verbs: explain, calculate, implement, identify, apply, etc.)
- Objectives should be achievable within the 30-minute session
- Objectives should build on prerequisites and prepare for dependents

Constraints
	•	Target 12–35 nodes total.
	•	Graph must be acyclic.
	•	Return only the JSON object in your final message (no markdown fencing).
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


def run_deep_research(topic: str, client: OpenAI, existing_job_id: Optional[str] = None) -> Dict:
    """
    Run Deep Research on a topic
    
    Args:
        topic: The learning topic
        client: OpenAI client instance
        existing_job_id: Optional job ID to retrieve results from
    
    Returns:
        Dict with report_markdown, graph, and footnotes
    """
    
    # If we have an existing job ID, just retrieve results
    if existing_job_id:
        job = client.responses.retrieve(existing_job_id)
        content_block = job.output[-1].content[0]
    else:
        # Build input messages
        input_messages = [
            {
                "role": "developer",
                "content": [{"type": "input_text", "text": DEVELOPER_PROMPT}]
            },
            {
                "role": "user",
                "content": [{"type": "input_text", "text": f"Topic: {topic}\nPlease follow the developer instructions."}]
            }
        ]

        # Tools configuration (no code_interpreter since no PDFs in v0.1)
        tools = [{"type": "web_search_preview"}]

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