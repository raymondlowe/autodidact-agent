"""
Autodidact - AI-Powered Learning Assistant
Main Streamlit application
"""

import streamlit as st
import uuid
import json
import time
from pathlib import Path
from typing import Optional, List

# Import our modules
from backend.db import (
    init_database, 
    get_project, 
    create_project,
    save_graph_to_db,
    get_next_nodes,
    get_db_connection
)
from backend.jobs import (
    clarify_topic,
    is_skip_response,
    process_clarification_responses,
    run_deep_research_job
)
from utils.config import (
    load_api_key, 
    save_api_key, 
    CONFIG_FILE,
    save_project_files
)
from components.graph_viz import (
    create_knowledge_graph,
    format_report_with_footnotes
)


# Page configuration
st.set_page_config(
    page_title="Autodidact - AI Learning Assistant",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize database
init_database()


def init_session_state():
    """Initialize Streamlit session state variables"""
    if "project_id" not in st.session_state:
        st.session_state.project_id = None
    if "current_node" not in st.session_state:
        st.session_state.current_node = None
    if "in_session" not in st.session_state:
        st.session_state.in_session = False
    if "api_key" not in st.session_state:
        st.session_state.api_key = load_api_key()
    if "clarification_state" not in st.session_state:
        st.session_state.clarification_state = None
    if "clarification_attempts" not in st.session_state:
        st.session_state.clarification_attempts = 0


def show_api_key_modal():
    """Show modal for API key setup"""
    with st.container():
        st.markdown("### 🔑 API Key Setup")
        st.info(
            "Autodidact requires an OpenAI API key to function. "
            "Your key will be stored locally and securely on your machine."
        )
        
        api_key = st.text_input(
            "Enter your OpenAI API key:",
            type="password",
            help="Your API key will be stored in ~/.autodidact/.env.json with secure permissions"
        )
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Save API Key", type="primary"):
                if api_key and api_key.startswith("sk-"):
                    save_api_key(api_key)
                    st.session_state.api_key = api_key
                    st.success("API key saved successfully!")
                    st.rerun()
                else:
                    st.error("Please enter a valid OpenAI API key (should start with 'sk-')")
        
        with col2:
            st.link_button(
                "Get API Key",
                "https://platform.openai.com/api-keys",
                help="Click to open OpenAI's API key page"
            )


def handle_clarification(topic: str, hours: int):
    """Handle the clarification flow"""
    # Check if we need clarification
    if st.session_state.clarification_state is None:
        with st.spinner("🔍 Analyzing your topic..."):
            try:
                result = clarify_topic(topic, hours)
                st.session_state.clarification_state = result
                st.session_state.clarification_attempts = 0
            except Exception as e:
                st.error(f"Error during topic analysis: {str(e)}")
                return
    
    result = st.session_state.clarification_state
    
    if result["need_clarification"]:
        # Show clarification in centered column
        col1, col2, col3 = st.columns([1, 2, 1])
        
        with col2:
            st.markdown("### 🤔 Let me understand better...")
            st.info(f"I'd like to narrow down **\"{topic}\"** to create a more focused learning plan.")
            
            # Show questions in expandable section
            with st.expander("📝 Clarification Questions", expanded=True):
                st.markdown("*Please answer the questions below to help me understand what you want to learn. You can type 'skip' for any question you're unsure about.*")
                
                responses = []
                for i, question in enumerate(result["questions"]):
                    response = st.text_input(
                        f"**{i+1}.** {question}",
                        key=f"clarification_q_{i}",
                        placeholder="Your answer (or type 'skip')"
                    )
                    responses.append(response)
            
            col_a, col_b = st.columns(2)
            with col_a:
                if st.button("✅ Submit Answers", type="primary", use_container_width=True):
                    # Check for skip responses
                    skip_count = sum(1 for r in responses if is_skip_response(r))
                    
                    if skip_count == len(responses) and st.session_state.clarification_attempts < 2:
                        st.warning("⚠️ Please try to answer at least one question to help me create a better learning plan.")
                        st.session_state.clarification_attempts += 1
                    else:
                        # Process responses
                        refined_topic = process_clarification_responses(result["questions"], responses)
                        if refined_topic:
                            topic = refined_topic
                        
                        # Start Deep Research
                        start_deep_research(topic, hours)
            
            with col_b:
                if st.button("⏩ Skip Clarification", use_container_width=True):
                    # Use original topic
                    start_deep_research(topic, hours)
    else:
        # No clarification needed, start Deep Research directly
        refined_topic = result.get("refined_topic", topic)
        start_deep_research(refined_topic, hours)


def start_deep_research(topic: str, hours: int):
    """Start the Deep Research process"""
    st.session_state.clarification_state = None  # Reset clarification
    
    # Show progress in centered column
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown("### 🔬 Deep Research in Progress")
        st.info(f"**Topic:** {topic}\n\n**Target Duration:** {hours} hours")
        
        progress_placeholder = st.empty()
        
        with st.spinner(""):
            # Show animated progress messages
            progress_messages = [
                "🔍 Conducting comprehensive research...",
                "📚 Analyzing learning resources...",
                "🧩 Building prerequisite relationships...",
                "📊 Creating your knowledge graph...",
                "✨ Generating learning objectives...",
                "📝 Finalizing your personalized curriculum..."
            ]
            
            try:
                # Note: In a real implementation, we'd update these messages based on actual progress
                progress_placeholder.info(
                    "**Please wait while I create your learning plan...**\n\n"
                    "This typically takes 10-30 minutes depending on the topic complexity.\n\n"
                    "I'm analyzing multiple sources to build the most effective learning path for you."
                )
                
                # Run Deep Research
                result = run_deep_research_job(topic, hours)
                
                # Create a temporary project ID for file storage
                temp_project_id = str(uuid.uuid4())
                
                # Save files to disk
                report_path = save_project_files(
                    temp_project_id,
                    result["report_markdown"],
                    result["graph"],
                    result
                )
                
                # Create project record (this creates the actual project_id)
                project_id = create_project(
                    topic=topic,
                    report_path=report_path,
                    graph_json=result["graph"],
                    footnotes=result["footnotes"]
                )
                
                # Save graph to database
                save_graph_to_db(project_id, result["graph"])
                
                # Update session state
                st.session_state.project_id = project_id
                
                # Show success message
                progress_placeholder.empty()
                st.success("✅ **Research complete!**\n\nYour personalized learning plan is ready.")
                st.balloons()
                
                # Wait a moment before redirecting
                import time
                time.sleep(2)
                st.rerun()
                
            except Exception as e:
                progress_placeholder.empty()
                st.error(f"❌ **Error during Deep Research**\n\n{str(e)}")
                st.info(
                    "**Troubleshooting tips:**\n"
                    "- Check your OpenAI API key is valid\n"
                    "- Ensure you have sufficient API credits\n"
                    "- Try a more specific topic\n"
                    "- Check your internet connection"
                )


def show_welcome_screen():
    """Show the welcome/landing screen"""
    # Centered layout with columns
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown("# 🧠 Autodidact")
        st.markdown("### Your AI-Powered Learning Assistant")
        
        st.markdown("""
        Welcome to Autodidact! I'm here to help you learn any topic through:
        - 🔍 **Deep Research**: I'll investigate your topic and create a comprehensive study plan
        - 📊 **Knowledge Graphs**: Visual representation of concepts and their prerequisites  
        - 👨‍🏫 **AI Tutoring**: Personalized 30-minute learning sessions
        - 📈 **Progress Tracking**: Monitor your mastery of each concept
        """)
        
        st.markdown("---")
        
        # Topic input section
        st.markdown("### What would you like to learn?")
        
        topic = st.text_input(
            "Enter a topic:",
            placeholder="e.g., Foundations of Statistical Learning, Bitcoin consensus mechanisms",
            label_visibility="collapsed"
        )
        
        hours = st.number_input(
            "Target study hours (optional):",
            min_value=1,
            max_value=100,
            value=8,
            help="This helps me plan the depth of coverage"
        )
        
        if st.button("🚀 Start Learning Journey", type="primary", use_container_width=True):
            if topic:
                # Handle clarification flow
                handle_clarification(topic, hours)
            else:
                st.error("Please enter a topic to learn")
        
        # Example topics in expandable section
        with st.expander("💡 Need inspiration? Try these example topics:"):
            st.markdown("""
            **Technology & Programming:**
            - Foundations of Statistical Learning
            - React Hooks and State Management
            - Bitcoin and Ethereum Internals
            - Quantum Computing Basics
            - Rust Programming Language Fundamentals
            
            **Science & Mathematics:**
            - Introduction to Neuroscience
            - Linear Algebra for Machine Learning
            - Climate Change: Causes and Solutions
            - Molecular Biology Essentials
            
            **History & Social Sciences:**
            - Modern World History: 1900-1950
            - Behavioral Economics Principles
            - Philosophy of Mind
            - Cultural Anthropology Basics
            
            **Business & Finance:**
            - Venture Capital Fundamentals
            - Supply Chain Management
            - Digital Marketing Strategy
            - Financial Derivatives Explained
            """)


def show_workspace():
    """Show the main workspace with report and graph"""
    project = get_project(st.session_state.project_id)
    if not project:
        st.error("Project not found!")
        if st.button("Go Back"):
            st.session_state.project_id = None
            st.rerun()
        return
    
    # Project header
    st.markdown(f"# 📚 {project['topic']}")
    
    # Add a subtle divider
    st.markdown("---")
    
    # Two-column layout with adjusted ratio
    col1, col2 = st.columns([1, 2])
    
    with col1:
        # Session controls section
        st.markdown("### 🎓 Learning Sessions")
        
        # Get available nodes
        next_nodes = get_next_nodes(st.session_state.project_id)
        
        if next_nodes:
            if len(next_nodes) == 1:
                st.info(f"**Ready to learn:**\n\n📖 {next_nodes[0]['label']}")
                if st.button("Start Session →", type="primary", use_container_width=True):
                    st.session_state.current_node = next_nodes[0]['id']
                    st.session_state.in_session = True
                    st.rerun()
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
                    st.session_state.current_node = selected
                    st.session_state.in_session = True
                    st.rerun()
        else:
            st.success("🎉 **Congratulations!**\n\nYou've completed all available topics!")
            # TODO: Add completion stats here
        
        st.markdown("---")
        
        # Collapsible report viewer
        with st.expander("📄 Research Report", expanded=False):
            try:
                # Load report and footnotes
                report_path = Path(project['report_path'])
                if report_path.exists():
                    report_md = report_path.read_text(encoding='utf-8')
                    footnotes = json.loads(project['footnotes_json'])
                    
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
            graph_data = json.loads(project['graph_json'])
            
            # Get node mastery data from database
            with get_db_connection() as conn:
                cursor = conn.execute("""
                    SELECT original_id, mastery 
                    FROM node 
                    WHERE project_id = ?
                """, (st.session_state.project_id,))
                
                node_mastery = {row[0]: row[1] for row in cursor.fetchall()}
            
            # Create graph
            graph_viz = create_knowledge_graph(
                graph_data['nodes'],
                graph_data['edges'],
                node_mastery
            )
            
            # Display graph with custom height
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
            
        except Exception as e:
            st.error(f"Error displaying graph: {str(e)}")
            # Show raw graph data as fallback
            with st.expander("Show raw graph data"):
                st.json(graph_data)


def show_tutor_session():
    """Show the tutor session interface"""
    # TODO: Implement tutor session
    st.markdown("## 🎓 Tutor Session")
    
    if st.button("End Session (temporary)"):
        st.session_state.in_session = False
        st.rerun()
    
    st.info("Tutor session implementation coming in Phase 4")


def main():
    """Main application entry point"""
    # Initialize session state
    init_session_state()
    
    # Sidebar
    with st.sidebar:
        st.markdown("# 🧠 Autodidact")
        
        if st.session_state.api_key:
            st.success("✅ API Key configured")
            
            if st.button("⚙️ Settings"):
                if st.button("Clear API Key"):
                    CONFIG_FILE.unlink(missing_ok=True)
                    st.session_state.api_key = None
                    st.rerun()
        else:
            st.warning("⚠️ API Key not configured")
        
        st.markdown("---")
        
        # Project selection (if any exist)
        if st.session_state.project_id:
            project = get_project(st.session_state.project_id)
            if project:
                st.markdown(f"**Current Project:**")
                st.markdown(f"📚 {project['topic']}")
                
                if st.button("🏠 New Project"):
                    st.session_state.project_id = None
                    st.session_state.current_node = None
                    st.session_state.in_session = False
                    st.session_state.clarification_state = None
                    st.rerun()
    
    # Main content area
    if not st.session_state.api_key:
        show_api_key_modal()
    elif not st.session_state.project_id:
        show_welcome_screen()
    elif st.session_state.in_session:
        show_tutor_session()
    else:
        show_workspace()
    
    # Footer
    st.markdown("---")
    st.markdown(
        "<div style='text-align: center; color: gray;'>"
        "Built with ❤️ for autodidacts everywhere | "
        "<a href='https://github.com/yourusername/autodidact'>GitHub</a>"
        "</div>",
        unsafe_allow_html=True
    )


if __name__ == "__main__":
    main() 