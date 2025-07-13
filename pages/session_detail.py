"""
Tutor Session page
Interactive learning sessions with AI tutor
"""

import streamlit as st
import openai
from backend.db import (
    get_node_with_objectives,
    save_transcript,
    get_latest_session_for_node,
    get_transcript_for_session,
    has_previous_sessions,
    complete_session,
    get_session_info
)
from backend.graph import create_tutor_graph


def run_tutor_response(session_info, node_info):
    """Run the tutor graph to generate response"""
    
    # Check if user has previous sessions
    has_prev = has_previous_sessions(
        session_info['project_id'],
        session_info['id']
    )
    
    # Create the graph
    tutor_graph = create_tutor_graph()
    
    # Convert messages to dict format before passing to graph
    def convert_message(msg):
        if hasattr(msg, 'content') and hasattr(msg, 'type'):
            return {"role": "assistant" if msg.type == "ai" else "user", "content": msg.content}
        return msg
    
    # Initialize state
    state = {
        "session_id": session_info['id'],
        "node_id": session_info['node_id'],
        "turn_count": st.session_state.turn_count,
        "has_previous_session": has_prev,
        "messages": [convert_message(msg) for msg in st.session_state.messages],
        "learning_objectives": node_info['learning_objectives'],
        "lo_scores": {},
        "current_phase": st.session_state.current_phase,
        "node_info": node_info,
        "project_id": session_info['project_id']
    }
    
    # Show thinking spinner
    with st.spinner("🤔 Thinking..."):
        try:
            # Run the graph
            result = tutor_graph.invoke(state)
            
            # Extract new messages and convert to dict format
            new_messages = result["messages"][len(st.session_state.messages):]
            
            # Update session state with converted messages
            st.session_state.messages = [convert_message(msg) for msg in result["messages"]]
            st.session_state.turn_count = result["turn_count"]
            
            # Display new assistant messages
            for msg in new_messages:
                converted_msg = convert_message(msg)
                if converted_msg["role"] == "assistant":
                    with st.chat_message("assistant"):
                        st.markdown(converted_msg["content"])
                    
                    # Save to transcript
                    save_transcript(
                        session_info['id'],
                        st.session_state.turn_count - 1,
                        "assistant",
                        converted_msg["content"]
                    )
            
            # Check if session is complete
            if "lo_scores" in result and result["lo_scores"]:
                # Calculate final score as average of all LO scores
                final_score = sum(result["lo_scores"].values()) / len(result["lo_scores"])
                
                # Complete the session
                complete_session(session_info['id'], final_score)
                
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
                    
        except openai.AuthenticationError:
            st.error("❌ API key authentication failed. Please check your API key in Settings.")
            if st.button("Go to Settings"):
                st.switch_page("pages/settings.py")
        except openai.RateLimitError:
            st.error("⏳ Rate limit reached. Please wait a moment and try again.")
            st.info("Consider upgrading your OpenAI plan for higher rate limits.")
        except Exception as e:
            st.error(f"❌ Error in tutor response: {str(e)}")
            st.info("Try refreshing the page or starting a new session.")
            
            # Show debug info in expander
            with st.expander("🐛 Debug Information"):
                st.json({
                    "session_id": session_info['id'],
                    "turn_count": st.session_state.turn_count,
                    "current_phase": st.session_state.current_phase,
                    "message_count": len(st.session_state.messages)
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
if "turn_count" not in st.session_state:
    st.session_state.turn_count = 0
if "current_phase" not in st.session_state:
    st.session_state.current_phase = "greet"

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

# Exit button
if st.button("🚪 Exit Session", type="secondary"):
    st.session_state.selected_project_id = project_id
    st.switch_page("pages/project_detail.py")

st.markdown("---")

# Two-column layout
col1, col2 = st.columns([1, 3])

with col1:
    # Session info
    st.markdown("### 📚 Session Info")
    st.info(f"**Topic:** {node_info['label']}\n\n**Summary:** {node_info['summary']}")
    
    st.markdown("### 📋 Learning Objectives")
    for i, obj in enumerate(node_info['learning_objectives'], 1):
        st.markdown(f"{i}. {obj['description']}")

with col2:
    # Chat interface
    chat_container = st.container()
    
    # Load existing messages if recovering session
    if len(st.session_state.messages) == 0 and session_info["status"] == "in_progress":
        # Load transcript
        transcript = get_transcript_for_session(session_id)
        if transcript:
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
    
    # Display chat history
    with chat_container:
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
    
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
                session_id,
                st.session_state.turn_count,
                "user",
                prompt
            )
            st.session_state.turn_count += 1
            
            # Display user message
            with st.chat_message("user"):
                st.markdown(prompt)
            
            # Run tutor graph
            run_tutor_response(session_info, node_info)
        
        # If no messages yet, start the session
        elif len(st.session_state.messages) == 0:
            run_tutor_response(session_info, node_info)
    else:
        st.info("This session has been completed. Exit to start a new session on a different topic!")