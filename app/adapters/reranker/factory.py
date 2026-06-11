"""Reranker factory — pluggable re-ranker selection via RERANKER_PROVIDER config.

Pattern mirrors app/core/llm_factory.py: one function, config-driven,
singleton via lru_cache.
"""

from functools import lru_cache
import structlog
from app.core.config import get_settings
from app.adapters.reranker.base import BaseReranker, TwoStageReranker
from app.adapters.reranker.rrf import RRFReranker

logger = structlog.get_logger()


@lru_cache()
def get_reranker() -> BaseReranker:
    """Return the configured re-ranker singleton.

    Provider mapping:
        rrf    → RRFReranker only (zero-dependency, always available)
        bge    → RRF + BGEReranker two-stage
        cohere → RRF + CohereReranker two-stage
    """
    s = get_settings()
    provider = s.reranker_provider

    # Stage 1: RRF is always the first stage (fixes cross-source scoring)
    stage1 = RRFReranker(k=s.rrf_k)

    if provider == "rrf":
        logger.info("reranker", provider="rrf")
        return stage1

    if provider == "bge":
        try:
            from app.adapters.reranker.bge import BGEReranker

            stage2 = BGEReranker(model_name=s.reranker_model)
            logger.info("reranker", provider="bge", model=s.reranker_model)
            return TwoStageReranker(stage1, stage2, top_k=s.reranker_top_k)
        except ImportError:
            logger.warning(
                "FlagEmbedding not installed, falling back to RRF. "
                "Install with: pip install FlagEmbedding"
            )
            return stage1
        except Exception as e:
            logger.warning("BGE reranker init failed, falling back to RRF", error=str(e))
            return stage1

    if provider == "cohere":
        try:
            from app.adapters.reranker.cohere import CohereReranker

            stage2 = CohereReranker(api_key=s.cohere_api_key or "")
            logger.info("reranker", provider="cohere")
            return TwoStageReranker(stage1, stage2, top_k=s.reranker_top_k)
        except ImportError:
            logger.warning(
                "cohere SDK not installed, falling back to RRF. "
                "Install with: pip install cohere"
            )
            return stage1
        except Exception as e:
            logger.warning("Cohere reranker init failed, falling back to RRF", error=str(e))
            return stage1

    logger.warning("unknown reranker provider, falling back to RRF", provider=provider)
    return stage1