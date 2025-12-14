import os
import yaml
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
    
    except FileNotFoundError:
        print(f"Warning: {yaml_path} not found. Using default instructions.")
        return [
            "You are a helpful local file assistant.",
            "Be proactive and use the available tools to help users with their files."
        ]
    except Exception as e:
        print(f"Error loading instructions: {e}. Using default instructions.")
        return [
            "You are a helpful local file assistant.",
            "Be proactive and use the available tools to help users with their files."
        ]

db = SqliteDb(db_file="assistant.db")

agent = Agent(
    name="LocalFileAssistant",
    model=Gemini(id="gemini-2.5-flash"),
    db=db,
    enable_user_memories=True,
    user_id="user_fenil",
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

def main():
    print("Local File Assistant initialized")
    print("Loaded instructions from instructions.yaml")
    print("Type 'exit' to quit\n")
    
    while True:
        user_input = input("You: ").strip()
        
        if user_input.lower() in ['exit', 'quit', 'bye']:
            print("Assistant: Goodbye!")
            break
        
        if not user_input:
            continue
        
        agent.print_response(user_input)
        print()

if __name__ == "__main__":
    main()