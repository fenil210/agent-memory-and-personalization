import os
from pathlib import Path
from dotenv import load_dotenv
from agno.agent import Agent
from agno.models.google import Gemini
from agno.db.sqlite import SqliteDb

load_dotenv()

db = SqliteDb(db_file="assistant.db")

test_agent = Agent(
    name="TestAgent",
    model=Gemini(id="gemini-2.5-flash"),
    db=db,
    enable_user_memories=True,
    user_id="test_user_1",
    markdown=True,
)

print("Testing memory and personalization...")
print("\nSession 1: Teaching the agent about preferences")
response1 = test_agent.run("My name is Alex and I prefer concise bullet-point answers")
print(response1.content)

print("\n" + "="*60)
print("Session 2: Testing memory recall")
response2 = test_agent.run("What is my name and how do I like my answers formatted?")
print(response2.content)

print("\n" + "="*60)
print("Session 3: Adding more preferences")
response3 = test_agent.run("I work with Python and prefer code examples without comments")
print(response3.content)

print("\n" + "="*60)
print("Session 4: Testing combined memory")
response4 = test_agent.run("Show me a quick Python hello world example")
print(response4.content)
