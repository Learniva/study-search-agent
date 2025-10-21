"""
Response Streaming Utilities

Enables streaming of LLM responses for better perceived performance.
Supports both async generators and Server-Sent Events (SSE).
"""

import asyncio
from typing import AsyncGenerator, Optional, Any, Dict
from datetime import datetime


class StreamingResponse:
    """
    Wrapper for streaming LLM responses.
    
    Enables progressive delivery of responses as they're generated,
    improving perceived performance significantly.
    """
    
    def __init__(self, response_generator: AsyncGenerator[str, None]):
        """
        Initialize streaming response.
        
        Args:
            response_generator: Async generator that yields response chunks
        """
        self.generator = response_generator
        self.start_time = datetime.now()
        self.chunks_sent = 0
        self.total_chars = 0
    
    async def stream(self) -> AsyncGenerator[str, None]:
        """
        Stream response chunks.
        
        Yields:
            Response chunks as they're generated
        """
        async for chunk in self.generator:
            self.chunks_sent += 1
            self.total_chars += len(chunk)
            yield chunk
    
    def get_stats(self) -> Dict[str, Any]:
        """Get streaming statistics."""
        elapsed = (datetime.now() - self.start_time).total_seconds()
        return {
            "chunks_sent": self.chunks_sent,
            "total_characters": self.total_chars,
            "elapsed_seconds": elapsed,
            "chars_per_second": self.total_chars / elapsed if elapsed > 0 else 0
        }


async def stream_llm_response(llm: Any, messages: list) -> AsyncGenerator[str, None]:
    """
    Stream LLM response chunks as they're generated.
    
    Args:
        llm: LLM instance (must support streaming)
        messages: List of messages for the LLM
        
    Yields:
        Response chunks
    """
    try:
        # Check if LLM supports streaming
        if hasattr(llm, 'astream'):
            # Use async streaming if available
            async for chunk in llm.astream(messages):
                if hasattr(chunk, 'content'):
                    yield chunk.content
                else:
                    yield str(chunk)
        elif hasattr(llm, 'stream'):
            # Use sync streaming with async wrapper
            for chunk in llm.stream(messages):
                if hasattr(chunk, 'content'):
                    yield chunk.content
                else:
                    yield str(chunk)
                # Small delay to prevent blocking
                await asyncio.sleep(0.001)
        else:
            # Fallback: no streaming, return full response
            response = await asyncio.to_thread(llm.invoke, messages)
            if hasattr(response, 'content'):
                yield response.content
            else:
                yield str(response)
    
    except Exception as e:
        yield f"\n\n[Streaming error: {str(e)}]"


def format_sse_message(data: str, event: Optional[str] = None) -> str:
    """
    Format a message for Server-Sent Events (SSE).
    
    Args:
        data: Message content
        event: Optional event type
        
    Returns:
        Formatted SSE message
    """
    message = ""
    if event:
        message += f"event: {event}\n"
    message += f"data: {data}\n\n"
    return message


async def stream_with_progress(
    generator: AsyncGenerator[str, None],
    progress_callback: Optional[callable] = None,
    chunk_size: int = 50
) -> AsyncGenerator[str, None]:
    """
    Stream with progress tracking.
    
    Args:
        generator: Source async generator
        progress_callback: Optional callback for progress updates
        chunk_size: Characters per progress update
        
    Yields:
        Response chunks with progress tracking
    """
    total_chars = 0
    chunk_buffer = ""
    
    async for chunk in generator:
        chunk_buffer += chunk
        total_chars += len(chunk)
        
        # Send progress update every chunk_size characters
        if len(chunk_buffer) >= chunk_size:
            yield chunk_buffer
            
            if progress_callback:
                progress_callback(total_chars, chunk_buffer)
            
            chunk_buffer = ""
    
    # Send remaining buffer
    if chunk_buffer:
        yield chunk_buffer
        if progress_callback:
            progress_callback(total_chars, chunk_buffer)


class ChunkedStreamBuffer:
    """
    Buffer for managing chunked streaming responses.
    
    Helps smooth out streaming for better UX by accumulating small chunks.
    """
    
    def __init__(self, min_chunk_size: int = 20, max_buffer_time: float = 0.5):
        """
        Initialize buffer.
        
        Args:
            min_chunk_size: Minimum characters before sending chunk
            max_buffer_time: Maximum seconds to buffer before sending
        """
        self.min_chunk_size = min_chunk_size
        self.max_buffer_time = max_buffer_time
        self.buffer = ""
        self.last_send_time = datetime.now()
    
    def add(self, text: str) -> Optional[str]:
        """
        Add text to buffer and return chunk if ready to send.
        
        Args:
            text: Text to add
            
        Returns:
            Chunk to send, or None if not ready
        """
        self.buffer += text
        
        # Send if buffer is large enough or time limit reached
        time_since_send = (datetime.now() - self.last_send_time).total_seconds()
        
        if len(self.buffer) >= self.min_chunk_size or time_since_send >= self.max_buffer_time:
            chunk = self.buffer
            self.buffer = ""
            self.last_send_time = datetime.now()
            return chunk
        
        return None
    
    def flush(self) -> Optional[str]:
        """
        Flush remaining buffer.
        
        Returns:
            Final chunk, or None if empty
        """
        if self.buffer:
            chunk = self.buffer
            self.buffer = ""
            return chunk
        return None


async def simulate_streaming(text: str, delay: float = 0.05) -> AsyncGenerator[str, None]:
    """
    Simulate streaming for non-streaming LLMs (for testing/demo).
    
    Args:
        text: Full text to stream
        delay: Delay between chunks in seconds
        
    Yields:
        Text chunks
    """
    words = text.split()
    for word in words:
        yield word + " "
        await asyncio.sleep(delay)


# Streaming configuration
STREAMING_CONFIG = {
    "min_chunk_size": 20,  # Minimum characters per chunk
    "max_buffer_time": 0.5,  # Maximum seconds to buffer
    "chunk_delay": 0.01,  # Delay between chunks for smooth streaming
    "enable_progress": True,  # Enable progress tracking
}


def is_streaming_supported(llm: Any) -> bool:
    """
    Check if LLM supports streaming.
    
    Args:
        llm: LLM instance to check
        
    Returns:
        True if streaming is supported
    """
    return hasattr(llm, 'astream') or hasattr(llm, 'stream')


async def stream_with_metadata(
    generator: AsyncGenerator[str, None],
    metadata: Optional[Dict[str, Any]] = None
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Stream chunks with metadata.
    
    Args:
        generator: Source async generator
        metadata: Optional metadata to include
        
    Yields:
        Dictionaries with 'chunk' and 'metadata' keys
    """
    chunk_index = 0
    start_time = datetime.now()
    
    async for chunk in generator:
        chunk_data = {
            "chunk": chunk,
            "chunk_index": chunk_index,
            "timestamp": datetime.now().isoformat(),
            "elapsed_seconds": (datetime.now() - start_time).total_seconds()
        }
        
        if metadata:
            chunk_data["metadata"] = metadata
        
        yield chunk_data
        chunk_index += 1


async def format_supervisor_sse_stream(
    chunk_generator: AsyncGenerator[str, None],
    logger: Any,
    stream_type: str = "regular"
) -> AsyncGenerator[str, None]:
    """
    Format supervisor agent stream as SSE with consistent error handling.
    
    This utility eliminates duplication between regular and concurrent streaming
    by providing a shared formatting layer.
    
    Args:
        chunk_generator: Async generator yielding chunks from supervisor
        logger: Logger instance for error tracking
        stream_type: Type of stream for logging (regular/concurrent)
        
    Yields:
        SSE-formatted strings ready for streaming response
    """
    try:
        async for chunk in chunk_generator:
            if chunk == "[DONE]":
                yield "data: [DONE]\n\n"
            elif chunk.startswith("[ERROR]"):
                logger.error(f"{stream_type.capitalize()} streaming error: {chunk}")
                yield f"data: {chunk}\n\n"
            else:
                yield f"data: {chunk}\n\n"
    except Exception as e:
        logger.error(f"{stream_type.capitalize()} streaming error: {e}")
        yield f"data: [ERROR] {str(e)}\n\n"


def get_sse_headers() -> Dict[str, str]:
    """
    Get standard SSE headers for streaming responses.
    
    Returns:
        Dictionary of HTTP headers for SSE
    """
    return {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no"  # Disable nginx buffering
    }

