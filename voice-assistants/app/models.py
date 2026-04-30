from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


# ── Shared ───────────────────────────────────────────────

class ProviderName(str, Enum):
    openai = "openai"
    claude = "claude"
    n8n = "n8n"


class ErrorDetail(BaseModel):
    reason: str


class ErrorResponse(BaseModel):
    error: ErrorDetail

    model_config = {"json_schema_extra": {"examples": [{"error": {"reason": "Session not found"}}]}}


class Message(BaseModel):
    role: str = Field(description="Message role: user, assistant, system")
    content: str = Field(description="Message content")


# ── Provider config ──────────────────────────────────────

class ProviderConfig(BaseModel):
    url: str | None = Field(None, description="Provider API URL (required for n8n)")
    api_key: str = Field(description="API key or auth token")
    model: str | None = Field(None, description="Model name (e.g. gpt-4o, claude-sonnet-4-20250514)")
    assistant_id: str | None = Field(None, description="OpenAI Assistant ID (enables Assistants API mode)")
    system_prompt: str | None = Field(None, description="System prompt for the assistant")
    temperature: float = Field(0.7, ge=0, le=2, description="Sampling temperature")
    max_tokens: int = Field(1000, gt=0, le=128000, description="Max tokens in response")


# ── CREATE ───────────────────────────────────────────────

class CreateRequest(BaseModel):
    session_id: str = Field(description="Call session ID from Oki-Toki")
    comp_id: int = Field(description="Company ID")
    contact_id: int = Field(description="Contact ID")
    provider: ProviderName = Field(description="AI provider to use")
    config: ProviderConfig
    parameters: dict = Field(default_factory=dict, description="Vendor-specific parameters")

    model_config = {"json_schema_extra": {"examples": [{
        "session_id": "call-123",
        "comp_id": 42,
        "contact_id": 7890,
        "provider": "openai",
        "config": {
            "api_key": "sk-...",
            "model": "gpt-4o",
            "system_prompt": "You are a call center operator for Oki-Toki.",
            "temperature": 0.7,
            "max_tokens": 1000,
        },
        "parameters": {},
    }]}}


class CreateResponse(BaseModel):
    assistant_session_id: str

    model_config = {"json_schema_extra": {"examples": [
        {"assistant_session_id": "550e8400-e29b-41d4-a716-446655440000"}
    ]}}


# ── RESUME ───────────────────────────────────────────────

class ResumeRequest(BaseModel):
    comp_id: int = Field(description="Company ID")
    assistant_session_id: str = Field(description="Session ID returned by /create")


class ResumeResponse(BaseModel):
    assistant_session_id: str


# ── MESSAGE ──────────────────────────────────────────────

class MessageRequest(BaseModel):
    comp_id: int = Field(description="Company ID")
    assistant_session_id: str = Field(description="Session ID")
    messages: list[Message] = Field(description="Messages to send")

    model_config = {"json_schema_extra": {"examples": [{
        "comp_id": 42,
        "assistant_session_id": "550e8400-e29b-41d4-a716-446655440000",
        "messages": [{"role": "user", "content": "Hello, I need help with my account."}],
    }]}}


class Completion(BaseModel):
    text: str = Field(description="Assistant response text")
    tokens_send: int = Field(description="Prompt tokens used")
    tokens_received: int = Field(description="Completion tokens used")


class MessageResponse(BaseModel):
    completion: Completion

    model_config = {"json_schema_extra": {"examples": [{
        "completion": {
            "text": "Hello! I'd be happy to help you with your account.",
            "tokens_send": 45,
            "tokens_received": 23,
        }
    }]}}


# ── CLOSE ────────────────────────────────────────────────

class CloseRequest(BaseModel):
    comp_id: int = Field(description="Company ID")
    assistant_session_id: str = Field(description="Session ID")


class CloseResponse(BaseModel):
    status: str = "closed"
