import os
from dotenv import load_dotenv
from agno.agent import Agent
from agno.models.google import Gemini
from file_tools import list_directory_contents

load_dotenv()

# Minimal agent for testing
agent = Agent(
    model=Gemini(id="gemini-2.5-flash"),
    tools=[list_directory_contents],
    markdown=True
)

print("Running agent with specific path to force tool call...")
# Give it a concrete path so it WILL call the tool
response = agent.run("List the files in D:\\Project_32_antigravity\\AGNO-example-agent")

print("\n=== RESPONSE ANALYSIS ===\n")

print("--- Final Content (what user sees) ---")
print(response.content)

print("\n--- All Messages in Conversation ---")
for i, msg in enumerate(response.messages):
    print(f"\n[Message {i}] Role: {msg.role}")
    if msg.content:
        print(f"  Content: {msg.content[:100]}...")  # First 100 chars
    
    # Check for tool calls
    if msg.tool_calls:
        print(f"  Tool Calls: {msg.tool_calls}")
    
    if msg.tool_name:
        print(f"  Tool Name: {msg.tool_name}")
    
    if msg.tool_args:
        print(f"  Tool Args: {msg.tool_args}")
    
    if msg.tool_call_id:
        print(f"  Tool Call ID: {msg.tool_call_id}")

print("\n--- Tools Used (from response.tools) ---")
if response.tools:
    for tool in response.tools:
        print(tool)
