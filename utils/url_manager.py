"""
URL parameter management for Autodidact
Handles navigation, validation, and state restoration from URL parameters
"""

import streamlit as st
from urllib.parse import quote, unquote
from typing import Dict, Optional, Any


class URLManager:
    """Centralized URL parameter management for navigation and bookmarking"""
    
    @staticmethod
    def get_current_params() -> Dict[str, Any]:
        """Get and parse current URL parameters"""
        params = st.query_params
        return dict(params)
    
    @staticmethod
    def navigate_to_welcome():
        """Clear all params and go to welcome page"""
        st.query_params.clear()
    
    @staticmethod
    def navigate_to_project(project_id: str):
        """Navigate to project workspace"""
        st.query_params.clear()
        st.query_params["project_id"] = project_id
        st.query_params["view"] = "workspace"
    
    @staticmethod
    def navigate_to_session(session_id: str):
        """Navigate to learning session"""
        st.query_params.clear()
        st.query_params["session_id"] = session_id
        st.query_params["view"] = "session"
    
    @staticmethod
    def navigate_to_clarify(topic: str, hours: int):
        """Navigate to clarification flow"""
        st.query_params.clear()
        st.query_params["topic"] = quote(topic)
        st.query_params["hours"] = str(hours)
        st.query_params["view"] = "clarify"
    
    @staticmethod
    def validate_and_restore_state() -> Dict[str, Any]:
        """
        Validate URL parameters against database and return state info
        
        Returns:
            dict with keys:
                - valid: bool
                - view: str or None
                - project_id: str or None
                - session_id: str or None
                - topic: str or None
                - hours: int or None
                - error: str or None
        """
        params = URLManager.get_current_params()
        
        # Default response
        result = {
            "valid": False,
            "view": params.get("view", "welcome"),
            "project_id": None,
            "session_id": None,
            "topic": None,
            "hours": None,
            "error": None
        }
        
        # If no params or view is welcome, that's valid
        if not params or result["view"] == "welcome":
            result["valid"] = True
            return result
        
        # Validate based on view type
        if result["view"] == "workspace":
            project_id = params.get("project_id")
            if project_id:
                # Will validate against DB in app.py
                result["project_id"] = project_id
                result["valid"] = True
            else:
                result["error"] = "Missing project_id for workspace view"
                
        elif result["view"] == "session":
            session_id = params.get("session_id")
            if session_id:
                # Will validate against DB in app.py
                result["session_id"] = session_id
                result["valid"] = True
            else:
                result["error"] = "Missing session_id for session view"
                
        elif result["view"] == "clarify":
            topic = params.get("topic")
            hours = params.get("hours", "8")
            if topic:
                result["topic"] = unquote(topic)
                try:
                    result["hours"] = int(hours)
                    result["valid"] = True
                except ValueError:
                    result["hours"] = 8
                    result["valid"] = True
            else:
                result["error"] = "Missing topic for clarification view"
        
        return result
    
    @staticmethod
    def get_shareable_link(base_url: str = None) -> str:
        """Get the current shareable link"""
        if base_url is None:
            # In production, this would come from config
            base_url = "http://localhost:8501"
        
        params = URLManager.get_current_params()
        if params:
            param_str = "&".join([f"{k}={v}" for k, v in params.items()])
            return f"{base_url}/?{param_str}"
        return base_url 