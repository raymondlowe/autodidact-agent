"""
Project workspace page
Shows project details, knowledge graph, and session management
"""

import streamlit as st
import json
import time
from pathlib import Path
import logging
from backend.db import (
    check_job,
    get_project, 
    check_and_complete_job, 
    get_next_nodes,
    get_db_connection,
    create_session,
    get_session_stats,
    get_all_projects,
    update_project_with_job,  # Add this import
    delete_project  # Add delete_project import
)
from backend.jobs import start_deep_research_job, test_job
from components.graph_viz import create_knowledge_graph
from utils.config import save_project_files

# Set up logging
logger = logging.getLogger(__name__)

# Get project ID from URL or session state
project_id = st.query_params.get("project_id")

def retry_with_better_model(st, project):
    print(f"[project_detail.py] Project: {project}")
    old_job_id = project['job_id']
    old_job_response = check_job(old_job_id)
    # print(f"[project_detail.py] Old job result: {old_job_response}")
    reasoning_texts = []
    
    # Check if old_job_response is None (job check failed)
    if old_job_response is None:
        print(f"[project_detail.py] Warning: Could not retrieve old job {old_job_id}, proceeding without reasoning texts")
    elif hasattr(old_job_response, 'output') and old_job_response.output:
        for item in old_job_response.output:
            # print(f"[project_detail.py] Item.type: {item.type}")
            if item.type == "reasoning":
                for summary in item.summary:
                    reasoning_texts.append(summary.text)

    # FIXME: unsure if we should even do anything with this: combined_text
    # combined_text = "An earlier research model failed partway, here are it's reasoning texts on the same prompt, in case those are useful:" + "\n\n".join(reasoning_texts)
    # print(f"[project_detail.py] Combined text: {combined_text}")

    combined_text = ""

    if 'hours' in project:
        hours = project['hours']
    else:
        hours = 5

    # Import the better model function
    from utils.providers import get_better_model_for_task
    
    # Get the better model for deep research
    model_to_use_now = get_better_model_for_task("deep_research")
    print(f"[project_detail.py] Using better model: {model_to_use_now}")

    new_job_id = start_deep_research_job(project['topic'], hours, combined_text, model_to_use_now)
    print(f"[project_detail.py] New Job ID: {new_job_id}")
    update_project_with_job(
                project_id=project_id,
                job_id=new_job_id,
                model_used=model_to_use_now,
                status='processing'
            )
    print(f"[project_detail.py] Project ID: {project_id}")

    st.rerun()

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
# if not project['status'] == 'processing':
#     print(f"[project_detail.py] Project: {project}")

if not project:
    st.error("Project not found!")
    if st.button("Go to Home"):
        st.switch_page("pages/home.py")
    st.stop()

# Page header
# Use name if available, otherwise fallback to topic
display_name = project.get('name') or project['topic']
st.markdown(f"# 📚 {display_name}")

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

                if project['model_used'] != "o3":
                    # this is a hack to get the user to retry with o3 if the job is taking too long
                    # Import here to get the better model name for display
                    from utils.providers import get_better_model_for_task, get_current_provider
                    from utils.config import get_current_provider as get_provider
                    try:
                        better_model = get_better_model_for_task("deep_research")
                        provider = get_provider()
                        button_text = f"Taking too long? Retry with {better_model.split('/')[-1] if '/' in better_model else better_model}"
                    except:
                        button_text = "Taking too long? Retry with better model"
                    
                    if st.button(button_text, type="primary"):
                        retry_with_better_model(st, project)
                
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
    
    col1, col2, col3 = st.columns(3)
    with col1:
        # Import here to get the better model name for display
        from utils.providers import get_better_model_for_task
        try:
            better_model = get_better_model_for_task("deep_research")
            button_text = f"Retry with {better_model.split('/')[-1] if '/' in better_model else better_model}"
        except:
            button_text = "Retry with better model"
            
        if st.button(button_text, type="primary"):
            retry_with_better_model(st, project)
    with col2:
        if st.button("➕ Create New Project", type="primary"):
            st.switch_page("pages/new_project.py")
    with col3:
        if st.button("🏠 Go Home"):
            st.switch_page("pages/home.py")

elif project['status'] == 'completed':
    # Normal workspace view
    st.markdown("---")
    
    # Two-column layout
    col1, col2 = st.columns([1, 3])
    
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
                    # FIXME: start with new session and work on getting this flow working
                    session_id = create_session(project_id, next_nodes[0]['id'])
                    st.session_state.selected_project_id = project_id
                    st.session_state.selected_session_id = session_id
                    st.switch_page("pages/session_detail.py")
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
                    logger.info(f"Start Session button clicked for project_id={project_id}, selected_node={selected}")
                    try:
                        # Create new session and navigate
                        logger.debug(f"Calling create_session with project_id={project_id}, node_id={selected}")
                        session_id = create_session(project_id, selected)
                        logger.info(f"Session created successfully: {session_id}")
                        
                        st.session_state.selected_project_id = project_id
                        st.session_state.selected_session_id = session_id
                        logger.debug(f"Session state updated, navigating to session_detail.py")
                        st.switch_page("pages/session_detail.py")
                    except Exception as e:
                        logger.error(f"Error creating session: {type(e).__name__}: {str(e)}")
                        logger.exception("Full traceback:")
                        st.error(f"Failed to create session: {str(e)}")
        else:
            st.success("🎉 **Congratulations!**\n\nYou've completed all available topics!")
            # Show completion stats
            stats = get_session_stats(project_id)
            if stats["total_sessions"] > 0:
                st.metric("Average Score", f"{int(stats['average_score'] * 100)}%")
        
        st.markdown("---")
        
        # Collapsible report viewer
        with st.expander("📄 References", expanded=False):
            try:
                # Load report and resources
                report_path = Path(project['report_path'])
                if report_path.exists():
                    report_md = report_path.read_text(encoding='utf-8')
                    formatted_report = report_md
                    
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
        
        # Add dropdown menu for project actions
        with st.expander("⚙️ Project Actions"):
            col1_inner, col2_inner, col3_inner = st.columns([1, 1, 2])
            with col3_inner:
                if st.button("🗑️ Delete Project", type="secondary", use_container_width=True):
                    st.session_state.show_delete_confirmation = True

        # Confirmation dialog
        if st.session_state.get('show_delete_confirmation', False):
            st.warning("⚠️ **Delete Project?**")
            st.error("This will permanently delete:")
            st.markdown("""
            - All learning progress and mastery scores
            - All session transcripts  
            - The knowledge graph and curriculum
            - Project files and resources
            
            **This action cannot be undone!**
            """)
            
            col1_dialog, col2_dialog = st.columns(2)
            with col1_dialog:
                if st.button("Cancel", use_container_width=True):
                    st.session_state.show_delete_confirmation = False
                    st.rerun()
            with col2_dialog:
                if st.button("Delete Permanently", type="primary", use_container_width=True):
                    try:
                        with st.spinner("Deleting project..."):
                            success = delete_project(project_id)
                            
                        if success:
                            st.success("Project deleted successfully!")
                            time.sleep(1)
                            # Clear session state
                            if 'show_delete_confirmation' in st.session_state:
                                del st.session_state.show_delete_confirmation
                            # Redirect to home
                            st.switch_page("pages/home.py")
                        else:
                            st.error("Failed to delete project. Please try again.")
                            
                    except Exception as e:
                        st.error(f"Error deleting project: {str(e)}")
    
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
            graph_data = project['graph']
            if graph_data and 'nodes' in graph_data:
                # Create graph
                graph_viz = create_knowledge_graph(
                    graph_data['nodes'],
                    graph_data['edges']
                )
                
                # Display graph
                st.graphviz_chart(graph_viz.source, use_container_width=True)
                
                # Add graph stats
                total_nodes = len(graph_data['nodes'])
                mastered_nodes = sum(1 for m in graph_data['nodes'] if m['mastery'] >= 0.7)
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
                    st.markdown("### 📊 Session Statistics")
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