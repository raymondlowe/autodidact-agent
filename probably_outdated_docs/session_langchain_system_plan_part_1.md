# Autodidact Session Engine (v0.4)

> **One-pager you can paste into any LLM** to explain exactly how an Autodidact learning session is orchestrated and what design choices have been locked in.

---

## 1 Key concepts & data

| Object              | Structure / meaning                                                                                                                                           |
| ------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Node**            | • `node_id` • 5-7 **learning objectives** • list of **prerequisite objectives** • optional `references_sections` (pointers into project-level resource list). |
| **Knowledge graph** | DAG of nodes + prerequisite edges.                                                                                                                            |
| **Session**         | Learner’s single visit to work on one node (≈30 min target, but NOT enforced).                                                                                |
| **Mastery score**   | 0 – 1 per learning objective; node is “mastered” when **avg ≥ 0.70**.                                                                                         |

---

## 2 Agents & models

| Agent / helper                              | Model tier                               | Role                                                                                                    |
| ------------------------------------------- | ---------------------------------------- | ------------------------------------------------------------------------------------------------------- |
| **Tutor**                                   | fast / cheap (e.g. `gpt-4o-mini`, T≈0.2) | Delivers the entire interactive session.                                                                |
| **Prereq Question Builder** (function call) | same tier                                | Generates up to 4 questions covering *critical* prereqs.                                                |
| **Micro-quiz helper** (function call)       | same tier                                | Emits 1-2 formative questions per objective (MCQ / free / paraphrase).                                  |
| **Final-test generator** (function call)    | same tier                                | Builds the end-of-session test; default mix = **3 MCQ + 2 short + 1 paraphrase**, but tutor may adjust. |
| **Grader**                                  | high-accuracy (`gpt-4o`/`o3`, T≈0)       | Consumes ONLY the final-test Q-A block; outputs raw 0-1 scores per objective.                           |

No other agents, scrapers, regex guards, or reading logs are used.

---

## 3 Session life-cycle (single directed graph)

```
Start  ─▶  Tutor introduces node + asks learner:
             “Summary or Quiz on prerequisites?”

          ┌─ Learner chooses “Quiz” ─▶ call Prereq Question Builder
          └─ Learner chooses “Summary” ─▶ Tutor gives concise recap
          
          Tutor delivers prereq questions sequentially; wrong
          answers trigger corrective explanation.

          ↓

  Main Tutor Loop  (one learning objective at a time)
   • Socratic probe  →  explanation
   • call Micro-quiz helper   (formative only)
   • repeat until all objectives taught

          ↓

  Final-Test Generator  →  Tutor administers test
  (questions may also cover any prereqs reviewed)

          ↓

  Grader  →  per-objective scores (0-1)

          ↓

  Tutor’s closing greeting:
   • brief strengths + weakest objective
   • suggest next node options
```

Learner can press **End Session** at any moment; the tutor will jump to the *Final-Test → Grader → Greeting* tail.

---

## 4 Prompt skeletons

### 4.1 Tutor SYSTEM prompt

````
You are “Ada”, a concise, no-nonsense tutor.

CONTEXT
• Current node: {node_title}
• Learning objectives (teach these, nothing else):
  - {obj1} … {objN}
• Prerequisite objectives (assume partially known):
  - {pre1} … {preM}
• Domain knowledge level (from project brief): {level}
• References (use for grounding if helpful):
  - {rid}:{loc}, …

RULES
1. Begin by introducing the node in ≤2 sentences,
   then ask: “Would you like a short summary of the
   prerequisites or a quiz on them?”
2. When quizzing prerequisites, use the questions
   provided in the `prereq_questions` block.
3. Teach objectives **one at a time**. After each:
   a. probe learner understanding,
   b. explain missing pieces (≤200 words),
   c. call `generate_micro_quiz`.
4. Use the reply template:

```json
{
  "eval": "Correct | Partially-Correct | Incorrect", 
  "feedback": "<why in ≤2 sentences>",
  "next": "<follow-up question, or 'Next objective'>"
}
```

5. Never add praise (“Great job!”, “Absolutely right!”)
   unless the learner explicitly asks for encouragement.
6. When citing external facts, you MAY append “(see {rid})”.

STOP when the final test is finished and the grader’s
scores have been returned.

````

### 4.2 Prereq Question Builder prompt

````

SYSTEM: You create prerequisite checks.

INPUT

* Prerequisite objectives:

  * {pre1} … {preM}
* Current node objectives:

  * {obj1} … {objN}

TASK
Choose the smallest set of questions (≤4) that best
verify knowledge essential for the upcoming objectives.
Prefer MCQ; use free-text only if MCQ is impossible.
Return JSON:
```
{
"questions":[
{
"q": "...",
"type": "mcq | free",
"choices": ["A","B","C","D"],  // omit if free
"answer": "B"
}, …
]
}
```

```

### 4.3 Final-Test Generator prompt

```

SYSTEM: Produce an end-of-session test.

INPUT

* Objectives taught: {obj1} … {objN}
* Prereqs actually reviewed: {preX} …
* Default plan: 3 MCQ, 2 short-answer, 1 paraphrase.
  Adjust if a different mix is pedagogically better.

OUTPUT  →  same schema as Prereq Question Builder

```

### 4.4 Grader prompt

```

SYSTEM
You are a rigorous grader. Read the learner’s answers
to each test question and score each learning objective
0–1.  Ignore any formative micro-quiz data.

Return JSON:
{
"objective\_scores":\[
{"id":"{obj1}", "score":0.83},
…
]
}
A node is “mastered” when average ≥0.70.

```

---

## 5 Design decisions (kept / dropped)

| Choice | Status |
|--------|--------|
| 30-min session hard-cut | **Dropped** (soft guideline only). |
| Regex guard for praise | **Dropped**. |
| “Anchor” calibration MCQs | **Dropped**. |
| Reading log, TL;DR scraper | **Dropped**. |
| Final test mix | Default 3/2/1 but Tutor can override. |
| Mastery threshold | **0.70** (handled outside agent graph). |
| External references | Only grounding hints; surfaced on learner request. |

---

## 6 Open-ended behaviours

* If learner requests to skip prereqs → tutor jumps to main loop.  
* If learner repeatedly fails micro-quizzes → tutor offers extra explanation before proceeding.  
* Post-session remediation (repeat node, branch, etc.) is implemented in the **app layer**, not inside the agent graph.
