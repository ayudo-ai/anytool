"""
OpenAI adapter — compile ActionSpecs into OpenAI function calling format.

Generates tool definitions for openai.chat.completions.create(tools=[...]).

Key design: The tool's parameters ARE the body_schema (or agent_params for Tier 3).
No flattening. No simplification. The LLM sees the exact structure the API expects.

    from anytool.core.adapters.openai import specs_to_openai_tools

    tools = specs_to_openai_tools(specs)
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[...],
        tools=tools,
    )
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

from anytool.core.models import ActionSpec


# JSON Schema type mapping
_TYPE_MAP = {
    "string": "string",
    "integer": "integer",
    "number": "number",
    "boolean": "boolean",
    "array": "array",
    "object": "object",
    "list": "array",  # our specs use "list" sometimes
}


def _clean_schema_for_openai(schema: Dict[str, Any]) -> Dict[str, Any]:
    """Clean a JSON Schema for OpenAI function calling.

    OpenAI's function calling has specific requirements:
    - No 'format' field (they don't support it)
    - No 'maxLength' (not supported)
    - Ensure 'type' values are valid JSON Schema types
    - Keep descriptions, enums, defaults
    """
    if not isinstance(schema, dict):
        return schema

    cleaned: Dict[str, Any] = {}

    for key, value in schema.items():
        # Skip fields OpenAI doesn't support
        if key in ("format", "maxLength", "minLength", "pattern", "note"):
            continue

        # Map our type names to JSON Schema types
        if key == "type" and isinstance(value, str):
            cleaned[key] = _TYPE_MAP.get(value, value)
            continue

        # Recursively clean nested schemas
        if key == "properties" and isinstance(value, dict):
            cleaned[key] = {
                k: _clean_schema_for_openai(v)
                for k, v in value.items()
            }
            continue

        if key == "items" and isinstance(value, dict):
            cleaned[key] = _clean_schema_for_openai(value)
            continue

        # additionalProperties can be a schema
        if key == "additionalProperties" and isinstance(value, dict):
            cleaned[key] = _clean_schema_for_openai(value)
            continue

        cleaned[key] = value

    return cleaned


def _build_description(spec: ActionSpec, include_examples: bool) -> str:
    """Build the tool description with optional examples.

    Examples are critical for LLM performance on complex APIs.
    A good example teaches more than paragraphs of parameter descriptions.
    """
    desc = spec.description.strip()

    if include_examples and spec.examples:
        # Include the first example
        ex = spec.examples[0]
        ex_input = ex.request or ex.agent_input
        if ex_input:
            desc += f"\n\nExample:\n```json\n{json.dumps(ex_input, indent=2)}\n```"

    return desc


def spec_to_openai_tool(spec: ActionSpec, include_examples: bool = True) -> Dict[str, Any]:
    """Convert a single ActionSpec into an OpenAI tool definition.

    The tool's parameters schema IS the spec's body_schema (for Tier 1/2)
    or agent_params (for Tier 3). No flattening. The LLM constructs
    the exact structure the API expects.
    """
    # Get the schema the LLM should use
    schema = spec.llm_schema
    cleaned = _clean_schema_for_openai(schema)

    # Ensure it's an object type with properties
    if cleaned.get("type") != "object":
        cleaned = {"type": "object", "properties": {}, "required": []}

    return {
        "type": "function",
        "function": {
            "name": spec.name,
            "description": _build_description(spec, include_examples),
            "parameters": cleaned,
        },
    }


def specs_to_openai_tools(
    specs: List[ActionSpec],
    include_examples: bool = True,
) -> List[Dict[str, Any]]:
    """Convert a list of ActionSpecs into OpenAI tool definitions."""
    return [spec_to_openai_tool(s, include_examples) for s in specs]
