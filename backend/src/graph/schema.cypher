// Neo4j schema for PDF GraphRAG.
// Run on application startup (idempotent via IF NOT EXISTS).

CREATE CONSTRAINT doc_id IF NOT EXISTS FOR (d:Document) REQUIRE d.id IS UNIQUE;
CREATE CONSTRAINT section_key IF NOT EXISTS FOR (s:Section) REQUIRE (s.doc_id, s.number) IS UNIQUE;
CREATE CONSTRAINT standard_code IF NOT EXISTS FOR (n:Standard) REQUIRE n.code IS UNIQUE;
CREATE CONSTRAINT material_grade IF NOT EXISTS FOR (n:Material) REQUIRE n.grade IS UNIQUE;
CREATE CONSTRAINT item_key IF NOT EXISTS FOR (n:Item) REQUIRE (n.doc_id, n.description) IS UNIQUE;
CREATE CONSTRAINT env_key IF NOT EXISTS FOR (n:EnvCondition) REQUIRE (n.doc_id, n.type, n.value) IS UNIQUE;
CREATE CONSTRAINT elec_key IF NOT EXISTS FOR (n:ElectricalSpec) REQUIRE (n.doc_id, n.type, n.value) IS UNIQUE;
CREATE CONSTRAINT test_key IF NOT EXISTS FOR (n:TestRequirement) REQUIRE (n.doc_id, n.category, n.criterion) IS UNIQUE;
CREATE CONSTRAINT toxic_key IF NOT EXISTS FOR (n:ToxicClause) REQUIRE (n.doc_id, n.text) IS UNIQUE;

CREATE INDEX section_page IF NOT EXISTS FOR (s:Section) ON (s.page_start);
CREATE INDEX doc_filename IF NOT EXISTS FOR (d:Document) ON (d.filename);
