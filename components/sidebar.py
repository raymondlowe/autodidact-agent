"""
Sidebar component for Autodidact
Shows on all pages with project list and navigation
"""

import streamlit as st
from backend.db import get_all_projects
from datetime import datetime

def show_sidebar():
    """Show sidebar with project list on all pages"""
    with st.sidebar:
        st.markdown("# Autodidact")

        st.page_link("pages/home.py", label="Home", icon="🏠")
        st.page_link("pages/settings.py", label="Settings", icon="⚙️")
        
        # New Project button
        if st.button("➕ New Project", type="primary", use_container_width=True):
            st.switch_page("pages/new_project.py")
        st.markdown("---")
        
        # Project list
        st.markdown("### Your Projects")
        projects = get_all_projects()
        
        if projects:
            # Get current project from query params
            current_project_id = st.query_params.get("project_id")
            
            for project in projects:
                status = project.get('status', 'completed')
                
                # # Show status indicator
                # if status == 'processing':
                #     status_icon = "⏳"
                # elif status == 'failed':
                #     status_icon = "❌"
                # else:
                #     status_icon = "✅"
                status_icon = ""
                
                # Create container for project
                with st.container():
                    col1, col2 = st.columns([4, 1])
                    with col1:
                        # Use name if available, otherwise fallback to topic
                        name_orig = project.get('name') or project['topic']
                        name = name_orig[:25]
                        if name != name_orig:
                            name = name + "..."
                        
                        if st.button(
                            f"{status_icon} {name}",
                            key=f"proj_{project['id']}",
                            use_container_width=True,
                            disabled=(status == 'pending')
                        ):
                            # Store project_id in session state before navigation
                            st.session_state.selected_project_id = project['id']
                            st.switch_page("pages/project_detail.py")
                    
                    with col2:
                        if status == 'processing':
                            st.markdown("🔄")
                        elif status == 'failed':
                            st.markdown("❌ Research failed")
                        elif status == 'completed' and project['total_nodes'] > 0:
                            progress = project.get('progress', 0)
                            st.markdown(f"**{progress}%**")
                    
                    # Show additional info
                    
                    # elif project['total_nodes'] > 0:
                    #     st.caption(f"📅 {time_str} • {project['total_nodes']} topics • {project['mastered_nodes']} mastered")
                    # else:
                    #     st.caption(f"📅 {time_str}")
        else:
            st.info("No projects yet. Click 'New Project' to start!")
        
        # Footer
        st.markdown("---")
        st.markdown(
            "<div style='text-align: center; color: gray; font-size: 0.8em;'>"
            "Built with ❤️ for autodidacts everywhere"
            "</div>",
            unsafe_allow_html=True
        ) 