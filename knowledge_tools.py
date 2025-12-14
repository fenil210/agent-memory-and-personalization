"""
Knowledge Base Tools for RAG (Retrieval-Augmented Generation)

This module provides vector-based document indexing and retrieval using:
- Google's gemini-embedding-001 model (768 dimensions)
- LanceDB for vector storage
- Smart chunking strategy for optimal retrieval

SOLID Principles Applied:
- Single Responsibility: Each function has one clear purpose
- Open/Closed: Configuration via constants, extensible design
- Dependency Inversion: Abstracts embedding and storage details
"""

import os
import lancedb
from pathlib import Path
from typing import List, Dict, Optional
import google.generativeai as genai
from markitdown import MarkItDown
from dotenv import load_dotenv

load_dotenv()

# Configuration (SOLID: Open/Closed Principle)
KNOWLEDGE_DB_PATH = "knowledge_db"
EMBEDDING_MODEL = "gemini-embedding-001"  # Gemini embedding model
EMBEDDING_DIMENSION = 768  # Recommended dimension from Google
CHUNK_SIZE_CHARS = 2000  # ~500 tokens
CHUNK_OVERLAP_CHARS = 200  # Overlap between chunks
TASK_TYPE_DOCUMENT = "RETRIEVAL_DOCUMENT"
TASK_TYPE_QUERY = "RETRIEVAL_QUERY"

# Initialize Google AI
genai.configure(api_key=os.getenv('GOOGLE_API_KEY') or os.getenv('GEMINI_API_KEY'))


class DocumentChunker:
    """
    Handles document chunking with overlap (Single Responsibility Principle)
    """
    
    def __init__(self, chunk_size: int = CHUNK_SIZE_CHARS, overlap: int = CHUNK_OVERLAP_CHARS):
        self.chunk_size = chunk_size
        self.overlap = overlap
    
    def chunk_text(self, text: str, source: str) -> List[Dict]:
        """
        Split text into overlapping chunks
        
        Args:
            text: Document text
            source: Source file path
            
        Returns:
            List of chunk dictionaries with text, source, and position
        """
        chunks = []
        start = 0
        chunk_idx = 0
        
        while start < len(text):
            end = start + self.chunk_size
            chunk_text = text[start:end]
            
            # Don't create tiny final chunks
            if len(chunk_text.strip()) < 100:
                break
            
            chunks.append({
                'text': chunk_text.strip(),
                'source': source,
                'chunk_index': chunk_idx,
                'char_start': start,
                'char_end': end
            })
            
            start += self.chunk_size - self.overlap
            chunk_idx += 1
        
        return chunks


class EmbeddingGenerator:
    """
    Generates embeddings using Gemini (Single Responsibility Principle)
    """
    
    def __init__(self, model: str = EMBEDDING_MODEL, dimension: int = EMBEDDING_DIMENSION):
        self.model = model
        self.dimension = dimension
    
    def generate_embedding(self, text: str, task_type: str = TASK_TYPE_DOCUMENT) -> List[float]:
        """
        Generate embedding for text
        
        Args:
            text: Input text
            task_type: Either RETRIEVAL_DOCUMENT or RETRIEVAL_QUERY
            
        Returns:
            Embedding vector
        """
        result = genai.embed_content(
            model=self.model,
            content=text,
            task_type=task_type,
            output_dimensionality=self.dimension
        )
        return result['embedding']
    
    def generate_batch_embeddings(self, texts: List[str], task_type: str = TASK_TYPE_DOCUMENT) -> List[List[float]]:
        """Generate embeddings for multiple texts efficiently"""
        # Gemini supports batch embedding
        embeddings = []
        for text in texts:
            embeddings.append(self.generate_embedding(text, task_type))
        return embeddings


# Tool functions for AGNO agent
def index_document(file_path: str) -> str:
    """
    Index a document into the knowledge base using vector embeddings.
    
    This tool extracts text from a document, chunks it, generates embeddings,
    and stores them in LanceDB for later retrieval.
    
    Args:
        file_path: Path to the document to index
        
    Returns:
        Status message about indexing result
    """
    try:
        path = Path(file_path)
        if not path.exists():
            return f"Error: File {file_path} does not exist"
        
        # Extract text using markitdown
        md = MarkItDown()
        result = md.convert(str(path.absolute()))
        text_content = result.text_content
        
        if not text_content or len(text_content.strip()) < 50:
            return f"Error: Could not extract meaningful text from {file_path}"
        
        # Chunk the document
        chunker = DocumentChunker()
        chunks = chunker.chunk_text(text_content, str(path.absolute()))
        
        if not chunks:
            return f"Error: No chunks created from {file_path}"
        
        # Generate embeddings
        embedder = EmbeddingGenerator()
        chunk_texts = [chunk['text'] for chunk in chunks]
        embeddings = embedder.generate_batch_embeddings(chunk_texts, TASK_TYPE_DOCUMENT)
        
        # Prepare data for LanceDB
        data_for_db = []
        for chunk, embedding in zip(chunks, embeddings):
            data_for_db.append({
                'text': chunk['text'],
                'vector': embedding,
                'source': chunk['source'],
                'chunk_index': chunk['chunk_index'],
                'char_start': chunk['char_start'],
                'char_end': chunk['char_end']
            })
        
        # Store in LanceDB
        db = lancedb.connect(KNOWLEDGE_DB_PATH)
        
        # Check if table exists, create or append
        try:
            table = db.open_table("documents")
            table.add(data_for_db)
        except Exception:
            # Table doesn't exist, create it
            table = db.create_table("documents", data=data_for_db)
        
        return f"Successfully indexed {path.name}: {len(chunks)} chunks created and embedded"
        
    except Exception as e:
        return f"Error indexing document: {str(e)}"


def search_knowledge_base(query: str, num_results: int = 5) -> str:
    """
    Search the knowledge base for relevant information using vector similarity.
    
    Use this tool when you need SPECIFIC information from indexed documents.
    Do NOT use this for summarization tasks - use read_document_content instead.
    
    Args:
        query: Search query (what you're looking for)
        num_results: Number of relevant chunks to retrieve (default: 5)
        
    Returns:
        Retrieved text chunks with source information
    """
    try:
        # Check if knowledge base exists
        db_path = Path(KNOWLEDGE_DB_PATH)
        if not db_path.exists():
            return "Knowledge base not found. Please index some documents first using the index_document tool."
        
        # Generate query embedding
        embedder = EmbeddingGenerator()
        query_embedding = embedder.generate_embedding(query, TASK_TYPE_QUERY)
        
        # Search LanceDB
        db = lancedb.connect(KNOWLEDGE_DB_PATH)
        try:
            table = db.open_table("documents")
        except Exception:
            return "No documents have been indexed yet. Use index_document first."
        
        # Perform vector search
        results = table.search(query_embedding).limit(num_results).to_list()
        
        if not results:
            return f"No relevant information found for query: '{query}'"
        
        # Format results
        output = [f"Found {len(results)} relevant chunks for '{query}':\n"]
        
        for i, result in enumerate(results, 1):
            source = Path(result['source']).name
            chunk_idx = result.get('chunk_index', '?')
            text = result['text'][:500]  # Limit to 500 chars for display
            
            output.append(f"\n--- Result {i} (from {source}, chunk {chunk_idx}) ---")
            output.append(text)
            if len(result['text']) > 500:
                output.append("... (truncated)")
        
        return "\n".join(output)
        
    except Exception as e:
        return f"Error searching knowledge base: {str(e)}"


def get_indexed_documents() -> str:
    """
    Get information about what documents are currently in the knowledge base.
    
    Returns:
        List of indexed documents and statistics
    """
    try:
        db_path = Path(KNOWLEDGE_DB_PATH)
        if not db_path.exists():
            return "Knowledge base is empty (no documents indexed yet)"
        
        db = lancedb.connect(KNOWLEDGE_DB_PATH)
        try:
            table = db.open_table("documents")
            
            # Get all unique sources
            all_data = table.to_pandas()
            sources = all_data['source'].unique()
            total_chunks = len(all_data)
            
            output = [f"Knowledge Base Statistics:"]
            output.append(f"- Total chunks: {total_chunks}")
            output.append(f"- Indexed documents: {len(sources)}")
            output.append(f"\nDocuments:")
            
            for source in sources:
                doc_chunks = all_data[all_data['source'] == source]
                output.append(f"  • {Path(source).name} ({len(doc_chunks)} chunks)")
            
            return "\n".join(output)
            
        except Exception:
            return "Knowledge base is empty (no documents indexed yet)"
            
    except Exception as e:
        return f"Error accessing knowledge base: {str(e)}"
