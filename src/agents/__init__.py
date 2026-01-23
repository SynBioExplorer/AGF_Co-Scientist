"""AI Co-Scientist agent implementations.

This module provides all specialized agents for the co-scientist system:
- GenerationAgent: Creates hypotheses via literature exploration or debate
- ReflectionAgent: Reviews and scores hypotheses
- RankingAgent: Pairwise hypothesis comparison for tournaments
- EvolutionAgent: Refines hypotheses through various strategies
- ProximityAgent: Builds similarity graphs for clustering
- MetaReviewAgent: Synthesizes feedback patterns
- SupervisorAgent: Orchestrates all agents
"""

from src.agents.base import BaseAgent
from src.agents.generation import GenerationAgent
from src.agents.reflection import ReflectionAgent
from src.agents.ranking import RankingAgent
from src.agents.evolution import EvolutionAgent
from src.agents.proximity import ProximityAgent
from src.agents.meta_review import MetaReviewAgent
from src.agents.supervisor import SupervisorAgent

__all__ = [
    "BaseAgent",
    "GenerationAgent",
    "ReflectionAgent",
    "RankingAgent",
    "EvolutionAgent",
    "ProximityAgent",
    "MetaReviewAgent",
    "SupervisorAgent",
]
