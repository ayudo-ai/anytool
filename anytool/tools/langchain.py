"""
LangChain tool wrappers — converts ActionSpecs into LangChain StructuredTools.

Supports two execution backends:
  1. Direct executor (standalone/nango mode)
  2. Platform client (platform mode — calls POST /v1/execute)
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, create_model

from anytool.specs.base import ActionSpec, ParamSpec

_TYPE_MAP = {
    "string": str,
    "integer": int,
    "number": float,
    "boolean": bool,
    "list": list,
    "object": dict,
}


def _build_pydantic_model(spec: ActionSpec) -> type[BaseModel]:
    """Build a Pydantic model from an ActionSpec's parameters."""
    fields: Dict[str, Any] = {}
    for param in spec.params:
        py_type = _TYPE_MAP.get(param.type, str)
        if param.required:
            fields[param.name] = (py_type, Field(description=param.description))
        else:
            default = param.default if param.default is not None else None
            fields[param.name] = (
                Optional[py_type],
                Field(default=default, description=param.description),
            )

    model_name = "".join(word.capitalize() for word in spec.name.split("_")) + "Input"
    return create_model(model_name, **fields)


def build_tools(
    executor,  # APIExecutor or None (platform mode)
    specs: List[ActionSpec],
    provider: str,
    connection_id: str,
    platform_client=None,  # _PlatformClient (platform mode)
) -> list:
    """Convert ActionSpecs into LangChain StructuredTools.

    If platform_client is provided, tool calls go through POST /v1/execute.
    Otherwise, they go through the executor directly.
    """
    try:
        from langchain_core.tools import StructuredTool
    except ImportError:
        raise ImportError(
            "langchain-core required. Install: pip install anytool[langchain]"
        )

    tools = []
    for spec in specs:
        input_model = _build_pydantic_model(spec)

        if platform_client:
            # Platform mode — call through API
            async def _execute_platform(
                _spec=spec,
                _cid=connection_id,
                _client=platform_client,
                **kwargs,
            ) -> str:
                result = await _client.post("/execute", json={
                    "action": _spec.name,
                    "user_id": _cid,
                    "params": kwargs,
                })
                return json.dumps(result, default=str)

            tool = StructuredTool.from_function(
                coroutine=_execute_platform,
                name=spec.name,
                description=spec.description,
                args_schema=input_model,
            )
        else:
            # Direct executor mode
            async def _execute_direct(
                _spec=spec,
                _provider=provider,
                _cid=connection_id,
                _exec=executor,
                **kwargs,
            ) -> str:
                result = await _exec.execute(
                    spec=_spec,
                    params=kwargs,
                    provider=_provider,
                    connection_id=_cid,
                )
                return json.dumps(result, default=str)

            tool = StructuredTool.from_function(
                coroutine=_execute_direct,
                name=spec.name,
                description=spec.description,
                args_schema=input_model,
            )

        tools.append(tool)

    return tools
