"""
Jobs module for Autodidact
Contains: clarifier agent, deep research wrapper, grader, and tutor nodes
"""

import json
import re
from typing import Dict, List, Optional
import openai
from openai import OpenAI


def clarify_topic(topic: str, hours: Optional[int] = None) -> Dict:
    """
    Determine if topic needs clarification and generate questions if needed.
    
    Returns either:
    - {"need_clarification": true, "questions": ["Q1", "Q2", ...]}
    - {"need_clarification": false, "refined_topic": "..."}
    """
    
    clarification_prompt = '''
    You are an intelligent assistant preparing to conduct a deep research report. 
    Before proceeding, determine if clarification is needed.
    
    If the topic is specific enough (e.g., "Foundations of Statistical Learning", 
    "Bitcoin consensus mechanisms", "React hooks"), return:
    {"need_clarification": false, "refined_topic": "<exact topic provided>"}
    
    If the topic is too broad or ambiguous (e.g., "Modern World History", "Programming", 
    "Science"), ask up to 5 clarifying questions in a numbered list to help narrow down:
    - What aspect/subtopic they're most interested in
    - Their current knowledge level
    - Specific goals or applications
    - Time constraints or depth preferences
    
    Return format must be valid JSON:
    {"need_clarification": true, "questions": ["Q1", "Q2", ...]}
    or
    {"need_clarification": false, "refined_topic": "<refined version of topic>"}
    '''
    
    # TODO: Implement OpenAI call
    # For now, return placeholder
    return {"need_clarification": False, "refined_topic": topic}


def is_skip_response(response: str) -> bool:
    """Check if response is a non-answer using regex patterns"""
    skip_pattern = re.compile(r'^\s*(idk|i don\'t know|skip|na|n/a|none)\s*$', re.IGNORECASE)
    return bool(skip_pattern.match(response.strip()))


def run_deep_research_job(topic: str, client: OpenAI) -> Dict:
    """
    Wrapper for Deep Research API call.
    Adapted from 02-topic-then-deep-research.py
    """
    # TODO: Implement based on existing deep_research.py
    pass


# LangGraph node implementations
def greet_node(state: Dict) -> Dict:
    """Welcome message for first session"""
    # TODO: Implement
    return state


def recap_node(state: Dict) -> Dict:
    """2 recall questions from previous sessions"""
    # TODO: Implement
    return state


def teach_node(state: Dict) -> Dict:
    """Main teaching with mid-lesson check"""
    # TODO: Implement
    return state


def quick_check_node(state: Dict) -> Dict:
    """Final assessment question"""
    # TODO: Implement
    return state


def grade_node(state: Dict) -> Dict:
    """Grade the student's understanding of learning objectives"""
    # TODO: Implement grading logic from implementation plan
    return state 