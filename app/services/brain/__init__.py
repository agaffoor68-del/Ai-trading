"""Autonomous AI Brain services.

Modules:

* ``data_intelligence`` – the only read surface for platform data (provenance +
  freshness).
* ``risk_engine`` – independent risk validation and the kill switch.
* ``decision_engine`` – Grok-driven 15-step decision pipeline.
* ``execution_service`` – order lifecycle, idempotency, reconciliation.
* ``learning_engine`` – post-trade analysis and strategy validation/promotion.
* ``memory_service`` – persistent, retrievable AI memory.
* ``news_service`` – India + global news ingestion and enrichment.
"""

__all__ = [
    "data_intelligence",
    "decision_engine",
    "execution_service",
    "learning_engine",
    "memory_service",
    "news_service",
    "risk_engine",
]
