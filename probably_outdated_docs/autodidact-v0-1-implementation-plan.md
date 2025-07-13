# Autodidact v0.1 Implementation Plan

**Status:** Ready for Implementation  
**Estimated Duration:** 2 weeks  
**Key Constraint:** Leverage existing `02-topic-then-deep-research.py` code

## Overview

This plan details the phased implementation of Autodidact v0.1, building a functional AI-powered learning system with:
- Topic clarification
- Deep Research integration (using existing code)
- Simple graph visualization with st.graphviz_chart
- LangGraph-based tutor sessions
- Progress tracking with SQLite

## Phase 1: Foundation & Setup (Days 1-2)

### 1.1 Project Structure
Create the modular file structure: (`autodidact` is the current working directory)
```
autodidact/
├── app.py                 # Streamlit entry point
├── backend/
│   ├── __init__.py
│   ├── jobs.py           # Clarifier, deep research wrapper, grader
│   ├── db.py             # SQLite setup and queries
│   ├── graph.py          # LangGraph tutor flow
│   └── models.py         # Data classes (Project, Node, LO, etc.)
├── components/
│   ├── __init__.py
│   └── graph_viz.py      # Graphviz wrapper for knowledge graph
├── utils/
│   ├── __init__.py
│   ├── config.py         # API key management, paths
│   └── deep_research.py  # Refactored from 02-topic-then-deep-research.py
└── requirements.txt
```

### 1.2 Core Dependencies
```
streamlit>=1.34.0
openai>=1.0.0
langgraph
langchain
networkx
graphviz
python-dotenv
```

### 1.3 Configuration Management
- Create `~/.autodidact/` directory structure
- Implement API key storage/retrieval (filesystem permissions 600)
- Environment configuration with defaults
- Define constants: `MASTERY_THRESHOLD = 0.7`

### 1.4 Database Schema
Implement SQLite schema with direct SQL (no ORM):
```sql
CREATE TABLE project (
    id TEXT PRIMARY KEY,  -- UUID
    topic TEXT NOT NULL,
    report_path TEXT,
    graph_json TEXT,
    footnotes_json TEXT,  -- JSON string containing footnotes dict
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE node (
    id TEXT PRIMARY KEY,  -- UUID
    project_id TEXT NOT NULL,
    original_id TEXT,     -- ID from Deep Research graph
    label TEXT NOT NULL,
    summary TEXT,
    mastery REAL DEFAULT 0.0,
    FOREIGN KEY (project_id) REFERENCES project(id)
);

CREATE TABLE edge (
    source TEXT NOT NULL,  -- original_id from Deep Research
    target TEXT NOT NULL,  -- original_id from Deep Research
    project_id TEXT NOT NULL,
    confidence REAL,
    rationale TEXT,
    FOREIGN KEY (project_id) REFERENCES project(id),
    PRIMARY KEY (project_id, source, target)
);

CREATE TABLE learning_objective (
    id TEXT PRIMARY KEY,  -- UUID
    node_id TEXT NOT NULL,
    description TEXT NOT NULL,
    mastery REAL DEFAULT 0.0,
    FOREIGN KEY (node_id) REFERENCES node(id)
);

CREATE TABLE transcript (
    session_id TEXT NOT NULL,
    turn_idx INTEGER NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (session_id, turn_idx)
);
```

## Phase 2: Deep Research Integration (Days 3-4)

### 2.1 Refactor Existing Code
Transform `02-topic-then-deep-research.py` into reusable module:
- Extract `run_deep_research()` to `utils/deep_research.py`
- Remove CLI-specific code
- Add proper error handling for Streamlit context
- Remove PDF handling (not needed for v0.1)
- Keep the JSON parsing and validation logic
- Use model name: `o4-mini-deep-research-2025-06-26`

### 2.2 Update Deep Research Prompt
Modify the DEVELOPER_PROMPT to include learning objectives:
```python
DEVELOPER_PROMPT = """
You are a "Deep Research + Graph Builder" agent.

Goal
====
Given a user-supplied learning topic and time duration they want to invest, your goal is to make the optimal learning syllabus for them. You must:

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
	4.	≥ 10 % of nodes must have no prerequisites (roots) and ≥ 15 % must have
no dependants (leaves).
	5.	Average branching factor ≥ 1.3 (some nodes point to ≥ 2 children).
	6.	Each node should be teachable in ≈ 30 minutes. If a concept exceeds
45 min, split it; if < 15 min, merge upward.
  7.  Each node must have 5-7 specific, measurable learning objectives

Additional rules for learning objectives:
  - Each node must have 5-7 learning objectives
  - Objectives should be specific and measurable (use action verbs: explain, calculate, implement, identify, apply, etc.)
  - Objectives should build on prerequisites and prepare for dependents

Constraints
	-	Target 12–35 nodes total.
	-	Graph must be acyclic.
	-	Return only the JSON object in your final message (no markdown fencing).
"""
```

### 2.3 Clarifier Agent
Implement in `backend/jobs.py`:
```python
def clarify_topic(topic: str, hours: int = None) -> dict:
    """
    Returns either:
    - {"need_clarification": true, "questions": ["Q1", "Q2", ...]}
    - {"need_clarification": false, "refined_topic": "..."}
    """
    
    clarification_prompt = '''
    You are an intelligent assistant preparing to conduct a deep research report. 
    Before proceeding, determine if clarification is needed.
    
    If the topic is specific enough (e.g., "Foundations of Statistical Learning", 
    "Bitcoin consensus mechanisms", "React hooks"), return:
    {"need_clarification": false}
    
    If the topic is too broad or ambiguous (e.g., "Modern World History", "Programming", 
    "Science"), ask up to 5 clarifying questions in a numbered list to help narrow down:
    - What aspect/subtopic they're most interested in
    - Their current knowledge level
    - Specific goals or applications
    - Time constraints or depth preferences
    
    Return format:
    {"need_clarification": true, "questions": ["Q1", "Q2", ...]}
    or
    {"need_clarification": false, "refined_topic": "<refined version of topic>"}
    '''
```

### 2.4 Skip-Protection Loop
- Regex patterns for detecting non-answers: `r'^\s*(idk|i don\'t know|skip|na|n/a|none)\s*$'`
- Maximum 2 re-asks before proceeding with original topic
- Clear warning messages to user

### 2.5 Deep Research Wrapper
Adapt existing code for Streamlit:
- Show spinner during API call
- Handle job polling synchronously
- Parse and store results in database including footnotes
- Extract learning objectives from each node (now included in prompt)

## Phase 3: UI & Navigation (Days 5-6)

### 3.1 Landing Page (`app.py`)
```python
# Streamlit page config
st.set_page_config(page_title="Autodidact", layout="wide")

# Session state initialization
if "project_id" not in st.session_state:
    st.session_state.project_id = None
    st.session_state.current_node = None
    st.session_state.in_session = False

# Main UI flow
if not st.session_state.project_id:
    show_topic_input()
elif st.session_state.in_session:
    show_tutor_session()
else:
    show_workspace()
```

### 3.2 Topic Input & Clarification
- Centered layout with `st.columns([1,2,1])`
- Text input for topic
- Optional number input for hours
- Clarification questions in expandable section
- Submit button triggers Deep Research

### 3.3 Workspace Layout
Two-column layout:
```python
col1, col2 = st.columns([1, 2])

with col1:
    # Collapsible report viewer
    with st.expander("Research Report", expanded=False):
        # Format markdown with footnotes
        report_with_footnotes = format_report_with_footnotes(report_md, footnotes)
        st.markdown(report_with_footnotes, unsafe_allow_html=True)
    
    # Session controls
    if st.button("Start Learning Session"):
        start_session()

with col2:
    # Knowledge graph visualization
    show_knowledge_graph()
```

### 3.4 Graph Visualization
Using st.graphviz_chart with Dagre layout (left-to-right):
```python
def create_graph_viz(nodes, edges, node_mastery):
    dot = graphviz.Digraph(engine='dot')
    dot.attr(rankdir='LR')  # Left to right layout
    
    # Configure graph attributes for better layout
    dot.attr('graph', ranksep='1.5', nodesep='0.5')
    dot.attr('node', shape='box', style='rounded,filled', fontname='Arial')
    
    for node in nodes:
        # Color based on mastery (white #ffffff to green #26c176)
        mastery = node_mastery.get(node['id'], 0)
        color = calculate_color_gradient(mastery)
        dot.node(node['id'], node['label'], 
                fillcolor=color, fontcolor='black')
    
    for edge in edges:
        # Confidence affects edge style
        style = 'solid' if edge.get('confidence', 1) > 0.7 else 'dashed'
        dot.edge(edge['source'], edge['target'], style=style)
    
    return dot

def calculate_color_gradient(mastery):
    """Linear interpolation from white to green based on mastery 0-1"""
    # White: #ffffff (255, 255, 255)
    # Green: #26c176 (38, 193, 118)
    r = int(255 - (255 - 38) * mastery)
    g = int(255 - (255 - 193) * mastery)
    b = int(255 - (255 - 118) * mastery)
    return f'#{r:02x}{g:02x}{b:02x}'
```

### 3.5 Report Formatting with Footnotes
```python
def format_report_with_footnotes(markdown_text, footnotes_dict):
    """Convert [^1] style citations to proper markdown footnotes"""
    formatted_text = markdown_text
    
    # Add footnotes section at the end
    if footnotes_dict:
        formatted_text += "\n\n---\n\n## References\n\n"
        for num, footnote in sorted(footnotes_dict.items(), key=lambda x: int(x[0])):
            title = footnote.get('title', 'Unknown')
            url = footnote.get('url', '#')
            formatted_text += f"[^{num}]: [{title}]({url})\n\n"
    
    return formatted_text
```

## Phase 4: LangGraph Tutor (Days 7-9)

### 4.1 State Definition
```python
from typing import TypedDict, List

class TutorState(TypedDict):
    session_id: str
    node_id: str
    turn_count: int
    has_previous_session: bool
    messages: List[dict]
    learning_objectives: List[dict]
    lo_scores: dict
```

### 4.2 Node Implementations
Each node is a pure function for testability:

```python
def greet_node(state: TutorState) -> TutorState:
    """Welcome message for first session"""
    
def recap_node(state: TutorState) -> TutorState:
    """2 recall questions from previous sessions"""
    
def teach_node(state: TutorState) -> TutorState:
    """Main teaching with mid-lesson check"""
    
def quick_check_node(state: TutorState) -> TutorState:
    """Final assessment question"""
    
def grade_node(state: TutorState) -> TutorState:
    """Grade the student's understanding of learning objectives"""
    
    grading_prompt = """
    Based on the teaching session transcript and the student's responses,
    evaluate their mastery of each learning objective.
    
    Learning objectives for this node:
    {learning_objectives}
    
    Transcript:
    {transcript}
    
    For each learning objective, assign a score from 0.0 to 1.0:
    - 0.0-0.3: Little to no understanding
    - 0.4-0.6: Partial understanding with gaps
    - 0.7-0.8: Good understanding with minor issues
    - 0.9-1.0: Excellent understanding
    
    Consider:
    - Accuracy of responses to questions
    - Depth of understanding shown
    - Ability to apply concepts
    - Recognition of connections to prerequisites
    
    Return JSON:
    {"lo_scores": {"lo_id_1": 0.8, "lo_id_2": 0.6, ...}}
    
    Important: Use the same context as the tutor (no privileged information).
    Base scores only on what the student demonstrated in this session.
    """
    
    # Call GPT-4o-mini with the grading prompt
    response = call_openai(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": grading_prompt.format(
                learning_objectives=state["learning_objectives"],
                transcript=format_transcript(state["messages"])
            )}
        ],
        response_format={"type": "json_object"}
    )
    
    # Parse scores and update state
    scores = json.loads(response.content)
    state["lo_scores"] = scores["lo_scores"]
    
    # Update database with new mastery scores
    update_mastery(state["node_id"], scores["lo_scores"])
    
    return state
```

### 4.3 Graph Assembly
```python
def create_tutor_graph():
    from langgraph.graph import StateGraph
    
    g = StateGraph(TutorState)
    
    # Add nodes
    g.add_node("greet", greet_node)
    g.add_node("recap", recap_node)
    g.add_node("teach", teach_node) 
    g.add_node("quick_check", quick_check_node)
    g.add_node("grade", grade_node)
    
    # Add conditional edges
    g.add_conditional_edge(
        "greet",
        lambda s: "recap" if s["has_previous_session"] else "teach"
    )
    g.add_edge("recap", "teach")
    g.add_edge("teach", "quick_check")
    g.add_edge("quick_check", "grade")
    
    return g.compile()
```

### 4.4 Streaming Integration
```python
def run_tutor_session(node_id: str):
    graph = create_tutor_graph()
    
    # Initialize state
    state = TutorState(
        session_id=str(uuid.uuid4()),
        node_id=node_id,
        # ... other fields
    )
    
    # Stream responses
    placeholder = st.empty()
    for event in graph.stream(state):
        if "messages" in event:
            placeholder.markdown(event["messages"][-1]["content"])
```

## Phase 5: Progress Tracking (Days 10-11)

### 5.1 Scheduler Logic
```python
def get_next_node(project_id: str) -> List[str]:
    """
    Returns up to 2 lowest-mastery unlocked nodes.
    Uses simple SQL query with prerequisite checking.
    """
    query = """
    WITH prerequisite_check AS (
        SELECT n.id, n.label, n.mastery,
               COUNT(e.source) as prereq_count,
               SUM(CASE WHEN pn.mastery >= ? THEN 1 ELSE 0 END) as met_count
        FROM node n
        LEFT JOIN edge e ON e.target = n.original_id AND e.project_id = n.project_id
        LEFT JOIN node pn ON pn.original_id = e.source AND pn.project_id = n.project_id
        WHERE n.project_id = ?
        GROUP BY n.id
    )
    SELECT id, label FROM prerequisite_check
    WHERE prereq_count = 0 OR prereq_count = met_count
    ORDER BY mastery ASC
    LIMIT 2
    """
    # Pass MASTERY_THRESHOLD and project_id as parameters
    return execute_query(query, [MASTERY_THRESHOLD, project_id])
```

### 5.2 Grading Implementation
Simple averaging for v0.1:
```python
def update_mastery(node_id: str, lo_scores: dict):
    # Update LO mastery with simple average
    for lo_id, score in lo_scores.items():
        old_mastery = get_lo_mastery(lo_id)
        new_mastery = (old_mastery + score) / 2
        update_lo_mastery(lo_id, new_mastery)
    
    # Update node mastery as average of LOs
    node_mastery = calculate_node_mastery(node_id)
    update_node_mastery(node_id, node_mastery)
```

### 5.3 Transcript Management
After each turn:
```python
def save_transcript(session_id: str, turn_idx: int, role: str, content: str):
    """Synchronous save to SQLite"""
    conn = get_db_connection()
    conn.execute(
        "INSERT INTO transcript VALUES (?, ?, ?, ?, datetime('now'))",
        (session_id, turn_idx, role, content)
    )
    conn.commit()
```

## Phase 6: Polish & Testing (Days 12-14)

### 6.1 Error Handling
- Graceful API failures with user-friendly messages
- Database transaction rollbacks
- Session recovery after browser refresh (reload from database)
- Deep Research failure recovery: save partial results if available

### 6.2 First-Run Experience
- API key setup modal
- Welcome message explaining the system
- Sample topics suggestion

### 6.3 Testing Checklist
- [ ] API key storage and retrieval
- [ ] Topic clarification flow
- [ ] Deep Research integration
- [ ] Graph visualization updates
- [ ] Complete tutor session flow
- [ ] Progress persistence
- [ ] Error scenarios

### 6.4 Performance Optimization
- Lazy loading of transcript history
- Efficient SQL queries with proper indexes
- Minimal state in st.session_state

## Key Implementation Notes

### From Existing Code
1. **Deep Research API**: Model name is `o4-mini-deep-research-2025-06-26`
2. **Polling interval**: 10 seconds (from existing code)
3. **Graph validation**: Can reuse the NetworkX validation logic
4. **JSON structure**: Already defined in existing code (now with LOs)

### Simplifications for v0.1
1. No async operations (except Deep Research API which is inherently async)
2. No progress bars - just spinners
3. Basic graph visualization without interactivity
4. Simple color gradient for mastery
5. No animations or fancy transitions
6. No PDF support (broken in existing code)

### Data Flow
1. User enters topic → Clarifier → Deep Research
2. Deep Research returns → Parse JSON → Store in DB (including footnotes)
3. Learning objectives come from Deep Research (no separate generation)
4. User starts session → Scheduler picks node → LangGraph flow
5. Grader scores → Update mastery → Refresh graph colors

### Critical Path Items
1. Deep Research integration (can fail if API changes)
2. LangGraph streaming (needs proper error boundaries)
3. Database migrations (plan for schema changes)
4. Session state management (Streamlit reloads)

## Success Criteria
- User can input a topic and get a study plan
- Knowledge graph displays with proper coloring
- Tutor sessions complete without errors
- Progress persists between sessions
- Total implementation time ≤ 2 weeks 