"""
LangChain tool wrappers — converts ActionSpecs into LangChain StructuredTools.

Usage:
    from anyapi.tools.langchain import build_tools

    tools = build_tools(
        executor=executor,
        specs=GOOGLE_SPECS,
        credentials=google_creds,
        user_id="workspace-123",
    )
    # Returns list of LangChain StructuredTools ready for bind_tools()
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, create_model

from anyapi.auth.models import AppCredentials
from anyapi.executor import APIExecutor
from anyapi.specs.base import ActionSpec, ParamSpec


# Map spec types to Python types for Pydantic model generation
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
    credentials: AppCredentials,
    user_id: str,
) -> list:
    """Convert ActionSpecs into LangChain StructuredTools.

    Returns a list of tools ready to be used with `llm.bind_tools(tools)`.
    """
    try:
        from langchain_core.tools import StructuredTool
    except ImportError:
        raise ImportError(
            "langchain-core is required for LangChain tools. "
            "Install it with: pip install anyapi[langchain]"
        )

    tools = []
    for spec in specs:
        # Build the Pydantic input model
        input_model = _build_pydantic_model(spec)

        # Create the async execution function
        async def _execute(
            _spec=spec,
            _creds=credentials,
            _uid=user_id,
            **kwargs,
        ) -> str:
            result = await executor.execute(
                spec=_spec,
                params=kwargs,
                credentials=_creds,
                user_id=_uid,
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
