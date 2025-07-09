"""
LangGraph module for Autodidact
Defines the tutor session state graph and flow
"""

from typing import TypedDict, List, Dict, Optional, Annotated
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
import json
import uuid
from datetime import datetime

from backend.db import (
    get_node_with_objectives, 
    save_transcript,
    update_mastery,
    get_db_connection
)
from utils.config import CHAT_MODEL, load_api_key
from openai import OpenAI


class TutorState(TypedDict):
    """State definition for tutor sessions"""
    session_id: str
    node_id: str
    turn_count: int
    has_previous_session: bool
    messages: Annotated[List[Dict], add_messages]
    learning_objectives: List[Dict]
    lo_scores: Dict[str, float]
    current_phase: str
    node_info: Dict
    project_id: str


def get_tutor_prompt(node_info: Dict) -> str:
    """Get the base tutor prompt with node context"""
    return f"""You are an expert tutor teaching about: {node_info['label']}

Summary: {node_info['summary']}

Your role is to help the student master the following learning objectives:
{format_learning_objectives(node_info['learning_objectives'])}

Guidelines:
- Be conversational and encouraging
- Use examples and analogies
- Check understanding frequently
- Adapt to the student's level
- Keep responses concise but clear
- Focus on one concept at a time
"""


def format_learning_objectives(objectives: List[Dict]) -> str:
    """Format learning objectives for display"""
    return "\n".join([f"{i+1}. {obj['description']}" for i, obj in enumerate(objectives)])


def greet_node(state: TutorState) -> TutorState:
    """Welcome message for first session or returning student"""
    client = OpenAI(api_key=load_api_key())
    
    if state["has_previous_session"]:
        # Get previous mastery info
        with get_db_connection() as conn:
            cursor = conn.execute("""
                SELECT COUNT(*) as completed_nodes 
                FROM node 
                WHERE project_id = ? AND mastery >= 0.7
            """, (state["project_id"],))
            completed = cursor.fetchone()[0]
        
        greeting = f"""Welcome back! Great to see you continuing your learning journey.

You've already mastered {completed} concepts. Today we'll be learning about **{state['node_info']['label']}**.

{state['node_info']['summary']}

Ready to dive in?"""
    else:
        greeting = f"""Welcome to your first Autodidact learning session! I'm excited to help you learn.

Today we'll be exploring **{state['node_info']['label']}**.

{state['node_info']['summary']}

I'll guide you through this topic step by step, and we'll have some interactive discussions along the way. 

Let's get started! Are you ready?"""
    
    # Add greeting message
    state["messages"].append({
        "role": "assistant",
        "content": greeting
    })
    
    # Save to transcript
    save_transcript(state["session_id"], state["turn_count"], "assistant", greeting)
    state["turn_count"] += 1
    
    return state


def recap_node(state: TutorState) -> TutorState:
    """Generate 2 recall questions from previous sessions"""
    client = OpenAI(api_key=load_api_key())
    
    # Get previous session content from database
    with get_db_connection() as conn:
        # Get recently learned nodes
        cursor = conn.execute("""
            SELECT n.label, n.summary, lo.description
            FROM node n
            JOIN learning_objective lo ON lo.node_id = n.id
            WHERE n.project_id = ? 
            AND n.mastery > 0.3 
            AND n.id != ?
            ORDER BY n.mastery DESC
            LIMIT 2
        """, (state["project_id"], state["node_id"]))
        
        previous_content = cursor.fetchall()
    
    if not previous_content:
        # Skip recap if no previous content
        return state
    
    # Generate recall questions
    recap_prompt = f"""Generate 2 quick recall questions based on previously learned concepts.
    
Previous concepts:
{chr(10).join([f"- {row[0]}: {row[2]}" for row in previous_content])}

Current topic: {state['node_info']['label']}

Create 2 short questions that:
1. Test recall of key concepts
2. Connect to what we're about to learn
3. Are answerable in 1-2 sentences

Format as a friendly conversation starter."""
    
    response = client.chat.completions.create(
        model=CHAT_MODEL,
        messages=[
            {"role": "system", "content": get_tutor_prompt(state["node_info"])},
            {"role": "user", "content": recap_prompt}
        ],
        temperature=0.7
    )
    
    recap_message = response.choices[0].message.content
    
    # Add to messages
    state["messages"].append({
        "role": "assistant",
        "content": recap_message
    })
    
    # Save to transcript
    save_transcript(state["session_id"], state["turn_count"], "assistant", recap_message)
    state["turn_count"] += 1
    
    return state


def teach_node(state: TutorState) -> TutorState:
    """Main teaching phase with interactive explanations"""
    client = OpenAI(api_key=load_api_key())
    
    # Get learning objectives
    objectives = state["node_info"]["learning_objectives"]
    
    # Create teaching prompt
    teaching_prompt = f"""Now let's learn about {state['node_info']['label']}.

Learning objectives for this session:
{format_learning_objectives(objectives)}

Please:
1. Start with an engaging introduction to the topic
2. Explain the first 2-3 learning objectives clearly
3. Use examples or analogies
4. End with a comprehension check question

Keep it conversational and under 300 words."""
    
    # Check if there's user input to respond to
    last_message = state["messages"][-1] if state["messages"] else None
    if last_message and last_message["role"] == "user":
        # Respond to user and continue teaching
        messages = [
            {"role": "system", "content": get_tutor_prompt(state["node_info"])},
            {"role": "assistant", "content": state["messages"][-2]["content"] if len(state["messages"]) > 1 else ""},
            {"role": "user", "content": last_message["content"]},
            {"role": "user", "content": "Please continue teaching based on my response."}
        ]
    else:
        # Initial teaching
        messages = [
            {"role": "system", "content": get_tutor_prompt(state["node_info"])},
            {"role": "user", "content": teaching_prompt}
        ]
    
    response = client.chat.completions.create(
        model=CHAT_MODEL,
        messages=messages,
        temperature=0.7
    )
    
    teaching_content = response.choices[0].message.content
    
    # Add to messages
    state["messages"].append({
        "role": "assistant",
        "content": teaching_content
    })
    
    # Save to transcript
    save_transcript(state["session_id"], state["turn_count"], "assistant", teaching_content)
    state["turn_count"] += 1
    
    return state


def quick_check_node(state: TutorState) -> TutorState:
    """Final assessment question covering key concepts"""
    client = OpenAI(api_key=load_api_key())
    
    # Create assessment prompt
    assessment_prompt = f"""We're near the end of our session on {state['node_info']['label']}.

Based on what we've discussed, create one comprehensive question that:
1. Tests understanding of 2-3 learning objectives
2. Requires application, not just recall
3. Can be answered in 2-3 sentences
4. Connects concepts together

Learning objectives covered:
{format_learning_objectives(state['node_info']['learning_objectives'])}

Make it encouraging and frame it as "Let's see what you've learned!" """
    
    response = client.chat.completions.create(
        model=CHAT_MODEL,
        messages=[
            {"role": "system", "content": get_tutor_prompt(state["node_info"])},
            {"role": "user", "content": assessment_prompt}
        ],
        temperature=0.7
    )
    
    assessment = response.choices[0].message.content
    
    # Add to messages
    state["messages"].append({
        "role": "assistant",
        "content": assessment
    })
    
    # Save to transcript
    save_transcript(state["session_id"], state["turn_count"], "assistant", assessment)
    state["turn_count"] += 1
    
    return state


def grade_node(state: TutorState) -> TutorState:
    """Grade the student's understanding of learning objectives"""
    client = OpenAI(api_key=load_api_key())
    
    # Format transcript for grading
    transcript = format_transcript(state["messages"])
    
    grading_prompt = f"""Based on the teaching session transcript and the student's responses,
evaluate their mastery of each learning objective.

Learning objectives for this node:
{format_learning_objectives(state['node_info']['learning_objectives'])}

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

Return ONLY valid JSON in this exact format:
{{"lo_scores": {{{', '.join([f'"{obj["id"]}": 0.0' for obj in state['node_info']['learning_objectives']])}}}}}

Important: Use the same context as the tutor (no privileged information).
Base scores only on what the student demonstrated in this session."""
    
    response = client.chat.completions.create(
        model=CHAT_MODEL,
        messages=[
            {"role": "system", "content": "You are an objective grader evaluating student understanding."},
            {"role": "user", "content": grading_prompt}
        ],
        response_format={"type": "json_object"},
        temperature=0.3
    )
    
    try:
        # Parse scores
        scores = json.loads(response.choices[0].message.content)
        state["lo_scores"] = scores.get("lo_scores", {})
        
        # Update database with new mastery scores
        update_mastery(state["node_id"], state["lo_scores"])
        
        # Generate feedback message
        avg_score = sum(state["lo_scores"].values()) / len(state["lo_scores"]) if state["lo_scores"] else 0
        
        if avg_score >= 0.7:
            feedback = f"""🎉 Excellent work! You've demonstrated a strong understanding of {state['node_info']['label']}.

Your mastery level: {int(avg_score * 100)}%

You're ready to move on to the next topic. Keep up the great work!"""
        elif avg_score >= 0.5:
            feedback = f"""Good progress! You're developing a solid understanding of {state['node_info']['label']}.

Your mastery level: {int(avg_score * 100)}%

You might want to review this topic once more before moving on, but you're on the right track!"""
        else:
            feedback = f"""You're making progress with {state['node_info']['label']}, but there's room for improvement.

Your mastery level: {int(avg_score * 100)}%

I recommend reviewing this topic again to strengthen your understanding. Don't worry - learning takes time!"""
        
        # Add feedback
        state["messages"].append({
            "role": "assistant",
            "content": feedback
        })
        
        # Save to transcript
        save_transcript(state["session_id"], state["turn_count"], "assistant", feedback)
        state["turn_count"] += 1
        
    except Exception as e:
        # Fallback if grading fails
        state["lo_scores"] = {obj["id"]: 0.5 for obj in state["node_info"]["learning_objectives"]}
        update_mastery(state["node_id"], state["lo_scores"])
    
    return state


def format_transcript(messages: List[Dict]) -> str:
    """Format messages into a readable transcript"""
    transcript = []
    for msg in messages:
        role = "Tutor" if msg["role"] == "assistant" else "Student"
        transcript.append(f"{role}: {msg['content']}")
    return "\n\n".join(transcript)


def should_recap(state: TutorState) -> str:
    """Conditional edge function to determine if recap is needed"""
    if state.get("has_previous_session", False):
        return "recap"
    return "teach"


def should_continue_teaching(state: TutorState) -> str:
    """Determine if we should continue teaching or move to assessment"""
    # Count teaching interactions
    teaching_turns = sum(1 for msg in state["messages"] if msg["role"] == "user")
    
    # After 2-3 exchanges, move to quick check
    if teaching_turns >= 2:
        return "quick_check"
    return "teach"


def create_tutor_graph():
    """Create and compile the tutor state graph"""
    # Create the graph with state schema
    workflow = StateGraph(TutorState)
    
    # Add all nodes
    workflow.add_node("greet", greet_node)
    workflow.add_node("recap", recap_node)
    workflow.add_node("teach", teach_node)
    workflow.add_node("quick_check", quick_check_node)
    workflow.add_node("grade", grade_node)
    
    # Set entry point
    workflow.set_entry_point("greet")
    
    # Add edges
    workflow.add_conditional_edges(
        "greet",
        should_recap,
        {
            "recap": "recap",
            "teach": "teach"
        }
    )
    
    workflow.add_edge("recap", "teach")
    
    workflow.add_conditional_edges(
        "teach",
        should_continue_teaching,
        {
            "teach": "teach",
            "quick_check": "quick_check"
        }
    )
    
    workflow.add_edge("quick_check", "grade")
    workflow.add_edge("grade", END)
    
    # Compile the graph
    return workflow.compile()


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