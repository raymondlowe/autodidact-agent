"""
Project workspace page
Shows project details, knowledge graph, and session management
"""

import streamlit as st
import json
import time
from pathlib import Path
from backend.db import (
    get_project, 
    check_and_complete_job, 
    get_next_nodes,
    get_db_connection,
    create_session,
    get_session_stats,
    get_all_projects  # Add this import
)
from components.graph_viz import create_knowledge_graph, format_report_with_footnotes
from utils.config import save_project_files

# Get project ID from URL or session state
project_id = st.query_params.get("project_id")

# If no project_id in URL but we have it in session state, set it in URL
if not project_id and "selected_project_id" in st.session_state:
    project_id = st.session_state.selected_project_id
    st.query_params["project_id"] = project_id
    # Clean up session state
    del st.session_state.selected_project_id

if not project_id:
    st.error("No project selected!")
    if st.button("Go to Home"):
        st.switch_page("pages/home.py")
    st.stop()

# Get project
project = get_project(project_id)

if not project:
    st.error("Project not found!")
    if st.button("Go to Home"):
        st.switch_page("pages/home.py")
    st.stop()

# Page header
st.markdown(f"# 📚 {project['topic']}")

# Check project status
if project['status'] == 'processing' and project['job_id']:
    # Project is still being researched
    st.markdown("---")
    
    col1, col2, col3 = st.columns([1, 3, 1])
    with col2:
        st.markdown("## 🔬 Deep Research in Progress")
        
        st.info("""
        Your personalized curriculum is being created. This typically takes 10-30 minutes depending on the topic complexity.
        
        **You can safely navigate to other projects while this completes!**
        """)
        
        # Progress messages
        progress_placeholder = st.empty()
        
        # Poll for completion
        with st.spinner("Checking research status..."):
            job_completed = check_and_complete_job(project_id, project['job_id'])
            
            if job_completed:
                st.success("✅ Research complete! Your learning journey is ready.")
                st.balloons()
                time.sleep(2)
                st.rerun()
            else:
                # Show estimated time and auto-refresh
                progress_placeholder.info("""
                🔄 Research is still in progress...
                
                This page will automatically refresh every 10 seconds.
                Feel free to explore other projects in the meantime!
                """)
                
                # Auto-refresh
                time.sleep(10)
                st.rerun()

elif project['status'] == 'failed':
    # Research failed
    st.error("""
    ❌ **Research Failed**
    
    Unfortunately, the deep research process encountered an error. This can happen due to:
    - Temporary API issues
    - Rate limiting
    - Complex topics that need refinement
    
    Please try creating a new project with a slightly different topic description.
    """)
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("➕ Create New Project", type="primary"):
            st.switch_page("pages/new_project.py")
    with col2:
        if st.button("🏠 Go Home"):
            st.switch_page("pages/home.py")

elif project['status'] == 'completed':
    # Normal workspace view
    st.markdown("---")
    
    # Two-column layout
    col1, col2 = st.columns([1, 2])
    
    with col1:
        # Session controls section
        st.markdown("### 🎓 Learning Sessions")
        
        # Get available nodes
        next_nodes = get_next_nodes(project_id)
        
        if next_nodes:
            if len(next_nodes) == 1:
                st.info(f"**Ready to learn:**\n\n📖 {next_nodes[0]['label']}")
                if st.button("Start Session →", type="primary", use_container_width=True):
                    # Create new session and navigate
                    session_id = create_session(project_id, next_nodes[0]['id'])
                    st.session_state.selected_project_id = project_id
                    st.session_state.selected_session_id = session_id
                    st.switch_page("pages/session-detail.py")
            else:
                # Multiple options
                st.info("**Choose your next topic:**")
                selected = st.radio(
                    "Available topics:",
                    options=[n['id'] for n in next_nodes],
                    format_func=lambda x: f"📖 {next(n['label'] for n in next_nodes if n['id'] == x)}",
                    label_visibility="collapsed"
                )
                if st.button("Start Session →", type="primary", use_container_width=True):
                    # Create new session and navigate
                    session_id = create_session(project_id, selected)
                    st.session_state.selected_project_id = project_id
                    st.session_state.selected_session_id = session_id
                    st.switch_page("pages/session-detail.py")
        else:
            st.success("🎉 **Congratulations!**\n\nYou've completed all available topics!")
            # Show completion stats
            stats = get_session_stats(project_id)
            if stats["total_sessions"] > 0:
                st.metric("Average Score", f"{int(stats['average_score'] * 100)}%")
        
        st.markdown("---")
        
        # Collapsible report viewer
        with st.expander("📄 Research Report", expanded=False):
            try:
                # Load report and footnotes
                report_path = Path(project['report_path'])
                if report_path.exists():
                    report_md = report_path.read_text(encoding='utf-8')
                    footnotes = json.loads(project['footnotes_json'] or '{}')
                    
                    # Format with footnotes
                    formatted_report = format_report_with_footnotes(report_md, footnotes)
                    
                    # Add custom CSS for better report styling
                    st.markdown("""
                    <style>
                    .report-content {
                        max-height: 600px;
                        overflow-y: auto;
                        padding-right: 10px;
                    }
                    .report-content h1, .report-content h2 {
                        color: #1f77b4;
                    }
                    .report-content blockquote {
                        border-left: 3px solid #1f77b4;
                        padding-left: 10px;
                        color: #666;
                    }
                    </style>
                    """, unsafe_allow_html=True)
                    
                    st.markdown(f'<div class="report-content">{formatted_report}</div>', 
                               unsafe_allow_html=True)
                else:
                    st.warning("Report file not found")
            except Exception as e:
                st.error(f"Error loading report: {str(e)}")
    
    with col2:
        # Knowledge graph visualization
        st.markdown("### 📊 Knowledge Graph")
        
        # Add legend
        legend_cols = st.columns([1, 1, 1])
        with legend_cols[0]:
            st.markdown("🟩 **Mastered** (70%+)")
        with legend_cols[1]:
            st.markdown("🟨 **In Progress**")
        with legend_cols[2]:
            st.markdown("⬜ **Not Started**")
        
        try:
            # Load graph data
            graph_data = json.loads(project['graph_json'] or '{}')
            
            if graph_data and 'nodes' in graph_data:
                # Get node mastery data from database
                with get_db_connection() as conn:
                    cursor = conn.execute("""
                        SELECT original_id, mastery 
                        FROM node 
                        WHERE project_id = ?
                    """, (project_id,))
                    
                    node_mastery = {row[0]: row[1] for row in cursor.fetchall()}
                
                # Create graph
                graph_viz = create_knowledge_graph(
                    graph_data['nodes'],
                    graph_data['edges'],
                    node_mastery
                )
                
                # Display graph
                st.graphviz_chart(graph_viz.source, use_container_width=True)
                
                # Add graph stats
                total_nodes = len(graph_data['nodes'])
                mastered_nodes = sum(1 for m in node_mastery.values() if m >= 0.7)
                progress_pct = int((mastered_nodes / total_nodes) * 100) if total_nodes > 0 else 0
                
                st.markdown(f"""
                **Overall Progress:** {progress_pct}% ({mastered_nodes}/{total_nodes} concepts mastered)
                """)
                
                # Progress bar
                st.progress(progress_pct / 100)
                
                # Session statistics
                session_stats = get_session_stats(project_id)
                if session_stats["total_sessions"] > 0:
                    st.markdown("---")
                    st.markdown("### �� Session Statistics")
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Total Sessions", session_stats["total_sessions"])
                    with col2:
                        st.metric("Completed", session_stats["completed_sessions"])
                    with col3:
                        st.metric("Avg Score", f"{int(session_stats['average_score'] * 100)}%")
            else:
                st.warning("No knowledge graph data available yet.")
                
        except Exception as e:
            st.error(f"Error displaying graph: {str(e)}")
            # Show raw graph data as fallback
            with st.expander("Show raw graph data"):
                st.json(graph_data)

else:
    # Unknown status
    st.error(f"Unknown project status: {project['status']}")
    if st.button("Go to Home"):
        st.switch_page("pages/home.py") 