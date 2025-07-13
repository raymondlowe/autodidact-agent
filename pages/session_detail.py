"""
Tutor Session page
Interactive learning sessions with AI tutor
"""

import streamlit as st
from backend.db import (
    get_node_with_objectives,
    get_session_info
)
from backend.graph_v04 import create_session_graph


def run_tutor_response(session_info, node_info):
    """Run the v0.4 tutor graph to generate response"""
    from backend.session_state import create_initial_state
    
    # Create the graph
    tutor_graph = create_session_graph()
    
    # Initialize or update state
    if 'graph_state' not in st.session_state:
        # Create initial state for the graph
        state = create_initial_state(
            session_id=session_info['id'],
            project_id=session_info['project_id'],
            node_id=session_info['node_id']
        )
        st.session_state.graph_state = state
    else:
        state = st.session_state.graph_state
    
    # Update messages from UI state
    state['messages'] = st.session_state.messages
    
    # Show thinking spinner
    with st.spinner("🤔 Thinking..."):
        try:
            # Track message count before invocation
            prev_msg_count = len(state['messages'])
            
            # Run the graph with recursion limit
            config = {"recursion_limit": 50}
            for event in tutor_graph.stream(state, config):
                # Update state with latest event
                for node_name, node_state in event.items():
                    state = node_state
                    st.session_state.graph_state = state
            
            # Get new messages
            new_messages = state['messages'][prev_msg_count:]
            
            # Update session state
            st.session_state.messages = state['messages']
            st.session_state.turn_count = state.get('turn_count', 0)
            st.session_state.current_phase = state.get('current_phase', 'teaching')
            
            # Display new assistant messages
            for msg in new_messages:
                if msg["role"] == "assistant":
                    with st.chat_message("assistant"):
                        st.markdown(msg["content"])
                    
                    # Note: Transcript saving is now handled by the graph's SessionLogger
            
            # Check if session is complete
            if state.get('current_phase') == 'completed':
                # Get final score
                final_score = sum(state.get('objective_scores', {}).values()) / len(state['objective_scores']) if state.get('objective_scores') else 0
                
                # Session complete, show completion message
                st.balloons()
                st.success(f"🎉 **Session Complete!** Your score: {int(final_score * 100)}%")
                
                # Show completion buttons
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("✅ Back to Project", type="primary", use_container_width=True):
                        st.session_state.selected_project_id = session_info['project_id']
                        st.switch_page("pages/project_detail.py")
                
                with col2:
                    if st.button("📊 View Progress", type="secondary", use_container_width=True):
                        st.session_state.selected_project_id = session_info['project_id']
                        st.switch_page("pages/project_detail.py")
                    
        except Exception as e:
            if "AuthenticationError" in str(type(e)):
                st.error("❌ API key authentication failed. Please check your API key in Settings.")
                if st.button("Go to Settings"):
                    st.switch_page("pages/settings.py")
            elif "RateLimitError" in str(type(e)):
                st.error("⏳ Rate limit reached. Please wait a moment and try again.")
                st.info("Consider upgrading your OpenAI plan for higher rate limits.")
            elif "GraphRecursionError" in str(type(e)):
                st.error("⚠️ Session is taking too long. The conversation might be stuck in a loop.")
                st.info("Try refreshing the page or starting a new session.")
            else:
                st.error(f"❌ Error in tutor response: {str(e)}")
                st.info("Try refreshing the page or starting a new session.")
            
            # Show debug info in expander
            with st.expander("🐛 Debug Information"):
                st.json({
                    "session_id": session_info['id'],
                    "current_phase": state.get('current_phase', 'unknown'),
                    "message_count": len(st.session_state.messages),
                    "objectives_to_teach": len(state.get('objectives_to_teach', [])),
                    "completed_objectives": len(state.get('completed_objectives', set()))
                })


# Get session info from URL or session state
project_id = st.query_params.get("project_id")
session_id = st.query_params.get("session_id")

# If not in URL but we have them in session state, set them in URL
if not project_id and "selected_project_id" in st.session_state:
    project_id = st.session_state.selected_project_id
    st.query_params["project_id"] = project_id
    del st.session_state.selected_project_id

if not session_id and "selected_session_id" in st.session_state:
    session_id = st.session_state.selected_session_id
    st.query_params["session_id"] = session_id
    del st.session_state.selected_session_id

if not project_id or not session_id:
    st.error("Invalid session URL!")
    if st.button("Go to Projects"):
        st.switch_page("pages/home.py")
    st.stop()

# Get session information
session_info = get_session_info(session_id)
if not session_info:
    st.error("Session not found!")
    if st.button("Go to Project"):
        if project_id:
            st.session_state.selected_project_id = project_id
            st.switch_page("pages/project_detail.py")
        else:
            st.switch_page("pages/home.py")
    st.stop()

# Initialize session state for this session
if "messages" not in st.session_state:
    st.session_state.messages = []
# Remove the graph_state initialization - let run_tutor_response handle it

# Get node information
node_info = get_node_with_objectives(session_info['node_id'])
if not node_info:
    st.error("Node information not found!")
    st.stop()

# Check if this is a completed session
is_completed = session_info["status"] == "completed"

# Header
if is_completed:
    st.info(f"📚 **Completed Session** - Score: {int(session_info['final_score'] * 100)}%")
st.markdown(f"# 🎓 Learning Session: {node_info['label']}")

# Session control buttons
col1, col2 = st.columns(2)
with col1:
    if st.button("🚪 Exit Session", type="secondary", use_container_width=True):
        st.session_state.selected_project_id = project_id
        st.switch_page("pages/project_detail.py")

with col2:
    if not is_completed and st.session_state.get('graph_state'):
        # Only show early end if session is active and we've started teaching
        if st.session_state.graph_state.get('current_phase') in ['teaching', 'final_test']:
            if st.button("⏹️ End Session Early", type="secondary", use_container_width=True):
                # Set the force end flag and run the graph
                st.session_state.graph_state['force_end_session'] = True
                st.session_state.messages.append({
                    "role": "user",
                    "content": "I'd like to end the session early please."
                })
                st.rerun()

st.markdown("---")

# Two-column layout for main content
col1, col2 = st.columns([1, 3])

with col1:
    # Session info
    st.markdown("### 📚 Session Info")
    st.info(f"**Topic:** {node_info['label']}")
    
    st.markdown("### 📋 Learning Objectives")
    for i, obj in enumerate(node_info['learning_objectives'], 1):
        st.markdown(f"{i}. {obj['description']}")

with col2:
    # Chat interface - all contained within this column
    
    # Create a container for chat messages
    chat_container = st.container()
    
    # Display all messages in the container
    with chat_container:
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
    
    # Input area (disabled for completed sessions)
    if not is_completed:
        if prompt := st.chat_input("Your response...", key="tutor_chat"):
            # Add user message to session state
            st.session_state.messages.append({
                "role": "user",
                "content": prompt
            })
            
            # Display user message in the chat container
            with chat_container:
                with st.chat_message("user"):
                    st.markdown(prompt)
            
            # Run tutor graph
            run_tutor_response(session_info, node_info)
        
        # If no messages yet, start the session
        elif len(st.session_state.messages) == 0:
            run_tutor_response(session_info, node_info)
    else:
        st.info("This session has been completed. Exit to start a new session on a different topic!")