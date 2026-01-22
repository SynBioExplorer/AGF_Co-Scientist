"""Google Gemini LLM client with cost tracking"""

from langchain_google_genai import ChatGoogleGenerativeAI
from src.llm.base import BaseLLMClient
from src.config import settings
from src.utils.errors import LLMClientError
import sys
sys.path.append(str(settings.project_root / "04_Scripts"))
from cost_tracker import get_tracker


class GoogleGeminiClient(BaseLLMClient):
    """Google Gemini LLM client with cost tracking"""

    def __init__(self, model: str, agent_name: str):
        cost_tracker = get_tracker(budget_aud=settings.budget_aud)
        super().__init__(model, cost_tracker)

        self.agent_name = agent_name
        self.llm = ChatGoogleGenerativeAI(
            model=model,
            google_api_key=settings.google_api_key,
            temperature=0.7,
            max_output_tokens=8192
        )

    def invoke(self, prompt: str) -> str:
        """Invoke Gemini and track costs"""
        try:
            # Check budget before calling
            self.cost_tracker.check_budget()

            response = self.llm.invoke(prompt)

            # Extract content (handle both string and list responses)
            if isinstance(response.content, list):
                # Handle list of content blocks
                content_parts = []
                for item in response.content:
                    if isinstance(item, dict) and 'text' in item:
                        content_parts.append(item['text'])
                    else:
                        content_parts.append(str(item))
                content = " ".join(content_parts)
            else:
                content = str(response.content)

            # Track usage (estimate tokens - rough heuristic)
            input_tokens = len(prompt.split()) * 1.3  # Rough estimate
            output_tokens = len(content.split()) * 1.3

            self.cost_tracker.add_usage(
                agent=self.agent_name,
                model=self.model,
                input_tokens=int(input_tokens),
                output_tokens=int(output_tokens)
            )

            return content

        except Exception as e:
            raise LLMClientError(f"Gemini invocation failed: {e}")

    async def ainvoke(self, prompt: str) -> str:
        """Async invoke for parallel execution"""
        try:
            self.cost_tracker.check_budget()

            response = await self.llm.ainvoke(prompt)

            # Extract content (handle both string and list responses)
            if isinstance(response.content, list):
                # Handle list of content blocks
                content_parts = []
                for item in response.content:
                    if isinstance(item, dict) and 'text' in item:
                        content_parts.append(item['text'])
                    else:
                        content_parts.append(str(item))
                content = " ".join(content_parts)
            else:
                content = str(response.content)

            # Track usage
            input_tokens = len(prompt.split()) * 1.3
            output_tokens = len(content.split()) * 1.3

            self.cost_tracker.add_usage(
                agent=self.agent_name,
                model=self.model,
                input_tokens=int(input_tokens),
                output_tokens=int(output_tokens)
            )

            return content

        except Exception as e:
            raise LLMClientError(f"Gemini async invocation failed: {e}")
