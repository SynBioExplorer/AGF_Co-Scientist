-- =============================================================================
-- AI Co-Scientist Database Schema
-- PostgreSQL 15+
-- =============================================================================
--
-- This schema defines all tables for the AI Co-Scientist system.
-- Tables map directly to Pydantic models in 03_Architecture/schemas.py
--
-- Design Principles:
-- - VARCHAR(255) for IDs (format: prefix_YYYYMMDD_hash)
-- - TEXT for long strings (statements, rationales, mechanisms)
-- - JSONB for complex nested objects (citations, experimental_protocol)
-- - FLOAT for Elo ratings
-- - TIMESTAMP WITH TIME ZONE for dates
-- - Foreign keys with ON DELETE CASCADE
-- - Indexes on frequently queried fields
-- =============================================================================

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- For text search

-- =============================================================================
-- Trigger function for updated_at timestamps
-- =============================================================================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- 1. Research Goals
-- =============================================================================

CREATE TABLE research_goals (
    id VARCHAR(255) PRIMARY KEY,
    description TEXT NOT NULL,
    constraints JSONB DEFAULT '[]'::jsonb,
    preferences JSONB DEFAULT '[]'::jsonb,
    prior_publications JSONB DEFAULT '[]'::jsonb,
    laboratory_context TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_research_goals_created ON research_goals(created_at DESC);

CREATE TRIGGER update_research_goals_updated_at
    BEFORE UPDATE ON research_goals
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- =============================================================================
-- 2. Hypotheses
-- =============================================================================

CREATE TABLE hypotheses (
    id VARCHAR(255) PRIMARY KEY,
    research_goal_id VARCHAR(255) NOT NULL REFERENCES research_goals(id) ON DELETE CASCADE,

    -- Core content
    title TEXT NOT NULL,
    summary TEXT NOT NULL,
    hypothesis_statement TEXT NOT NULL,
    rationale TEXT NOT NULL,
    mechanism TEXT,

    -- Experimental validation (JSONB for complex nested object)
    experimental_protocol JSONB,

    -- Supporting information (JSONB for arrays)
    literature_citations JSONB DEFAULT '[]'::jsonb,
    assumptions JSONB DEFAULT '[]'::jsonb,
    category VARCHAR(255),

    -- Status and method
    status VARCHAR(50) DEFAULT 'generated',
    generation_method VARCHAR(50) NOT NULL,

    -- Evolution lineage
    parent_hypothesis_ids JSONB DEFAULT '[]'::jsonb,

    -- Tournament rating (default 1200 per Google paper)
    elo_rating FLOAT DEFAULT 1200.0,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Performance indexes
CREATE INDEX idx_hypotheses_goal ON hypotheses(research_goal_id);
CREATE INDEX idx_hypotheses_elo ON hypotheses(elo_rating DESC);
CREATE INDEX idx_hypotheses_status ON hypotheses(status);
CREATE INDEX idx_hypotheses_created ON hypotheses(created_at DESC);
CREATE INDEX idx_hypotheses_category ON hypotheses(category);

-- Full-text search on title and statement
CREATE INDEX idx_hypotheses_title_trgm ON hypotheses USING gin(title gin_trgm_ops);
CREATE INDEX idx_hypotheses_statement_trgm ON hypotheses USING gin(hypothesis_statement gin_trgm_ops);

CREATE TRIGGER update_hypotheses_updated_at
    BEFORE UPDATE ON hypotheses
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- =============================================================================
-- 3. Reviews
-- =============================================================================

CREATE TABLE reviews (
    id VARCHAR(255) PRIMARY KEY,
    hypothesis_id VARCHAR(255) NOT NULL REFERENCES hypotheses(id) ON DELETE CASCADE,
    review_type VARCHAR(50) NOT NULL,

    -- Assessment scores (0-1 scale)
    correctness_score FLOAT CHECK (correctness_score >= 0.0 AND correctness_score <= 1.0),
    quality_score FLOAT CHECK (quality_score >= 0.0 AND quality_score <= 1.0),
    novelty_score FLOAT CHECK (novelty_score >= 0.0 AND novelty_score <= 1.0),
    testability_score FLOAT CHECK (testability_score >= 0.0 AND testability_score <= 1.0),
    safety_score FLOAT CHECK (safety_score >= 0.0 AND safety_score <= 1.0),

    -- Qualitative feedback (JSONB arrays)
    strengths JSONB DEFAULT '[]'::jsonb,
    weaknesses JSONB DEFAULT '[]'::jsonb,
    suggestions JSONB DEFAULT '[]'::jsonb,
    critiques JSONB DEFAULT '[]'::jsonb,

    -- Novelty review fields
    known_aspects JSONB DEFAULT '[]'::jsonb,
    novel_aspects JSONB DEFAULT '[]'::jsonb,

    -- Observation review fields
    explained_observations JSONB DEFAULT '[]'::jsonb,

    -- Simulation review fields
    simulation_steps JSONB DEFAULT '[]'::jsonb,
    potential_failures JSONB DEFAULT '[]'::jsonb,

    -- Decision
    passed BOOLEAN NOT NULL,
    rationale TEXT NOT NULL,

    -- Literature searched
    literature_searched JSONB DEFAULT '[]'::jsonb,

    -- Deep verification fields (for DeepVerificationReview subclass)
    verified_assumptions JSONB DEFAULT '[]'::jsonb,
    invalidated_assumptions JSONB DEFAULT '[]'::jsonb,
    invalidation_reasons JSONB DEFAULT '[]'::jsonb,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_reviews_hypothesis ON reviews(hypothesis_id);
CREATE INDEX idx_reviews_type ON reviews(review_type);
CREATE INDEX idx_reviews_passed ON reviews(passed);
CREATE INDEX idx_reviews_created ON reviews(created_at DESC);

-- =============================================================================
-- 4. Tournament Matches
-- =============================================================================

CREATE TABLE tournament_matches (
    id VARCHAR(255) PRIMARY KEY,
    hypothesis_a_id VARCHAR(255) NOT NULL REFERENCES hypotheses(id) ON DELETE CASCADE,
    hypothesis_b_id VARCHAR(255) NOT NULL REFERENCES hypotheses(id) ON DELETE CASCADE,

    -- Debate content (JSONB array of DebateTurn objects)
    debate_turns JSONB DEFAULT '[]'::jsonb,
    is_multi_turn BOOLEAN DEFAULT FALSE,

    -- Outcome
    winner_id VARCHAR(255) REFERENCES hypotheses(id) ON DELETE SET NULL,
    decision_rationale TEXT NOT NULL,
    comparison_criteria JSONB DEFAULT '[]'::jsonb,

    -- Elo updates
    elo_change_a FLOAT DEFAULT 0.0,
    elo_change_b FLOAT DEFAULT 0.0,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_matches_hypothesis_a ON tournament_matches(hypothesis_a_id);
CREATE INDEX idx_matches_hypothesis_b ON tournament_matches(hypothesis_b_id);
CREATE INDEX idx_matches_winner ON tournament_matches(winner_id);
CREATE INDEX idx_matches_created ON tournament_matches(created_at DESC);

-- =============================================================================
-- 5. Tournament State
-- =============================================================================

CREATE TABLE tournament_states (
    research_goal_id VARCHAR(255) PRIMARY KEY REFERENCES research_goals(id) ON DELETE CASCADE,
    hypotheses JSONB DEFAULT '[]'::jsonb,
    elo_ratings JSONB DEFAULT '{}'::jsonb,
    match_history JSONB DEFAULT '[]'::jsonb,
    total_matches INTEGER DEFAULT 0,

    -- Statistics
    win_patterns JSONB DEFAULT '[]'::jsonb,
    loss_patterns JSONB DEFAULT '[]'::jsonb,

    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TRIGGER update_tournament_states_updated_at
    BEFORE UPDATE ON tournament_states
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- =============================================================================
-- 6. Proximity Edges
-- =============================================================================

CREATE TABLE proximity_edges (
    id SERIAL PRIMARY KEY,
    research_goal_id VARCHAR(255) NOT NULL REFERENCES research_goals(id) ON DELETE CASCADE,
    hypothesis_a_id VARCHAR(255) NOT NULL REFERENCES hypotheses(id) ON DELETE CASCADE,
    hypothesis_b_id VARCHAR(255) NOT NULL REFERENCES hypotheses(id) ON DELETE CASCADE,
    similarity_score FLOAT NOT NULL CHECK (similarity_score >= 0.0 AND similarity_score <= 1.0),
    shared_concepts JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Ensure unique edges (unordered pair)
    CONSTRAINT unique_edge UNIQUE (research_goal_id, hypothesis_a_id, hypothesis_b_id)
);

CREATE INDEX idx_edges_goal ON proximity_edges(research_goal_id);
CREATE INDEX idx_edges_hypothesis_a ON proximity_edges(hypothesis_a_id);
CREATE INDEX idx_edges_hypothesis_b ON proximity_edges(hypothesis_b_id);
CREATE INDEX idx_edges_similarity ON proximity_edges(similarity_score DESC);

-- =============================================================================
-- 7. Hypothesis Clusters
-- =============================================================================

CREATE TABLE hypothesis_clusters (
    id VARCHAR(255) PRIMARY KEY,
    research_goal_id VARCHAR(255) NOT NULL REFERENCES research_goals(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    hypothesis_ids JSONB DEFAULT '[]'::jsonb,
    representative_id VARCHAR(255) REFERENCES hypotheses(id) ON DELETE SET NULL,
    common_themes JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_clusters_goal ON hypothesis_clusters(research_goal_id);
CREATE INDEX idx_clusters_representative ON hypothesis_clusters(representative_id);

-- =============================================================================
-- 8. Proximity Graphs (metadata linking edges and clusters)
-- =============================================================================

CREATE TABLE proximity_graphs (
    research_goal_id VARCHAR(255) PRIMARY KEY REFERENCES research_goals(id) ON DELETE CASCADE,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TRIGGER update_proximity_graphs_updated_at
    BEFORE UPDATE ON proximity_graphs
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- =============================================================================
-- 9. Meta-Review Critiques
-- =============================================================================

CREATE TABLE meta_reviews (
    id VARCHAR(255) PRIMARY KEY,
    research_goal_id VARCHAR(255) NOT NULL REFERENCES research_goals(id) ON DELETE CASCADE,

    -- Patterns identified
    recurring_strengths JSONB DEFAULT '[]'::jsonb,
    recurring_weaknesses JSONB DEFAULT '[]'::jsonb,
    improvement_opportunities JSONB DEFAULT '[]'::jsonb,

    -- Feedback for agents
    generation_feedback JSONB DEFAULT '[]'::jsonb,
    reflection_feedback JSONB DEFAULT '[]'::jsonb,
    evolution_feedback JSONB DEFAULT '[]'::jsonb,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_meta_reviews_goal ON meta_reviews(research_goal_id);
CREATE INDEX idx_meta_reviews_created ON meta_reviews(created_at DESC);

-- =============================================================================
-- 10. Research Directions (nested in Research Overview)
-- =============================================================================

CREATE TABLE research_directions (
    id SERIAL PRIMARY KEY,
    research_overview_id VARCHAR(255) NOT NULL,  -- FK added after research_overviews table
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    justification TEXT NOT NULL,
    suggested_experiments JSONB DEFAULT '[]'::jsonb,
    example_topics JSONB DEFAULT '[]'::jsonb,
    related_hypothesis_ids JSONB DEFAULT '[]'::jsonb,
    display_order INTEGER DEFAULT 0
);

CREATE INDEX idx_directions_overview ON research_directions(research_overview_id);

-- =============================================================================
-- 11. Research Contacts (nested in Research Overview)
-- =============================================================================

CREATE TABLE research_contacts (
    id SERIAL PRIMARY KEY,
    research_overview_id VARCHAR(255) NOT NULL,  -- FK added after research_overviews table
    name TEXT NOT NULL,
    affiliation TEXT,
    expertise JSONB DEFAULT '[]'::jsonb,
    relevance_reasoning TEXT NOT NULL,
    publications JSONB DEFAULT '[]'::jsonb,
    display_order INTEGER DEFAULT 0
);

CREATE INDEX idx_contacts_overview ON research_contacts(research_overview_id);

-- =============================================================================
-- 12. Research Overviews
-- =============================================================================

CREATE TABLE research_overviews (
    id VARCHAR(255) PRIMARY KEY,
    research_goal_id VARCHAR(255) NOT NULL REFERENCES research_goals(id) ON DELETE CASCADE,

    -- Overview content
    executive_summary TEXT NOT NULL,
    current_knowledge_boundary TEXT NOT NULL,
    top_hypotheses_summary JSONB DEFAULT '[]'::jsonb,

    -- Key literature (JSONB array of Citation objects)
    key_literature JSONB DEFAULT '[]'::jsonb,

    -- Format
    output_format VARCHAR(255),

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_overviews_goal ON research_overviews(research_goal_id);
CREATE INDEX idx_overviews_created ON research_overviews(created_at DESC);

CREATE TRIGGER update_research_overviews_updated_at
    BEFORE UPDATE ON research_overviews
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Add foreign keys for nested tables
ALTER TABLE research_directions
    ADD CONSTRAINT fk_directions_overview
    FOREIGN KEY (research_overview_id) REFERENCES research_overviews(id) ON DELETE CASCADE;

ALTER TABLE research_contacts
    ADD CONSTRAINT fk_contacts_overview
    FOREIGN KEY (research_overview_id) REFERENCES research_overviews(id) ON DELETE CASCADE;

-- =============================================================================
-- 13. Agent Tasks (for Supervisor)
-- =============================================================================

CREATE TABLE agent_tasks (
    id VARCHAR(255) PRIMARY KEY,
    agent_type VARCHAR(50) NOT NULL,
    task_type VARCHAR(100) NOT NULL,
    priority INTEGER DEFAULT 1 CHECK (priority >= 1 AND priority <= 10),
    parameters JSONB DEFAULT '{}'::jsonb,
    status VARCHAR(50) DEFAULT 'pending',
    result JSONB,
    worker_id VARCHAR(255),  -- For task claiming

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_tasks_agent ON agent_tasks(agent_type);
CREATE INDEX idx_tasks_status ON agent_tasks(status);
CREATE INDEX idx_tasks_priority ON agent_tasks(priority DESC);
CREATE INDEX idx_tasks_created ON agent_tasks(created_at);

-- =============================================================================
-- 14. System Statistics
-- =============================================================================

CREATE TABLE system_statistics (
    id SERIAL PRIMARY KEY,
    research_goal_id VARCHAR(255) NOT NULL REFERENCES research_goals(id) ON DELETE CASCADE,

    -- Hypothesis counts
    total_hypotheses INTEGER DEFAULT 0,
    hypotheses_pending_review INTEGER DEFAULT 0,
    hypotheses_in_tournament INTEGER DEFAULT 0,
    hypotheses_archived INTEGER DEFAULT 0,

    -- Tournament progress
    tournament_matches_completed INTEGER DEFAULT 0,
    tournament_convergence_score FLOAT DEFAULT 0.0,

    -- Agent effectiveness
    generation_success_rate FLOAT DEFAULT 0.0,
    evolution_improvement_rate FLOAT DEFAULT 0.0,
    method_effectiveness JSONB DEFAULT '{}'::jsonb,

    -- Resource allocation
    agent_weights JSONB DEFAULT '{}'::jsonb,

    computed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_stats_goal ON system_statistics(research_goal_id);
CREATE INDEX idx_stats_computed ON system_statistics(computed_at DESC);

-- =============================================================================
-- 15. Context Memory (Checkpoints)
-- =============================================================================

CREATE TABLE context_memory (
    id SERIAL PRIMARY KEY,
    research_goal_id VARCHAR(255) NOT NULL REFERENCES research_goals(id) ON DELETE CASCADE,

    -- Current state (references, not full objects - those are in other tables)
    research_plan_config JSONB,
    tournament_state_snapshot JSONB,  -- Snapshot for checkpoint
    proximity_graph_snapshot JSONB,   -- Snapshot for checkpoint
    latest_meta_review_id VARCHAR(255),
    latest_research_overview_id VARCHAR(255),
    system_statistics_snapshot JSONB,

    -- History
    hypothesis_ids JSONB DEFAULT '[]'::jsonb,
    review_ids JSONB DEFAULT '[]'::jsonb,
    iteration_count INTEGER DEFAULT 0,

    -- Scientist contributions
    scientist_reviews JSONB DEFAULT '[]'::jsonb,
    scientist_hypotheses JSONB DEFAULT '[]'::jsonb,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_context_goal ON context_memory(research_goal_id);
CREATE INDEX idx_context_created ON context_memory(created_at DESC);

CREATE TRIGGER update_context_memory_updated_at
    BEFORE UPDATE ON context_memory
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- =============================================================================
-- 16. Scientist Feedback
-- =============================================================================

CREATE TABLE scientist_feedback (
    id VARCHAR(255) PRIMARY KEY,
    research_goal_id VARCHAR(255) NOT NULL REFERENCES research_goals(id) ON DELETE CASCADE,
    hypothesis_id VARCHAR(255) REFERENCES hypotheses(id) ON DELETE SET NULL,
    feedback_type VARCHAR(50) NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_feedback_goal ON scientist_feedback(research_goal_id);
CREATE INDEX idx_feedback_hypothesis ON scientist_feedback(hypothesis_id);
CREATE INDEX idx_feedback_type ON scientist_feedback(feedback_type);
CREATE INDEX idx_feedback_created ON scientist_feedback(created_at DESC);

-- =============================================================================
-- 17. Chat Messages
-- =============================================================================

CREATE TABLE chat_messages (
    id VARCHAR(255) PRIMARY KEY,
    research_goal_id VARCHAR(255) NOT NULL REFERENCES research_goals(id) ON DELETE CASCADE,
    role VARCHAR(50) NOT NULL,
    content TEXT NOT NULL,
    hypothesis_references JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_chat_goal ON chat_messages(research_goal_id);
CREATE INDEX idx_chat_created ON chat_messages(created_at);

-- =============================================================================
-- 18. Research Plan Configuration
-- =============================================================================

CREATE TABLE research_plan_configurations (
    research_goal_id VARCHAR(255) PRIMARY KEY REFERENCES research_goals(id) ON DELETE CASCADE,
    require_novelty BOOLEAN DEFAULT TRUE,
    evaluation_criteria JSONB DEFAULT '[]'::jsonb,
    output_format VARCHAR(255),
    domain_constraints JSONB DEFAULT '[]'::jsonb,
    tools_enabled JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TRIGGER update_research_plan_configurations_updated_at
    BEFORE UPDATE ON research_plan_configurations
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- =============================================================================
-- Views for Common Queries
-- =============================================================================

-- Top hypotheses by Elo rating
CREATE OR REPLACE VIEW top_hypotheses AS
SELECT
    h.*,
    rg.description as research_goal_description,
    (SELECT COUNT(*) FROM reviews r WHERE r.hypothesis_id = h.id) as review_count,
    (SELECT COUNT(*) FROM tournament_matches tm
     WHERE tm.hypothesis_a_id = h.id OR tm.hypothesis_b_id = h.id) as match_count
FROM hypotheses h
JOIN research_goals rg ON h.research_goal_id = rg.id
ORDER BY h.elo_rating DESC;

-- Hypothesis win rates
CREATE OR REPLACE VIEW hypothesis_win_rates AS
SELECT
    h.id as hypothesis_id,
    h.title,
    h.elo_rating,
    COUNT(tm.id) as total_matches,
    COUNT(CASE WHEN tm.winner_id = h.id THEN 1 END) as wins,
    CASE
        WHEN COUNT(tm.id) > 0
        THEN COUNT(CASE WHEN tm.winner_id = h.id THEN 1 END)::float / COUNT(tm.id)
        ELSE 0
    END as win_rate
FROM hypotheses h
LEFT JOIN tournament_matches tm ON h.id = tm.hypothesis_a_id OR h.id = tm.hypothesis_b_id
GROUP BY h.id, h.title, h.elo_rating
ORDER BY win_rate DESC, h.elo_rating DESC;

-- Pending tasks by priority
CREATE OR REPLACE VIEW pending_tasks AS
SELECT *
FROM agent_tasks
WHERE status = 'pending'
ORDER BY priority DESC, created_at ASC;

-- =============================================================================
-- Comments
-- =============================================================================

COMMENT ON TABLE research_goals IS 'Scientist input research goals that initiate the co-scientist system';
COMMENT ON TABLE hypotheses IS 'Research hypotheses generated and refined by the system';
COMMENT ON TABLE reviews IS 'Reviews performed by the Reflection agent on hypotheses';
COMMENT ON TABLE tournament_matches IS 'Pairwise comparisons for Elo-based hypothesis ranking';
COMMENT ON TABLE proximity_edges IS 'Similarity edges between hypotheses for clustering';
COMMENT ON TABLE hypothesis_clusters IS 'Groups of similar hypotheses identified by Proximity agent';
COMMENT ON TABLE meta_reviews IS 'Synthesized feedback patterns from Meta-review agent';
COMMENT ON TABLE research_overviews IS 'Comprehensive research summaries with directions and contacts';
COMMENT ON TABLE agent_tasks IS 'Task queue for Supervisor agent to coordinate work';
COMMENT ON TABLE context_memory IS 'Checkpoints for pause/resume and crash recovery';
COMMENT ON TABLE scientist_feedback IS 'Feedback provided by human scientists';
COMMENT ON TABLE chat_messages IS 'Conversation history between scientist and system';

-- =============================================================================
-- End of Schema
-- =============================================================================
