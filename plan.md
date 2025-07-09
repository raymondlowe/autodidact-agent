# Autodidact – Product Requirements Document

**Version 0.1 ("Topic Mode only")**   <br>**Status:** Final   <br>**Last updated:** 2025‑01‑09

> **Audience** – This document is meant to be consumed by:
>
> * the *implementation‑agent LLM* that will write code, and
> * any future human contributors.
>
> It MUST contain every design decision made in chat, leaving no hidden context.

---

## Table of Contents

1. [Vision](#1-vision)
2. ["Never‑List"](#2-never-list-🚫) – permanent non‑goals
3. [User Story (Topic Mode)](#3-user-story-topic-mode)
4. [Functional Requirements (v0.1)](#4-functional-requirements-v01)
5. [Non‑Functional Requirements](#5-non-functional-requirements)
6. [Data Model](#6-data-model)
7. [Tech Stack (locked‑in)](#7-tech-stack-locked-in)
8. [Security & Privacy](#8-security--privacy)
9. [Implementation Notes for Developers](#9-implementation-notes-for-developers)
10. [Hard‑Won Technical Decisions (summary)](#10-hard-won-technical-decisions-summary)
11. [Incremental Road‑map](#11-incremental-road-map)
12. [Future Feature – PDF Mode (v0.3)](#12-future-feature--pdf-mode-v03)
13. [Future Enhancements](#13-future-enhancements)

---

## 1. Vision

Autodidact turns a plain‑language learning goal into a **30‑minute‑per‑session study plan** plus a **conversational AI tutor**.

**Version 0.1** delivers *Topic Mode* only:

1. **Plan** – learner types e.g. "Learn Bitcoin & Ethereum internals in 8 h."
2. **Clarify** – a short bullet‑question block refines scope.
3. **Syllabus** – OpenAI *Deep Research* returns

   * Markdown report
   * knowledge graph (12‑35 nodes, ≈30 min each)
   * 5–7 learning objectives (LOs) per node
4. **Daily Tutor Loop** (GPT‑4o‑mini)

   * greet/recap → teach → quick‑check
   * grader updates LO mastery ~~& awards XP~~ *(moved to v0.1.5)*.

No servers; everything runs on the learner's computer. PDF ingestion, RAG and citation‑aware tutoring are postponed to v0.3.

---

## 2. Never‑List 🚫

|  #  |  Autodidact will **never** …                                   |  Reason                                        |
| --- | -------------------------------------------------------------- | ---------------------------------------------- |
|  1  |  Run as a **multi‑tenant SaaS** (hosted accounts, cloud auth)  | Always a personal, local tool.                 |
|  2  |  Support **EPUB or other e‑book formats**                      | Scope limited to PDF and free‑form topic text. |
|  3  |  Provide **offline/local LLM support**                         | Always uses learner‑supplied OpenAI API key.   |
|  4  |  Offer **full custom theming / white‑label branding**          | UI look is secondary to agent logic.           |
|  5  |  Ship a **mobile‑first or native mobile app**                  | Desktop browser via Streamlit is sufficient.   |

Any proposal conflicting with this list must be rejected.

---

## 3. User Story (Topic Mode)

1. **Launch** – clone repo → `pip install -r requirements.txt` → `streamlit run app.py`.
2. **API Key** – first‑run modal asks for OpenAI key; stored at `~/.autodidact/.env.json` (chmod 600).
3. **Enter Topic** – text box centred: *“Learn X (target hours optional)”*.
4. **Clarifier** – GPT‑4o‑mini asks ≤5 bullets in one message.  Empty/"idk" answers prompt a warning & re‑ask.
5. **Deep Research** – async job; spinner with progress bar.  Polls `/deep_research/{job_id}` every 3 s.
6. **Workspace** – two‑pane layout:

   * **Left**: collapsible Markdown report.
   * **Right**: force‑directed graph; hover shows summary, LO list, % mastery.
7. **Start Session** – scheduler selects lowest‑mastery unlocked node (ties → learner picks).
8. **Chat phases** (LangGraph DAG):

   * `greet` – (session 1) or `recap` – (later sessions, 2 recall Qs)
   * `teach` – explanation + mid‑question
   * `quick_check` – final Q, returns JSON LO scores.
9. **Grader** – async pass; updates `lo_mastery`, `node_mastery`; awards XP = minutes × k.
10. **Graph recolours** → learner done for the day.

---

## 4. Functional Requirements (v 0.1)

### 4.1 Landing & Clarifier

* Widgets: `st.text_input` (topic), `st.number_input` (optional hours).
* Clarifier agent prompt:
  *If the topic is ambiguous, ask targeted Qs; else return JSON `{need_clarification:false}`.*
* Skip‑protection loop.

### 4.2 Deep Research Job

* POST to OpenAI Deep Research (`async=true`).
* Store outputs under `~/.autodidact/projects/<project_id>/`:

  * `report.md`, `graph.json`, raw `deep_research_response.json`.
* ~~Polls `/deep_research/{job_id}` every 3 s with progress bar~~ *(moved to v0.1.5)* – Simple spinner for v0.1.

### 4.3 Graph & Report Viewer

* ~~Streamlit Component (`react‑force‑graph`)~~ **v0.1: Use `st.graphviz_chart`** *(react‑force‑graph moved to v0.1.5)*

  * Node colour: white → green via linear scale of `mastery 0–1`.
  * ~~Hover pop‑over: summary, LO list with mini‑bar (▁▂▃▅█).~~ *(moved to v0.1.5)* – Basic node labels for v0.1.
* `st.markdown(report_md, unsafe_allow_html=True)` inside `st.expander("Report")`.

### 4.4 Scheduler

* Query:

  ```sql
  SELECT node_id FROM Node
  WHERE prerequisites_met = 1
  ORDER BY node_mastery ASC
  LIMIT 2;
  ```
* If 2 rows: Streamlit `st.radio("Choose topic", …)`.

### 4.5 Tutor Session (LangGraph)

* **Graph definition**

  ```python
  g = StateGraph()
  g.add_node("greet", greet_node)
  g.add_node("recap", recap_node)      # cond
  g.add_node("teach", teach_node)
  g.add_node("quick", quick_node)
  g.add_node("grade", grade_node)      # sync for v0.1
  g.add_edge("greet", "recap", cond=lambda s: s["has_prev"])
  g.add_edge("greet", "teach", cond=lambda s: not s["has_prev"])
  g.add_edge("recap", "teach")
  g.add_edge("teach", "quick")
  g.add_edge("quick", "grade")
  compiled = g.compile()
  ```
* Each node function is **pure** (dict → dict) for testability.
* Streaming: `for chunk in compiled.stream(state): st.write_stream(chunk)`.

### 4.6 Grader

* Prompt uses the same context as tutor (no privileged info).\*  Returns

  ```json
  {"lo_scores":{"lo1":1.0,"lo2":0.7}}
  ```
* Update with ~~EWMA `new = 0.5*old + 0.5*score`~~ **simple averaging for v0.1**.
* ~~XP toast when async job finishes.~~ *(moved to v0.1.5)*

### 4.7 Autosave

* After every turn append to `Transcript`.
* ~~Background task uses `aiosqlite` connection pool.~~ **Sync SQLite operations for v0.1**.

### 4.8 Voice Input ~~(optional)~~ *(moved to v0.1.5)*

* ~~`st_webrtc` recorder; on stop → temp WAV → OpenAI Whisper; pre‑fill chat input.~~

---

## 5. Non‑Functional Requirements

| Metric                    | Target             |
| ------------------------- | ------------------ |
| Clarifier + DR initiate   | ≤ 2 min (95‑pct)   |
| Deep Research (DR) step   | ≤ 1 hour           |
| Tutor first‑token latency | ≤ 3 s              |
| Memory footprint          | ≤ 1 GB topic mode  |
| Local install             | ≤ 5 min, no Docker |
| Cost / 30‑min session     | ≤ \$0.05           |

---

## 6. Data Model

```mermaid
erDiagram
    Project ||--o{ Node : contains
    Node ||--o{ LO : has
    Project ||--o{ Transcript : has

    Project {
      uuid id PK
      text topic
      text report_path
      timestamp created_at
    }

    Node {
      uuid id PK
      uuid project_id FK
      text label
      text summary
      float mastery default 0
      int page_start 0   -- reserved
      int page_end 0     -- reserved
      bool rag_flag false
    }

    LO {
      uuid id PK
      uuid node_id FK
      text description
      float mastery default 0
    }

    Transcript {
      uuid session_id
      int  turn_idx
      text role
      text content
      timestamp created_at
    }
```

Vector index (future): LanceDB table `Chunk(id, node_id, text, embedding)`.

---

## 7. Tech Stack (locked‑in)

| Layer                 | Library / service                   | Notes                             |
| --------------------- | ----------------------------------- | --------------------------------- |
| **UI**                | Streamlit ≥ 1.34                    | Single script, hot‑reload.        |
| **Custom components** | ~~`react‑force‑graph`~~ *(v0.1.5)*, PDF.js (v 0.3) | ~~via Streamlit Components.~~ **v0.1: st.graphviz_chart**         |
| **LLM orchestration** | LangGraph (StateGraph)              | DAG with streaming events.        |
| **LLM provider**      | OpenAI API, model `gpt-4o-mini`     | Clarifier, tutor, grader.         |
| **Deep Research**     | OpenAI Deep Research beta endpoint  | ~~Async~~ **Sync job for v0.1**.                        |
| **Background tasks**  | ~~`asyncio.create_task`~~ *(v0.1.5)*              | **Sync operations for v0.1**.        |
| **DB**                | SQLite ~~+ SQLModel~~ *(v0.1.5)*                  | **Direct SQL for v0.1**. File under `~/.autodidact/`.      |
| **Vector DB** (later) | LanceDB                             | Stores embeddings in Arrow files. |
| **Voice**             | ~~`streamlit-webrtc` + Whisper API~~ *(v0.1.5)*   | ~~Optional.~~                         |

---

## 8. Security & Privacy

* No auth; everything local.
* One‑time consent banner: *“Your prompts & chat are sent to OpenAI for processing.”*
* API key stored locally with filesystem permissions 600.

---

## 9. Implementation Notes for Developers

1. **File layout**

```bash
autodidact/
├── app.py               # Streamlit entry
├── backend/
    ├── jobs.py            # clarifier, deep_research, tutor, grader nodes
    ├── db.py              # SQLModel setup
    ├── graph.py           # LangGraph compile
├── components/
    ├── force_graph/       # React bundle
        ├── (pdf_viewer v0.3)
```

2. **State keys** – keep all Streamlit state in `st.session_state` (`project_id`, `graph`, `transcript`, `job_progress`).
3. **Error surfacing** – any exception inside a LangGraph node should be caught, written to `Project.error_log`, and shown via `st.error`.
4. **Unit tests** – test every node in isolation with OpenAI stub (return canned text). pytest markers: `@pytest.mark.asyncio`.
5. **Skip‑protection** – regex check for empty / idk answers.
6. **Autosave** – flush transcript every turn to avoid losing data on browser refresh.
7. **Hot reload** – Streamlit reruns script on every input; put job polling inside `st.experimental_rerun()` safe blocks.

---

## 10. Hard‑Won Technical Decisions (summary)

1. **Streamlit** chosen over Next.js for zero build & local simplicity.
2. **LangGraph** adopted early to practise agent orchestration and to ease future branching.
3. **Single‑process asyncio** instead of Celery/Redis – fits single‑user offline use.
4. **XP formula** simple time‑based; no social leaderboard.
5. **Graph read‑only in v0.1**; edits added in v0.2.
6. **PDF support deferred to v0.3** but schema fields reserved.
7. **Never‑list** enshrined (§2) to prevent scope creep.

---

## 11. Incremental Road‑map

| Version | Scope | Target effort |
|---------|-------|---------------|
| **0.1** | Topic Mode (simplified - sync operations, basic UI) | 2 weeks |
| **0.1.5** | Enhanced UX (async ops, React graph, voice, XP, progress bars) | +1 week |
| **0.2** | Graph merge/split UI & spaced‑repetition queue | +2 weeks |
| **0.3** | PDF Mode (see §12) | +3 weeks |

---

## 12. Future Feature – PDF Mode (v0.3)

### 12.1 Scope recap
* Upload PDF   → extract TOC   → Deep Research on TOC. 
* Tutor uses chunk‑level RAG; answers cite `(p. NN)`. 
* Right‑hand PDF viewer jumps to cited page.

### 12.2 Additional nodes
| Node | Description | Key libs |
|------|-------------|----------|
| `outline_pdf` | Extract `/Outlines`; fallback Gemini Vision first 20 pages. | PyMuPDF, `google-generativeai` |
| `chunk_embed` | Chunk by TOC leaf, 1 000 tokens / 100 overlap; embed & save. | PyMuPDF, LanceDB |
| `retrieve_ctx` | Lookup top‑k chunks for node; feed tutor prompt. | LanceDB |

### 12.3 Citation jump
* Tutor/report emit `{{page:42}}` tokens.
* Regex in Streamlit converts to `<a>` with JS `data-page`.
* PDF.js component listens and calls `goToPage(page)`.

### 12.4 Out of scope
* OCR of scanned PDFs, diagrams, multi‑PDF curricula, DRM’d content.

---

## 13. Future Enhancements

This section documents features and architectural improvements that were considered but deferred from v0.1 for simplicity. These enhancements are planned for future versions to improve user experience and system capabilities.

### 13.1 Version 0.1.5 Enhancements

The following features will be added in v0.1.5 to enhance the user experience without changing core functionality:

#### Async Everything
- **Async grading**: Make the grader asynchronous to avoid blocking the UI during score calculation
- **aiosqlite connection pool**: Implement connection pooling for better database performance
- **Background tasks with asyncio.create_task**: Enable true background processing for long-running operations
- **Rationale**: While not needed for single-user v0.1, these prepare the architecture for potential future multi-session support

#### React Force-Graph Component  
- **Interactive graph visualization**: Replace st.graphviz_chart with react-force-graph for better interactivity
- **Hover effects**: Show node summary, LO list with progress mini-bars (▁▂▃▅█) on hover
- **Smooth animations**: Animate node color changes as mastery increases
- **Rationale**: Provides a more engaging and informative learning progress visualization

#### SQLModel Abstraction
- **ORM layer**: Add SQLModel for type-safe database operations
- **Migration support**: Enable schema evolution for future versions
- **Rationale**: Reduces SQL injection risks and makes the codebase more maintainable

#### Voice Input
- **Voice-to-text**: Implement st_webrtc recorder with OpenAI Whisper API
- **Hands-free interaction**: Allow learners to respond to tutor questions verbally
- **Rationale**: Improves accessibility and enables learning while doing other activities

#### XP System and Gamification
- **Experience points**: Award XP based on session time and performance
- **Achievement toasts**: Show progress notifications when milestones are reached
- **Rationale**: Increases learner motivation and engagement through game-like elements

#### Progress Bars for Deep Research
- **Real-time updates**: Poll Deep Research API every 3 seconds
- **Visual feedback**: Show estimated time remaining and current processing stage
- **Rationale**: Reduces user anxiety during long wait times

### 13.2 Future Architectural Considerations

#### Performance Optimizations
- Caching layer for repeated API calls
- Incremental graph updates instead of full redraws
- Lazy loading for large knowledge graphs

#### Enhanced Learning Features  
- Adaptive difficulty adjustment based on performance
- Multiple learning paths through the same material
- Integration with external learning resources

#### Developer Experience
- Plugin architecture for custom node types
- Export/import functionality for sharing curricula
- Analytics dashboard for learning insights

---

**End of PRD – ready for implementation.**
