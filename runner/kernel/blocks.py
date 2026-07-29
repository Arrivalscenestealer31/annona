"""Translation between runner value types and datapizza blocks (layer L0).

The canonical transcript is a sequence of :class:`datapizza.type.Block` values.
This module is the only place that knows how our tool types map onto them, so
the mapping is testable in isolation and every adapter shares one dialect.

Why datapizza's blocks rather than our own message classes: they already carry
the distinctions a transcript needs — text, function call, function result,
structured output — and datapizza's provider clients already know how to
translate them. See ``docs/adr/0001-adopt-datapizza-ai.md``.

``FunctionCallBlock`` and ``FunctionCallResultBlock`` both require a
:class:`datapizza.tools.Tool`. We synthesise schema-only tools (no callable):
the block records *what was asked of which tool*, and execution is the runner's
job, not datapizza's.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from typing import Any

from datapizza.tools import Tool
from datapizza.type import (
    Block,
    FunctionCallBlock,
    FunctionCallResultBlock,
    TextBlock,
)

from runner.kernel.types import Role, ToolCall, ToolResult, ToolSpec, Turn

__all__ = [
    "ToolResultBlock",
    "as_datapizza_tool",
    "encode_result_content",
    "function_call_block",
    "function_result_block",
    "text_block",
    "tool_spec_from_schema",
    "turn",
]


class ToolResultBlock(FunctionCallResultBlock):
    """A tool result that remembers whether it failed.

    datapizza's ``FunctionCallResultBlock`` carries the payload but not an
    error flag, and the distinction matters twice over: providers accept an
    ``is_error`` marker that tells the model its call failed rather than
    returned odd data, and Phase 3's trace needs failures to be visible without
    parsing the payload.

    Subclassing rather than wrapping keeps the value usable anywhere a datapizza
    block is expected; adapters that do not care read it as a plain result
    block, and adapters that do read ``is_error``.
    """

    def __init__(self, id: str, tool: Tool, result: str, is_error: bool = False) -> None:  # noqa: A002
        super().__init__(id=id, tool=tool, result=result)
        self.is_error = is_error


def tool_spec_from_schema(schema: Mapping[str, Any]) -> ToolSpec:
    """Build a :class:`ToolSpec` from the runner's tool-registry schema shape.

    The registry emits ``{"name", "description", "parameters"}``, which is also
    what ``datapizza.tools.Tool.schema`` produces — the two vocabularies already
    agree, so this is a rename rather than a conversion.
    """
    return ToolSpec(
        name=str(schema.get("name", "")),
        description=str(schema.get("description", "")),
        schema=schema.get("parameters", {}) or {},
    )


def as_datapizza_tool(spec: ToolSpec) -> Tool:
    """Represent a :class:`ToolSpec` as a schema-only datapizza tool.

    No callable is attached: the runner executes tools itself, under policy, and
    a framework-held reference to a live function would be a way around that.
    """
    return Tool(
        name=spec.name,
        description=spec.description,
        properties=dict(spec.properties),
        required=list(spec.required),
    )


def text_block(content: str) -> TextBlock:
    """A plain text block."""
    return TextBlock(content=content)


def function_call_block(call: ToolCall, spec: ToolSpec | None = None) -> FunctionCallBlock:
    """A block recording that the model asked for ``call``.

    ``spec`` is optional so a transcript can still be built for a tool that is
    not registered — a hallucinated tool name is part of what happened and
    belongs in the record.
    """
    resolved = spec or ToolSpec(name=call.name, description="", schema={})
    return FunctionCallBlock(
        id=call.id,
        arguments=dict(call.arguments),
        name=call.name,
        tool=as_datapizza_tool(resolved),
    )


def function_result_block(result: ToolResult, spec: ToolSpec | None = None) -> ToolResultBlock:
    """A block recording the outcome of a tool call, error flag included."""
    resolved = spec or ToolSpec(name=result.name, description="", schema={})
    return ToolResultBlock(
        id=result.call_id,
        tool=as_datapizza_tool(resolved),
        result=encode_result_content(result.content),
        is_error=result.is_error,
    )


def encode_result_content(content: Any) -> str:
    """Serialise a tool result for transport back to the model.

    Tool results are arbitrary Python values. ``default=str`` keeps a Path or a
    datetime from turning a successful tool call into a failed run: a slightly
    lossy string beats an exception the model can neither see nor recover from.
    """
    if isinstance(content, str):
        return content
    try:
        return json.dumps(content, default=str)
    except (TypeError, ValueError):
        return str(content)


def turn(role: Role, blocks: Iterable[Block]) -> Turn:
    """Build a transcript turn from an iterable of blocks."""
    return Turn(role=role, blocks=tuple(blocks))
