# Tutor System Diagrams

This directory contains Mermaid diagrams documenting the LangGraph implementation of the Autodidact v0.4 tutor system.

## Diagrams

### 1. Complete Graph Flow (`1_complete_graph_flow.mmd`)
Shows all 11 nodes and their connections in the LangGraph:
- Entry point: `load_context`
- Conditional edges: `should_do_prerequisites` and `should_continue_teaching`
- All possible paths through the system
- Color-coded nodes for easy identification

### 2. Detailed Node Descriptions (`2_detailed_node_descriptions.mmd`)
Provides detailed information about what each node does:
- Specific responsibilities of each node
- Data processing and state updates
- User interactions handled
- Model selections (e.g., GPT-4o for grading)

### 3. High-Level Session Phases (`3_high_level_session_phases.mmd`)
Conceptual flow through major phases:
- Prerequisites → Teaching → Testing → Grading → Wrap-up
- Shows optional paths (prerequisites can be skipped)
- Early exit capability from teaching to testing

### 4. Teaching Loop State Machine (`4_teaching_loop_state_machine.mmd`)
Details the six-state machine within `tutor_loop`:
- `probe_ask` → `probe_respond`
- `explain_present` → `explain_respond`
- `quiz_ask` → `quiz_evaluate`
- Shows how objectives are cycled through

### 5. State Diagram with Wait Points (`5_state_diagram_with_wait_points.mmd`)
Shows where the graph pauses for user input:
- Prerequisite choice waiting
- Teaching phase wait points (after probe, explain, quiz)
- Final test answer collection
- Critical for understanding the interactive nature

## How to View

These are Mermaid diagrams that can be viewed in:
1. **GitHub**: Will render automatically in the web interface
2. **VS Code**: Install the Mermaid extension
3. **Online**: Copy content to [mermaid.live](https://mermaid.live)
4. **Markdown**: Include in any Markdown file with triple backticks: ```mermaid

## Implementation Details

The actual implementation is in `/backend/graph_v04.py` with:
- 11 nodes total
- 2 conditional edge functions
- State machine for teaching loop
- Comprehensive error handling
- Session logging throughout

## Key Features

- **Entry Point**: Always starts at `load_context`
- **Conditional Routing**: Based on prerequisites and teaching progress
- **State Machine**: Explicit phases prevent bugs and ensure proper flow
- **Graceful Exits**: Supports early termination with proper cleanup
- **Smart Grading**: LLM-based answer parsing and grading with fallbacks 