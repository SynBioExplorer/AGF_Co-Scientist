"""Chat interface for scientist interaction with AI Co-Scientist"""

from fastapi import APIRouter, HTTPException
from datetime import datetime
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "03_Architecture"))

from src.api.models import ChatRequest, ChatResponse
from src.storage.memory import storage
from src.llm.factory import get_llm_client
from src.config import settings
from src.utils.ids import generate_id
from schemas import ChatMessage
import structlog

logger = structlog.get_logger()
router = APIRouter()


# Store chat history per goal (in-memory for now)
_chat_history: dict[str, list[ChatMessage]] = {}


def get_chat_history(goal_id: str) -> list[ChatMessage]:
    """Get chat history for a goal"""
    return _chat_history.get(goal_id, [])


def add_chat_message(goal_id: str, message: ChatMessage) -> None:
    """Add a message to chat history"""
    if goal_id not in _chat_history:
        _chat_history[goal_id] = []
    _chat_history[goal_id].append(message)


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Chat with the AI Co-Scientist about a research goal.

    The chat interface provides:
    - Q&A about generated hypotheses
    - Explanations of ranking decisions
    - Research direction guidance
    - Follow-up questions about findings

    Args:
        request: Chat request with message, goal_id, and optional context

    Returns:
        AI response with referenced hypotheses
    """
    logger.info(
        "Chat request received",
        goal_id=request.goal_id,
        message_preview=request.message[:100]
    )

    # Verify goal exists
    goal = storage.get_research_goal(request.goal_id)
    if not goal:
        raise HTTPException(status_code=404, detail="Research goal not found")

    # Get top hypotheses for context
    all_hypotheses = storage.get_hypotheses_by_goal(request.goal_id)
    top_hypotheses = sorted(
        all_hypotheses,
        key=lambda h: h.elo_rating or 1200.0,
        reverse=True
    )[:5]

    # If specific hypotheses requested, include those
    context_hypotheses = top_hypotheses
    if request.context_hypothesis_ids:
        specific = [
            storage.get_hypothesis(hid)
            for hid in request.context_hypothesis_ids
        ]
        specific = [h for h in specific if h is not None]
        # Combine specific with top, deduplicating
        seen_ids = {h.id for h in specific}
        context_hypotheses = specific + [
            h for h in top_hypotheses if h.id not in seen_ids
        ]
        context_hypotheses = context_hypotheses[:7]  # Limit total context

    # Get recent chat history
    history = get_chat_history(request.goal_id)[-5:]  # Last 5 messages

    # Build context for LLM
    hypothesis_context = "\n\n".join([
        f"**Hypothesis {i+1}: {h.title}** (Elo: {h.elo_rating:.0f})\n"
        f"Statement: {h.hypothesis_statement}\n"
        f"Summary: {h.summary}"
        for i, h in enumerate(context_hypotheses)
    ])

    history_context = ""
    if history:
        history_context = "\n\n**Recent Chat History:**\n" + "\n".join([
            f"{'Scientist' if msg.role == 'scientist' else 'AI'}: {msg.content}"
            for msg in history
        ])

    # Build prompt
    system_prompt = f"""You are an AI research assistant for the AI Co-Scientist system.
You help scientists understand and explore generated hypotheses.

**Research Goal:**
{goal.description}

**Constraints:** {', '.join(goal.constraints) if goal.constraints else 'None specified'}
**Preferences:** {', '.join(goal.preferences) if goal.preferences else 'None specified'}

**Top Hypotheses:**
{hypothesis_context}
{history_context}

When responding:
1. Be scientifically rigorous and precise
2. Reference specific hypotheses by number when relevant
3. Explain rankings and tournament results if asked
4. Suggest potential follow-up experiments or directions
5. Acknowledge limitations and uncertainties
6. Keep responses focused and actionable

Scientist's Question: {request.message}
"""

    # Invoke LLM
    try:
        llm_client = get_llm_client(
            model=settings.supervisor_model,  # Use lighter model for chat
            agent_name="chat"
        )
        response_text = llm_client.invoke(system_prompt)
    except Exception as e:
        logger.error("Chat LLM invocation failed", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate response: {str(e)}"
        )

    # Store messages in history
    scientist_msg = ChatMessage(
        id=generate_id("msg"),
        role="scientist",
        content=request.message,
        hypothesis_references=request.context_hypothesis_ids or [],
    )
    add_chat_message(request.goal_id, scientist_msg)

    system_msg = ChatMessage(
        id=generate_id("msg"),
        role="system",
        content=response_text,
        hypothesis_references=[h.id for h in context_hypotheses],
    )
    add_chat_message(request.goal_id, system_msg)

    logger.info(
        "Chat response generated",
        goal_id=request.goal_id,
        response_length=len(response_text),
        hypotheses_referenced=len(context_hypotheses)
    )

    return ChatResponse(
        message=response_text,
        context_used=[h.id for h in context_hypotheses],
        timestamp=datetime.utcnow(),
    )


@router.get("/chat/{goal_id}/history")
async def get_chat_history_endpoint(goal_id: str):
    """Get chat history for a research goal.

    Args:
        goal_id: Research goal ID

    Returns:
        List of chat messages
    """
    # Verify goal exists
    goal = storage.get_research_goal(goal_id)
    if not goal:
        raise HTTPException(status_code=404, detail="Research goal not found")

    history = get_chat_history(goal_id)

    return {
        "goal_id": goal_id,
        "messages": [
            {
                "id": msg.id,
                "role": msg.role,
                "content": msg.content,
                "hypothesis_references": msg.hypothesis_references,
                "timestamp": msg.created_at.isoformat(),
            }
            for msg in history
        ],
        "total_messages": len(history),
    }


@router.delete("/chat/{goal_id}/history")
async def clear_chat_history(goal_id: str):
    """Clear chat history for a research goal.

    Args:
        goal_id: Research goal ID

    Returns:
        Confirmation message
    """
    # Verify goal exists
    goal = storage.get_research_goal(goal_id)
    if not goal:
        raise HTTPException(status_code=404, detail="Research goal not found")

    if goal_id in _chat_history:
        cleared_count = len(_chat_history[goal_id])
        _chat_history[goal_id] = []
        logger.info("Chat history cleared", goal_id=goal_id, messages_cleared=cleared_count)
    else:
        cleared_count = 0

    return {
        "status": "cleared",
        "goal_id": goal_id,
        "messages_cleared": cleared_count,
    }


@router.post("/chat/{goal_id}/explain-hypothesis/{hypothesis_id}")
async def explain_hypothesis(goal_id: str, hypothesis_id: str):
    """Get an explanation of a specific hypothesis.

    Convenience endpoint that generates a detailed explanation of
    a hypothesis including its rationale, mechanism, and experimental approach.

    Args:
        goal_id: Research goal ID
        hypothesis_id: Hypothesis ID to explain

    Returns:
        Detailed explanation
    """
    # Verify goal and hypothesis exist
    goal = storage.get_research_goal(goal_id)
    if not goal:
        raise HTTPException(status_code=404, detail="Research goal not found")

    hypothesis = storage.get_hypothesis(hypothesis_id)
    if not hypothesis:
        raise HTTPException(status_code=404, detail="Hypothesis not found")

    if hypothesis.research_goal_id != goal_id:
        raise HTTPException(status_code=400, detail="Hypothesis does not belong to this goal")

    # Get reviews and tournament record
    reviews = storage.get_reviews_for_hypothesis(hypothesis_id)
    matches = storage.get_matches_for_hypothesis(hypothesis_id)
    wins = len([m for m in matches if m.winner_id == hypothesis_id])
    win_rate = wins / len(matches) if matches else 0.0

    # Build explanation prompt
    review_summary = ""
    if reviews:
        avg_quality = sum(r.quality_score or 0 for r in reviews) / len(reviews)
        review_summary = f"Average quality score: {avg_quality:.2f}"
        strengths = []
        weaknesses = []
        for r in reviews:
            strengths.extend(r.strengths[:2])
            weaknesses.extend(r.weaknesses[:2])
        if strengths:
            review_summary += f"\nKey strengths: {', '.join(set(strengths)[:3])}"
        if weaknesses:
            review_summary += f"\nKey weaknesses: {', '.join(set(weaknesses)[:3])}"

    prompt = f"""Provide a clear, scientific explanation of this hypothesis:

**Title:** {hypothesis.title}
**Statement:** {hypothesis.hypothesis_statement}
**Rationale:** {hypothesis.rationale}
**Mechanism:** {hypothesis.mechanism or 'Not specified'}
**Elo Rating:** {hypothesis.elo_rating:.0f} (Tournament record: {wins}W-{len(matches)-wins}L, {win_rate:.1%} win rate)
{f'**Review Summary:** {review_summary}' if review_summary else ''}

Please explain:
1. What this hypothesis proposes and why it matters
2. The scientific basis and key assumptions
3. How it could be tested experimentally
4. Potential limitations and risks
5. Why it ranks where it does among other hypotheses

Keep the explanation accessible but scientifically rigorous.
"""

    # Invoke LLM
    try:
        llm_client = get_llm_client(
            model=settings.supervisor_model,
            agent_name="chat"
        )
        explanation = llm_client.invoke(prompt)
    except Exception as e:
        logger.error("Explanation generation failed", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate explanation: {str(e)}"
        )

    return {
        "hypothesis_id": hypothesis_id,
        "title": hypothesis.title,
        "elo_rating": hypothesis.elo_rating,
        "tournament_record": {
            "wins": wins,
            "losses": len(matches) - wins,
            "win_rate": win_rate,
        },
        "explanation": explanation,
    }
