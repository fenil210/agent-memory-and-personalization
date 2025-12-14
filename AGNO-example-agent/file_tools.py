import os
from pathlib import Path
from typing import List

def list_directory_contents(directory_path: str) -> str:
    try:
        path = Path(directory_path)
        if not path.exists():
            return f"Error: Directory {directory_path} does not exist"
        
        if not path.is_dir():
            return f"Error: {directory_path} is not a directory"
        
        items = []
        for item in sorted(path.iterdir()):
            item_type = "DIR" if item.is_dir() else "FILE"
            items.append(f"{item_type}: {item.name}")
        
        return f"Contents of {directory_path}:\n" + "\n".join(items)
    except Exception as e:
        return f"Error listing directory: {str(e)}"

def read_file_content(file_path: str, max_lines: int = 100) -> str:
    try:
        path = Path(file_path)
        if not path.exists():
            return f"Error: File {file_path} does not exist"
        
        if not path.is_file():
            return f"Error: {file_path} is not a file"
        
        with open(path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            total_lines = len(lines)
            
            if total_lines > max_lines:
                content = ''.join(lines[:max_lines])
                return f"First {max_lines} lines of {file_path} (total {total_lines} lines):\n{content}\n... truncated ..."
            else:
                content = ''.join(lines)
                return f"Content of {file_path} ({total_lines} lines):\n{content}"
    except UnicodeDecodeError:
        return f"Error: Cannot read {file_path} - binary file or unsupported encoding"
    except Exception as e:
        return f"Error reading file: {str(e)}"

def search_files_by_name(directory_path: str, pattern: str) -> str:
    try:
        path = Path(directory_path)
        if not path.exists():
            return f"Error: Directory {directory_path} does not exist"
        
        matches = list(path.rglob(f"*{pattern}*"))
        
        if not matches:
            return f"No files matching '{pattern}' found in {directory_path}"
        
        results = [str(match.relative_to(path)) for match in matches[:50]]
        count_msg = f"Found {len(matches)} matches" + (" (showing first 50)" if len(matches) > 50 else "")
        
        return f"{count_msg} for '{pattern}' in {directory_path}:\n" + "\n".join(results)
    except Exception as e:
        return f"Error searching files: {str(e)}"

def search_in_files(directory_path: str, search_text: str, file_extension: str = "") -> str:
    try:
        path = Path(directory_path)
        if not path.exists():
            return f"Error: Directory {directory_path} does not exist"
        
        pattern = f"*{file_extension}" if file_extension else "*"
        files_to_search = [f for f in path.rglob(pattern) if f.is_file()]
        
        matches = []
        for file_path in files_to_search:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    for line_num, line in enumerate(f, 1):
                        if search_text.lower() in line.lower():
                            rel_path = file_path.relative_to(path)
                            matches.append(f"{rel_path}:{line_num}: {line.strip()}")
                            if len(matches) >= 50:
                                break
            except (UnicodeDecodeError, PermissionError):
                continue
            
            if len(matches) >= 50:
                break
        
        if not matches:
            ext_msg = f" in {file_extension} files" if file_extension else ""
            return f"No matches found for '{search_text}'{ext_msg} in {directory_path}"
        
        count_msg = f"Found {len(matches)} matches"
        return f"{count_msg} for '{search_text}':\n" + "\n".join(matches)
    except Exception as e:
        return f"Error searching in files: {str(e)}"

def get_file_info(file_path: str) -> str:
    try:
        path = Path(file_path)
        if not path.exists():
            return f"Error: {file_path} does not exist"
        
        stat = path.stat()
        size_kb = stat.st_size / 1024
        
        info = [
            f"File: {path.name}",
            f"Path: {path.absolute()}",
            f"Size: {size_kb:.2f} KB",
            f"Type: {'Directory' if path.is_dir() else 'File'}",
        ]
        
        if path.is_file():
            info.append(f"Extension: {path.suffix}")
        
        return "\n".join(info)
    except Exception as e:
        return f"Error getting file info: {str(e)}"

def read_document_content(file_path: str) -> str:
    try:
        from markitdown import MarkItDown
        
        path = Path(file_path)
        if not path.exists():
            return f"Error: {file_path} does not exist"
        
        if not path.is_file():
            return f"Error: {file_path} is not a file"
        
        supported_extensions = {
            '.pdf', '.docx', '.pptx', '.xlsx', '.xls',
            '.doc', '.ppt', '.jpg', '.jpeg', '.png',
            '.html', '.htm', '.csv', '.json', '.xml',
            '.zip', '.wav', '.mp3', '.msg'
        }
        
        if path.suffix.lower() not in supported_extensions:
            return f"Warning: {file_path} may not be supported. Attempting conversion anyway.\nSupported formats: PDF, DOCX, PPTX, XLSX, XLS, images, HTML, CSV, JSON, XML, ZIP, audio, Outlook MSG"
        
        md = MarkItDown()
        result = md.convert(str(path.absolute()))
        
        file_type = path.suffix.upper().replace('.', '')
        return f"{file_type} Content from {path.name}:\n\n{result.text_content}"
    except ImportError:
        return "Error: markitdown library not installed. Run: pip install markitdown"
    except Exception as e:
        return f"Error reading document: {str(e)}"

