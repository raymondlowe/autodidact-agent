import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import List

import networkx as nx
import openai

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #

# MODEL_NAME = "o3-deep-research-2025-06-26"      # adjust if you have access to other tiers
MODEL_NAME = "o4-mini-deep-research-2025-06-26"      # adjust if you have access to other tiers


POLL_INTERVAL = 10                              # seconds between background-job polls
BRANCHING_MIN = 1.3
ROOT_RATIO_MIN = 0.25
LEAF_RATIO_MIN = 0.25

DEVELOPER_PROMPT = """
You are a “Deep Research + Graph Builder” agent.

Goal
====
Given a user-supplied learning topic (and optional PDFs / URLs), you must:

1. Investigate the topic thoroughly (use web_search_preview, code_interpreter, and
   any attached files).
2. Write a concise but comprehensive report in Markdown, with inline citations
   like “…text [^1]”.
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
        "source_citations": [1,3]      // footnote numbers from the report
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

Constraints
	•	Target 12–35 nodes total.
	•	Graph must be acyclic.
	•	Return only the JSON object in your final message (no markdown fencing).
"""


def upload_pdfs(client: openai.OpenAI, pdf_paths: List[Path]) -> List[str]:
  """Upload local PDFs and return a list of file_ids."""
  file_ids = []
  for p in pdf_paths:
    print(f"Uploading {p} …")
    with open(p, "rb") as f:
      up = client.files.create(file=f, purpose="assistants")
      file_ids.append(up.id)
  return file_ids

def poll_background_job(client: openai.OpenAI, job_id: str):
  """Poll until a background deep-research job is complete."""
  while True:
    job = client.responses.retrieve(job_id)
    status = job.status
    if status in ("completed", "failed", "cancelled", "expired"):
      return job
    print(f"[{time.strftime('%H:%M:%S')}] Job {job_id} → {status} …")
    time.sleep(POLL_INTERVAL)

def validate_graph(data: dict) -> None:
  """Raise ValueError if the graph violates DAG/branching/roots/leaves/30-min rules."""
  nodes = data["graph"]["nodes"]
  edges = data["graph"]["edges"]

  # 30-minute rule
  bad_study_time = [n for n in nodes if n.get("study_time_minutes") != 30]
  if bad_study_time:
      raise ValueError(f"{len(bad_study_time)} nodes violate study_time_minutes != 30")

  # Build graph
  g = nx.DiGraph()
  g.add_nodes_from(n["id"] for n in nodes)
  g.add_edges_from((e["source"], e["target"]) for e in edges)

  # DAG check
  if not nx.is_directed_acyclic_graph(g):
      raise ValueError("Graph is not acyclic")

  roots = [n for n in g if g.in_degree(n) == 0]
  leaves = [n for n in g if g.out_degree(n) == 0]
  branching = sum(g.out_degree(n) for n in g) / max(1, len(g))

  if len(roots) / len(g) < ROOT_RATIO_MIN:
      raise ValueError(f"Root ratio too low: {len(roots)}/{len(g)}")
  if len(leaves) / len(g) < LEAF_RATIO_MIN:
      raise ValueError(f"Leaf ratio too low: {len(leaves)}/{len(g)}")
  if branching < BRANCHING_MIN:
      raise ValueError(f"Branching factor too low: {branching:.2f}")

# --------------------------------------------------------------------------- #
# Main Deep-Research runner
# --------------------------------------------------------------------------- #

def run_deep_research(topic: str, pdf_paths: List[Path]) -> dict:
  openai_api_key = os.environ.get("OPENAI_API_KEY")
  if not openai_api_key:
    raise ValueError("OPENAI_API_KEY environment variable is not set")

  client = openai.OpenAI(api_key=openai_api_key)


  # Old job id is to faciliate the case of getting output of old job so that we don't have to wait the long 15-30 minutes every time
  old_job_id = None
  # old_job_id = "resp_686d6a4a623481998fe7458cba9f7bd301fded9dee4b8748"
  content_block = None

  if old_job_id:
    job = client.responses.retrieve(old_job_id)

    content_block = job.output[-1].content[0]
    print(content_block)
  else:
    file_ids = upload_pdfs(client, pdf_paths) if pdf_paths else []

    # --------------------------------------------------------------------------- #
    # Build input messages & tool declaration
    # --------------------------------------------------------------------------- #
    input_messages = [
        {
            "role": "developer",
            "content": [{"type": "input_text", "text": DEVELOPER_PROMPT}]
        },
        {
            "role": "user",
            "content": [{"type": "input_text", "text": f"Topic: {topic}\nPlease follow the developer instructions."}]
                      + [{"type": "file", "file_id": fid} for fid in file_ids]
        }
    ]

    tools = [
        {"type": "web_search_preview"},
    ]
    if file_ids:
        tools.append({"type": "code_interpreter", "container": {"type": "auto", "file_ids": file_ids}})

    print("Submitting deep-research job …")
    resp = client.responses.create(
        model=MODEL_NAME,
        background=True,
        input=input_messages,
        tools=tools,
        # options are concise detailed and auto
        reasoning={"summary": "auto"},
    )

    resp = poll_background_job(client, resp.id)
    if resp.status != "completed":
        raise RuntimeError(f"Job ended with status {resp.status}")

    # The final assistant message is in resp.output[-1]
    content_block = resp.output[-1].content[0]

    # print("="*50)
    # print("resp:")
    # print(resp)
  
  if content_block.type != "output_text":
      raise RuntimeError("Unexpected content block type")
  
  print("="*50)
  print("Final Assistant Message:")
  print(content_block.text)

  # Parse JSON
  try:
      data = json.loads(content_block.text)
      return data
  except json.JSONDecodeError as e:
      raise RuntimeError(f"Failed to parse JSON response: {e}")

# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def cli():
  parser = argparse.ArgumentParser(description="Deep-Research → Markdown report + prerequisite graph.")
  parser.add_argument("topic", help="Learning topic, e.g. 'Foundations of Statistical Learning'")
  parser.add_argument("--pdf", action="append", type=Path, default=[], help="Path to a supporting PDF (can be given multiple times)")
  parser.add_argument("--outdir", type=Path, default=Path.cwd(), help="Directory to write outputs")
  args = parser.parse_args()

  try:
      result = run_deep_research(args.topic, args.pdf)
      # validate_graph(result)
  except Exception as e:
      print(f"❌ Validation or API error: {e}", file=sys.stderr)
      sys.exit(1)

  topic_slug = args.topic.lower().replace(" ", "-")
  md_path = args.outdir / f"outputs/{topic_slug}-report.md"
  json_path = args.outdir / f"outputs/{topic_slug}-graph.json"

  md_path.write_text(result["report_markdown"], encoding="utf-8")
  json_path.write_text(json.dumps(result["graph"], indent=2), encoding="utf-8")

  print(f"✅ Saved Markdown report → {md_path}")
  print(f"✅ Saved knowledge-graph JSON → {json_path}")

if __name__ == "__main__":
  if not os.environ.get("OPENAI_API_KEY"):
    print("❌ Set OPENAI_API_KEY in your environment.", file=sys.stderr)
    sys.exit(1)
cli()

# --------------------------------------------------------------------------- #
# How it lines up with what we discussed
# --------------------------------------------------------------------------- #

# | Requirement | Where it appears |
# |-------------|------------------|
# | **Dual output (Markdown + graph)** | `DEVELOPER_PROMPT` → JSON schema with `report_markdown` & `graph` |
# | **30-minute nodes** | Prompt rule + validator checks `study_time_minutes == 30` |
# | **Parallel DAG (branching) constraints** | Prompt rules + `validate_graph()` (roots / leaves / branching) |
# | **PDF ingestion** | `upload_pdfs()` → files passed to `code_interpreter` |
# | **Background job polling** | `poll_background_job()` |
# | **Graph validation (acyclic etc.)** | `networkx` checks |
# | **Outputs for human + machine** | Writes `*-report.md` and `*-graph.json` |

# Feel free to extend the schema (difficulty, estimated effort, tags, etc.) or to wire the JSON directly into Neo4j / ReactFlow for visual mind-mapping.