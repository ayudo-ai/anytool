"""
anytool — Connect your users' apps. Execute actions. Deploy triggers.

Quickstart:
    from anytool import AnyTool

    anytool = AnyTool(api_key="at_xxxx")

    # Execute an action
    result = await anytool.call("gmail_send_email", "user-123",
        to="vendor@example.com", subject="Hello", body="Hi there")

    # Use with OpenAI
    from anytool.tools.openai import OpenAIToolSet
    toolset = OpenAIToolSet(anytool)
    tools = await toolset.get_tools("user-123", apps=["google", "github"])

    # Use with LangChain
    tools = anytool.get_tools("google", "user-123")
"""

from anytool.client import AnyTool
from anytool.auth.token_store import TokenStore, MemoryTokenStore
from anytool.auth.models import AppCredentials, UserTokens
from anytool.auth.nango import NangoClient
from anytool.triggers.base import TriggerConfig, TriggerEvent
from anytool.triggers.store import TriggerStore, MemoryTriggerStore
from anytool.triggers.engine import TriggerEngine
from anytool.webhook import verify_webhook, sign_webhook

__version__ = "0.2.0"

__all__ = [
    "AnyTool",
    "NangoClient",
    "TokenStore",
    "MemoryTokenStore",
    "AppCredentials",
    "UserTokens",
    "TriggerConfig",
    "TriggerEvent",
    "TriggerStore",
    "MemoryTriggerStore",
    "TriggerEngine",
    "verify_webhook",
    "sign_webhook",
]
