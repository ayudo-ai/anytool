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
import { Separator } from '@/components/ui/separator'
import { Copy, Check, ArrowRight, Plug, Wrench, Zap } from 'lucide-react'

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
  const baseUrl = window.location.origin

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Quickstart</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Get up and running in 5 minutes. All code snippets are pre-filled with your API key.
        </p>
      </div>

      {/* How it works */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">How anytool works</CardTitle>
          <CardDescription>Three steps to integrate any app into your product.</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="flex flex-col items-center text-center gap-2 p-4 rounded-lg border">
              <div className="flex size-10 items-center justify-center rounded-full bg-blue-100 dark:bg-blue-900">
                <Plug className="size-5 text-blue-700 dark:text-blue-300" />
              </div>
              <h3 className="font-medium text-sm">1. Connect</h3>
              <p className="text-xs text-muted-foreground">
                Your user authorizes their Gmail, Slack, etc. via OAuth. One API call.
              </p>
            </div>
            <div className="flex flex-col items-center text-center gap-2 p-4 rounded-lg border">
              <div className="flex size-10 items-center justify-center rounded-full bg-emerald-100 dark:bg-emerald-900">
                <Wrench className="size-5 text-emerald-700 dark:text-emerald-300" />
              </div>
              <h3 className="font-medium text-sm">2. Execute</h3>
              <p className="text-xs text-muted-foreground">
                Call any action (send email, create ticket, etc.) with their credentials. One API call.
              </p>
            </div>
            <div className="flex flex-col items-center text-center gap-2 p-4 rounded-lg border">
              <div className="flex size-10 items-center justify-center rounded-full bg-amber-100 dark:bg-amber-900">
                <Zap className="size-5 text-amber-700 dark:text-amber-300" />
              </div>
              <h3 className="font-medium text-sm">3. Trigger</h3>
              <p className="text-xs text-muted-foreground">
                Deploy a trigger to watch for new events. Get webhooks automatically.
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      <Tabs defaultValue="python">
        <TabsList>
          <TabsTrigger value="python">Python</TabsTrigger>
          <TabsTrigger value="node">Node.js / TypeScript</TabsTrigger>
          <TabsTrigger value="curl">cURL</TabsTrigger>
          <TabsTrigger value="langchain">LangChain</TabsTrigger>
          <TabsTrigger value="openai">OpenAI Functions</TabsTrigger>
        </TabsList>

        {/* ── Python ── */}
        <TabsContent value="python" className="flex flex-col gap-4 mt-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">1. Connect a user's app</CardTitle>
              <CardDescription>
                Start OAuth so your end-user can connect their Gmail, Slack, etc.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <CodeBlock
                language="python"
                code={`import httpx

API_KEY = "${apiKey}"
BASE = "${baseUrl}/v1"
headers = {"Authorization": f"Bearer {API_KEY}"}

# Start OAuth for an end-user
# user_id = your customer's unique ID in YOUR app
# For testing, use your own email. In production, use your customer's ID.
resp = httpx.post(f"{BASE}/connections", json={
    "provider": "gmail",
    "user_id": "customer-123",  # your customer's ID
}, headers=headers)

auth_url = resp.json()["auth_url"]
print(f"Redirect user to: {auth_url}")
# After they authorize, their connection is active automatically`}
              />
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">2. Execute an action</CardTitle>
              <CardDescription>
                Call any API on behalf of a connected user. One call handles auth, execution, and errors.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <CodeBlock
                language="python"
                code={`# Send email on behalf of the connected user
resp = httpx.post(f"{BASE}/execute", json={
    "action": "gmail_send_email",
    "user_id": "customer-123",
    "params": {
        "to": "vendor@example.com",
        "subject": "Invoice Follow-up",
        "body": "Hi, please send the updated invoice."
    }
}, headers=headers)

result = resp.json()
print(result["successful"])  # True
print(result["data"])        # {"id": "msg_xxx", "threadId": "..."}

# List all 98 available actions
actions = httpx.get(f"{BASE}/actions", headers=headers).json()
print(f"{actions['total']} actions available")

# Filter by app
gmail_actions = httpx.get(f"{BASE}/actions?app=gmail", headers=headers).json()`}
              />
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">3. Deploy a trigger</CardTitle>
              <CardDescription>
                Watch for new events and get webhooks. Handles deduplication + retries.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <CodeBlock
                language="python"
                code={`# Deploy a trigger — polls every 60s, POSTs to your webhook
resp = httpx.post(f"{BASE}/triggers", json={
    "trigger_type": "gmail_new_message",
    "user_id": "customer-123",
    "webhook_url": "https://myapp.com/webhooks/inbox",
    "filters": {"from_contains": "vendor@example.com"},
    "poll_interval_seconds": 60,
}, headers=headers)

print(resp.json())
# → {"trigger_id": "...", "status": "active"}

# Your webhook receives:
# POST https://myapp.com/webhooks/inbox
# Headers: X-Anytool-Signature: sha256=xxx
# Body: {
#   "trigger_id": "...",
#   "trigger_type": "gmail_new_message",
#   "data": {"from": "vendor@example.com", "subject": "..."}
# }`}
              />
            </CardContent>
          </Card>
        </TabsContent>

        {/* ── Node.js ── */}
        <TabsContent value="node" className="flex flex-col gap-4 mt-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">1. Connect a user</CardTitle>
            </CardHeader>
            <CardContent>
              <CodeBlock
                language="typescript"
                code={`const API_KEY = "${apiKey}";
const BASE = "${baseUrl}/v1";
const headers = {
  "Authorization": \`Bearer \${API_KEY}\`,
  "Content-Type": "application/json",
};

// Start OAuth for end-user
const res = await fetch(\`\${BASE}/connections\`, {
  method: "POST",
  headers,
  body: JSON.stringify({
    provider: "gmail",
    user_id: "customer-123",
  }),
});
const { auth_url } = await res.json();
// Redirect user to auth_url in a popup or new tab`}
              />
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">2. Execute an action</CardTitle>
            </CardHeader>
            <CardContent>
              <CodeBlock
                language="typescript"
                code={`const res = await fetch(\`\${BASE}/execute\`, {
  method: "POST",
  headers,
  body: JSON.stringify({
    action: "gmail_send_email",
    user_id: "customer-123",
    params: {
      to: "vendor@example.com",
      subject: "Invoice Follow-up",
      body: "Hi, please send the updated invoice.",
    },
  }),
});
const result = await res.json();
console.log(result.successful); // true
console.log(result.data);       // { id: "msg_xxx", ... }`}
              />
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">3. Deploy a trigger</CardTitle>
            </CardHeader>
            <CardContent>
              <CodeBlock
                language="typescript"
                code={`const res = await fetch(\`\${BASE}/triggers\`, {
  method: "POST",
  headers,
  body: JSON.stringify({
    trigger_type: "gmail_new_message",
    user_id: "customer-123",
    webhook_url: "https://myapp.com/webhooks/inbox",
    poll_interval_seconds: 60,
  }),
});
const trigger = await res.json();
console.log(trigger.trigger_id, trigger.status); // "uuid" "active"`}
              />
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Webhook handler (Express)</CardTitle>
              <CardDescription>Handle incoming trigger events on your server.</CardDescription>
            </CardHeader>
            <CardContent>
              <CodeBlock
                language="typescript"
                code={`import express from "express";
import crypto from "crypto";

const app = express();
app.use(express.json());

const WEBHOOK_SECRET = "whsec_xxx"; // from your .env

app.post("/webhooks/inbox", (req, res) => {
  // Verify HMAC signature
  const signature = req.headers["x-anytool-signature"];
  const expected = "sha256=" + crypto
    .createHmac("sha256", WEBHOOK_SECRET)
    .update(JSON.stringify(req.body))
    .digest("hex");

  if (signature !== expected) {
    return res.status(401).send("Invalid signature");
  }

  // Process the event
  const { trigger_type, data } = req.body;
  console.log(\`New \${trigger_type}:\`, data);

  res.sendStatus(200);
});

app.listen(3000);`}
              />
            </CardContent>
          </Card>
        </TabsContent>

        {/* ── cURL ── */}
        <TabsContent value="curl" className="flex flex-col gap-4 mt-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Connect a user</CardTitle>
            </CardHeader>
            <CardContent>
              <CodeBlock
                language="bash"
                code={`curl -X POST ${baseUrl}/v1/connections \\
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
                code={`curl -X POST ${baseUrl}/v1/execute \\
  -H "Authorization: Bearer ${apiKey}" \\
  -H "Content-Type: application/json" \\
  -d '{
    "action": "gmail_send_email",
    "user_id": "customer-123",
    "params": {
      "to": "vendor@example.com",
      "subject": "Hello from anytool",
      "body": "This email was sent via the anytool API!"
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
                code={`# All actions
curl ${baseUrl}/v1/actions \\
  -H "Authorization: Bearer ${apiKey}"

# Filter by app
curl "${baseUrl}/v1/actions?app=gmail" \\
  -H "Authorization: Bearer ${apiKey}"

# Get OpenAI-compatible tool definitions
curl "${baseUrl}/v1/tools?app=gmail" \\
  -H "Authorization: Bearer ${apiKey}"`}
              />
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Deploy a trigger</CardTitle>
            </CardHeader>
            <CardContent>
              <CodeBlock
                language="bash"
                code={`curl -X POST ${baseUrl}/v1/triggers \\
  -H "Authorization: Bearer ${apiKey}" \\
  -H "Content-Type: application/json" \\
  -d '{
    "trigger_type": "gmail_new_message",
    "user_id": "customer-123",
    "webhook_url": "https://myapp.com/webhooks/inbox",
    "poll_interval_seconds": 60
  }'`}
              />
            </CardContent>
          </Card>
        </TabsContent>

        {/* ── LangChain ── */}
        <TabsContent value="langchain" className="flex flex-col gap-4 mt-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Use with LangChain</CardTitle>
              <CardDescription>
                Fetch OpenAI tool definitions from the API and use them with LangChain's function calling.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <CodeBlock
                language="python"
                code={`import httpx
from langchain_openai import ChatOpenAI
from langchain_core.tools import StructuredTool

API_KEY = "${apiKey}"
BASE = "${baseUrl}/v1"
headers = {"Authorization": f"Bearer {API_KEY}"}

# Fetch tool definitions for Gmail
tools_resp = httpx.get(f"{BASE}/tools?app=gmail", headers=headers).json()

# Convert to LangChain tools
def make_tool(tool_def):
    """Convert anytool definition to a LangChain StructuredTool."""
    func_def = tool_def["function"]

    async def execute(**kwargs):
        resp = httpx.post(f"{BASE}/execute", json={
            "action": func_def["name"],
            "user_id": "customer-123",
            "params": kwargs,
        }, headers=headers)
        return resp.json()

    return StructuredTool.from_function(
        coroutine=execute,
        name=func_def["name"],
        description=func_def["description"],
    )

tools = [make_tool(t) for t in tools_resp["tools"]]
print(f"Loaded {len(tools)} tools")

# Bind to LLM
llm = ChatOpenAI(model="gpt-4o")
llm_with_tools = llm.bind_tools(tools)

response = await llm_with_tools.ainvoke(
    "Send an email to vendor@example.com about the invoice"
)`}
              />
            </CardContent>
          </Card>
        </TabsContent>

        {/* ── OpenAI ── */}
        <TabsContent value="openai" className="flex flex-col gap-4 mt-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Use with OpenAI Function Calling</CardTitle>
              <CardDescription>
                Plug anytool directly into the OpenAI API's function calling feature.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <CodeBlock
                language="python"
                code={`import httpx
from openai import OpenAI

API_KEY = "${apiKey}"
BASE = "${baseUrl}/v1"
at_headers = {"Authorization": f"Bearer {API_KEY}"}

# Get tool definitions (already in OpenAI format!)
tools = httpx.get(f"{BASE}/tools?app=gmail", headers=at_headers).json()["tools"]

# Call OpenAI with tools
client = OpenAI()
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[
        {"role": "user", "content": "Send an email to vendor@example.com about the invoice"}
    ],
    tools=tools,
)

# Execute the tool call
tool_call = response.choices[0].message.tool_calls[0]
result = httpx.post(f"{BASE}/execute", json={
    "action": tool_call.function.name,
    "user_id": "customer-123",
    "params": json.loads(tool_call.function.arguments),
}, headers=at_headers).json()

print(result["successful"])  # True`}
              />
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">MCP (Claude Desktop / Cursor)</CardTitle>
              <CardDescription>
                Use anytool as an MCP server for Claude Desktop or Cursor.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <CodeBlock
                language="json"
                code={`// Add to Claude Desktop config (~/.config/claude/config.json)
{
  "mcpServers": {
    "anytool": {
      "url": "${baseUrl}/v1/mcp",
      "headers": {
        "Authorization": "Bearer ${apiKey}"
      }
    }
  }
}`}
              />
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Supported Apps */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Supported Apps</CardTitle>
          <CardDescription>
            8 apps, 98 actions, built-in OAuth. More coming soon.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {[
              { name: 'Gmail / Google', actions: 15, color: 'text-red-600' },
              { name: 'Slack', actions: 12, color: 'text-purple-600' },
              { name: 'HubSpot', actions: 15, color: 'text-orange-600' },
              { name: 'GitHub', actions: 12, color: 'text-neutral-600' },
              { name: 'DocuSign', actions: 8, color: 'text-blue-600' },
              { name: 'Freshdesk', actions: 12, color: 'text-green-600' },
              { name: 'Zendesk', actions: 12, color: 'text-emerald-600' },
              { name: 'WhatsApp', actions: 8, color: 'text-green-700' },
            ].map((app) => (
              <div key={app.name} className="flex items-center gap-2 rounded-md border px-3 py-2">
                <span className={`text-sm font-medium ${app.color}`}>{app.name}</span>
                <Badge variant="secondary" className="ml-auto text-[10px]">
                  {app.actions} actions
                </Badge>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* What's Next */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">What's Next?</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col gap-2">
            {[
              { label: 'Browse & test actions', href: '/dashboard/actions', desc: 'Try any action from the UI' },
              { label: 'Connect a User', href: '/dashboard/connections', desc: 'Connect your first end-user\'s app' },
              { label: 'Read the API Reference', href: '/dashboard/api-docs', desc: 'Full endpoint documentation' },
              { label: 'Monitor Logs', href: '/dashboard/logs', desc: 'Watch every API call' },
            ].map((item) => (
              <a
                key={item.href}
                href={item.href}
                className="flex items-center justify-between rounded-md border px-4 py-3 transition-colors hover:bg-muted/50"
              >
                <div>
                  <p className="text-sm font-medium">{item.label}</p>
                  <p className="text-xs text-muted-foreground">{item.desc}</p>
                </div>
                <ArrowRight className="size-4 text-muted-foreground" />
              </a>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
