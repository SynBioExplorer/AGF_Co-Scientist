"""OpenAI GPT client with cost tracking"""

from langchain_openai import ChatOpenAI
from src.llm.base import BaseLLMClient
from src.config import settings
from src.utils.errors import LLMClientError
import sys
sys.path.append(str(settings.project_root / "04_Scripts"))
from cost_tracker import get_tracker


class OpenAIClient(BaseLLMClient):
    """OpenAI GPT client with cost tracking"""

    def __init__(self, model: str, agent_name: str):
        cost_tracker = get_tracker(budget_aud=settings.budget_aud)
        super().__init__(model, cost_tracker)

        self.agent_name = agent_name

        if not settings.openai_api_key:
            raise LLMClientError("OpenAI API key not configured in .env")

        self.llm = ChatOpenAI(
            model=model,
            api_key=settings.openai_api_key,
            temperature=0.7,
            max_tokens=8192
        )

    def invoke(self, prompt: str) -> str:
        """Invoke OpenAI and track costs"""
        try:
            # Check budget before calling
            self.cost_tracker.check_budget()

            response = self.llm.invoke(prompt)

            # Track usage (estimate tokens - rough heuristic)
            input_tokens = len(prompt.split()) * 1.3
            output_tokens = len(response.content.split()) * 1.3

            self.cost_tracker.add_usage(
                agent=self.agent_name,
                model=self.model,
                input_tokens=int(input_tokens),
                output_tokens=int(output_tokens)
            )

            return response.content

        except Exception as e:
            raise LLMClientError(f"OpenAI invocation failed: {e}")

    async def ainvoke(self, prompt: str) -> str:
        """Async invoke for parallel execution"""
        try:
            self.cost_tracker.check_budget()

            response = await self.llm.ainvoke(prompt)

            # Track usage
            input_tokens = len(prompt.split()) * 1.3
            output_tokens = len(response.content.split()) * 1.3

            self.cost_tracker.add_usage(
                agent=self.agent_name,
                model=self.model,
                input_tokens=int(input_tokens),
                output_tokens=int(output_tokens)
            )

            return response.content

        except Exception as e:
            raise LLMClientError(f"OpenAI async invocation failed: {e}")
