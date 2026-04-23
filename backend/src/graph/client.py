"""Thin wrapper around the Neo4j async driver with schema bootstrap."""

from pathlib import Path

from neo4j import AsyncDriver, AsyncGraphDatabase

from src.core.config import settings

_SCHEMA_PATH = Path(__file__).parent / "schema.cypher"


class Neo4jClient:
    def __init__(self, driver: AsyncDriver):
        self._driver = driver

    @property
    def driver(self) -> AsyncDriver:
        return self._driver

    async def ensure_schema(self) -> None:
        if not _SCHEMA_PATH.exists():
            return
        statements = [
            s.strip()
            for s in _SCHEMA_PATH.read_text(encoding="utf-8").split(";")
            if s.strip() and not s.strip().startswith("//")
        ]
        async with self._driver.session() as session:
            for stmt in statements:
                # comments inside a statement block are possible — keep as-is
                await session.run(stmt)  # type: ignore[arg-type]

    async def close(self) -> None:
        await self._driver.close()

    async def run_read(self, cypher: str, params: dict | None = None) -> list[dict]:
        async with self._driver.session() as session:
            result = await session.run(cypher, params or {})  # type: ignore[arg-type]
            return [record.data() async for record in result]

    async def run_write(self, cypher: str, params: dict | None = None) -> None:
        async with self._driver.session() as session:
            await session.run(cypher, params or {})  # type: ignore[arg-type]


def get_neo4j_client() -> Neo4jClient:
    driver = AsyncGraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password),
    )
    return Neo4jClient(driver)
