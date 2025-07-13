# Autodidact Session Engine (v 0.4) — **Full specification + LangGraph implementation notes**

> A single, self-contained document you can hand to another engineer (human or LLM) so they understand *why* the system looks the way it does **and** how to wire it up with [LangGraph](https://github.com/langchain-ai/langgraph).

---

## 📌 1 · Vision & context

* **Product goal** – Make it painless for a self-learner to master any topic by stepping through a directed-acyclic knowledge-graph.
* **One node ≈ one focussed session** (≈30 min guideline).
* **Pedagogy** – Activate relevant prior knowledge ➜ teach new concepts ➜ formative checks ➜ summative test ➜ mastery score.
* **Cost philosophy** – Burn the expensive model **once**, at the end, for grading; keep everything else on a fast, cheap model.

---

## 🗄️ 2 · Core data shapes (Python-style Pydantic)

```python
class Objective(BaseModel):
    id: str
    text: str

class Node(BaseModel):
    node_id: str
    title: str
    objectives: list[Objective]      # 5–7 items
    prereq_objectives: list[Objective]
    references_sections: list[dict]  # e.g. {"rid":"digital_gold","loc":"Ch.6"}

class FinalTestQ(BaseModel):
    q: str
    type: Literal["mcq","short","paraphrase"]
    choices: Optional[list[str]]
    answer: str

class GradePayload(BaseModel):
    objective_scores: list[dict]     # {"id":..,"score":float}
```

---

## 🔀 3 · LangGraph anatomy

### 3.1 High-level graph

```mermaid
flowchart TD
  Start --> LoadCtx
  LoadCtx --> TutorIntro
  TutorIntro -->|summary| PrereqRecap
  TutorIntro -->|quiz|   PrereqQuizBuild
  PrereqQuizBuild --> PrereqQuizAsk
  PrereqQuizAsk --> TutorLoop               %% main teaching loop
  PrereqRecap   --> TutorLoop
  TutorLoop -->|all objectives done| FinalTestBuild
  FinalTestBuild --> FinalTestAsk
  FinalTestAsk --> GradePrep
  GradePrep --> GraderCall
  GraderCall --> TutorWrapUp
  TutorWrapUp --> End
```

### 3.2 Recommended LangGraph node → function mapping

| Graph node        | Python handler                                           | Model / code  |
| ----------------- | -------------------------------------------------------- | ------------- |
| `LoadCtx`         | gather user + node metadata, prepare shared `state` dict | code          |
| `TutorIntro`      | intro + summary/quiz choice prompt                       | fast LLM      |
| `PrereqRecap`     | synthesise ≤200-word recap                               | fast LLM      |
| `PrereqQuizBuild` | **prereq question builder** (≤4 Qs)                      | fast LLM      |
| `PrereqQuizAsk`   | deliver Qs, correct errors inline                        | fast LLM      |
| `TutorLoop`       | iterate objectives, call micro-quiz helper               | fast LLM      |
| `FinalTestBuild`  | build 6-Q (or tutor-chosen mix) test                     | fast LLM      |
| `FinalTestAsk`    | administer test, collect answers                         | fast LLM      |
| `GradePrep`       | pack `test_log` JSON                                     | code          |
| `GraderCall`      | grade via big model (o3)                                 | expensive LLM |
| `TutorWrapUp`     | strengths + next steps greeting                          | fast LLM      |

### 3.3 LangGraph state object

```python
state = {
    "user_id": "...",
    "node": Node(...),
    "completed_objectives": set[str],   # from earlier sessions
    "domain_level": "basic|intermediate|advanced",
    "prereq_questions": list[FinalTestQ],   # filled by PrereqQuizBuild
    "micro_quiz_answers": list[dict],       # formative only
    "test_log": list[dict],                 # final-test Q-A
    "grades": list[dict]                    # filled by GraderCall
}
```

*State is mutated in-place by each node handler; LangGraph automatically passes the dict along the edges.*

---

## 📝 4 · Prompt templates (condensed)

### 4.1 Tutor SYSTEM (shared)

```
You are “Ada”, a concise, no-nonsense tutor.

CONTEXT
• Node: {node.title}
• Objectives: {obj_list}
• Prerequisites: {prereq_list}
• Learner level: {domain_level}
• When citing facts, you MAY append (see {rid}).

RULES
1. Return JSON with keys: eval, feedback, next.
2. Never add praise unless user asks.
3. Follow phase-specific instructions below.
```

### 4.2 Phase-specific snippets

* **Intro** – append:

  ```
  TASK: Introduce the node in ≤2 sentences, then ask the learner:
  “Would you like a short summary of the prerequisites or a quiz on them?”
  ```
* **PrereqQuizBuild** – see full builder prompt in previous answer.
* **TutorLoop** – append instructions to teach current objective, call `generate_micro_quiz`, etc.
* **FinalTestBuild** – default 3 MCQ + 2 short + 1 paraphrase; allow override.
* **TutorWrapUp** – use `grades` to mention strongest and weakest objective; suggest 2 next nodes with edges from KG.

---

## ⚙️ 5 · Implementation pointers

1. **Node handlers** – Write each as an *async* Python function that receives `(state, input_message)` and returns `(next_state, output_message)`; LangGraph will handle routing.
2. **Conditional routing** – In `TutorIntro`, branch on learner’s choice (`summary` vs `quiz`) by inspecting the assistant’s JSON output.
3. **Looping objectives** – Maintain `state["obj_cursor"]`. After each cycle, edge back to `TutorLoop` if objectives remain.
4. **End-session button** – Expose a UI action that sets `state["force_finish"]=True`; LangGraph edge condition checks this to jump to `FinalTestBuild` from anywhere.
5. **Cost guard** – Log tokens per node; optionally short-circuit micro-quiz helper if latency > x s.
6. **Error tolerance** – Wrap each LLM call in retry with exponential back-off; save partial state to Redis or Postgres every time `state` mutates.
7. **Testing** – Unit-test each handler with pre-frozen LLM stubs; integration-test the full graph with `langgraph.testing.SimulatedChat`.

---

## 🚦 6 · Why these choices were made (quick recap)

* **Interactive prerequisite activation** – primes prior knowledge, but caps cognitive load by using ≤4 tailored Qs.
* **Formative micro-quizzes** – immediate feedback loop; *not* used for grading to avoid penalising on-the-spot learning.
* **Single expensive grading call** – keeps billing predictable.
* **No regex guard, no hard timer** – trust the tutor prompt; keep UX flexible.
* **References only as grounding hints** – avoids building a full RAG pipeline today; can be swapped later.

---

### End-of-packet

Paste this block verbatim into any LLM (or hand to an engineer) and they’ll know exactly what we’re building and how to spin it up in LangGraph.
