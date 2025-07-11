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
from datetime import datetime

# Import our modules
from backend.db import (
    init_database, 
    get_project, 
    create_project,
    save_graph_to_db,
    get_next_nodes,
    get_db_connection,
    get_node_with_objectives,
    save_transcript,
    get_latest_session_for_node,
    get_transcript_for_session,
    get_all_projects,
    create_session,
    has_previous_sessions,
    complete_session,
    get_session_stats,
    get_session_info
)
from backend.jobs import (
    clarify_topic,
    is_skip_response,
    process_clarification_responses,
    run_deep_research_job,
    rewrite_topic
)
from utils.config import (
    load_api_key, 
    save_api_key, 
    CONFIG_FILE,
    save_project_files
)
from utils.url_manager import URLManager
from components.graph_viz import (
    create_knowledge_graph,
    format_report_with_footnotes
)

import openai


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
    """Initialize Streamlit session state variables with URL parameter checking"""
    
    # First check URL parameters
    url_state = URLManager.validate_and_restore_state()
    
    # Initialize basic session state
    if "project_id" not in st.session_state:
        st.session_state.project_id = None
    if "current_node" not in st.session_state:
        st.session_state.current_node = None
    if "in_session" not in st.session_state:
        st.session_state.in_session = False
    if "api_key" not in st.session_state:
        st.session_state.api_key = load_api_key()
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "tutor_session_id" not in st.session_state:
        st.session_state.tutor_session_id = None
    if "turn_count" not in st.session_state:
        st.session_state.turn_count = 0
    if "current_phase" not in st.session_state:
        st.session_state.current_phase = "greet"
    if "has_previous_session" not in st.session_state:
        st.session_state.has_previous_session = False
    
    # Now restore from URL if valid
    if url_state["valid"]:
        if url_state["view"] == "workspace" and url_state["project_id"]:
            # Validate project exists
            project = get_project(url_state["project_id"])
            if project:
                st.session_state.project_id = url_state["project_id"]
                st.session_state.in_session = False
                st.session_state.current_node = None
            else:
                # Invalid project, redirect to welcome
                st.error("Project not found")
                URLManager.navigate_to_welcome()
                st.rerun()
                
        elif url_state["view"] == "session" and url_state["session_id"]:
            # Validate and restore session
            session_info = get_session_info(url_state["session_id"])
            if session_info:
                st.session_state.project_id = session_info["project_id"]
                st.session_state.current_node = session_info["node_id"]
                st.session_state.tutor_session_id = url_state["session_id"]
                st.session_state.in_session = True
                
                # Restore messages if session is in progress
                if session_info["status"] == "in_progress":
                    transcript = get_transcript_for_session(url_state["session_id"])
                    st.session_state.messages = [
                        {"role": entry["role"], "content": entry["content"]}
                        for entry in transcript
                    ]
                    st.session_state.turn_count = len(transcript)
                    
                    # Determine phase from transcript
                    if any("Let's see what you've learned" in msg["content"] for msg in st.session_state.messages):
                        st.session_state.current_phase = "grade"
                    elif len([m for m in st.session_state.messages if m["role"] == "user"]) >= 2:
                        st.session_state.current_phase = "quick_check"
                    else:
                        st.session_state.current_phase = "teach"
                else:
                    # Session is completed, show read-only view
                    st.session_state.messages = [
                        {"role": entry["role"], "content": entry["content"]}
                        for entry in get_transcript_for_session(url_state["session_id"])
                    ]
            else:
                # Invalid session, redirect to welcome
                st.error("Session not found")
                URLManager.navigate_to_welcome()
                st.rerun()
                
        elif url_state["view"] == "clarify":
            # Handle clarification flow
            st.session_state.clarification_topic = url_state["topic"]
            st.session_state.clarification_hours = url_state["hours"]


def show_api_key_modal():
    """Show enhanced modal for API key setup"""
    with st.container():
        st.markdown("## 🔑 Welcome to Autodidact!")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.markdown("""
            ### Getting Started
            
            Autodidact is an AI-powered learning assistant that creates personalized study plans 
            and provides interactive tutoring sessions.
            
            **To get started, you'll need an OpenAI API key.**
            
            1. Click "Get API Key" to create one (if you don't have one)
            2. Enter your API key below
            3. Your key will be stored securely on your local machine
            
            **Features you'll unlock:**
            - 🔍 Deep research on any topic
            - 📊 Visual knowledge graphs
            - 👨‍🏫 Personalized AI tutoring
            - 📈 Progress tracking
            """)
        
        with col2:
            st.info("""
            **Privacy Note:**
            
            Your API key is stored locally in:
            `~/.autodidact/.env.json`
            
            It's never sent to any server except OpenAI's API.
            """)
        
        st.markdown("---")
        
        api_key = st.text_input(
            "Enter your OpenAI API key:",
            type="password",
            placeholder="sk-...",
            help="Your API key will be stored in ~/.autodidact/.env.json with secure permissions"
        )
        
        col1, col2, col3 = st.columns([1, 1, 1])
        with col1:
            if st.button("💾 Save API Key", type="primary", use_container_width=True):
                if api_key and api_key.startswith("sk-"):
                    try:
                        # Test the API key
                        test_client = OpenAI(api_key=api_key)
                        test_client.models.list()  # Quick test call
                        
                        # If successful, save it
                        save_api_key(api_key)
                        st.session_state.api_key = api_key
                        st.success("✅ API key validated and saved successfully!")
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Invalid API key: {str(e)}")
                else:
                    st.error("Please enter a valid OpenAI API key (should start with 'sk-')")
        
        with col2:
            st.link_button(
                "🔗 Get API Key",
                "https://platform.openai.com/api-keys",
                help="Click to open OpenAI's API key page",
                use_container_width=True
            )
        
        with col3:
            st.link_button(
                "📖 Pricing Info",
                "https://openai.com/pricing",
                help="View OpenAI's pricing details",
                use_container_width=True
            )


def handle_clarification(topic: str, hours: int):
    """Handle the clarification flow"""
    print(f"\n[handle_clarification] Starting with topic: '{topic}', hours: {hours}")
    
    # Set URL parameters for bookmarkability
    URLManager.navigate_to_clarify(topic, hours)
    
    # Check if we need to get clarification questions
    if "clarification_questions" not in st.session_state:
        print("[handle_clarification] No questions in session state, fetching...")
        with st.spinner("🔍 Preparing clarification questions..."):
            try:
                questions = clarify_topic(topic, hours)
                st.session_state.clarification_questions = questions
                st.session_state.original_topic = topic
                st.session_state.original_hours = hours
                print(f"[handle_clarification] Got {len(questions)} questions")
            except Exception as e:
                print(f"[handle_clarification] ERROR getting questions: {str(e)}")
                st.error(f"Error during topic analysis: {str(e)}")
                return
    
    # Show clarification UI in centered column
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown("### 🤔 Let me understand better...")
        st.info(f"I'd like to understand more about **\"{topic}\"** to create the best learning plan for you.")
        
        # Display questions
        st.markdown("#### 📝 Clarification Questions")
        st.markdown("*Please answer the questions below. Feel free to be as detailed as you'd like, or leave questions blank if they don't apply.*")
        
        # Show all questions
        questions = st.session_state.clarification_questions
        st.markdown("---")
        for i, question in enumerate(questions, 1):
            st.markdown(f"**{i}.** {question}")
        st.markdown("---")
        
        # Single text area for all answers
        user_answers = st.text_area(
            "Your answers:",
            height=200,
            placeholder="Type your answers here. You can answer all questions together or number your responses (1., 2., etc.)",
            key="clarification_answers"
        )
        
        if st.button("✅ Submit Answers", type="primary", use_container_width=True):
            print(f"[handle_clarification] User submitted answers, length: {len(user_answers)} chars")
            
            if not user_answers.strip():
                print("[handle_clarification] Empty answers, using original topic")
                st.warning("No answers provided. Using your original topic.")
                # Use original topic
                start_deep_research(topic, hours)
            else:
                print("[handle_clarification] Processing answers...")
                # Rewrite topic based on answers
                with st.spinner("🔄 Processing your answers..."):
                    try:
                        rewritten_topic = rewrite_topic(
                            st.session_state.original_topic,
                            questions,
                            user_answers
                        )
                        print(f"[handle_clarification] Got rewritten topic: '{rewritten_topic}'")
                        
                        # Clear clarification state
                        if "clarification_questions" in st.session_state:
                            del st.session_state.clarification_questions
                        if "original_topic" in st.session_state:
                            del st.session_state.original_topic
                        if "original_hours" in st.session_state:
                            del st.session_state.original_hours
                        
                        # Start Deep Research with rewritten topic
                        start_deep_research(rewritten_topic, hours)
                    except Exception as e:
                        print(f"[handle_clarification] ERROR rewriting topic: {str(e)}")
                        st.error(f"Error processing your answers: {str(e)}")


def start_deep_research(topic: str, hours: int):
    """Start the Deep Research process"""
    print(f"\n[start_deep_research] Starting deep research for topic: '{topic}'")
    
    # Clear any clarification-related session state
    for key in ["clarification_questions", "original_topic", "original_hours"]:
        if key in st.session_state:
            del st.session_state[key]
    
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
                
                # Navigate to project workspace
                URLManager.navigate_to_project(project_id)
                
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
                # Clear URL on error
                URLManager.navigate_to_welcome()


def show_welcome_screen():
    """Show the welcome/landing screen"""
    # Check if we have clarification parameters in URL
    if hasattr(st.session_state, 'clarification_topic') and st.session_state.clarification_topic:
        # Handle clarification from URL
        handle_clarification(
            st.session_state.clarification_topic,
            st.session_state.clarification_hours
        )
        return
    
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
            
        # Show current URL for debugging (remove in production)
        with st.expander("🔗 Share this page", expanded=False):
            current_url = URLManager.get_shareable_link()
            st.code(current_url, language=None)
            st.caption("Copy this link to bookmark or share your current view")


def show_workspace():
    """Show the main workspace with report and graph"""
    project = get_project(st.session_state.project_id)
    if not project:
        st.error("Project not found!")
        if st.button("Go Back"):
            URLManager.navigate_to_welcome()
            st.rerun()
        return
    
    # Breadcrumb navigation
    col1, col2, col3 = st.columns([1, 6, 1])
    with col1:
        if st.button("🏠 Home", use_container_width=True):
            URLManager.navigate_to_welcome()
            st.rerun()
    
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
                    # Create new session and navigate
                    session_id = create_session(
                        st.session_state.project_id,
                        next_nodes[0]['id']
                    )
                    URLManager.navigate_to_session(session_id)
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
                    # Create new session and navigate
                    session_id = create_session(
                        st.session_state.project_id,
                        selected
                    )
                    URLManager.navigate_to_session(session_id)
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
            
            # Session statistics
            session_stats = get_session_stats(st.session_state.project_id)
            if session_stats["total_sessions"] > 0:
                st.markdown("---")
                st.markdown("### 📈 Session Statistics")
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Total Sessions", session_stats["total_sessions"])
                with col2:
                    st.metric("Completed", session_stats["completed_sessions"])
                with col3:
                    st.metric("Avg Score", f"{int(session_stats['average_score'] * 100)}%")
            
            # Shareable link
            st.markdown("---")
            with st.expander("🔗 Share this project", expanded=False):
                current_url = URLManager.get_shareable_link()
                st.code(current_url, language=None)
                st.caption("Bookmark this link to return to this project anytime")
            
        except Exception as e:
            st.error(f"Error displaying graph: {str(e)}")
            # Show raw graph data as fallback
            with st.expander("Show raw graph data"):
                st.json(graph_data)


def show_tutor_session():
    """Show the tutor session interface with session recovery"""
    if not st.session_state.current_node:
        st.error("No node selected for tutoring")
        if st.button("Go Back"):
            URLManager.navigate_to_project(st.session_state.project_id)
            st.rerun()
        return
    
    # Get node information
    node_info = get_node_with_objectives(st.session_state.current_node)
    if not node_info:
        st.error("Node not found!")
        return
    
    # Check if this is a completed session
    if st.session_state.tutor_session_id:
        session_info = get_session_info(st.session_state.tutor_session_id)
        if session_info and session_info["status"] == "completed":
            # Show read-only completed session
            st.info(f"📚 **Completed Session** - Score: {int(session_info['final_score'] * 100)}%")
    
    # Header
    st.markdown(f"# 🎓 Learning Session: {node_info['label']}")
    
    # Session info in sidebar
    with st.sidebar:
        st.markdown("### 📚 Session Info")
        st.info(f"**Topic:** {node_info['label']}\n\n**Summary:** {node_info['summary']}")
        
        st.markdown("### 📋 Learning Objectives")
        for i, obj in enumerate(node_info['learning_objectives']):
            st.markdown(f"{i+1}. {obj['description']}")
        
        st.markdown("---")
        
        if st.button("🚪 Exit Session", type="secondary", use_container_width=True):
            URLManager.navigate_to_project(st.session_state.project_id)
            st.rerun()
    
    # Check if session was already initialized from URL
    session_initialized_from_url = (
        st.session_state.tutor_session_id and 
        len(st.session_state.messages) > 0
    )
    
    # Initialize or recover session (skip if already initialized from URL)
    if not session_initialized_from_url and "tutor_session_id" not in st.session_state:
        # Check for existing session to recover
        latest_session = get_latest_session_for_node(
            st.session_state.project_id, 
            st.session_state.current_node
        )
        
        if latest_session and st.checkbox("📂 Resume previous session?", value=True):
            # Recover from previous session
            st.session_state.tutor_session_id = latest_session
            
            # Load transcript
            transcript = get_transcript_for_session(latest_session)
            st.session_state.messages = [
                {"role": entry["role"], "content": entry["content"]}
                for entry in transcript
            ]
            st.session_state.turn_count = len(transcript)
            
            # Determine phase from transcript
            if any("Let's see what you've learned" in msg["content"] for msg in st.session_state.messages):
                st.session_state.current_phase = "grade"
            elif len([m for m in st.session_state.messages if m["role"] == "user"]) >= 2:
                st.session_state.current_phase = "quick_check"
            else:
                st.session_state.current_phase = "teach"
            
            st.info("✅ Previous session recovered!")
        else:
            # Start new session (this shouldn't happen if we came from URL)
            st.session_state.tutor_session_id = create_session(
                st.session_state.project_id,
                st.session_state.current_node
            )
            st.session_state.messages = []
            st.session_state.turn_count = 0
            st.session_state.current_phase = "greet"
        
        # Check if user has previous sessions
        st.session_state.has_previous_session = has_previous_sessions(
            st.session_state.project_id,
            st.session_state.tutor_session_id
        )
    
    # Chat interface
    chat_container = st.container()
    
    # Display chat history
    with chat_container:
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
    
    # Check if session is completed (disable input)
    is_completed = False
    if st.session_state.tutor_session_id:
        session_info = get_session_info(st.session_state.tutor_session_id)
        is_completed = session_info and session_info["status"] == "completed"
    
    # Input area (disabled for completed sessions)
    if not is_completed:
        if prompt := st.chat_input("Your response...", key="tutor_chat"):
            # Add user message
            st.session_state.messages.append({
                "role": "user",
                "content": prompt
            })
            
            # Save to transcript
            save_transcript(
                st.session_state.tutor_session_id,
                st.session_state.turn_count,
                "user",
                prompt
            )
            st.session_state.turn_count += 1
            
            # Display user message
            with st.chat_message("user"):
                st.markdown(prompt)
            
            # Run tutor graph
            run_tutor_response()
        
        # If no messages yet, start the session
        elif len(st.session_state.messages) == 0:
            run_tutor_response()
    else:
        st.info("This session has been completed. Start a new session to continue learning!")


def run_tutor_response():
    """Run the tutor graph to generate response with better error handling"""
    from backend.graph import create_tutor_graph, TutorState
    
    # Create the graph
    tutor_graph = create_tutor_graph()
    
    # Initialize state
    state = {
        "session_id": st.session_state.tutor_session_id,
        "node_id": st.session_state.current_node,
        "turn_count": st.session_state.turn_count,
        "has_previous_session": st.session_state.has_previous_session,
        "messages": st.session_state.messages.copy(),
        "learning_objectives": get_node_with_objectives(st.session_state.current_node)['learning_objectives'],
        "lo_scores": {},
        "current_phase": st.session_state.current_phase,
        "node_info": get_node_with_objectives(st.session_state.current_node),
        "project_id": st.session_state.project_id
    }
    
    # Show thinking spinner
    with st.spinner("🤔 Thinking..."):
        try:
            # Run the graph
            result = tutor_graph.invoke(state)
            
            # Extract new messages
            new_messages = result["messages"][len(st.session_state.messages):]
            
            # Update session state
            st.session_state.messages = result["messages"]
            st.session_state.turn_count = result["turn_count"]
            
            # Display new assistant messages
            for msg in new_messages:
                if msg["role"] == "assistant":
                    with st.chat_message("assistant"):
                        st.markdown(msg["content"])
            
            # Check if session is complete
            if "lo_scores" in result and result["lo_scores"]:
                # Calculate final score as average of all LO scores
                final_score = sum(result["lo_scores"].values()) / len(result["lo_scores"])
                
                # Complete the session
                complete_session(st.session_state.tutor_session_id, final_score)
                
                # Session complete, show completion button
                st.balloons()
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("✅ Complete Session", type="primary", use_container_width=True):
                        URLManager.navigate_to_project(st.session_state.project_id)
                        st.rerun()
                with col2:
                    if st.button("📊 View Progress", type="secondary", use_container_width=True):
                        URLManager.navigate_to_project(st.session_state.project_id)
                        st.rerun()
                    
        except openai.AuthenticationError:
            st.error("❌ API key authentication failed. Please check your API key.")
            with st.expander("🔧 Update API Key"):
                new_key = st.text_input("Enter new API key:", type="password")
                if st.button("Update"):
                    if new_key and new_key.startswith("sk-"):
                        save_api_key(new_key)
                        st.session_state.api_key = new_key
                        st.rerun()
        except openai.RateLimitError:
            st.error("⏳ Rate limit reached. Please wait a moment and try again.")
            st.info("Consider upgrading your OpenAI plan for higher rate limits.")
        except Exception as e:
            st.error(f"❌ Error in tutor response: {str(e)}")
            st.info("Try refreshing the page or starting a new session.")
            
            # Show debug info in expander
            with st.expander("🐛 Debug Information"):
                st.json({
                    "session_id": st.session_state.tutor_session_id,
                    "turn_count": st.session_state.turn_count,
                    "current_phase": st.session_state.current_phase,
                    "message_count": len(st.session_state.messages)
                })


def main():
    """Main application entry point"""
    # Initialize session state
    init_session_state()
    
    # Sidebar
    with st.sidebar:
        st.markdown("# 🧠 Autodidact")
        
        if st.session_state.api_key:
            st.success("✅ API Key configured")
            
            with st.expander("⚙️ Settings"):
                if st.button("Clear API Key", type="secondary", use_container_width=True):
                    CONFIG_FILE.unlink(missing_ok=True)
                    st.session_state.api_key = None
                    st.rerun()
        else:
            st.warning("⚠️ API Key not configured")
        
        st.markdown("---")
        
        # New Project button (always visible)
        if st.button("➕ New Project", type="primary", use_container_width=True):
            URLManager.navigate_to_welcome()
            st.rerun()
        
        st.markdown("---")
        
        # List all projects
        st.markdown("### 📚 Your Projects")
        
        all_projects = get_all_projects()
        
        if all_projects:
            # Show current project first if it exists
            if st.session_state.project_id:
                current_project = get_project(st.session_state.project_id)
                if current_project:
                    st.markdown("**Current:**")
                    st.info(f"📖 {current_project['topic']}")
                    st.markdown("---")
            
            # Show other projects
            st.markdown("**All Projects:**")
            for project in all_projects:
                # Skip current project if already shown
                if project['id'] == st.session_state.project_id:
                    continue
                
                # Format creation date
                created = datetime.strptime(project['created_at'], "%Y-%m-%d %H:%M:%S")
                days_ago = (datetime.now() - created).days
                if days_ago == 0:
                    time_str = "Today"
                elif days_ago == 1:
                    time_str = "Yesterday"
                else:
                    time_str = f"{days_ago} days ago"
                
                # Create project button with info
                with st.container():
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        if st.button(
                            f"📚 {project['topic'][:28]}{'...' if len(project['topic']) > 28 else ''}",
                            key=f"proj_{project['id']}",
                            use_container_width=True
                        ):
                            URLManager.navigate_to_project(project['id'])
                            st.rerun()
                    
                    with col2:
                        st.markdown(f"**{project['progress']}%**")
                    
                    # Show additional info below button
                    st.caption(f"📅 {time_str} • {project['total_nodes']} topics • {project['mastered_nodes']} mastered")
        else:
            st.info("No projects yet. Click 'New Project' to start!")
    
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