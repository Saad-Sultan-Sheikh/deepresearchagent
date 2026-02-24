// ── Constraints ────────────────────────────────────────────────────────────────
CREATE CONSTRAINT person_entity_id IF NOT EXISTS
  FOR (n:Person) REQUIRE n.entity_id IS UNIQUE;

CREATE CONSTRAINT organization_entity_id IF NOT EXISTS
  FOR (n:Organization) REQUIRE n.entity_id IS UNIQUE;

CREATE CONSTRAINT location_entity_id IF NOT EXISTS
  FOR (n:Location) REQUIRE n.entity_id IS UNIQUE;

CREATE CONSTRAINT email_entity_id IF NOT EXISTS
  FOR (n:Email) REQUIRE n.entity_id IS UNIQUE;

CREATE CONSTRAINT phone_entity_id IF NOT EXISTS
  FOR (n:Phone) REQUIRE n.entity_id IS UNIQUE;

CREATE CONSTRAINT url_entity_id IF NOT EXISTS
  FOR (n:Url) REQUIRE n.entity_id IS UNIQUE;

CREATE CONSTRAINT alias_entity_id IF NOT EXISTS
  FOR (n:Alias) REQUIRE n.entity_id IS UNIQUE;

CREATE CONSTRAINT financial_account_entity_id IF NOT EXISTS
  FOR (n:FinancialAccount) REQUIRE n.entity_id IS UNIQUE;

CREATE CONSTRAINT run_id IF NOT EXISTS
  FOR (r:Run) REQUIRE r.run_id IS UNIQUE;

// ── Indexes ────────────────────────────────────────────────────────────────────
CREATE INDEX person_value IF NOT EXISTS FOR (n:Person) ON (n.value);
CREATE INDEX person_persona_id IF NOT EXISTS FOR (n:Person) ON (n.persona_id);
CREATE INDEX organization_value IF NOT EXISTS FOR (n:Organization) ON (n.value);
CREATE INDEX location_value IF NOT EXISTS FOR (n:Location) ON (n.value);
CREATE INDEX email_value IF NOT EXISTS FOR (n:Email) ON (n.value);
CREATE INDEX run_persona_id IF NOT EXISTS FOR (r:Run) ON (r.persona_id);

// ── Relationship schema documentation (not enforced in community edition) ──────
// (:Person)-[:WORKS_AT]->(:Organization)
// (:Person)-[:WORKED_AT {start_year, end_year}]->(:Organization)
// (:Person)-[:LIVES_AT]->(:Location)
// (:Person)-[:LIVED_AT {start_year, end_year}]->(:Location)
// (:Person)-[:ASSOCIATED_WITH {type}]->(:Person)
// (:Person)-[:HAS_EMAIL]->(:Email)
// (:Person)-[:HAS_PHONE]->(:Phone)
// (:Person)-[:HAS_ALIAS]->(:Alias)
// (:Person)-[:CONTROLS_URL]->(:Url)
// (:Person)-[:CONTROLS_FINANCIAL_ACCOUNT]->(:FinancialAccount)
// (:Run)-[:PRODUCED]->(:Person)
