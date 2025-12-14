import streamlit as st
import os
import yaml
import sqlite3
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

load_dotenv()

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
            read_document_content
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
                        with st.expander(f"🔧 Tool: **{tool_exec.tool_name}**", expanded=False):
                            st.write("**Arguments:**")
                            st.json(tool_exec.tool_args)
                            st.write("**Result:**")
                            st.code(tool_exec.result, language="text")
                
                # Display final response
                st.markdown(msg['content'])

# Chat input
user_input = st.chat_input("Ask me about your files...")

if user_input:
    # Add user message to history
    st.session_state.chat_history.append({
        'role': 'user',
        'content': user_input
    })
    
    # Get agent response
    with st.spinner("Thinking..."):
        response = st.session_state.agent.run(user_input)
    
    # Add assistant response to history
    st.session_state.chat_history.append({
        'role': 'assistant',
        'content': response.content,
        'tool_calls': response.tools if response.tools else []
    })
    
    st.rerun()
