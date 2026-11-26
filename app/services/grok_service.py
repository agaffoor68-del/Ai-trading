"""
Grok AI Central Intelligence Service

Secure xAI API client for the Grok AI Trading Brain.
All API keys remain server-side. Implements retry, timeout, error handling,
usage monitoring, and structured response validation.
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from zoneinfo import ZoneInfo

import httpx
from pydantic import BaseModel, Field, ValidationError

from app.core.config import settings

IST = ZoneInfo("Asia/Kolkata")
logger = logging.getLogger(__name__)


# ============================================================================
# Grok API Models
# ============================================================================

class GrokMessage(BaseModel):
    role: str  # "system", "user", "assistant", "tool"
    content: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tool_call_id: Optional[str] = None
    name: Optional[str] = None


class GrokTool(BaseModel):
    type: str = "function"
    function: Dict[str, Any]


class GrokRequest(BaseModel):
    model: str
    messages: List[GrokMessage]
    tools: Optional[List[GrokTool]] = None
    tool_choice: Optional[Union[str, Dict[str, str]]] = None
    temperature: float = 0.1
    max_tokens: int = 4096
    stream: bool = False


class GrokUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class GrokChoice(BaseModel):
    index: int
    message: GrokMessage
    finish_reason: Optional[str] = None


class GrokResponse(BaseModel):
    id: str
    object: str
    created: int
    model: str
    choices: List[GrokChoice]
    usage: Optional[GrokUsage] = None


# ============================================================================
# Internal Models
# ============================================================================

@dataclass
class GrokCallResult:
    success: bool
    response: Optional[GrokResponse] = None
    structured_data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    error_code: Optional[str] = None
    latency_ms: float = 0.0
    tokens_used: int = 0
    cost_usd: float = 0.0


@dataclass
class GrokServiceMetrics:
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    total_latency_ms: float = 0.0
    last_call_at: Optional[datetime] = None
    errors_by_code: Dict[str, int] = field(default_factory=dict)


# ============================================================================
# Grok Service
# ============================================================================

class GrokService:
    """
    Secure xAI Grok API client for the AI Trading Brain.
    
    Features:
    - Server-side API key only (never exposed to frontend)
    - Retry with exponential backoff
    - Timeout handling
    - Structured response validation
    - Usage monitoring & cost tracking
    - Rate limit handling
    - Comprehensive error handling
    """

    def __init__(self):
        self.api_key = settings.XAI_API_KEY
        self.model = settings.XAI_MODEL or "grok-2-latest"
        self.base_url = "https://api.x.ai/v1"
        
        if not self.api_key:
            logger.warning("XAI_API_KEY not configured - Grok service will not work")
        
        # Cost tracking (approximate, update based on actual pricing)
        self.cost_per_1k_prompt_tokens = 0.002  # $0.002 per 1K prompt tokens
        self.cost_per_1k_completion_tokens = 0.006  # $0.006 per 1K completion tokens
        
        self.metrics = GrokServiceMetrics()
        self._client: Optional[httpx.AsyncClient] = None
        self._lock = asyncio.Lock()

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client with connection pooling."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                timeout=httpx.Timeout(60.0, connect=10.0),
                limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
            )
        return self._client

    async def close(self):
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    def _calculate_cost(self, usage: Optional[GrokUsage]) -> float:
        """Calculate approximate cost in USD."""
        if not usage:
            return 0.0
        prompt_cost = (usage.prompt_tokens / 1000) * self.cost_per_1k_prompt_tokens
        completion_cost = (usage.completion_tokens / 1000) * self.cost_per_1k_completion_tokens
        return prompt_cost + completion_cost

    def _update_metrics(self, result: GrokCallResult):
        """Update service metrics."""
        self.metrics.total_calls += 1
        self.metrics.total_latency_ms += result.latency_ms
        self.metrics.last_call_at = datetime.now(IST)
        
        if result.success:
            self.metrics.successful_calls += 1
            if result.response and result.response.usage:
                self.metrics.total_tokens += result.response.usage.total_tokens
                self.metrics.total_cost_usd += result.cost_usd
        else:
            self.metrics.failed_calls += 1
            if result.error_code:
                self.metrics.errors_by_code[result.error_code] = \
                    self.metrics.errors_by_code.get(result.error_code, 0) + 1

    async def chat_completion(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[Union[str, Dict[str, str]]] = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
        max_retries: int = 3,
        base_delay: float = 1.0,
    ) -> GrokCallResult:
        """
        Execute a chat completion with retry logic and error handling.
        
        Args:
            messages: List of message dicts with role and content
            tools: Optional list of function definitions for function calling
            tool_choice: "auto", "none", or specific function name
            temperature: Sampling temperature (0.0-2.0)
            max_tokens: Maximum tokens in response
            max_retries: Maximum retry attempts
            base_delay: Base delay for exponential backoff
            
        Returns:
            GrokCallResult with success status, response, or error
        """
        if not self.api_key:
            return GrokCallResult(
                success=False,
                error="XAI_API_KEY not configured",
                error_code="MISSING_API_KEY",
            )

        # Prepare request
        grok_messages = [GrokMessage(**msg) for msg in messages]
        grok_tools = [GrokTool(**t) for t in tools] if tools else None
        
        request = GrokRequest(
            model=self.model,
            messages=grok_messages,
            tools=grok_tools,
            tool_choice=tool_choice,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        client = await self._get_client()
        url = "/chat/completions"
        
        last_error = None
        
        for attempt in range(max_retries + 1):
            start_time = time.perf_counter()
            
            try:
                response = await client.post(
                    url,
                    json=request.model_dump(exclude_none=True, by_alias=True),
                )
                
                latency_ms = (time.perf_counter() - start_time) * 1000
                
                if response.status_code == 200:
                    data = response.json()
                    try:
                        grok_response = GrokResponse(**data)
                        result = GrokCallResult(
                            success=True,
                            response=grok_response,
                            latency_ms=latency_ms,
                            tokens_used=grok_response.usage.total_tokens if grok_response.usage else 0,
                            cost_usd=self._calculate_cost(grok_response.usage),
                        )
                        self._update_metrics(result)
                        return result
                    except ValidationError as e:
                        logger.error(f"Grok response validation failed: {e}")
                        return GrokCallResult(
                            success=False,
                            error=f"Response validation failed: {e}",
                            error_code="VALIDATION_ERROR",
                            latency_ms=latency_ms,
                        )
                
                elif response.status_code == 429:
                    # Rate limited - retry with backoff
                    retry_after = response.headers.get("Retry-After")
                    delay = float(retry_after) if retry_after else base_delay * (2 ** attempt)
                    logger.warning(f"Grok rate limited, retrying in {delay}s (attempt {attempt + 1})")
                    await asyncio.sleep(delay)
                    continue
                
                elif response.status_code == 401:
                    return GrokCallResult(
                        success=False,
                        error="Invalid or expired xAI API key",
                        error_code="UNAUTHORIZED",
                        latency_ms=latency_ms,
                    )
                
                elif response.status_code >= 500:
                    # Server error - retry
                    delay = base_delay * (2 ** attempt)
                    logger.warning(f"Grok server error {response.status_code}, retrying in {delay}s")
                    await asyncio.sleep(delay)
                    continue
                
                else:
                    # Other client errors - don't retry
                    error_text = response.text
                    return GrokCallResult(
                        success=False,
                        error=f"Grok API error {response.status_code}: {error_text}",
                        error_code=f"HTTP_{response.status_code}",
                        latency_ms=latency_ms,
                    )
            
            except httpx.TimeoutException:
                latency_ms = (time.perf_counter() - start_time) * 1000
                last_error = "Request timeout"
                logger.warning(f"Grok request timeout (attempt {attempt + 1})")
                if attempt < max_retries:
                    await asyncio.sleep(base_delay * (2 ** attempt))
                    continue
                return GrokCallResult(
                    success=False,
                    error="Request timeout after retries",
                    error_code="TIMEOUT",
                    latency_ms=latency_ms,
                )
            
            except httpx.NetworkError as e:
                latency_ms = (time.perf_counter() - start_time) * 1000
                last_error = str(e)
                logger.warning(f"Grok network error: {e} (attempt {attempt + 1})")
                if attempt < max_retries:
                    await asyncio.sleep(base_delay * (2 ** attempt))
                    continue
                return GrokCallResult(
                    success=False,
                    error=f"Network error: {e}",
                    error_code="NETWORK_ERROR",
                    latency_ms=latency_ms,
                )
            
            except Exception as e:
                latency_ms = (time.perf_counter() - start_time) * 1000
                logger.exception(f"Unexpected error calling Grok API: {e}")
                return GrokCallResult(
                    success=False,
                    error=f"Unexpected error: {e}",
                    error_code="UNEXPECTED_ERROR",
                    latency_ms=latency_ms,
                )
        
        # All retries exhausted
        return GrokCallResult(
            success=False,
            error=f"Max retries exceeded. Last error: {last_error}",
            error_code="MAX_RETRIES_EXCEEDED",
            latency_ms=0.0,
        )

    async def structured_completion(
        self,
        messages: List[Dict[str, Any]],
        response_schema: Dict[str, Any],
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ) -> GrokCallResult:
        """
        Get a structured JSON response validated against a schema.
        
        Uses function calling to enforce schema compliance.
        """
        schema_tool = {
            "type": "function",
            "function": {
                "name": "structured_response",
                "description": "Return a structured response matching the required schema",
                "parameters": response_schema,
            }
        }
        
        result = await self.chat_completion(
            messages=messages,
            tools=[schema_tool],
            tool_choice={"type": "function", "function": {"name": "structured_response"}},
            temperature=temperature,
            max_tokens=max_tokens,
        )
        
        if not result.success or not result.response:
            return result
        
        # Extract structured response from tool call
        try:
            message = result.response.choices[0].message
            if message.tool_calls:
                for tool_call in message.tool_calls:
                    if tool_call.get("function", {}).get("name") == "structured_response":
                        args = json.loads(tool_call["function"]["arguments"])
                        # Return the structured data as a special response
                        return GrokCallResult(
                            success=True,
                            response=result.response,
                            structured_data=args,
                            error=None,
                            latency_ms=result.latency_ms,
                            tokens_used=result.tokens_used,
                            cost_usd=result.cost_usd,
                        )
            return GrokCallResult(
                success=False,
                error="No structured response in tool call",
                error_code="NO_STRUCTURED_RESPONSE",
            )
        except Exception as e:
            return GrokCallResult(
                success=False,
                error=f"Failed to parse structured response: {e}",
                error_code="PARSE_ERROR",
            )

    def get_metrics(self) -> Dict[str, Any]:
        """Get service metrics for monitoring."""
        return {
            "total_calls": self.metrics.total_calls,
            "successful_calls": self.metrics.successful_calls,
            "failed_calls": self.metrics.failed_calls,
            "success_rate": (
                self.metrics.successful_calls / self.metrics.total_calls 
                if self.metrics.total_calls > 0 else 0
            ),
            "total_tokens": self.metrics.total_tokens,
            "total_cost_usd": round(self.metrics.total_cost_usd, 6),
            "avg_latency_ms": (
                self.metrics.total_latency_ms / self.metrics.total_calls 
                if self.metrics.total_calls > 0 else 0
            ),
            "last_call_at": self.metrics.last_call_at.isoformat() if self.metrics.last_call_at else None,
            "errors_by_code": self.metrics.errors_by_code,
        }

    async def health_check(self) -> Dict[str, Any]:
        """Check Grok API connectivity."""
        if not self.api_key:
            return {"healthy": False, "reason": "API key not configured"}
        
        result = await self.chat_completion(
            messages=[{"role": "user", "content": "Health check - respond with OK"}],
            max_tokens=10,
            temperature=0,
            max_retries=1,
        )
        
        return {
            "healthy": result.success,
            "latency_ms": result.latency_ms if result.success else None,
            "error": result.error if not result.success else None,
        }


# ============================================================================
# Singleton Instance
# ============================================================================

_grok_service: Optional[GrokService] = None


def get_grok_service() -> GrokService:
    """Get or create the singleton Grok service instance."""
    global _grok_service
    if _grok_service is None:
        _grok_service = GrokService()
    return _grok_service
