"""
Index assistant chunks for RAG system.
Reads events from app DB, chunks content, generates embeddings, and stores in assistant_chunks table.
"""
import uuid
import json
from typing import List, Dict, Any
from pathlib import Path
import sqlalchemy as sa
from fastembed import TextEmbedding
import numpy as np
from .config import settings
from .app_db import engine as app_engine, event, localized_event_data, localized_event_so_far, localized_event_analysis, event_so_far, event_analysis, seo_tag, event_seo_tag
from sqlalchemy.dialects.postgresql import insert as pg_insert

# Embedding model (same as clustering)
EMB_DIM = 384
CHUNK_SIZE = 500  # Characters per chunk
CHUNK_OVERLAP = 100  # Overlap between chunks

def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    """Split text into overlapping chunks."""
    if not text or len(text) <= chunk_size:
        return [text] if text else []
    
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        chunks.append(chunk.strip())
        if end >= len(text):
            break
        start = end - overlap
    return chunks

def extract_text_from_content(content: Any) -> str:
    """Extract plain text from JSONB content field."""
    if not content:
        return ""
    
    if isinstance(content, str):
        return content
    
    if isinstance(content, list):
        text_parts = []
        for item in content:
            if isinstance(item, dict):
                # Handle different content types
                if "content" in item:
                    text_parts.append(str(item["content"]))
                elif "text" in item:
                    text_parts.append(str(item["text"]))
                elif "title" in item:
                    text_parts.append(str(item["title"]))
                else:
                    text_parts.append(str(item))
            elif isinstance(item, str):
                text_parts.append(item)
        return " ".join(text_parts)
    
    if isinstance(content, dict):
        # Try common keys
        for key in ["content", "text", "title", "description"]:
            if key in content:
                return str(content[key])
        return str(content)
    
    return str(content)

# Tags are now retrieved via JOINs at query time, not stored in assistant_chunks

def index_event(event_id: str, conn, embedding_model: TextEmbedding, verbose: bool = False) -> int:
    """Index a single event into assistant_chunks."""
    chunks_created = 0
    
    # Get English localized data
    query = sa.select(localized_event_data).where(
        localized_event_data.c.event_id == event_id,
        localized_event_data.c.language_id == 'en'
    )
    result = conn.execute(query)
    event_data = result.mappings().first()
    
    if not event_data:
        if verbose:
            print(f"  No English data for event {event_id}")
        return 0
    
    # Get title (tags retrieved via JOIN at query time)
    title = event_data.get('title') or ''
    
    # Prepare chunks
    chunks_to_embed = []
    chunk_metadata = []
    
    # 1. Title chunk
    if title:
        chunks_to_embed.append(title)
        chunk_metadata.append({
            'chunk_type': 'title',
            'chunk_text': title,
            'sequence': 0,
        })
    
    # 2. Description chunk
    description = event_data.get('description') or ''
    if description:
        chunks_to_embed.append(description)
        chunk_metadata.append({
            'chunk_type': 'description',
            'chunk_text': description,
            'sequence': 0,
        })
    
    # 3. Content chunks
    content = event_data.get('content')
    if content:
        content_text = extract_text_from_content(content)
        if content_text:
            content_chunks = chunk_text(content_text)
            for i, chunk in enumerate(content_chunks):
                chunks_to_embed.append(chunk)
                chunk_metadata.append({
                    'chunk_type': 'content',
                    'chunk_text': chunk,
                    'sequence': i,
                })
    
    # 4. Story so far chunks
    story_query = sa.text("""
        SELECT lesf.content, lesf.content_type
        FROM localized_event_so_far lesf
        JOIN event_so_far esf ON lesf.event_so_far_id = esf.id
        WHERE esf.event_id = :event_id AND lesf.language_id = 'en'
        ORDER BY esf.sequence
    """)
    story_result = conn.execute(story_query, {'event_id': str(event_id)})
    for i, row in enumerate(story_result.mappings()):
        content_text = extract_text_from_content(row['content'])
        if content_text:
            story_chunks = chunk_text(content_text)
            for j, chunk in enumerate(story_chunks):
                chunks_to_embed.append(chunk)
                chunk_metadata.append({
                    'chunk_type': 'story_so_far',
                    'chunk_text': chunk,
                    'sequence': i * 100 + j,  # Preserve ordering
                })
    
    # 5. Analysis chunks
    analysis_query = sa.text("""
        SELECT lea.content, lea.content_type
        FROM localized_event_analysis lea
        JOIN event_analysis ea ON lea.event_analysis_id = ea.id
        WHERE ea.event_id = :event_id AND lea.language_id = 'en'
        ORDER BY ea.sequence
    """)
    analysis_result = conn.execute(analysis_query, {'event_id': str(event_id)})
    for i, row in enumerate(analysis_result.mappings()):
        content_text = extract_text_from_content(row['content'])
        if content_text:
            analysis_chunks = chunk_text(content_text)
            for j, chunk in enumerate(analysis_chunks):
                chunks_to_embed.append(chunk)
                chunk_metadata.append({
                    'chunk_type': 'analysis',
                    'chunk_text': chunk,
                    'sequence': i * 100 + j,
                })
    
    if not chunks_to_embed:
        if verbose:
            print(f"  No chunks to embed for event {event_id}")
        return 0
    
    # Generate embeddings
    embeddings = list(embedding_model.embed(chunks_to_embed))
    
    # Insert chunks - use raw SQL for vector type casting
    if chunks_to_embed:
        for embedding, metadata in zip(embeddings, chunk_metadata):
            embedding_array = np.array(embedding).tolist()
            # Format embedding as PostgreSQL array string for vector type
            embedding_str = '[' + ','.join(str(x) for x in embedding_array) + ']'
            
            insert_sql = sa.text("""
                INSERT INTO assistant_chunks (
                    id, event_id, chunk_text, embedding, chunk_type, sequence, title, created_at, updated_at
                ) VALUES (
                    gen_random_uuid(),
                    CAST(:event_id AS uuid),
                    :chunk_text,
                    CAST(:embedding AS vector(384)),
                    :chunk_type,
                    :sequence,
                    :title,
                    NOW(),
                    NOW()
                )
                ON CONFLICT DO NOTHING
            """)
            # Convert arrays to proper format
            conn.execute(insert_sql, {
                'event_id': str(event_id),
                'chunk_text': metadata['chunk_text'],
                'embedding': embedding_str,
                'chunk_type': metadata['chunk_type'],
                'sequence': metadata['sequence'],
                'title': title,
            })
            chunks_created += 1
    
    return chunks_created
