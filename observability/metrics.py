from typing import Dict, List
from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class SyncMetrics:
    """Metrics for GitHub sync operations"""
    repo: str
    start_time: datetime
    end_time: datetime
    files_processed: int = 0
    files_skipped: int = 0
    chunks_created: int = 0
    errors: List[str] = field(default_factory=list)
    
    @property
    def duration_seconds(self) -> float:
        return (self.end_time - self.start_time).total_seconds()
    
    def to_dict(self) -> Dict:
        return {
            "repo": self.repo,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "duration_seconds": round(self.duration_seconds, 2),
            "files_processed": self.files_processed,
            "files_skipped": self.files_skipped,
            "chunks_created": self.chunks_created,
            "error_count": len(self.errors),
            "errors": self.errors[:5]
        }

@dataclass
class QueryMetrics:
    """Metrics for query operations"""
    query: str
    start_time: datetime
    end_time: datetime
    chunks_retrieved: int = 0
    llm_model: str = ""
    tokens_used: int = 0
    cost_usd: float = 0.0
    citations: List[str] = field(default_factory=list)
    
    @property
    def duration_ms(self) -> int:
        return int((self.end_time - self.start_time).total_seconds() * 1000)
    
    def to_dict(self) -> Dict:
        return {
            "query": self.query,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "duration_ms": self.duration_ms,
            "chunks_retrieved": self.chunks_retrieved,
            "llm_model": self.llm_model,
            "tokens_used": self.tokens_used,
            "cost_usd": round(self.cost_usd, 4),
            "citation_count": len(self.citations),
            "citations": self.citations
        }

class MetricsCollector:
    """Simple in-memory metrics collector"""
    
    def __init__(self):
        self.sync_metrics: List[SyncMetrics] = []
        self.query_metrics: List[QueryMetrics] = []
    
    def record_sync(self, metrics: SyncMetrics):
        self.sync_metrics.append(metrics)
    
    def record_query(self, metrics: QueryMetrics):
        self.query_metrics.append(metrics)
    
    def get_summary(self) -> Dict:
        return {
            "total_syncs": len(self.sync_metrics),
            "total_queries": len(self.query_metrics),
            "total_files_processed": sum(m.files_processed for m in self.sync_metrics),
            "total_chunks_created": sum(m.chunks_created for m in self.sync_metrics),
            "avg_query_latency_ms": int(
                sum(m.duration_ms for m in self.query_metrics) / len(self.query_metrics)
            ) if self.query_metrics else 0,
            "total_cost_usd": round(
                sum(m.cost_usd for m in self.query_metrics), 2
            )
        }

metrics_collector = MetricsCollector()