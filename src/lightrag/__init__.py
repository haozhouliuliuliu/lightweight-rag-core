"""lightweight-rag-core: explicit Python RAG pipeline."""

from .answer import AnswerGenerationError, AnswerResult, Citation, QwenAnswerer
from .chunker import Chunk, ChunkerConfig, chunk_document, chunk_documents
from .config import AppConfig, ConfigError, load_config
from .documents import DocumentManager, DocumentManagerError
from .embeddings import DashScopeEmbedder, EmbeddingError
from .evaluation import evaluate, judge, load_questions, summarize
from .indexer import IndexError, IndexReport, build_index
from .parser import (
    DocumentParseError,
    ParsedDocument,
    TextBlock,
    find_supported_documents,
    parse_document,
)
from .retriever import RetrievalError, Retriever, RetrievedChunk
from .vector_store import ChromaStore, StoredMatch, VectorStoreError

__all__ = [
    "AnswerGenerationError",
    "AnswerResult",
    "AppConfig",
    "Chunk",
    "ChunkerConfig",
    "ChromaStore",
    "Citation",
    "ConfigError",
    "DashScopeEmbedder",
    "DocumentManager",
    "DocumentManagerError",
    "DocumentParseError",
    "EmbeddingError",
    "IndexError",
    "IndexReport",
    "ParsedDocument",
    "QwenAnswerer",
    "RetrievalError",
    "RetrievedChunk",
    "Retriever",
    "StoredMatch",
    "TextBlock",
    "VectorStoreError",
    "build_index",
    "chunk_document",
    "chunk_documents",
    "evaluate",
    "find_supported_documents",
    "judge",
    "load_config",
    "load_questions",
    "parse_document",
    "summarize",
]
