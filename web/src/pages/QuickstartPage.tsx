import { useState } from 'react'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Copy, Check } from 'lucide-react'

function CodeBlock({ code, language }: { code: string; language: string }) {
  const [copied, setCopied] = useState(false)

  function handleCopy() {
    navigator.clipboard.writeText(code)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="relative rounded-md border bg-muted">
      <div className="flex items-center justify-between border-b px-3 py-1.5">
        <Badge variant="outline" className="text-[10px]">
          {language}
        </Badge>
        <Button variant="ghost" size="sm" className="h-6 px-2" onClick={handleCopy}>
          {copied ? <Check className="size-3" /> : <Copy className="size-3" />}
        </Button>
      </div>
      <pre className="overflow-x-auto p-3 text-xs leading-relaxed">
        <code>{code}</code>
      </pre>
    </div>
  )
}

import { getStoredApiKey } from '@/lib/api'

const API_KEY_PLACEHOLDER = 'YOUR_API_KEY'

export function QuickstartPage() {
  const apiKey = getStoredApiKey() || API_KEY_PLACEHOLDER

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Quickstart</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Get up and running in 5 minutes. Code snippets pre-filled with your API key.
        </p>
      </div>

      <Tabs defaultValue="python">
        <TabsList>
          <TabsTrigger value="python">Python SDK</TabsTrigger>
          <TabsTrigger value="curl">cURL</TabsTrigger>
          <TabsTrigger value="langchain">LangChain</TabsTrigger>
        </TabsList>

        <TabsContent value="python" className="flex flex-col gap-4 mt-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">1. Install</CardTitle>
            </CardHeader>
            <CardContent>
              <CodeBlock language="bash" code="pip install anytool" />
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">2. Connect a user's app</CardTitle>
              <CardDescription>
                Start OAuth so your end-user can connect their Gmail, Slack, etc.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <CodeBlock
                language="python"
                code={`import httpx

API_KEY = "${apiKey}"
BASE = "http://localhost:8100/v1"

# Start OAuth for a user
resp = httpx.post(f"{BASE}/connections", json={
    "provider": "gmail",
    "user_id": "customer-123",
}, headers={"Authorization": f"Bearer {API_KEY}"})

print(resp.json()["auth_url"])  # → redirect user here`}
              />
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">3. Execute an action</CardTitle>
              <CardDescription>
                Call any API on behalf of a connected user.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <CodeBlock
                language="python"
                code={`resp = httpx.post(f"{BASE}/execute", json={
    "action": "gmail_send_email",
    "user_id": "customer-123",
    "params": {
        "to": "vendor@example.com",
        "subject": "Invoice Follow-up",
        "body": "Hi, please send the updated invoice."
    }
}, headers={"Authorization": f"Bearer {API_KEY}"})

print(resp.json())
# → {"successful": true, "data": {...}, "extracted_ids": {"message_id": "..."}}`}
              />
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">4. Deploy a trigger</CardTitle>
              <CardDescription>
                Poll for events and POST to your webhook.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <CodeBlock
                language="python"
                code={`resp = httpx.post(f"{BASE}/triggers", json={
    "trigger_type": "gmail_new_message",
    "user_id": "customer-123",
    "webhook_url": "https://myapp.com/webhooks/inbox",
    "filters": {"from_contains": "vendor@example.com"},
    "poll_interval_seconds": 60,
}, headers={"Authorization": f"Bearer {API_KEY}"})

print(resp.json())
# → {"trigger_id": "...", "status": "active"}`}
              />
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="curl" className="flex flex-col gap-4 mt-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Connect a user</CardTitle>
            </CardHeader>
            <CardContent>
              <CodeBlock
                language="bash"
                code={`curl -X POST http://localhost:8100/v1/connections \\
  -H "Authorization: Bearer ${apiKey}" \\
  -H "Content-Type: application/json" \\
  -d '{"provider": "gmail", "user_id": "customer-123"}'`}
              />
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Execute an action</CardTitle>
            </CardHeader>
            <CardContent>
              <CodeBlock
                language="bash"
                code={`curl -X POST http://localhost:8100/v1/execute \\
  -H "Authorization: Bearer ${apiKey}" \\
  -H "Content-Type: application/json" \\
  -d '{
    "action": "gmail_send_email",
    "user_id": "customer-123",
    "params": {
      "to": "vendor@example.com",
      "subject": "Hello",
      "body": "Test email from anytool"
    }
  }'`}
              />
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">List available actions</CardTitle>
            </CardHeader>
            <CardContent>
              <CodeBlock
                language="bash"
                code={`curl http://localhost:8100/v1/actions?app=gmail \\
  -H "Authorization: Bearer ${apiKey}"`}
              />
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="langchain" className="flex flex-col gap-4 mt-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Use with LangChain</CardTitle>
              <CardDescription>
                The SDK generates LangChain StructuredTools directly.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <CodeBlock
                language="python"
                code={`from anytool import AnyTool
from langchain_openai import ChatOpenAI

# Initialize with your Nango key (SDK mode)
api = AnyTool(nango_secret_key="your-nango-key")

# Get tools for Gmail
tools = api.get_tools("google", connection_id="customer-123")
# → [gmail_send_email, gmail_search, gmail_get_message, ...]

# Or get ALL tools across all apps
all_tools = api.get_all_tools(connection_id="customer-123")
# → 98 tools ready for function calling

# Bind to LLM
llm = ChatOpenAI(model="gpt-4o")
llm_with_tools = llm.bind_tools(all_tools)

# The LLM can now call any API directly
response = await llm_with_tools.ainvoke(
    "Send an email to vendor@example.com about the invoice"
)`}
              />
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}
