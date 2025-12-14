"""
Observability module for AGNO Local Assistant

Provides Langfuse integration via OpenTelemetry for session/user tracking.
"""

import os
import base64
from typing import Optional, Dict, Any
from dotenv import load_dotenv

load_dotenv()

# Global state
_observability_initialized = False


def setup_langfuse_observability() -> bool:
    """
    Setup Langfuse observability via OTEL with session/user tracking.
    
    Uses OpenLIT to send traces to Langfuse with proper resource attributes
    for session_id and user_id tracking.
    
    Returns:
        bool: True if setup successful, False otherwise
    """
    global _observability_initialized
    
    if _observability_initialized:
        return True
    
    try:
        # Get credentials
        public_key = os.getenv('LANGFUSE_PUBLIC_KEY')
        secret_key = os.getenv('LANGFUSE_SECRET_KEY')
        host = os.getenv('LANGFUSE_BASE_URL', 'https://cloud.langfuse.com')
        
        if not public_key or not secret_key:
            print("⚠️  Langfuse credentials not configured")
            return False
        
        # Build Basic Auth header for OTEL endpoint
        auth_header = base64.b64encode(
            f"{public_key}:{secret_key}".encode()
        ).decode()
        
        # Configure OTEL to send to Langfuse
        os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = f"{host}/api/public/otel"
        os.environ["OTEL_EXPORTER_OTLP_HEADERS"] = f"Authorization=Basic {auth_header}"
        
        # Initialize OpenLIT
        import openlit
        openlit.init(
            environment="development",
            application_name="local-assistant"
        )
        
        _observability_initialized = True
        
        print(f"✅ Langfuse observability enabled")
        print(f"   Host: {host}")
        print(f"   Method: OpenLIT + OTEL")
        
        return True
        
    except ImportError as e:
        print(f"⚠️  OpenLIT not available: {e}")
        return False
    except Exception as e:
        print(f"⚠️  Failed to setup observability: {e}")
        return False


def set_session_attributes(session_id: str, user_id: str, tags: Optional[list] = None):
    """
    Update OTEL resource attributes with session and user info.
    
    This makes session_id and user_id show up in Langfuse traces.
    Call this when session or user changes.
    
    Args:
        session_id: Session identifier
        user_id: User identifier
        tags: Optional tags (joined as comma-separated string)
    """
    tags_str = ",".join(tags) if tags else "local-assistant,streamlit,agno"
    
    # Set OTEL resource attributes - these get sent with every trace
    os.environ["OTEL_RESOURCE_ATTRIBUTES"] = (
        f"session.id={session_id},"
        f"user.id={user_id},"
        f"deployment.environment.name=development,"
        f"service.name=local-assistant,"
        f"service.tags={tags_str}"
    )


def is_observability_enabled() -> bool:
    """Check if observability has been successfully initialized"""
    return _observability_initialized


def calculate_cost(input_tokens: int, output_tokens: int) -> float:
    """
    Calculate cost for Gemini 2.5 Flash.
    
    Pricing (as of Dec 2024):
    - Input: $0.30 per 1M tokens
    - Output: $2.50 per 1M tokens
    
    Args:
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens
    
    Returns:
        Total cost in USD
    """
    input_cost = (input_tokens / 1_000_000) * 0.30
    output_cost = (output_tokens / 1_000_000) * 2.50
    return input_cost + output_cost

    """
    Setup Langfuse observability with SDK direct integration.
    
    Uses Langfuse SDK for proper session/user tracking.
    
    Returns:
        bool: True if setup successful, False otherwise
    """
    global _observability_initialized, _langfuse_client
    
    if _observability_initialized:
        return True
    
    try:
        # Get credentials
        public_key = os.getenv('LANGFUSE_PUBLIC_KEY')
        secret_key = os.getenv('LANGFUSE_SECRET_KEY')
        host = os.getenv('LANGFUSE_BASE_URL', 'https://cloud.langfuse.com')
        
        if not public_key or not secret_key:
            print("⚠️  Langfuse credentials not configured")
            return False
        
        # Initialize Langfuse SDK (for session/user tracking)
        from langfuse import Langfuse
        _langfuse_client = Langfuse(
            public_key=public_key,
            secret_key=secret_key,
            host=host
        )
        
        # Also initialize OpenLIT for auto-instrumentation
        try:
            import openlit
            
            # Build Basic Auth header
            auth_header = base64.b64encode(
                f"{public_key}:{secret_key}".encode()
            ).decode()
            
            # Configure OTEL
            os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = f"{host}/api/public/otel"
            os.environ["OTEL_EXPORTER_OTLP_HEADERS"] = f"Authorization=Basic {auth_header}"
            
            # Initialize OpenLIT (without disabled param - not supported)
            openlit.init(
                environment="development",
                application_name="local-assistant"
            )
        except Exception as e:
            print(f"⚠️  OpenLIT init warning: {e} (continuing with Langfuse SDK)")
        
        _observability_initialized = True
        
        print(f"✅ Langfuse observability enabled")
        print(f"   Host: {host}")
        print(f"   SDK: Direct integration")
        
        return True
        
    except ImportError as e:
        print(f"⚠️  Langfuse SDK not available: {e}")
        return False
    except Exception as e:
        print(f"⚠️  Failed to setup observability: {e}")
        return False


def get_langfuse_client():
    """Get the Langfuse client instance"""
    return _langfuse_client


def create_trace_context(
    session_id: str,
    user_id: str,
    tags: Optional[list] = None,
    metadata: Optional[Dict[str, Any]] = None
):
    """
    Create Langfuse trace with session and user context.
    
    This uses Langfuse SDK v2 API to create traces with proper session/user tracking.
    
    Args:
        session_id: Session identifier
        user_id: User identifier
        tags: List of tags for filtering
        metadata: Additional metadata
    
    Returns:
        Langfuse trace object or None
    """
    if not _langfuse_client:
        return None
    
    default_tags = ["local-assistant", "streamlit", "agno"]
    if tags:
        default_tags.extend(tags)
    
    try:
        # Langfuse SDK v2 API uses create_trace (not trace)
        trace = _langfuse_client.trace(
            name="agent-interaction",
            session_id=session_id,
            user_id=user_id,
            tags=default_tags,
            metadata=metadata or {}
        )
        return trace
    except AttributeError:
        # Fallback: Try alternative API
        try:
            # Some versions use different method
            trace_id = f"trace-{session_id}-{hash(user_id) % 10000}"
            _langfuse_client.score(
                trace_id=trace_id,
                name="session",
                session_id=session_id,
                user_id=user_id,
                metadata=metadata or {}
            )
            return {"id": trace_id, "session_id": session_id}
        except Exception:
            # If all else fails, just flush to ensure client is connected
            _langfuse_client.flush()
            return {"session_id": session_id, "user_id": user_id}
    except Exception as e:
        print(f"Trace creation error: {e}")
        return None


def is_observability_enabled() -> bool:
    """Check if observability has been successfully initialized"""
    return _observability_initialized


def calculate_cost(input_tokens: int, output_tokens: int) -> float:
    """
    Calculate cost for Gemini 2.5 Flash.
    
    Pricing (as of Dec 2024):
    - Input: $0.30 per 1M tokens
    - Output: $2.50 per 1M tokens
    
    Args:
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens
    
    Returns:
        Total cost in USD
    """
    input_cost = (input_tokens / 1_000_000) * 0.30
    output_cost = (output_tokens / 1_000_000) * 2.50
    return input_cost + output_cost

