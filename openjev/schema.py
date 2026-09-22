"""Public request contract and resource limits for the local service."""

import json
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator, model_validator

Description = str | dict[str, JsonValue] | list[JsonValue]


def nonempty_description(value):
    if not value or isinstance(value, str) and not value.strip():
        raise ValueError("must not be empty")
    if len(json.dumps(value, ensure_ascii=False, allow_nan=False)) > 8000:
        raise ValueError("must not exceed 8,000 characters")
    return value


class Question(BaseModel):
    model_config = ConfigDict(extra="forbid")
    instructions: Description

    @field_validator("instructions")
    @classmethod
    def validate_instructions(cls, value):
        return nonempty_description(value)


class Choice(Question):
    type: Literal["choice"] = "choice"
    criteria: dict[str, Description | None] = Field(min_length=2, max_length=255)

    @field_validator("criteria")
    @classmethod
    def validate_options(cls, value):
        for key, description in value.items():
            if not key.strip() or len(key) > 200:
                raise ValueError("option names must contain 1–200 characters")
            if description is not None:
                nonempty_description(description)
        return value


class Score(Question):
    type: Literal["score"] = "score"
    criteria: list[Description] = Field(min_length=2, max_length=10)

    @field_validator("criteria")
    @classmethod
    def validate_levels(cls, value):
        for description in value:
            nonempty_description(description)
        return value


class Noul(Question):
    type: Literal["noul"] = "noul"
    criteria: dict[Literal["true", "false"], Description] | None = None

    @field_validator("criteria")
    @classmethod
    def validate_criteria(cls, value):
        if value is not None:
            if set(value) != {"true", "false"}:
                raise ValueError("Noul criteria must include both 'true' and 'false'")
            for description in value.values():
                nonempty_description(description)
        return value


TypedQuestion = Annotated[Choice | Score | Noul, Field(discriminator="type")]


class SystemOneRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    state: Description
    model: Literal["openjev-local", "openjev-latest", "jev-latest"] = "openjev-local"
    questions: dict[str, TypedQuestion] = Field(min_length=1, max_length=32)

    @field_validator("state")
    @classmethod
    def validate_state(cls, value):
        if not value or isinstance(value, str) and not value.strip():
            raise ValueError("state must not be empty")
        if len(json.dumps(value, ensure_ascii=False, allow_nan=False)) > 60000:
            raise ValueError("state must not exceed 60,000 characters")
        return value

    @field_validator("questions")
    @classmethod
    def validate_ids(cls, value):
        if any(not key.strip() or len(key) > 100 for key in value):
            raise ValueError("question IDs must contain 1–100 characters")
        return value

    @model_validator(mode="after")
    def limit_pairs(self):
        count = sum(len(q.criteria) if q.criteria else 1 for q in self.questions.values())
        if count > 256:
            raise ValueError("at most 256 candidate evaluations per request")
        return self


# A deliberately small, checked subset of the chat-completions contract.
CHAT_MODEL = "diffusiongemma-26b"
CHAT_MAX_MESSAGES = 32
CHAT_MAX_MESSAGE_CHARS = 16000
CHAT_MAX_INPUT_CHARS = 32000
CHAT_MAX_OUTPUT_TOKENS = 512
CHAT_DEFAULT_OUTPUT_TOKENS = 128


class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: Literal["system", "user", "assistant"]
    content: str = Field(min_length=1, max_length=CHAT_MAX_MESSAGE_CHARS, strict=True)

    @field_validator("content")
    @classmethod
    def nonempty_text(cls, value):
        if not value.strip():
            raise ValueError("message content must not be blank")
        return value


class ChatCompletionRequest(BaseModel):
    """Text only: unsupported OpenAI fields are rejected instead of discarded."""

    model_config = ConfigDict(extra="forbid")
    model: Literal["diffusiongemma-26b"] = CHAT_MODEL
    messages: list[ChatMessage] = Field(min_length=1, max_length=CHAT_MAX_MESSAGES)
    max_tokens: int = Field(default=CHAT_DEFAULT_OUTPUT_TOKENS, strict=True,
                            ge=1, le=CHAT_MAX_OUTPUT_TOKENS)
    stream: Literal[False] = False

    @field_validator("stream", mode="before")
    @classmethod
    def no_streaming(cls, value):
        if value is not False:
            raise ValueError("only stream=false is supported; streaming is not implemented")
        return value

    @model_validator(mode="after")
    def validate_conversation(self):
        if sum(len(message.content) for message in self.messages) > CHAT_MAX_INPUT_CHARS:
            raise ValueError("message content must not exceed 32,000 characters in total")
        if any(message.role == "system" for message in self.messages[1:]):
            raise ValueError("a system message is allowed only at the start")
        if self.messages[-1].role != "user":
            raise ValueError("the last message must have role=user")
        return self
