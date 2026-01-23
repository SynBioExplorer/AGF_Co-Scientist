"""LangGraph workflow for Generate → Review → Rank → Evolve pipeline (Phase 3)"""

from typing import Dict, Any
from langgraph.graph import StateGraph, END
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent / "03_architecture"))
from schemas import ResearchGoal, ReviewType, EvolutionStrategy

from src.graphs.state import WorkflowState
from src.agents.generation import GenerationAgent
from src.agents.reflection import ReflectionAgent
from src.agents.ranking import RankingAgent
from src.agents.evolution import EvolutionAgent
from src.agents.proximity import ProximityAgent
from src.agents.meta_review import MetaReviewAgent
from src.tournament.elo import TournamentRanker
from src.storage.memory import storage
import structlog

logger = structlog.get_logger()


class CoScientistWorkflow:
    """LangGraph workflow for AI Co-Scientist (Phase 3: Full Pipeline)"""

    def __init__(self, enable_evolution: bool = False):
        self.generation_agent = GenerationAgent()
        self.reflection_agent = ReflectionAgent()
        self.ranking_agent = RankingAgent()
        self.evolution_agent = EvolutionAgent()
        self.proximity_agent = ProximityAgent()
        self.meta_review_agent = MetaReviewAgent()
        self.ranker = TournamentRanker()
        self.enable_evolution = enable_evolution

    def generate_node(self, state: WorkflowState) -> Dict[str, Any]:
        """Generate new hypotheses"""
        logger.info("Node: Generate", iteration=state["iteration"])

        # Generate 2-3 hypotheses per iteration
        num_hypotheses = 2
        new_hypotheses = []

        for i in range(num_hypotheses):
            hypothesis = self.generation_agent.execute(
                research_goal=state["research_goal"]
            )
            storage.add_hypothesis(hypothesis)
            new_hypotheses.append(hypothesis)

            logger.info(
                "Hypothesis generated",
                hypothesis_id=hypothesis.id,
                title=hypothesis.title,
                elo=hypothesis.elo_rating
            )

        return {"hypotheses": new_hypotheses}

    def review_node(self, state: WorkflowState) -> Dict[str, Any]:
        """Review hypotheses"""
        logger.info("Node: Review", iteration=state["iteration"])

        new_reviews = []

        # Get hypotheses from this iteration
        recent_hypotheses = state["hypotheses"][-2:] if len(state["hypotheses"]) > 2 else state["hypotheses"]

        for hypothesis in recent_hypotheses:
            # Perform initial review
            review = self.reflection_agent.execute(
                hypothesis=hypothesis,
                review_type=ReviewType.INITIAL
            )
            storage.add_review(review)
            new_reviews.append(review)

            logger.info(
                "Review completed",
                hypothesis_id=hypothesis.id,
                review_id=review.id,
                passed=review.passed,
                quality=review.quality_score
            )

        # Calculate average quality score
        quality_scores = [r.quality_score for r in new_reviews if r.quality_score is not None]
        avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else None

        return {
            "reviews": new_reviews,
            "average_quality_score": avg_quality
        }

    def rank_node(self, state: WorkflowState) -> Dict[str, Any]:
        """Run tournament matches and update Elo ratings"""
        logger.info("Node: Rank", iteration=state["iteration"])

        all_hypotheses = storage.get_all_hypotheses()

        if len(all_hypotheses) < 2:
            logger.warning("Not enough hypotheses for tournament", count=len(all_hypotheses))
            return {"matches": []}

        # Select pairs for comparison
        pairs = self.ranker.select_match_pairs(all_hypotheses, top_n=5)

        new_matches = []
        for hyp_a, hyp_b in pairs[:3]:  # Limit to 3 matches per iteration
            # Run match
            match = self.ranking_agent.execute(
                hypothesis_a=hyp_a,
                hypothesis_b=hyp_b,
                method="tournament",
                multi_turn=False,
                goal=state["research_goal"].description
            )
            storage.add_match(match)
            new_matches.append(match)

            # Update Elo ratings
            updated_a, updated_b = self.ranker.elo_calculator.apply_match_results(
                hyp_a, hyp_b, match
            )
            storage.update_hypothesis(updated_a)
            storage.update_hypothesis(updated_b)

            logger.info(
                "Match completed",
                match_id=match.id,
                winner_id=match.winner_id,
                elo_a=updated_a.elo_rating,
                elo_b=updated_b.elo_rating
            )

        # Get current top hypothesis
        top_hyps = storage.get_top_hypotheses(n=1)
        top_id = top_hyps[0].id if top_hyps else None

        return {
            "matches": new_matches,
            "top_hypothesis_id": top_id
        }

    def should_continue_node(self, state: WorkflowState) -> str:
        """Decide whether to continue or end the workflow"""
        iteration = state["iteration"]
        max_iterations = state.get("max_iterations", 5)

        # Check iteration limit
        if iteration >= max_iterations:
            logger.info("Stopping: Max iterations reached", iteration=iteration)
            return "end"

        # Check if we have enough hypotheses
        if len(state.get("hypotheses", [])) < 2:
            logger.info("Continuing: Need more hypotheses")
            return "continue"

        # Simple convergence check: stop after 3 iterations if quality is high
        avg_quality = state.get("average_quality_score")
        if avg_quality and avg_quality > 0.7 and iteration >= 3:
            logger.info(
                "Stopping: Quality threshold met",
                avg_quality=avg_quality,
                iteration=iteration
            )
            return "end"

        # Continue by default
        logger.info("Continuing workflow", iteration=iteration)
        return "continue"

    def increment_iteration(self, state: WorkflowState) -> Dict[str, Any]:
        """Increment iteration counter"""
        return {"iteration": state["iteration"] + 1}

    def evolve_node(self, state: WorkflowState) -> Dict[str, Any]:
        """Evolve top hypotheses (optional)"""
        logger.info("Node: Evolve", iteration=state["iteration"])

        if not self.enable_evolution:
            logger.info("Evolution disabled, skipping")
            return {"hypotheses": []}

        # Get top hypotheses for evolution
        top_hypotheses = storage.get_top_hypotheses(n=2)
        evolved_hypotheses = []

        for hypothesis in top_hypotheses:
            # Get reviews for context
            reviews = storage.get_reviews_for_hypothesis(hypothesis.id)

            # Evolve with feasibility improvement strategy
            evolved = self.evolution_agent.execute(
                hypothesis=hypothesis,
                strategy=EvolutionStrategy.FEASIBILITY,
                reviews=reviews
            )

            storage.add_hypothesis(evolved)
            evolved_hypotheses.append(evolved)

            logger.info(
                "Hypothesis evolved",
                original_id=hypothesis.id,
                evolved_id=evolved.id,
                strategy="FEASIBILITY"
            )

        return {"hypotheses": evolved_hypotheses}

    def finalize_node(self, state: WorkflowState) -> Dict[str, Any]:
        """Finalize workflow with proximity analysis and meta-review"""
        logger.info("Node: Finalize")

        # Build proximity graph
        all_hypotheses = storage.get_all_hypotheses()
        if len(all_hypotheses) >= 2:
            proximity_graph = self.proximity_agent.execute(
                hypotheses=all_hypotheses,
                research_goal_id=state["research_goal"].id,
                similarity_threshold=0.6
            )

            logger.info(
                "Proximity graph built",
                num_edges=len(proximity_graph.edges),
                num_clusters=len(proximity_graph.clusters)
            )

        # Generate meta-review
        all_reviews = list(storage.reviews.values())
        all_matches = storage.get_all_matches()

        if all_reviews and all_matches:
            meta_review = self.meta_review_agent.execute(
                reviews=all_reviews,
                matches=all_matches,
                goal=state["research_goal"].description,
                preferences=state["research_goal"].preferences
            )

            logger.info(
                "Meta-review generated",
                num_strengths=len(meta_review.recurring_strengths),
                num_weaknesses=len(meta_review.recurring_weaknesses)
            )

            # Generate research overview
            top_hypotheses = storage.get_top_hypotheses(n=5)
            overview = self.meta_review_agent.generate_research_overview(
                goal=state["research_goal"].description,
                top_hypotheses=top_hypotheses,
                meta_review=meta_review,
                preferences=state["research_goal"].preferences
            )

            logger.info(
                "Research overview generated",
                num_directions=len(overview.research_directions),
                num_contacts=len(overview.suggested_contacts)
            )

        return {}

    def build_graph(self) -> StateGraph:
        """Build the LangGraph workflow"""

        # Create graph
        workflow = StateGraph(WorkflowState)

        # Add nodes
        workflow.add_node("generate", self.generate_node)
        workflow.add_node("review", self.review_node)
        workflow.add_node("rank", self.rank_node)
        workflow.add_node("evolve", self.evolve_node)
        workflow.add_node("increment", self.increment_iteration)
        workflow.add_node("finalize", self.finalize_node)

        # Add edges
        workflow.set_entry_point("generate")
        workflow.add_edge("generate", "review")
        workflow.add_edge("review", "rank")

        # Optional evolution step
        if self.enable_evolution:
            workflow.add_edge("rank", "evolve")
            workflow.add_edge("evolve", "increment")
        else:
            workflow.add_edge("rank", "increment")

        # Conditional edge: continue or finalize
        workflow.add_conditional_edges(
            "increment",
            self.should_continue_node,
            {
                "continue": "generate",
                "end": "finalize"
            }
        )

        # End after finalization
        workflow.add_edge("finalize", END)

        return workflow.compile()

    def run(
        self,
        research_goal: ResearchGoal,
        max_iterations: int = 5
    ) -> Dict[str, Any]:
        """Run the complete workflow

        Args:
            research_goal: Research goal to explore
            max_iterations: Maximum number of Generate → Review → Rank cycles

        Returns:
            Final state with all hypotheses, reviews, and matches
        """
        logger.info("Starting workflow", goal=research_goal.description[:100])

        # Store research goal
        storage.add_research_goal(research_goal)

        # Initialize state
        initial_state: WorkflowState = {
            "research_goal": research_goal,
            "hypotheses": [],
            "reviews": [],
            "matches": [],
            "iteration": 1,
            "max_iterations": max_iterations,
            "convergence_threshold": 50.0,  # Elo variance threshold
            "top_hypothesis_id": None,
            "average_quality_score": None,
            "should_continue": True,
            "reason_for_stopping": None
        }

        # Build and run graph
        graph = self.build_graph()
        final_state = graph.invoke(initial_state)

        logger.info(
            "Workflow complete",
            iterations=final_state["iteration"],
            hypotheses=len(final_state["hypotheses"]),
            reviews=len(final_state["reviews"]),
            matches=len(final_state["matches"])
        )

        return final_state
