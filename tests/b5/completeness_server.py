from __future__ import annotations

import argparse
from pathlib import Path

import uvicorn

from cyberwife.application.api_gateway import ApiGateway
from cyberwife.application.health_aggregator import HealthAggregator
from cyberwife.application.memory_service import MemoryService
from cyberwife.application.model_registry import ModelRegistry
from cyberwife.application.retention_service import RetentionService
from cyberwife.infrastructure.sqlite_memory_repository import SqliteMemoryRepository
from cyberwife.infrastructure.sqlite_repository import SqliteRepository


class DeterministicEmbedding:
    def embed(self, text):
        value = [0.0] * 512
        value[sum(map(ord, str(text))) % 512] = 1.0
        return value

    def embed_batch(self, texts):
        return [self.embed(text) for text in texts]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--assets", type=Path, required=True)
    parser.add_argument("--port", type=int, default=7862)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    repo = SqliteRepository(args.db, root / "migrations" / "0001_init.sql")
    memory_repo = SqliteMemoryRepository(repo.conn, repo.lock)
    memory = MemoryService(repo, memory_repo, DeterministicEmbedding())
    registry = ModelRegistry(root)
    gateway = ApiGateway(
        registry, HealthAggregator(registry, data_root=args.db.parent), repository=repo,
        assets_root=args.assets, memory_service=memory,
        retention_service=RetentionService(repo, data_root=args.db.parent),
    )
    uvicorn.run(gateway.build_app(), host="127.0.0.1", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
