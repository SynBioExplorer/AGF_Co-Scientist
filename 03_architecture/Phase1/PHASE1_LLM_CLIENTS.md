# Phase 1: LLM Client Infrastructure

## Overview

Provider-agnostic LLM client abstraction supporting Google Gemini and OpenAI GPT models with cost tracking integration and structured response handling.

**Location:** `src/llm/`
**Status:** ✅ Complete

## Architecture

```
src/llm/
├── __init__.py           # Package exports
├── base.py               # Abstract base client
├── google.py             # Google Gemini client
└── openai.py             # OpenAI GPT client
```

## Abstract Base Client (`src/llm/base.py`)

```python
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any

class BaseLLMClient(ABC):
    """Abstract base class for LLM clients"""

    def __init__(self, model: str, agent_name: str = "unknown"):
        self.model = model
        self.agent_name = agent_name

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096
    ) -> str:
        """Generate text completion"""
        pass

    @abstractmethod
    async def generate_structured(
        self,
        prompt: str,
        response_schema: Dict[str, Any],
        system_prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate structured JSON response"""
        pass

    @abstractmethod
    def estimate_tokens(self, text: str) -> int:
        """Estimate token count for text"""
        pass
```

## Google Gemini Client (`src/llm/google.py`)

```python
from langchain_google_genai import ChatGoogleGenerativeAI
from src.utils.logging_config import get_logger
import sys
sys.path.append("04_Scripts")
from cost_tracker import get_tracker

logger = get_logger("google_llm")

class GoogleLLMClient(BaseLLMClient):
    """Google Gemini client with cost tracking"""

    def __init__(self, model: str, agent_name: str, api_key: str):
        super().__init__(model, agent_name)
        self.client = ChatGoogleGenerativeAI(
            model=model,
            google_api_key=api_key,
            temperature=0.7
        )
        self.tracker = get_tracker()

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096
    ) -> str:
        """Generate text completion"""
        # Estimate input tokens
        input_tokens = self.estimate_tokens(prompt)
        if system_prompt:
            input_tokens += self.estimate_tokens(system_prompt)

        # Build messages
        messages = []
        if system_prompt:
            messages.append(("system", system_prompt))
        messages.append(("human", prompt))

        # Invoke model
        response = await self.client.ainvoke(messages)

        # Extract text from response
        content = response.content
        if isinstance(content, list):
            # Handle content blocks
            text = "".join(
                block.get("text", "") if isinstance(block, dict) else str(block)
                for block in content
            )
        else:
            text = str(content)

        # Track usage
        output_tokens = self.estimate_tokens(text)
        self.tracker.add_usage(
            agent_name=self.agent_name,
            model=self.model,
            input_tokens=input_tokens,
            output_tokens=output_tokens
        )

        logger.info(
            "LLM generation complete",
            model=self.model,
            input_tokens=input_tokens,
            output_tokens=output_tokens
        )

        return text

    def estimate_tokens(self, text: str) -> int:
        """Rough token estimation (4 chars per token)"""
        return len(text) // 4
```

## OpenAI Client (`src/llm/openai.py`)

```python
from langchain_openai import ChatOpenAI
import tiktoken

class OpenAILLMClient(BaseLLMClient):
    """OpenAI GPT client with cost tracking"""

    def __init__(self, model: str, agent_name: str, api_key: str):
        super().__init__(model, agent_name)
        self.client = ChatOpenAI(
            model=model,
            openai_api_key=api_key,
            temperature=0.7
        )
        self.tracker = get_tracker()
        self.encoding = tiktoken.encoding_for_model(model)

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096
    ) -> str:
        """Generate text completion"""
        messages = []
        if system_prompt:
            messages.append(("system", system_prompt))
        messages.append(("human", prompt))

        response = await self.client.ainvoke(messages)
        text = response.content

        # Track with accurate token count
        input_tokens = self.estimate_tokens(prompt)
        output_tokens = self.estimate_tokens(text)
        self.tracker.add_usage(
            agent_name=self.agent_name,
            model=self.model,
            input_tokens=input_tokens,
            output_tokens=output_tokens
        )

        return text

    def estimate_tokens(self, text: str) -> int:
        """Accurate token count via tiktoken"""
        return len(self.encoding.encode(text))
```

## Key Features

### Cost Tracking Integration
Every API call automatically records:
- Input/output token counts
- Model used
- Agent making the call

### Content Block Handling
Gemini responses may contain multiple content blocks:
```python
# Response structure: [{"text": "..."}, {"text": "..."}]
if isinstance(content, list):
    text = "".join(block.get("text", "") for block in content)
```

### Structured Response Parsing
For JSON outputs:
```python
async def generate_structured(self, prompt, schema):
    response = await self.generate(prompt)
    return json.loads(response)
```

## Usage

```python
from src.llm.google import GoogleLLMClient
from src.config import settings

client = GoogleLLMClient(
    model=settings.generation_model,
    agent_name="generation",
    api_key=settings.google_api_key
)

response = await client.generate(
    prompt="Generate a hypothesis about AML treatment",
    system_prompt="You are a scientific researcher"
)
```

## Dependencies

- `langchain-google-genai>=1.0.0` - Google Gemini
- `langchain-openai>=0.1.0` - OpenAI GPT
- `tiktoken>=0.5.0` - Token counting

## Testing

```python
@pytest.mark.asyncio
async def test_google_client():
    """Test Google client generation"""
    client = GoogleLLMClient(
        model="gemini-2.0-flash-exp",
        agent_name="test",
        api_key=os.environ["GOOGLE_API_KEY"]
    )

    response = await client.generate("Say hello")
    assert len(response) > 0
    assert isinstance(response, str)
```
