"""
LangGraph module for Autodidact
Defines the tutor session state graph and flow
"""

from typing import TypedDict, List, Dict, Optional
from langgraph.graph import StateGraph, END
from backend.jobs import (
    greet_node, 
    recap_node, 
    teach_node, 
    quick_check_node, 
    grade_node
)


class TutorState(TypedDict):
    """State definition for tutor sessions"""
    session_id: str
    node_id: str
    turn_count: int
    has_previous_session: bool
    messages: List[Dict]
    learning_objectives: List[Dict]
    lo_scores: Dict[str, float]
    current_phase: str


def should_recap(state: TutorState) -> str:
    """Conditional edge function to determine if recap is needed"""
    if state.get("has_previous_session", False):
        return "recap"
    return "teach"


def create_tutor_graph():
    """Create and compile the tutor session graph"""
    # Create the graph with TutorState
    graph = StateGraph(TutorState)
    
    # Add nodes
    graph.add_node("greet", greet_node)
    graph.add_node("recap", recap_node)
    graph.add_node("teach", teach_node)
    graph.add_node("quick_check", quick_check_node)
    graph.add_node("grade", grade_node)
    
    # Set entry point
    graph.set_entry_point("greet")
    
    # Add edges
    graph.add_conditional_edges(
        "greet",
        should_recap,
        {
            "recap": "recap",
            "teach": "teach"
        }
    )
    
    graph.add_edge("recap", "teach")
    graph.add_edge("teach", "quick_check")
    graph.add_edge("quick_check", "grade")
    graph.add_edge("grade", END)
    
    # Compile the graph
    return graph.compile()


def initialize_tutor_state(
    session_id: str,
    node_id: str,
    has_previous_session: bool,
    learning_objectives: List[Dict]
) -> TutorState:
    """Initialize the state for a new tutor session"""
    return TutorState(
        session_id=session_id,
        node_id=node_id,
        turn_count=0,
        has_previous_session=has_previous_session,
        messages=[],
        learning_objectives=learning_objectives,
        lo_scores={},
        current_phase="greet"
    ) 