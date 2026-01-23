"""Safety review agent for ethical and experimental risk assessment

This agent reviews research goals and hypotheses for potential safety concerns,
including dual-use risks, biosafety, human subjects, environmental impact,
and regulatory compliance.
"""

from typing import Dict
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent / "03_architecture"))
from schemas import ResearchGoal, Hypothesis

from src.agents.base import BaseAgent
from src.llm.factory import get_llm_client
from src.config import settings
from src.utils.errors import CoScientistError
from src.utils.json_parser import parse_llm_json
import structlog

logger = structlog.get_logger()


class SafetyReviewError(CoScientistError):
    """Raised when safety review fails"""
    pass


class SafetyAgent(BaseAgent):
    """Safety review agent for research goals and hypotheses

    Assesses ethical concerns and experimental safety risks across categories:
    - Dual-use potential (military, surveillance, bioweapons)
    - Biosafety risks (pathogen enhancement, high-risk organisms)
    - Human subjects (IRB requirements, vulnerable populations)
    - Environmental impact (GMO release, toxic waste, ecosystem)
    - Data privacy (genetic data, medical records, PII)
    - Experimental hazards (chemical, biological, physical, regulatory)
    """

    def __init__(self):
        llm_client = get_llm_client(
            model=settings.supervisor_model,  # Use fast model for reviews
            agent_name="safety"
        )
        super().__init__(llm_client, "SafetyAgent")

    async def execute(self, **kwargs) -> Dict:
        """Execute safety review based on provided parameters

        Args:
            goal: ResearchGoal to review (for goal review)
            hypothesis: Hypothesis to review (for hypothesis review)

        Returns:
            Safety assessment dictionary
        """
        if "goal" in kwargs:
            return await self.review_goal(kwargs["goal"])
        elif "hypothesis" in kwargs:
            return await self.review_hypothesis(kwargs["hypothesis"])
        else:
            raise SafetyReviewError(
                "SafetyAgent.execute() requires either 'goal' or 'hypothesis' parameter"
            )

    async def review_goal(self, goal: ResearchGoal) -> Dict:
        """Review research goal for ethical and safety concerns

        Args:
            goal: Research goal to review

        Returns:
            Dict with:
                - safety_score: 0.0-1.0 (1.0 = completely safe)
                - concerns: List of ethical/safety concerns
                - recommendations: List of recommendations
                - requires_ethics_review: Boolean
                - risk_categories: Dict of risk scores by category
        """
        self.log_execution(
            task="goal_safety_review",
            goal_id=goal.id
        )

        constraints_text = ', '.join(goal.constraints) if goal.constraints else 'None specified'
        preferences_text = ', '.join(goal.preferences) if goal.preferences else 'None specified'

        prompt = f"""You are a research ethics and safety reviewer. Review this research goal for ethical and safety concerns.

Research Goal: {goal.description}
Constraints: {constraints_text}
Preferences: {preferences_text}
Laboratory Context: {goal.laboratory_context or 'Not specified'}

Assess the following risk categories (0.0-1.0 scale, where higher = MORE risk):

1. **Dual-Use Potential**: Could this research be misused for harmful purposes?
   - Military/weapons applications
   - Surveillance or privacy violations
   - Bioweapons or toxins

2. **Biosafety Risks**: Does this involve hazardous biological materials?
   - Pathogen enhancement (gain-of-function)
   - Creation of new pathogens
   - Work with high-risk organisms (BSL-3/4)

3. **Human Subjects**: Does this involve human participants?
   - Requires IRB/ethics board approval?
   - Vulnerable populations involved?
   - Informed consent issues?

4. **Environmental Impact**: Could this harm the environment?
   - Release of GMOs
   - Toxic waste generation
   - Ecosystem disruption

5. **Data Privacy**: Does this involve sensitive data?
   - Human genetic data
   - Medical records
   - Personally identifiable information

Return ONLY a JSON object:
{{
    "safety_score": 0.0-1.0 (where 1.0 = completely safe, calculated as 1 - average_risk),
    "concerns": ["concern1", "concern2", ...],
    "recommendations": ["recommendation1", "recommendation2", ...],
    "requires_ethics_review": true/false,
    "risk_categories": {{
        "dual_use": 0.0-1.0,
        "biosafety": 0.0-1.0,
        "human_subjects": 0.0-1.0,
        "environmental": 0.0-1.0,
        "data_privacy": 0.0-1.0
    }}
}}

Respond with ONLY the JSON object, no additional text."""

        # Invoke LLM asynchronously
        response = await self.llm_client.ainvoke(prompt)

        # Parse response
        try:
            data = parse_llm_json(response, agent_name="SafetyAgent")

            # Ensure all required fields exist with defaults
            data.setdefault("concerns", [])
            data.setdefault("recommendations", [])
            data.setdefault("requires_ethics_review", False)
            data.setdefault("risk_categories", {})

            # Calculate overall safety score if not provided
            if "safety_score" not in data:
                risk_scores = data.get("risk_categories", {})
                if risk_scores:
                    avg_risk = sum(risk_scores.values()) / len(risk_scores)
                    data["safety_score"] = round(1.0 - avg_risk, 3)
                else:
                    data["safety_score"] = 0.5  # Default to uncertain

            self.logger.info(
                "Goal safety review complete",
                goal_id=goal.id,
                safety_score=data["safety_score"],
                num_concerns=len(data.get("concerns", [])),
                requires_ethics=data.get("requires_ethics_review", False)
            )

            return data

        except Exception as e:
            raise SafetyReviewError(
                f"Failed to parse goal safety review: {e}\nResponse: {response[:500]}"
            )

    async def review_hypothesis(self, hypothesis: Hypothesis) -> Dict:
        """Review hypothesis for experimental safety risks

        Args:
            hypothesis: Hypothesis to review

        Returns:
            Dict with:
                - safety_score: 0.0-1.0 (1.0 = completely safe)
                - risks: List of safety risks
                - mitigations: List of recommended mitigations
                - requires_special_approval: Boolean
                - hazard_categories: Dict of hazard scores by category
        """
        self.log_execution(
            task="hypothesis_safety_review",
            hypothesis_id=hypothesis.id
        )

        # Format experimental protocol if available
        protocol_text = "No experimental protocol provided"
        if hypothesis.experimental_protocol:
            ep = hypothesis.experimental_protocol
            controls_text = ', '.join(ep.controls) if ep.controls else 'None specified'
            materials_text = ', '.join(ep.materials) if ep.materials else 'None specified'
            protocol_text = f"""
Objective: {ep.objective}
Methodology: {ep.methodology}
Controls: {controls_text}
Materials: {materials_text}
Success Criteria: {ep.success_criteria}
"""

        prompt = f"""You are a laboratory safety reviewer. Review this hypothesis and its experimental protocol for safety risks.

Hypothesis Title: {hypothesis.title}
Statement: {hypothesis.hypothesis_statement}
Rationale: {hypothesis.rationale}
Mechanism: {hypothesis.mechanism or 'Not specified'}

Experimental Protocol:
{protocol_text}

Assess safety risks in the proposed experiments using a 0.0-1.0 scale (higher = MORE risk):

1. **Chemical Hazards**: Use of toxic, flammable, corrosive, or reactive chemicals?
   - Carcinogens, mutagens, teratogens
   - Flammable solvents or gases
   - Strong acids/bases, oxidizers

2. **Biological Hazards**: Use of infectious agents, GMOs, or human samples?
   - Pathogens (bacteria, viruses, fungi)
   - Genetically modified organisms
   - Human blood, tissues, cell lines

3. **Physical Hazards**: Radiation, high voltage, cryogenics, high pressure?
   - Ionizing or non-ionizing radiation
   - High voltage equipment
   - Extreme temperatures, pressures

4. **Regulatory Compliance**: Special permits or approvals needed?
   - IACUC approval for animal use
   - IRB approval for human subjects
   - DEA license for controlled substances
   - Biosafety committee approval

Return ONLY a JSON object:
{{
    "safety_score": 0.0-1.0 (where 1.0 = completely safe, calculated as 1 - average_hazard),
    "risks": ["risk1", "risk2", ...],
    "mitigations": ["mitigation1", "mitigation2", ...],
    "requires_special_approval": true/false,
    "approval_types_needed": ["IACUC", "IRB", etc.] or [],
    "hazard_categories": {{
        "chemical": 0.0-1.0,
        "biological": 0.0-1.0,
        "physical": 0.0-1.0,
        "regulatory": 0.0-1.0
    }}
}}

Respond with ONLY the JSON object, no additional text."""

        # Invoke LLM asynchronously
        response = await self.llm_client.ainvoke(prompt)

        # Parse response
        try:
            data = parse_llm_json(response, agent_name="SafetyAgent")

            # Ensure all required fields exist with defaults
            data.setdefault("risks", [])
            data.setdefault("mitigations", [])
            data.setdefault("requires_special_approval", False)
            data.setdefault("approval_types_needed", [])
            data.setdefault("hazard_categories", {})

            # Calculate overall safety score if not provided
            if "safety_score" not in data:
                hazard_scores = data.get("hazard_categories", {})
                if hazard_scores:
                    avg_hazard = sum(hazard_scores.values()) / len(hazard_scores)
                    data["safety_score"] = round(1.0 - avg_hazard, 3)
                else:
                    data["safety_score"] = 0.5  # Default to uncertain

            self.logger.info(
                "Hypothesis safety review complete",
                hypothesis_id=hypothesis.id,
                safety_score=data["safety_score"],
                num_risks=len(data.get("risks", [])),
                requires_approval=data.get("requires_special_approval", False)
            )

            return data

        except Exception as e:
            raise SafetyReviewError(
                f"Failed to parse hypothesis safety review: {e}\nResponse: {response[:500]}"
            )

    def is_safe(self, safety_assessment: Dict, threshold: float = 0.5) -> bool:
        """Determine if goal/hypothesis passes safety threshold

        Args:
            safety_assessment: Output from review_goal() or review_hypothesis()
            threshold: Minimum safety score to pass (default 0.5)

        Returns:
            True if safe (score >= threshold), False otherwise
        """
        safety_score = safety_assessment.get("safety_score", 0.0)
        return safety_score >= threshold

    def requires_human_review(self, safety_assessment: Dict) -> bool:
        """Determine if safety assessment requires human ethics review

        Args:
            safety_assessment: Output from review_goal() or review_hypothesis()

        Returns:
            True if human review required
        """
        # Check for explicit ethics review requirement
        if safety_assessment.get("requires_ethics_review", False):
            return True
        if safety_assessment.get("requires_special_approval", False):
            return True

        # Check for high-risk categories
        risk_categories = safety_assessment.get("risk_categories", {})
        hazard_categories = safety_assessment.get("hazard_categories", {})

        all_categories = {**risk_categories, **hazard_categories}

        # If any category has risk > 0.7, require human review
        for category, score in all_categories.items():
            if score > 0.7:
                return True

        return False

    def get_safety_summary(self, safety_assessment: Dict) -> str:
        """Generate human-readable safety summary

        Args:
            safety_assessment: Output from review_goal() or review_hypothesis()

        Returns:
            Formatted summary string
        """
        score = safety_assessment.get("safety_score", 0.0)

        # Determine safety level
        if score >= 0.8:
            level = "LOW RISK"
        elif score >= 0.5:
            level = "MODERATE RISK"
        else:
            level = "HIGH RISK"

        summary_lines = [
            f"Safety Assessment: {level} (score: {score:.2f})",
            ""
        ]

        # Add concerns/risks
        concerns = safety_assessment.get("concerns", []) or safety_assessment.get("risks", [])
        if concerns:
            summary_lines.append("Concerns/Risks:")
            for concern in concerns:
                summary_lines.append(f"  - {concern}")
            summary_lines.append("")

        # Add recommendations/mitigations
        recommendations = (
            safety_assessment.get("recommendations", []) or
            safety_assessment.get("mitigations", [])
        )
        if recommendations:
            summary_lines.append("Recommendations:")
            for rec in recommendations:
                summary_lines.append(f"  - {rec}")
            summary_lines.append("")

        # Note if human review required
        if self.requires_human_review(safety_assessment):
            summary_lines.append("⚠️ HUMAN ETHICS REVIEW REQUIRED")

        return "\n".join(summary_lines)
