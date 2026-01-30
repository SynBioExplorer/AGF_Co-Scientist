"""
Phase 6 Week 3 Integration Test: Observation Review Agent

Tests the ObservationReviewAgent that validates hypotheses against
literature observations extracted from citation graphs.
"""

import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.agents.observation_review import ObservationReviewAgent
from src.storage.memory import InMemoryStorage
from src.literature.citation_graph import CitationGraph, CitationNode
from schemas import (
    ResearchGoal,
    Hypothesis,
    ExperimentalProtocol,
    GenerationMethod,
    Observation,
    ObservationType,
    ObservationReviewScore,
    AgentType,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def research_goal():
    """Sample research goal for testing."""
    return ResearchGoal(
        id="test_goal_week3",
        description="Novel hypotheses for Alzheimer's treatment using FDA-approved drugs",
        preferences=["Focus on repurposing existing drugs", "Emphasize safety profiles"]
    )


@pytest.fixture
def hypothesis():
    """Sample hypothesis for testing."""
    return Hypothesis(
        id="hyp_week3_001",
        research_goal_id="test_goal_week3",
        title="Metformin activates AMPK pathway to reduce tau phosphorylation",
        summary="Metformin activates AMPK, which reduces tau hyperphosphorylation",
        hypothesis_statement="Metformin, by activating the AMPK pathway, reduces tau phosphorylation and amyloid-beta aggregation in Alzheimer's disease",
        rationale="AMPK activation has been shown to reduce tau phosphorylation in preclinical models",
        mechanism="Metformin activates AMPK which inhibits mTOR, reducing tau phosphorylation",
        experimental_protocol=ExperimentalProtocol(
            objective="Test metformin in Alzheimer's mouse model",
            methodology="Administer metformin to transgenic mice, measure tau levels",
            controls=["Vehicle control", "Positive control drug"],
            expected_outcomes=["Reduced tau phosphorylation", "Improved cognitive function"],
            success_criteria="Statistically significant reduction in tau phosphorylation"
        ),
        literature_citations=[],
        generation_method=GenerationMethod.LITERATURE_EXPLORATION,
        elo_rating=1200.0
    )


@pytest.fixture
def citation_graph():
    """Sample citation graph with papers."""
    graph = CitationGraph()

    # Add papers
    papers = [
        {
            "id": "paper1",
            "title": "Metformin activates AMPK in Alzheimer's models",
            "authors": ["Smith J", "Doe A"],
            "year": 2020,
            "doi": "10.1234/test1",
            "citation_count": 150,
            "abstract": "We demonstrated that metformin activates AMPK and reduces tau phosphorylation in transgenic mouse models of Alzheimer's disease."
        },
        {
            "id": "paper2",
            "title": "Clinical trial of metformin in Alzheimer's patients",
            "authors": ["Johnson B"],
            "year": 2019,
            "doi": "10.1234/test2",
            "citation_count": 200,
            "abstract": "Clinical trial showed metformin improved cognitive function in Alzheimer's patients with diabetes comorbidity."
        },
        {
            "id": "paper3",
            "title": "AMPK pathway reduces tau phosphorylation",
            "authors": ["Williams C"],
            "year": 2018,
            "doi": "10.1234/test3",
            "citation_count": 300,
            "abstract": "AMPK activation was found to reduce tau hyperphosphorylation through mTOR inhibition in neuronal cultures."
        }
    ]

    for paper in papers:
        # Create CitationNode directly to include all fields
        node = CitationNode(
            id=paper["id"],
            title=paper["title"],
            authors=paper["authors"],
            year=paper["year"],
            doi=paper["doi"],
            citation_count=paper["citation_count"]
        )
        # Add abstract as a custom attribute (not in CitationNode schema)
        node.abstract = paper["abstract"]
        graph.nodes[paper["id"]] = node

    return graph


@pytest.fixture
def sample_observations():
    """Sample observations for testing."""
    return [
        Observation(
            id="obs_001",
            paper_id="10.1234/test1",
            paper_title="Metformin activates AMPK in Alzheimer's models",
            observation_type=ObservationType.EXPERIMENTAL,
            text="Metformin activates AMPK and reduces tau phosphorylation in transgenic mouse models",
            context="We demonstrated that metformin activates AMPK and reduces tau phosphorylation in transgenic mouse models of Alzheimer's disease.",
            relevance_score=0.95,
            citation_count=150
        ),
        Observation(
            id="obs_002",
            paper_id="10.1234/test2",
            paper_title="Clinical trial of metformin in Alzheimer's patients",
            observation_type=ObservationType.CLINICAL,
            text="Metformin improved cognitive function in Alzheimer's patients",
            context="Clinical trial showed metformin improved cognitive function in Alzheimer's patients with diabetes comorbidity.",
            relevance_score=0.85,
            citation_count=200
        ),
        Observation(
            id="obs_003",
            paper_id="10.1234/test3",
            paper_title="AMPK pathway reduces tau phosphorylation",
            observation_type=ObservationType.MECHANISM,
            text="AMPK activation reduces tau hyperphosphorylation through mTOR inhibition",
            context="AMPK activation was found to reduce tau hyperphosphorylation through mTOR inhibition in neuronal cultures.",
            relevance_score=0.90,
            citation_count=300
        )
    ]


# ============================================================================
# Test 1: Observation Extraction from Citation Graph
# ============================================================================

def test_extract_observations_from_citation_graph(citation_graph, research_goal):
    """Test extracting observations from papers in citation graph."""
    agent = ObservationReviewAgent()

    observations = agent.extract_observations_from_papers(
        citation_graph,
        research_goal,
        max_observations=10
    )

    # Verify observations were extracted
    assert len(observations) == 3  # 3 papers in graph

    # Verify observation structure
    for obs in observations:
        assert isinstance(obs, Observation)
        assert obs.id is not None
        assert obs.paper_id is not None
        assert obs.paper_title is not None
        assert obs.observation_type in ObservationType
        assert obs.text is not None
        assert obs.context is not None
        assert 0.0 <= obs.relevance_score <= 1.0
        assert obs.citation_count >= 0

    print(f"\nExtracted {len(observations)} observations from citation graph")
    for obs in observations:
        print(f"  - {obs.observation_type.value}: {obs.text[:60]}...")


# ============================================================================
# Test 2: Observation Type Inference
# ============================================================================

def test_observation_type_inference():
    """Test observation type inference from abstract text."""
    agent = ObservationReviewAgent()

    test_cases = [
        ("Clinical trial showed patients improved", ObservationType.CLINICAL),
        ("Experiment measured protein levels", ObservationType.EXPERIMENTAL),
        ("Dataset contains 1000 samples", ObservationType.DATASET),
        ("Mechanism involves AMPK pathway", ObservationType.MECHANISM),
        ("Results showed significant effect", ObservationType.RESULT),
    ]

    for text, expected_type in test_cases:
        inferred_type = agent._infer_observation_type(text)
        assert inferred_type == expected_type, f"Expected {expected_type} for '{text}', got {inferred_type}"

    print("\nObservation type inference tests passed")


# ============================================================================
# Test 3: Key Finding Extraction
# ============================================================================

def test_key_finding_extraction():
    """Test extracting key findings from abstracts."""
    agent = ObservationReviewAgent()

    test_abstract = "Background text here. We found that metformin reduces tau levels. More discussion."

    finding = agent._extract_key_finding(test_abstract)

    # Should extract the sentence with "found"
    assert "found" in finding.lower() or "metformin" in finding.lower()

    print(f"\nExtracted finding: {finding}")


# ============================================================================
# Test 4: Observation Review Execution (Mocked LLM)
# ============================================================================

@pytest.mark.asyncio
async def test_observation_review_execution_mocked(
    hypothesis,
    sample_observations,
    research_goal
):
    """Test observation review with mocked LLM response."""
    agent = ObservationReviewAgent()

    # Mock LLM response
    mock_response = """
    {
        "explanations": [
            {
                "observation_id": "obs_001",
                "explains": true,
                "explanation_score": 0.9,
                "reasoning": "Hypothesis directly explains this observation through AMPK mechanism",
                "mechanism_match": true,
                "prediction_match": true
            },
            {
                "observation_id": "obs_002",
                "explains": true,
                "explanation_score": 0.8,
                "reasoning": "Hypothesis predicts improved cognitive function",
                "mechanism_match": true,
                "prediction_match": true
            },
            {
                "observation_id": "obs_003",
                "explains": true,
                "explanation_score": 0.95,
                "reasoning": "Hypothesis mechanism perfectly aligns with this observation",
                "mechanism_match": true,
                "prediction_match": true
            }
        ],
        "overall_score": 0.88,
        "observations_explained_count": 3,
        "observations_total_count": 3,
        "strengths": [
            "Strong mechanistic alignment with AMPK pathway literature",
            "Explains both preclinical and clinical observations"
        ],
        "weaknesses": [],
        "summary": "Hypothesis demonstrates excellent explanatory power for all observations tested."
    }
    """

    # Patch LLM client
    with patch.object(agent.llm_client, 'invoke', return_value=mock_response) as mock_invoke:
        # Already patched with return_value in context manager

        # Execute review
        review = await agent.execute(
            hypothesis=hypothesis,
            observations=sample_observations,
            research_goal=research_goal
        )

        # Verify review structure
        assert isinstance(review, ObservationReviewScore)
        assert review.id is not None
        assert review.hypothesis_id == hypothesis.id
        assert review.research_goal_id == research_goal.id
        assert len(review.observations) == 3
        assert len(review.explanations) == 3
        assert review.overall_score == 0.88
        assert review.observations_explained_count == 3
        assert review.observations_total_count == 3
        assert len(review.strengths) == 2
        assert len(review.weaknesses) == 0

        print(f"\nObservation Review Results:")
        print(f"  Overall Score: {review.overall_score}")
        print(f"  Explained: {review.observations_explained_count}/{review.observations_total_count}")
        print(f"  Summary: {review.summary[:100]}...")


# ============================================================================
# Test 5: Observation Review with Citation Graph
# ============================================================================

@pytest.mark.asyncio
async def test_observation_review_with_citation_graph(
    hypothesis,
    citation_graph,
    research_goal
):
    """Test observation review using citation graph (end-to-end with mocks)."""
    agent = ObservationReviewAgent()

    # Mock LLM response
    mock_response = """
    {
        "explanations": [
            {
                "observation_id": "obs_001",
                "explains": true,
                "explanation_score": 0.9,
                "reasoning": "Test reasoning",
                "mechanism_match": true,
                "prediction_match": true
            },
            {
                "observation_id": "obs_002",
                "explains": true,
                "explanation_score": 0.8,
                "reasoning": "Test reasoning",
                "mechanism_match": true,
                "prediction_match": true
            },
            {
                "observation_id": "obs_003",
                "explains": true,
                "explanation_score": 0.85,
                "reasoning": "Test reasoning",
                "mechanism_match": true,
                "prediction_match": true
            }
        ],
        "overall_score": 0.85,
        "observations_explained_count": 3,
        "observations_total_count": 3,
        "strengths": ["Good alignment"],
        "weaknesses": [],
        "summary": "Strong hypothesis"
    }
    """

    with patch.object(agent.llm_client, 'invoke', return_value=mock_response) as mock_invoke:
        # Already patched with return_value in context manager

        # Execute with citation graph
        review = await agent.execute_with_citation_graph(
            hypothesis=hypothesis,
            citation_graph=citation_graph,
            research_goal=research_goal,
            max_observations=10
        )

        # Verify review
        assert isinstance(review, ObservationReviewScore)
        assert review.overall_score == 0.85
        assert review.observations_explained_count == 3

        print(f"\nCitation Graph Review:")
        print(f"  Papers in graph: {len(citation_graph.nodes)}")
        print(f"  Observations extracted: {len(review.observations)}")
        print(f"  Overall score: {review.overall_score}")


# ============================================================================
# Test 6: Empty Citation Graph Handling
# ============================================================================

@pytest.mark.asyncio
async def test_empty_citation_graph(hypothesis, research_goal):
    """Test observation review with empty citation graph."""
    agent = ObservationReviewAgent()
    empty_graph = CitationGraph()

    review = await agent.execute_with_citation_graph(
        hypothesis=hypothesis,
        citation_graph=empty_graph,
        research_goal=research_goal
    )

    # Should return empty review
    assert review.observations_total_count == 0
    assert review.observations_explained_count == 0
    assert review.overall_score == 0.0
    assert len(review.weaknesses) > 0  # Should note no observations available

    print("\nEmpty graph handled correctly - returned empty review")


# ============================================================================
# Test 7: Storage Integration
# ============================================================================

@pytest.mark.asyncio
async def test_storage_integration(hypothesis, sample_observations, research_goal):
    """Test observation review storage integration."""
    storage = InMemoryStorage()
    await storage.connect()

    # Store hypothesis
    await storage.add_hypothesis(hypothesis)

    agent = ObservationReviewAgent()

    # Mock LLM
    mock_response = """
    {
        "explanations": [
            {"observation_id": "obs_001", "explains": true, "explanation_score": 0.9, "reasoning": "Test", "mechanism_match": true, "prediction_match": true},
            {"observation_id": "obs_002", "explains": true, "explanation_score": 0.8, "reasoning": "Test", "mechanism_match": true, "prediction_match": true}
        ],
        "overall_score": 0.85,
        "observations_explained_count": 2,
        "observations_total_count": 2,
        "strengths": ["Good"],
        "weaknesses": [],
        "summary": "Good hypothesis"
    }
    """

    with patch.object(agent.llm_client, 'invoke', return_value=mock_response) as mock_invoke:
        # Already patched with return_value in context manager

        # Execute review
        review = await agent.execute(
            hypothesis=hypothesis,
            observations=sample_observations[:2],  # Use first 2
            research_goal=research_goal
        )

        # Store review
        await storage.add_observation_review(review)

        # Retrieve review
        retrieved = await storage.get_observation_review(hypothesis.id)
        assert retrieved is not None
        assert retrieved.id == review.id
        assert retrieved.overall_score == review.overall_score

        # Get by goal
        reviews_by_goal = await storage.get_observation_reviews_by_goal(research_goal.id)
        assert len(reviews_by_goal) == 1
        assert reviews_by_goal[0].id == review.id

        print(f"\nStorage integration successful:")
        print(f"  Stored review: {review.id}")
        print(f"  Retrieved review: {retrieved.id}")


# ============================================================================
# Run Tests
# ============================================================================

if __name__ == "__main__":
    print("Running Phase 6 Week 3 Integration Tests...")
    print("=" * 70)

    # Run with pytest
    import pytest
    exit_code = pytest.main([
        __file__,
        "-v",
        "-s",
        "--tb=short"
    ])

    sys.exit(exit_code)
