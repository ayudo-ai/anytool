"""
LangChain tool wrappers — converts ActionSpecs into LangChain StructuredTools.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, create_model

from anyapi.executor import APIExecutor
from anyapi.specs.base import ActionSpec, ParamSpec

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
    executor: APIExecutor,
    specs: List[ActionSpec],
    provider: str,
    connection_id: str,
) -> list:
    """Convert ActionSpecs into LangChain StructuredTools."""
    try:
        from langchain_core.tools import StructuredTool
    except ImportError:
        raise ImportError(
            "langchain-core required. Install: pip install anyapi[langchain]"
        )

    tools = []
    for spec in specs:
        input_model = _build_pydantic_model(spec)

        async def _execute(
            _spec=spec,
            _provider=provider,
            _cid=connection_id,
            **kwargs,
        ) -> str:
            result = await executor.execute(
                spec=_spec,
                params=kwargs,
                provider=_provider,
                connection_id=_cid,
            )
            return json.dumps(result, default=str)

        tool = StructuredTool.from_function(
            coroutine=_execute,
            name=spec.name,
            description=spec.description,
            args_schema=input_model,
        )
        tools.append(tool)

    return tools
