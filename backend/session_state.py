"""
Session state definitions for Autodidact v0.4 session engine
Defines the state that flows through the LangGraph nodes
"""

from typing import TypedDict, List, Dict, Set, Optional, Literal
from pydantic import BaseModel
from datetime import datetime


class Objective(BaseModel):
    """Represents a learning objective"""
    id: str
    description: str
    mastery: float
    node_id: Optional[str] = None  # Which node this objective belongs to
    
    def is_mastered(self) -> bool:
        """Check if objective is mastered (>= 0.7)"""
        return self.mastery >= 0.7


class QuizQuestion(BaseModel):
    """Represents a quiz question"""
    q: str  # The question text
    type: Literal["mcq", "free", "short", "paraphrase"]
    choices: Optional[List[str]] = None  # For MCQ only
    answer: str  # Correct answer or expected answer pattern
    objective_ids: List[str]  # Which objectives this question tests
    
    def format_for_display(self) -> str:
        """Format question for display to user"""
        if self.type == "mcq" and self.choices:
            choices_text = "\n".join([f"{chr(65+i)}. {choice}" for i, choice in enumerate(self.choices)])
            return f"{self.q}\n\n{choices_text}"
        return self.q


class TestAnswer(BaseModel):
    """Represents a user's answer to a test question"""
    question_id: int  # Index in the test
    question: QuizQuestion
    user_answer: str
    timestamp: str


class SessionState(TypedDict):
    """Complete state for a learning session"""
    
    # Core identifiers
    session_id: str
    project_id: str
    node_id: str
    node_original_id: str  # Original ID from deep research graph
    
    # Node content
    node_title: str
    resources: List[Dict]  # Project-level resources
    references_sections: List[Dict]  # Node-specific references
    
    # Objectives tracking
    all_objectives: List[Objective]  # All objectives for this node
    objectives_to_teach: List[Objective]  # Filtered by mastery < 0.7
    objectives_already_known: List[Objective]  # mastery >= 0.7
    prerequisite_objectives: List[Objective]  # From prerequisite nodes
    completed_objectives: Set[str]  # IDs of objectives taught this session
    
    # User interaction
    current_phase: str  # Which phase we're in
    messages: List[Dict]  # Chat history [{role, content}]
    user_chose_quiz: Optional[bool]  # For prereq choice
    
    # Quiz tracking
    prereq_quiz_questions: List[QuizQuestion]
    prereq_quiz_answers: List[TestAnswer]  # User's prereq quiz answers
    micro_quiz_history: List[Dict]  # Formative assessments
    final_test_questions: List[QuizQuestion]
    final_test_answers: List[TestAnswer]
    
    # Grading
    objective_scores: Dict[str, float]  # Final scores per objective ID
    
    # Control flags
    force_end_session: bool  # User requested early end
    current_objective_index: int  # Which objective we're teaching
    current_objective_phase: str  # "probe", "explain", "quiz", or "done"
    objective_exchanges: int  # Track exchanges within current objective
    
    # Metadata
    domain_level: str  # "basic", "intermediate", or "advanced"
    turn_count: int
    start_time: str
    end_time: Optional[str]


# Helper functions for state management

def create_initial_state(
    session_id: str,
    project_id: str, 
    node_id: str,
    domain_level: str = "intermediate"
) -> Dict:
    """Create an initial session state"""
    return {
        # Core identifiers
        "session_id": session_id,
        "project_id": project_id,
        "node_id": node_id,
        "node_original_id": "",  # Will be populated by load_context
        
        # Node content
        "node_title": "",
        "resources": [],
        "references_sections": [],
        
        # Objectives tracking
        "all_objectives": [],
        "objectives_to_teach": [],
        "objectives_already_known": [],
        "prerequisite_objectives": [],
        "completed_objectives": set(),
        
        # User interaction
        "current_phase": "loading",
        "messages": [],
        "user_chose_quiz": None,
        
        # Quiz tracking
        "prereq_quiz_questions": [],
        "prereq_quiz_answers": [],
        "micro_quiz_history": [],
        "final_test_questions": [],
        "final_test_answers": [],
        
        # Grading
        "objective_scores": {},
        
        # Control flags
        "force_end_session": False,
        "current_objective_index": 0,
        "current_objective_phase": "probe",
        "objective_exchanges": 0,
        
        # Metadata
        "domain_level": domain_level,
        "turn_count": 0,
        "start_time": datetime.now().isoformat(),
        "end_time": None
    }


def get_current_objective(state: SessionState) -> Optional[Objective]:
    """Get the current objective being taught"""
    if state["current_objective_index"] < len(state["objectives_to_teach"]):
        return state["objectives_to_teach"][state["current_objective_index"]]
    return None


def has_prerequisites(state: SessionState) -> bool:
    """Check if this node has any prerequisites"""
    return len(state["prerequisite_objectives"]) > 0


def all_objectives_completed(state: SessionState) -> bool:
    """Check if all objectives have been taught"""
    return state["current_objective_index"] >= len(state["objectives_to_teach"])


def get_objectives_for_testing(state: SessionState) -> List[Objective]:
    """Get objectives that should be included in final test"""
    if state["force_end_session"]:
        # Only test objectives that were actually taught
        return [
            obj for obj in state["objectives_to_teach"]
            if obj.id in state["completed_objectives"]
        ]
    else:
        # Test all objectives that needed teaching
        return state["objectives_to_teach"]


def calculate_final_score(state: SessionState) -> float:
    """Calculate overall mastery score from objective scores"""
    if not state["objective_scores"]:
        return 0.0
    return sum(state["objective_scores"].values()) / len(state["objective_scores"])


def format_learning_objectives(objectives: List[Objective]) -> str:
    """Format objectives for display in prompts"""
    if not objectives:
        return "No objectives"
    return "\n".join([f"- {obj.description}" for obj in objectives])


def format_references(references: List[Dict]) -> str:
    """Format references for inclusion in prompts"""
    if not references:
        return "No specific references"
    
    formatted = []
    for ref in references:
        rid = ref.get("rid", "unknown")
        loc = ref.get("loc", "")
        formatted.append(f"- {rid}: {loc}")
    
    return "\n".join(formatted) 