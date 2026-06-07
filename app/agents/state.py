from typing import TypedDict, List, Dict, Literal

class SubTask(TypedDict):
    id: str
    description: str
    intent: Literal["fact", "relation", "comparison", "reasoning", "exact"]
    depends_on: List[str]
    status: Literal["pending", "running", "done", "failed"]

class RetrievedChunk(TypedDict):
    chunk_id: str
    document_id: str
    text: str
    score: float
    source: str
    metadata: dict

class VerifiedClaim(TypedDict):
    text: str
    status: Literal["verified", "unverified", "contradicted"]
    source_chunk_id: str | None
    contradiction_note: str | None

class Citation(TypedDict):
    chunk_id: str
    document_title: str
    text: str
    relevance: float

class AgentState(TypedDict, total=False):
    query: str
    conversation_history: List[dict]
    intent: str
    rewritten_query: str
    sub_tasks: List[SubTask]
    routes: Dict[str, list[str]]
    retrieved: List[RetrievedChunk]
    raw_milvus_hits: List[dict]
    raw_kg_results: List[dict]
    raw_keyword_hits: List[dict]
    reflection_notes: str
    missing_info: List[str]
    quality_score: float
    need_another_round: bool
    draft_answer: str
    verified_claims: List[VerifiedClaim]
    supplement_queries: List[str]
    need_supplement: bool
    final_answer: str
    citations: List[Citation]
    uncertainty_flags: List[dict]
    warnings: List[str]
    bare_minimum_mode: bool
    iteration: int
    max_iterations: int
    prev_score: float | None
    collection_ids: List[str]
    session_id: str
    enable_web_search: bool
