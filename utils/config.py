"""
Configuration module for Autodidact
Handles API key management, paths, and environment settings
"""

import json
import os
from pathlib import Path
from typing import Optional, Dict
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Constants
APP_NAME = "autodidact"
CONFIG_DIR = Path.home() / f".{APP_NAME}"
CONFIG_FILE = CONFIG_DIR / ".env.json"
PROJECTS_DIR = CONFIG_DIR / "projects"

# Deep Research API settings
# DEEP_RESEARCH_MODEL = "o4-mini-deep-research-2025-06-26"
DEEP_RESEARCH_MODEL = "o3-deep-research"
# could maybe use o3-deep-research if we're okay with higher costs for this
DEEP_RESEARCH_POLL_INTERVAL = 10  # seconds

# LLM settings
CHAT_MODEL = "gpt-4o-mini"

# Mastery settings
MASTERY_THRESHOLD = 0.7


def ensure_config_directory():
    """Ensure configuration directory exists with proper permissions"""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_DIR.chmod(0o700)
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)


def save_api_key(api_key: str):
    """Save OpenAI API key to config file"""
    ensure_config_directory()
    config = {"openai_api_key": api_key}
    
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f)
    
    # Set file permissions to 600 (rw-------)
    CONFIG_FILE.chmod(0o600)


def load_api_key() -> Optional[str]:
    """Load API key from config file or environment"""
    # # First check environment variable
    # api_key = os.environ.get("OPENAI_API_KEY")
    # if api_key:
    #     return api_key
    
    # Then check config file
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                return config.get("openai_api_key")
        except (json.JSONDecodeError, IOError):
            pass
    
    return None


def get_project_directory(project_id: str) -> Path:
    """Get the directory path for a specific project"""
    project_dir = PROJECTS_DIR / project_id
    project_dir.mkdir(parents=True, exist_ok=True)
    return project_dir


def get_report_path(project_id: str) -> Path:
    """Get the report markdown file path for a project"""
    return get_project_directory(project_id) / "report.md"


def get_graph_path(project_id: str) -> Path:
    """Get the graph JSON file path for a project"""
    return get_project_directory(project_id) / "graph.json"


def get_deep_research_response_path(project_id: str) -> Path:
    """Get the raw deep research response file path"""
    return get_project_directory(project_id) / "deep_research_response.json"


def save_project_files(project_id: str, report_markdown: str, graph_data: Dict, full_result: Dict) -> str:
    """
    Save project files to disk
    
    Args:
        project_id: UUID for the project
        report_markdown: The markdown report content
        graph_data: The graph dictionary
        full_result: Full Deep Research result for backup
    
    Returns:
        Path to the saved report file
    """
    # Create project directory
    project_dir = PROJECTS_DIR / project_id
    project_dir.mkdir(parents=True, exist_ok=True)
    
    # Save report
    report_path = project_dir / "report.md"
    report_path.write_text(report_markdown, encoding='utf-8')
    
    # Save graph
    graph_path = project_dir / "graph.json"
    with open(graph_path, 'w', encoding='utf-8') as f:
        json.dump(graph_data, f, indent=2)
    
    # Save full result as backup
    backup_path = project_dir / "deep_research_result.json"
    with open(backup_path, 'w', encoding='utf-8') as f:
        json.dump(full_result, f, indent=2)
    
    return str(report_path)


# Initialize configuration on import
ensure_config_directory() 