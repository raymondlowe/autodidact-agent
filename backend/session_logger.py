"""
Session logging functionality for Autodidact v0.4
Handles creation and updating of markdown session logs
"""

from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any
import json

from backend.session_state import (
    SessionState, Objective, QuizQuestion, TestAnswer,
    format_learning_objectives
)


class SessionLogger:
    """Handles logging of learning sessions to markdown files"""
    
    def __init__(self, project_id: str, session_id: str):
        self.project_id = project_id
        self.session_id = session_id
        self.log_path = self._get_log_path()
        self._ensure_log_directory()
    
    def _get_log_path(self) -> Path:
        """Get the path for this session's log file"""
        return (
            Path.home() / '.autodidact' / 'projects' / 
            self.project_id / 'sessions' / f"{self.session_id}.md"
        )
    
    def _ensure_log_directory(self):
        """Ensure the log directory exists"""
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
    
    def initialize_log(self, state: SessionState):
        """Create the initial log file with session metadata"""
        with open(self.log_path, 'w', encoding='utf-8') as f:
            f.write(f"# Learning Session: {state['node_title']}\n\n")
            f.write(f"**Session ID:** `{state['session_id']}`\n")
            f.write(f"**Started:** {state['session_start']}\n")
            f.write(f"**Node:** {state['node_title']}\n")
            f.write(f"**Domain Level:** {state.get('domain_level', 'unknown')}\n\n")
            
            # Learning objectives section
            f.write("## 📚 Learning Objectives\n\n")
            
            if state['objectives_to_teach']:
                f.write("### To Learn (Mastery < 70%)\n\n")
                for obj in state['objectives_to_teach']:
                    f.write(f"- [ ] {obj.description} *(current: {obj.mastery:.0%})*\n")
            
            if state['objectives_already_known']:
                f.write("\n### Already Mastered (Mastery ≥ 70%)\n\n")
                for obj in state['objectives_already_known']:
                    f.write(f"- [x] {obj.description} *(current: {obj.mastery:.0%})*\n")
            
            # Prerequisites section
            if state['prerequisite_objectives']:
                f.write("\n## 🔗 Prerequisites\n\n")
                for obj in state['prerequisite_objectives']:
                    mastery_indicator = "✅" if obj.mastery >= 0.7 else "⚠️"
                    f.write(f"- {obj.description} {mastery_indicator} *({obj.mastery:.0%})*\n")
            
            # References section
            if state.get('references_sections_resolved'):
                f.write("\n## 📖 References\n\n")
                for ref in state.get('references_sections_resolved'):
                    rid = ref.get('rid', 'unknown')
                    loc = ref.get('loc') or ref.get('section') or ''
                    f.write(f"- **{rid}**: {loc}\n")
            
            f.write("\n---\n\n## 💬 Session Transcript\n\n")
    
    def log_message(self, role: str, content: str, metadata: Optional[Dict] = None):
        """Append a message to the session log"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        with open(self.log_path, 'a', encoding='utf-8') as f:
            if role == "assistant":
                emoji = "🤖"
                name = "Ada"
            else:
                emoji = "👤"
                name = "You"
            
            f.write(f"### {emoji} {name} ({timestamp})")
            
            if metadata:
                phase = metadata.get('phase', '')
                if phase:
                    f.write(f" - *{phase}*")
            
            f.write(f"\n\n{content}\n\n")
    
    def log_quiz(self, quiz_type: str, question: QuizQuestion, 
                  user_answer: Optional[str] = None, feedback: Optional[str] = None):
        """Log a quiz question and optionally the answer"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        with open(self.log_path, 'a', encoding='utf-8') as f:
            f.write(f"### 📝 {quiz_type} ({timestamp})\n\n")
            f.write(f"**Question:** {question.q}\n")
            f.write(f"**Type:** {question.type}\n")
            
            if question.type == "mcq" and question.choices:
                f.write("\n**Choices:**\n")
                for i, choice in enumerate(question.choices):
                    f.write(f"- {chr(65+i)}. {choice}\n")
            
            if user_answer is not None:
                f.write(f"\n**Your Answer:** {user_answer}\n")
            
            if feedback is not None:
                f.write(f"**Feedback:** {feedback}\n")
            
            f.write("\n")
    
    def log_event(self, event_type: str, data: Dict[str, Any]):
        """Log a system event"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        with open(self.log_path, 'a', encoding='utf-8') as f:
            f.write(f"### ⚡ System Event ({timestamp})\n\n")
            f.write(f"**Event:** {event_type}\n")
            
            if data:
                f.write("**Details:**\n")
                for key, value in data.items():
                    f.write(f"- {key}: {value}\n")
            
            f.write("\n")
    
    def log_final_results(self, state: SessionState):
        """Log the final test results and session summary"""
        with open(self.log_path, 'a', encoding='utf-8') as f:
            f.write("---\n\n## 📊 Final Results\n\n")
            
            # Individual objective scores
            if state['objective_scores']:
                f.write("### Objective Scores\n\n")
                for obj in state['objectives_to_teach']:
                    if obj.id in state['objective_scores']:
                        score = state['objective_scores'][obj.id]
                        emoji = "✅" if score >= 0.7 else "⚠️" if score >= 0.5 else "❌"
                        f.write(f"- {obj.description}: **{score:.0%}** {emoji}\n")
            
            # Overall score
            final_score = calculate_final_score(state)
            mastery_status = "Mastered! 🎉" if final_score >= 0.7 else "Keep practicing 💪"
            f.write(f"\n### Overall Score: {final_score:.0%} - {mastery_status}\n\n")
            
            # Session stats
            f.write("### Session Statistics\n\n")
            f.write(f"- **Duration:** {calculate_duration(state)}\n")
            f.write(f"- **Objectives Taught:** {len(state['completed_objectives'])} / {len(state['objectives_to_teach'])}\n")
            f.write(f"- **Total Messages:** {state['turn_count']}\n")
            
            if state['exit_requested']:
                f.write("\n⚠️ *Session ended early by user request*\n")
            
            f.write(f"\n**Completed:** {datetime.now().isoformat()}\n")
    
    def log_phase_transition(self, from_phase: str, to_phase: str):
        """Log a transition between phases"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        with open(self.log_path, 'a', encoding='utf-8') as f:
            f.write(f"### 🔄 Phase Transition ({timestamp})\n\n")
            f.write(f"**{from_phase}** → **{to_phase}**\n\n")


# Helper functions

def calculate_final_score(state: SessionState) -> float:
    """Calculate the overall mastery score"""
    if not state['objective_scores']:
        return 0.0
    return sum(state['objective_scores'].values()) / len(state['objective_scores'])


def calculate_duration(state: SessionState) -> str:
    """Calculate session duration"""
    if not state['session_end']:
        return "In progress"
    
    start = datetime.fromisoformat(state['session_start'])
    end = datetime.fromisoformat(state['session_end'])
    duration = end - start
    
    minutes = int(duration.total_seconds() / 60)
    seconds = int(duration.total_seconds() % 60)
    
    return f"{minutes}m {seconds}s"


# Convenience functions for use in graph nodes

def get_logger(state: SessionState) -> SessionLogger:
    """Get a logger instance for the current session"""
    return SessionLogger(state['project_id'], state['session_id'])


def log_session_start(state: SessionState):
    """Initialize the session log"""
    logger = get_logger(state)
    logger.initialize_log(state)


def log_session_message(state: SessionState, role: str, content: str, metadata: Optional[Dict] = None):
    """Log a message to the session"""
    logger = get_logger(state)
    logger.log_message(role, content, metadata)


def log_session_event(state: SessionState, event_type: str, data: Dict[str, Any]):
    """Log an event to the session"""
    logger = get_logger(state)
    logger.log_event(event_type, data)


def log_session_end(state: SessionState):
    """Log the final results"""
    logger = get_logger(state)
    logger.log_final_results(state) 