"""Upsert ExtractionResult into Neo4j.

Nodes created:
  (Document), (Section), (Item), (Standard), (Material),
  (EnvCondition), (ElectricalSpec), (TestRequirement), (ToxicClause)

Relationships:
  (Document)-[:CONTAINS]->(Section)
  (Section)-[:MENTIONS]->(*)  (most-specific section only)
  (Section)-[:HAS_RISK]->(ToxicClause)

Phase 2 will add (Section)-[:REFERS_TO]->(Section|Standard) via Jump Engine
and (EnvCondition)-[:CONFLICTS_WITH]->(Material) via validation.
"""

from src.extraction.pipeline import ExtractionResult, SectionOut
from src.graph.client import Neo4jClient


def _find_best_section(sections: list[SectionOut], page: int | None) -> str | None:
    """Return the number of the *deepest* section whose page range covers `page`.

    Resolves the overlap problem where "1.0" and "2.1" both cover page 6 —
    we always prefer "2.1" (more specific). Ties broken by latest page_start.
    """
    if page is None:
        return None
    candidates = [
        s
        for s in sections
        if s.page_start <= page and (s.page_end is None or s.page_end >= page)
    ]
    if not candidates:
        return None
    best = max(candidates, key=lambda s: (s.depth, s.page_start))
    return best.number


async def build_graph(client: Neo4jClient, result: ExtractionResult) -> dict[str, int]:
    doc_id = result.doc_id
    sections_for_resolve = result.sections
    stats = {
        "documents": 0,
        "sections": 0,
        "items": 0,
        "standards": 0,
        "materials": 0,
        "env_conditions": 0,
        "electrical_specs": 0,
        "tests": 0,
        "toxic_clauses": 0,
        "references": 0,
    }

    async with client.driver.session() as session:
        # 1. Document
        await session.run(
            """
            MERGE (d:Document {id: $id})
            SET d.filename = $filename,
                d.page_count = $page_count
            """,
            {"id": doc_id, "filename": result.filename, "page_count": result.page_count},
        )
        stats["documents"] = 1

        # 2. Sections
        for s in result.sections:
            await session.run(
                """
                MERGE (sec:Section {doc_id: $doc_id, number: $number})
                SET sec.title = $title,
                    sec.page_start = $page_start,
                    sec.page_end = $page_end,
                    sec.depth = $depth
                WITH sec
                MATCH (d:Document {id: $doc_id})
                MERGE (d)-[:CONTAINS]->(sec)
                """,
                {
                    "doc_id": doc_id,
                    "number": s.number,
                    "title": s.title,
                    "page_start": s.page_start,
                    "page_end": s.page_end,
                    "depth": s.depth,
                },
            )
            stats["sections"] += 1

        async def _mention(
            label: str,
            merge_clause: str,
            set_clause: str,
            params: dict,
            page: int | None,
        ) -> None:
            section_number = _find_best_section(sections_for_resolve, page)
            cypher = f"""
            {merge_clause}
            SET {set_clause}
            WITH n
            MATCH (d:Document {{id: $doc_id}})
            MERGE (d)-[:HAS_ENTITY]->(n)
            WITH n
            OPTIONAL MATCH (sec:Section {{doc_id: $doc_id, number: $section_number}})
            FOREACH (_ IN CASE WHEN sec IS NULL OR $section_number IS NULL THEN [] ELSE [1] END |
                MERGE (sec)-[:MENTIONS]->(n)
            )
            """
            await session.run(
                cypher,
                {
                    **params,
                    "doc_id": doc_id,
                    "section_number": section_number,
                    "page": page,
                },
            )

        ex = result.extracted

        # 3. Items (doc-scoped — stock codes are often "New Item")
        for it in ex.items:
            await _mention(
                "Item",
                "MERGE (n:Item {doc_id: $doc_id, description: $description})",
                "n.stock_code = $stock_code, n.page = $page",
                {"description": it.description, "stock_code": it.stock_code},
                it.page,
            )
            stats["items"] += 1

        # 4. Standards (global — shared across documents, enables cross-doc similarity)
        for st in ex.standards:
            await _mention(
                "Standard",
                "MERGE (n:Standard {code: $code})",
                "n.title = coalesce($title, n.title, '')",
                {"code": st.code, "title": st.title},
                st.page,
            )
            stats["standards"] += 1

        # 5. Materials (global)
        for mat in ex.materials:
            await _mention(
                "Material",
                "MERGE (n:Material {grade: $grade})",
                "n.standard = coalesce($standard, n.standard, '')",
                {"grade": mat.grade, "standard": mat.standard},
                mat.page,
            )
            stats["materials"] += 1

        # 6. Environmental
        for env in ex.environmental:
            await _mention(
                "EnvCondition",
                "MERGE (n:EnvCondition {doc_id: $doc_id, type: $type, value: $value})",
                "n.unit = $unit, n.page = $page",
                {"type": env.type, "value": env.value, "unit": env.unit},
                env.page,
            )
            stats["env_conditions"] += 1

        # 7. Electrical
        for el in ex.electrical:
            await _mention(
                "ElectricalSpec",
                "MERGE (n:ElectricalSpec {doc_id: $doc_id, type: $type, value: $value})",
                "n.unit = $unit, n.page = $page",
                {"type": el.type, "value": el.value, "unit": el.unit},
                el.page,
            )
            stats["electrical_specs"] += 1

        # 8. Tests
        for t in ex.tests:
            await _mention(
                "TestRequirement",
                "MERGE (n:TestRequirement {doc_id: $doc_id, category: $category, criterion: $criterion})",
                "n.reference = $reference, n.page = $page",
                {"category": t.category, "criterion": t.criterion, "reference": t.reference},
                t.page,
            )
            stats["tests"] += 1

        # 9. Toxic clauses
        for tc in ex.toxic_clauses:
            section_number = _find_best_section(sections_for_resolve, tc.page)
            await session.run(
                """
                MERGE (n:ToxicClause {doc_id: $doc_id, text: $text})
                SET n.severity = $severity, n.reason = $reason, n.page = $page
                WITH n
                MATCH (d:Document {id: $doc_id})
                MERGE (d)-[:HAS_RISK]->(n)
                WITH n
                OPTIONAL MATCH (sec:Section {doc_id: $doc_id, number: $section_number})
                FOREACH (_ IN CASE WHEN sec IS NULL OR $section_number IS NULL THEN [] ELSE [1] END |
                    MERGE (sec)-[:HAS_RISK]->(n)
                )
                """,
                {
                    "doc_id": doc_id,
                    "text": tc.text,
                    "severity": tc.severity,
                    "reason": tc.reason,
                    "page": tc.page,
                    "section_number": section_number,
                },
            )
            stats["toxic_clauses"] += 1

        # 10. References (Jump Engine)
        for ref in result.references:
            src_sec = ref.source_section
            if src_sec is None:
                continue

            if ref.kind == "standard":
                # External: point to Standard node
                await session.run(
                    """
                    MATCH (src:Section {doc_id: $doc_id, number: $src_section})
                    MERGE (tgt:Standard {code: $target})
                    MERGE (src)-[r:REFERS_TO {kind: $kind}]->(tgt)
                    SET r.context = $context, r.source_page = $source_page
                    """,
                    {
                        "doc_id": doc_id,
                        "src_section": src_sec,
                        "target": ref.target,
                        "kind": ref.kind,
                        "context": ref.context,
                        "source_page": ref.source_page,
                    },
                )
                stats["references"] += 1
            elif ref.kind in ("section", "clause") and ref.target_page is not None:
                # Internal: point to resolved Section
                await session.run(
                    """
                    MATCH (src:Section {doc_id: $doc_id, number: $src_section})
                    MATCH (tgt:Section {doc_id: $doc_id, number: $tgt_section})
                    MERGE (src)-[r:REFERS_TO {kind: $kind}]->(tgt)
                    SET r.context = $context, r.source_page = $source_page
                    """,
                    {
                        "doc_id": doc_id,
                        "src_section": src_sec,
                        "tgt_section": ref.target,
                        "kind": ref.kind,
                        "context": ref.context,
                        "source_page": ref.source_page,
                    },
                )
                stats["references"] += 1
            elif ref.kind == "appendix" and ref.target_page is not None:
                # Point to section containing the appendix page
                tgt_sec = _find_best_section(sections_for_resolve, ref.target_page)
                if tgt_sec:
                    await session.run(
                        """
                        MATCH (src:Section {doc_id: $doc_id, number: $src_section})
                        MATCH (tgt:Section {doc_id: $doc_id, number: $tgt_section})
                        MERGE (src)-[r:REFERS_TO {kind: $kind, target: $target}]->(tgt)
                        SET r.context = $context, r.source_page = $source_page
                        """,
                        {
                            "doc_id": doc_id,
                            "src_section": src_sec,
                            "tgt_section": tgt_sec,
                            "target": ref.target,
                            "kind": ref.kind,
                            "context": ref.context,
                            "source_page": ref.source_page,
                        },
                    )
                    stats["references"] += 1
            elif ref.kind == "table" and ref.target_page is not None:
                # Point to the section that contains the table definition
                tgt_sec = _find_best_section(sections_for_resolve, ref.target_page)
                if tgt_sec:
                    await session.run(
                        """
                        MATCH (src:Section {doc_id: $doc_id, number: $src_section})
                        MATCH (tgt:Section {doc_id: $doc_id, number: $tgt_section})
                        MERGE (src)-[r:REFERS_TO {kind: $kind, target: $target}]->(tgt)
                        SET r.context = $context, r.source_page = $source_page
                        """,
                        {
                            "doc_id": doc_id,
                            "src_section": src_sec,
                            "tgt_section": tgt_sec,
                            "target": ref.target,
                            "kind": ref.kind,
                            "context": ref.context,
                            "source_page": ref.source_page,
                        },
                    )
                    stats["references"] += 1

    return stats
