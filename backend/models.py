"""
Data models for Autodidact
Contains dataclasses and type definitions
"""

from dataclasses import dataclass
from typing import List, Dict, Optional
from datetime import datetime


@dataclass
class Project:
    """Represents a learning project"""
    id: str
    topic: str
    report_path: str
    graph_json: Dict
    resources_json: Dict
    created_at: datetime


@dataclass
class Node:
    """Represents a knowledge graph node"""
    id: str
    project_id: str
    original_id: str
    label: str
    summary: str
    mastery: float = 0.0
    learning_objectives: List['LearningObjective'] = None
    
    def __post_init__(self):
        if self.learning_objectives is None:
            self.learning_objectives = []


@dataclass
class Edge:
    """Represents a prerequisite relationship"""
    source: str
    target: str
    project_id: str
    confidence: float = 1.0
    rationale: str = ""


@dataclass
class LearningObjective:
    """Represents a learning objective for a node"""
    id: str
    node_id: str
    description: str
    mastery: float = 0.0


@dataclass
class TranscriptEntry:
    """Represents a single conversation turn"""
    session_id: str
    turn_idx: int
    role: str
    content: str
    created_at: datetime 