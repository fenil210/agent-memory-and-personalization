import streamlit as st
import os
import yaml
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from agno.agent import Agent
from agno.models.google import Gemini
from agno.db.sqlite import SqliteDb
from file_tools import (
    list_directory_contents,
    read_file_content,
    search_files_by_name,
    search_in_files,
    get_file_info,
    read_document_content
)
from agno.tools.reasoning import ReasoningTools
from knowledge_tools import (
    index_document,
    search_knowledge_base,
    get_indexed_documents
)

load_dotenv()

# Initialize Langfuse observability (OpenLIT + OTEL)
from observability import (
    setup_langfuse_observability, 
    is_observability_enabled, 
    calculate_cost,
    set_session_attributes
)

LANGFUSE_ENABLED = setup_langfuse_observability()

# Configuration constants (SOLID: Open/Closed Principle)
MAX_HISTORY_LENGTH = 10  # Compress history after this many messages
COMPRESS_KEEP_RECENT = 4  # Keep this many recent messages uncompressed

# Load instructions function
def load_instructions(yaml_path: str = "instructions.yaml") -> list:
    try:
        with open(yaml_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        instructions = []
        
        if 'system' in config and 'role' in config['system']:
            instructions.append(config['system']['role'])
        
        if 'core_principles' in config:
            instructions.extend(config['core_principles'])
        
        for category, items in config.get('behavioral_guidelines', {}).items():
            if isinstance(items, list):
                instructions.extend(items)
            elif isinstance(items, dict):
                for subcategory, subitems in items.items():
                    if isinstance(subitems, list):
                        instructions.extend(subitems)
        
        for category, items in config.get('advanced_capabilities', {}).items():
            if isinstance(items, list):
                instructions.extend(items)
        
        if 'error_handling' in config:
            instructions.extend(config['error_handling'])
        
        if 'prohibited_behaviors' in config:
            instructions.extend(config['prohibited_behaviors'])
        
        if 'quality_standards' in config:
            instructions.extend(config['quality_standards'])
        
        return instructions
    
    except Exception as e:
        return [
            "You are a helpful local file assistant.",
            "Be proactive and use the available tools to help users with their files."
        ]

# Session management functions (SOLID: Single Responsibility Principle)
def compress_chat_history(agent: Agent, chat_history: list, max_length: int, keep_recent: int) -> list:
    """
    Compress old chat messages into a summary to manage context window.
    
    Args:
        agent: Agent instance to generate summary
        chat_history: List of chat messages
        max_length: Maximum history length before compression
        keep_recent: Number of recent messages to preserve
    
    Returns:
        Compressed chat history with summary
    """
    if len(chat_history) <= max_length:
        return chat_history
    
    # Separate old and recent messages
    old_messages = chat_history[:len(chat_history) - keep_recent]
    recent_messages = chat_history[len(chat_history) - keep_recent:]
    
    # Build conversation text from old messages
    conversation_text = "\n".join([
        f"{msg['role']}: {msg['content'][:200]}..." if len(msg['content']) > 200 else f"{msg['role']}: {msg['content']}"
        for msg in old_messages
        if msg['role'] in ['user', 'assistant']
    ])
    
    # Generate summary
    try:
        summary_response = agent.run(
            f"Provide a concise summary of this conversation (2-3 sentences):\n\n{conversation_text}"
        )
        
        # Create summary message
        summary_msg = {
            'role': 'summary',
            'content': summary_response.content,
            'is_summary': True
        }
        
        return [summary_msg] + recent_messages
    except Exception as e:
        # If summarization fails, just return original history
        return chat_history

# Page config
st.set_page_config(
    page_title="Local File Assistant",
    page_icon="🤖",
    layout="wide"
)

# Initialize session state
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []

if 'user_id' not in st.session_state:
    st.session_state.user_id = "user_fenil"

# Generate session_id for Langfuse trace grouping
if 'session_id' not in st.session_state:
    # Create unique session ID: timestamp + random UUID
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    st.session_state.session_id = f"session_{timestamp}_{uuid.uuid4().hex[:8]}"
    
    # Set OTEL resource attributes for session/user tracking in Langfuse
    if LANGFUSE_ENABLED:
        set_session_attributes(
            session_id=st.session_state.session_id,
            user_id=st.session_state.user_id,
            tags=["file-assistant", "rag", "streamlit"]
        )

# Initialize session stats for cost tracking
if 'total_tokens' not in st.session_state:
    st.session_state.total_tokens = 0
if 'total_input_tokens' not in st.session_state:
    st.session_state.total_input_tokens = 0
if 'total_output_tokens' not in st.session_state:
    st.session_state.total_output_tokens = 0
if 'total_requests' not in st.session_state:
    st.session_state.total_requests = 0

if 'agent' not in st.session_state:
    db = SqliteDb(db_file="assistant.db")
    st.session_state.agent = Agent(
        name="LocalFileAssistant",
        model=Gemini(id="gemini-2.5-flash"),
        db=db,
        enable_user_memories=True,
        user_id=st.session_state.user_id,
        tools=[
            list_directory_contents,
            read_file_content,
            search_files_by_name,
            search_in_files,
            get_file_info,
            read_document_content,
            ReasoningTools(),  # Enable explicit chain-of-thought reasoning
            index_document,  # RAG: Index documents into knowledge base
            search_knowledge_base,  # RAG: Search indexed documents
            get_indexed_documents  # RAG: View what's indexed
        ],
        description="An intelligent local file system assistant with comprehensive directory access, contextual memory, and proactive analysis capabilities.",
        instructions=load_instructions(),
        markdown=True
    )

# Sidebar
with st.sidebar:
    st.title("⚙️ Settings")
    
    # User ID selector
    new_user_id = st.text_input("User ID", value=st.session_state.user_id, key="user_id_input")
    
    if new_user_id != st.session_state.user_id:
        st.session_state.user_id = new_user_id
        
        # Update OTEL attributes with new user_id
        if LANGFUSE_ENABLED:
            set_session_attributes(
                session_id=st.session_state.session_id,
                user_id=st.session_state.user_id,
                tags=["file-assistant", "rag", "streamlit"]
            )
        
        # Recreate agent with new user_id
        db = SqliteDb(db_file="assistant.db")
        st.session_state.agent = Agent(
            name="LocalFileAssistant",
            model=Gemini(id="gemini-2.5-flash"),
            db=db,
            enable_user_memories=True,
            user_id=st.session_state.user_id,
            tools=[
                list_directory_contents,
                read_file_content,
                search_files_by_name,
                search_in_files,
                get_file_info,
                read_document_content
            ],
            description="An intelligent local file system assistant with comprehensive directory access, contextual memory, and proactive analysis capabilities.",
            instructions=load_instructions(),
            markdown=True
        )
        st.rerun()
    
    st.divider()
    
    # Session Information
    st.subheader("🎯 Session Info")
    
    st.caption("**Session ID:**")
    st.code(st.session_state.session_id, language="text")
    
    st.caption("**Current User:**")
    st.code(st.session_state.user_id, language="text")
    
    if st.button("Start New Session", use_container_width=True):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        st.session_state.session_id = f"session_{timestamp}_{uuid.uuid4().hex[:8]}"
        
        # Update OTEL attributes for new session
        if LANGFUSE_ENABLED:
            set_session_attributes(
                session_id=st.session_state.session_id,
                user_id=st.session_state.user_id,
                tags=["file-assistant", "rag", "streamlit"]
            )
        
        st.session_state.chat_history = []
        st.session_state.total_tokens = 0
        st.session_state.total_input_tokens = 0
        st.session_state.total_output_tokens = 0
        st.session_state.total_requests = 0
        
        st.success("✅ New session started!")
        st.rerun()
    
    st.divider()
    
    # Session Statistics & Cost Tracking
    st.subheader("📊 Session Stats")
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Total Requests", st.session_state.total_requests)
    with col2:
        st.metric("Total Tokens", f"{st.session_state.total_tokens:,}")
    
    # Show token breakdown
    with st.expander("Token Breakdown", expanded=False):
        st.caption(f"Input: {st.session_state.total_input_tokens:,} tokens")
        st.caption(f"Output: {st.session_state.total_output_tokens:,} tokens")
    
    # Accurate cost calculation (Gemini 2.5 Flash pricing)
    # Input: $0.30/1M tokens, Output: $2.50/1M tokens
    total_cost = calculate_cost(
        st.session_state.total_input_tokens,
        st.session_state.total_output_tokens
    )
    st.metric("Estimated Cost", f"${total_cost:.4f}")
    
    if LANGFUSE_ENABLED:
        st.success("✅ Langfuse monitoring active")
        st.caption("View detailed traces at [langfuse.com](https://cloud.langfuse.com)")
    else:
        st.warning("⚠️ Langfuse not configured")
    
    if st.button("Reset Stats", use_container_width=True):
        st.session_state.total_tokens = 0
        st.session_state.total_input_tokens = 0
        st.session_state.total_output_tokens = 0
        st.session_state.total_requests = 0
        st.rerun()
    
    st.divider()
    
    # Knowledge Base Section
    st.subheader("🧠 Knowledge Base (RAG)")
    
    # Show indexed documents count
    if st.button("View Indexed Documents", use_container_width=True):
        result = get_indexed_documents()
        st.text_area("Knowledge Base Status", result, height=150)
    
    st.caption("💡 Index documents to enable efficient semantic search")
    
    st.divider()
    
    # Memory Viewer
    st.subheader("💾 Memory Viewer")
    
    if st.button("View Memories", use_container_width=True):
        try:
            conn = sqlite3.connect('assistant.db')
            conn.row_factory = sqlite3.Row  # Enable column access by name
            cursor = conn.cursor()
            
            # Query agno_memories table directly
            try:
                cursor.execute("""
                    SELECT * FROM agno_memories 
                    WHERE user_id = ? 
                    ORDER BY created_at DESC
                """, (st.session_state.user_id,))
                
                memories = cursor.fetchall()
                
                if memories:
                    st.success(f"Found **{len(memories)}** memories for user: **{st.session_state.user_id}**")
                    
                    for i, mem in enumerate(memories, 1):
                        with st.expander(f"💭 Memory #{i}", expanded=i==1):
                            # Display each field
                            for key in mem.keys():
                                if key == 'memory' or key == 'content':
                                    st.markdown(f"**{key.title()}:**")
                                    st.info(mem[key])
                                elif key in ['created_at', 'updated_at']:
                                    from datetime import datetime
                                    try:
                                        # Try to format timestamp
                                        ts = datetime.fromtimestamp(mem[key])
                                        st.caption(f"{key}: {ts.strftime('%Y-%m-%d %H:%M:%S')}")
                                    except:
                                        st.caption(f"{key}: {mem[key]}")
                                else:
                                    st.write(f"**{key}:** {mem[key]}")
                else:
                    st.warning(f"No memories found for user: **{st.session_state.user_id}**")
                    st.info("💡 Try chatting with the assistant and mentioning your preferences!\n\nExample: *'My name is Alex and I prefer concise answers'*")
                    
            except sqlite3.OperationalError as e:
                st.error(f"Could not query agno_memories table: {e}")
                
                # Fallback: show what tables exist
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
                tables = cursor.fetchall()
                st.write("**Available tables:**")
                for table in tables:
                    st.code(table['name'])
            
            conn.close()
            
        except Exception as e:
            st.error(f"Database error: {e}")
    
    if st.button("Clear Chat History", use_container_width=True):
        st.session_state.chat_history = []
        st.rerun()

# Main area
st.title("🤖 Local File Assistant")
st.caption(f"User: **{st.session_state.user_id}**")

# Chat container
chat_container = st.container()

with chat_container:
    for msg in st.session_state.chat_history:
        if msg['role'] == 'user':
            with st.chat_message("user"):
                st.markdown(msg['content'])
        
        elif msg['role'] == 'assistant':
            with st.chat_message("assistant"):
                # Display tool calls first (if any)
                if 'tool_calls' in msg and msg['tool_calls']:
                    for tool_exec in msg['tool_calls']:
                        # Special display for reasoning tool
                        if 'think' in tool_exec.tool_name.lower() or 'reason' in tool_exec.tool_name.lower():
                            with st.expander("🧠 Agent Reasoning", expanded=False):
                                st.markdown("**Thought Process:**")
                                st.info(tool_exec.result)
                                if tool_exec.tool_args:
                                    with st.expander("View reasoning parameters", expanded=False):
                                        st.json(tool_exec.tool_args)
                        else:
                            # Regular tool display
                            with st.expander(f"🔧 Tool: **{tool_exec.tool_name}**", expanded=False):
                                st.write("**Arguments:**")
                                st.json(tool_exec.tool_args)
                                st.write("**Result:**")
                                st.code(tool_exec.result, language="text")
                
                # Display final response
                st.markdown(msg['content'])
        
        elif msg['role'] == 'summary':
            # Display compressed conversation summary with special styling
            with st.chat_message("assistant", avatar="📋"):
                st.info(f"**Earlier Conversation Summary:**\n\n{msg['content']}")
                st.caption("_Older messages were compressed to maintain context efficiency_")

# Chat input
user_input = st.chat_input("Ask me about your files...")

if user_input:
    # Add user message to history
    st.session_state.chat_history.append({
        'role': 'user',
        'content': user_input
    })
    
    # Get agent response (OTEL attributes already set, will auto-trace to Langfuse)
    with st.spinner("Thinking..."):
        response = st.session_state.agent.run(user_input)
    
    # Track metrics for accurate cost monitoring
    if hasattr(response, 'metrics') and response.metrics:
        st.session_state.total_tokens += response.metrics.total_tokens
        st.session_state.total_input_tokens += response.metrics.input_tokens
        st.session_state.total_output_tokens += response.metrics.output_tokens
        st.session_state.total_requests += 1
    
    # Add assistant response to history
    st.session_state.chat_history.append({
        'role': 'assistant',
        'content': response.content,
        'tool_calls': response.tools if response.tools else []
    })
    
    # Auto-compress history if it gets too long
    st.session_state.chat_history = compress_chat_history(
        st.session_state.agent,
        st.session_state.chat_history,
        MAX_HISTORY_LENGTH,
        COMPRESS_KEEP_RECENT
    )
    
    st.rerun()
