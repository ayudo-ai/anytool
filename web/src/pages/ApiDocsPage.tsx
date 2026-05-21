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
import { ScrollArea } from '@/components/ui/scroll-area'
import { Copy, Check, ExternalLink } from 'lucide-react'
import { getStoredApiKey } from '@/lib/api'
import { cn } from '@/lib/utils'

function CodeBlock({ code, language }: { code: string; language: string }) {
  const [copied, setCopied] = useState(false)
  const handleCopy = () => {
    navigator.clipboard.writeText(code)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }
  return (
    <div className="relative rounded-md border bg-muted">
      <div className="flex items-center justify-between border-b px-3 py-1">
        <Badge variant="outline" className="text-[10px]">{language}</Badge>
        <Button variant="ghost" size="sm" className="h-6 px-2" onClick={handleCopy}>
          {copied ? <Check className="size-3" /> : <Copy className="size-3" />}
        </Button>
      </div>
      <pre className="overflow-x-auto p-3 text-xs leading-relaxed"><code>{code}</code></pre>
    </div>
  )
}

const METHOD_COLORS: Record<string, string> = {
  GET: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900 dark:text-emerald-200',
  POST: 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200',
  PUT: 'bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200',
  DELETE: 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200',
}

interface Endpoint {
  method: string
  path: string
  title: string
  description: string
  auth: 'api_key' | 'session' | 'none'
  request?: string
  response?: string
  category: string
}

const ENDPOINTS: Endpoint[] = [
  // Auth
  {
    method: 'POST',
    path: '/v1/auth/signup',
    title: 'Sign Up',
    description: 'Create a new account with email and password. Returns session token + API key.',
    auth: 'none',
    request: `{
  "name": "Acme Inc",
  "email": "dev@acme.com",
  "password": "securepass123"
}`,
    response: `{
  "session_token": "sess_xxx",
  "api_key": "at_xxx",
  "account_id": "uuid",
  "name": "Acme Inc",
  "email": "dev@acme.com"
}`,
    category: 'Authentication',
  },
  {
    method: 'POST',
    path: '/v1/auth/google',
    title: 'Google SSO Login',
    description: 'Sign in with a Google ID token from Google One Tap or OAuth.',
    auth: 'none',
    request: `{ "id_token": "eyJhbGciOi..." }`,
    response: `{
  "session_token": "sess_xxx",
  "api_key": "at_xxx",
  "account_id": "uuid",
  "name": "John Doe",
  "email": "john@gmail.com"
}`,
    category: 'Authentication',
  },

  // Connections
  {
    method: 'POST',
    path: '/v1/connections',
    title: 'Connect User',
    description: 'Start OAuth flow for an end-user. Returns an auth_url to redirect them to. After they authorize, tokens are stored automatically.',
    auth: 'api_key',
    request: `{
  "provider": "gmail",
  "user_id": "customer-123"
}`,
    response: `{
  "auth_url": "https://accounts.google.com/o/oauth2/...",
  "user_id": "customer-123",
  "provider": "gmail"
}`,
    category: 'Connections',
  },
  {
    method: 'GET',
    path: '/v1/connections',
    title: 'List Connections',
    description: 'List all OAuth connections. Optionally filter by user_id.',
    auth: 'api_key',
    response: `{
  "connections": [
    {
      "provider": "google",
      "user_id": "customer-123",
      "status": "active",
      "connected_at": "2024-01-15T10:30:00Z"
    }
  ],
  "total": 1
}`,
    category: 'Connections',
  },
  {
    method: 'GET',
    path: '/v1/connections/check?provider=gmail&user_id=customer-123',
    title: 'Check Connection',
    description: 'Check if a user has connected a specific provider.',
    auth: 'api_key',
    response: `{ "connected": true, "provider": "gmail", "user_id": "customer-123" }`,
    category: 'Connections',
  },
  {
    method: 'DELETE',
    path: '/v1/connections',
    title: 'Disconnect',
    description: 'Remove a user\'s connection to a provider. Revokes and deletes tokens.',
    auth: 'api_key',
    request: `{ "provider": "gmail", "user_id": "customer-123" }`,
    response: `{ "disconnected": true }`,
    category: 'Connections',
  },

  // Execute
  {
    method: 'POST',
    path: '/v1/execute',
    title: 'Execute Action',
    description: 'Call any API action using a connected user\'s credentials. This is the core endpoint — one call does auth, execution, and error handling.',
    auth: 'api_key',
    request: `{
  "action": "gmail_send_email",
  "user_id": "customer-123",
  "params": {
    "to": "vendor@example.com",
    "subject": "Invoice Follow-up",
    "body": "Hi, please send the updated invoice."
  }
}`,
    response: `{
  "successful": true,
  "data": { "id": "msg_abc123", "threadId": "thread_xyz" },
  "extracted_ids": { "message_id": "msg_abc123" },
  "status_code": 200,
  "error": null
}`,
    category: 'Execution',
  },
  {
    method: 'GET',
    path: '/v1/actions',
    title: 'List Actions',
    description: 'List all available actions. Filter by app with ?app=gmail. Returns parameter schemas.',
    auth: 'api_key',
    response: `{
  "actions": [
    {
      "name": "gmail_send_email",
      "app": "google",
      "method": "POST",
      "description": "Send an email",
      "params": [
        { "name": "to", "type": "string", "required": true, "description": "Recipient" },
        { "name": "subject", "type": "string", "required": true, "description": "Subject" },
        { "name": "body", "type": "string", "required": true, "description": "Email body" }
      ]
    }
  ],
  "total": 98
}`,
    category: 'Execution',
  },
  {
    method: 'GET',
    path: '/v1/tools?app=gmail',
    title: 'Get Tool Definitions',
    description: 'Get OpenAI-compatible function calling tool definitions for an app. Use directly with GPT-4, Claude, etc.',
    auth: 'api_key',
    response: `{
  "tools": [
    {
      "type": "function",
      "function": {
        "name": "gmail_send_email",
        "description": "Send an email",
        "parameters": {
          "type": "object",
          "required": ["to", "subject", "body"],
          "properties": { ... }
        }
      }
    }
  ],
  "total": 15,
  "app": "gmail"
}`,
    category: 'Execution',
  },

  // Triggers
  {
    method: 'POST',
    path: '/v1/triggers',
    title: 'Deploy Trigger',
    description: 'Start polling a user\'s connected app for new events. Events are POSTed to your webhook_url with HMAC signatures.',
    auth: 'api_key',
    request: `{
  "trigger_type": "gmail_new_message",
  "user_id": "customer-123",
  "webhook_url": "https://myapp.com/webhooks/inbox",
  "filters": { "from_contains": "vendor@example.com" },
  "poll_interval_seconds": 60
}`,
    response: `{
  "trigger_id": "uuid",
  "trigger_type": "gmail_new_message",
  "status": "active"
}`,
    category: 'Triggers',
  },
  {
    method: 'GET',
    path: '/v1/triggers',
    title: 'List Triggers',
    description: 'List all active triggers. Optionally filter by user_id.',
    auth: 'api_key',
    response: `{
  "triggers": [
    {
      "trigger_id": "uuid",
      "trigger_type": "gmail_new_message",
      "user_id": "customer-123",
      "webhook_url": "https://myapp.com/webhooks/inbox",
      "poll_interval_seconds": 60,
      "enabled": true,
      "last_poll_at": "2024-01-15T10:30:00Z"
    }
  ],
  "total": 1
}`,
    category: 'Triggers',
  },
  {
    method: 'DELETE',
    path: '/v1/triggers/{trigger_id}',
    title: 'Remove Trigger',
    description: 'Stop and delete a trigger. Immediately stops polling.',
    auth: 'api_key',
    response: `{ "removed": true, "trigger_id": "uuid" }`,
    category: 'Triggers',
  },
  {
    method: 'GET',
    path: '/v1/triggers/types',
    title: 'List Trigger Types',
    description: 'List all available trigger types (gmail_new_message, slack_new_message, etc).',
    auth: 'api_key',
    response: `{
  "trigger_types": [
    { "type": "gmail_new_message", "provider": "google", "description": "..." },
    { "type": "slack_new_message", "provider": "slack", "description": "..." }
  ]
}`,
    category: 'Triggers',
  },

  // MCP
  {
    method: 'POST',
    path: '/v1/mcp/tools/list',
    title: 'MCP List Tools',
    description: 'List all tools in MCP (Model Context Protocol) format. Compatible with Claude Desktop, Cursor, etc.',
    auth: 'api_key',
    request: `{}`,
    response: `{
  "tools": [
    {
      "name": "gmail_send_email",
      "description": "Send an email",
      "inputSchema": { "type": "object", ... }
    }
  ]
}`,
    category: 'MCP',
  },
  {
    method: 'POST',
    path: '/v1/mcp/tools/call',
    title: 'MCP Call Tool',
    description: 'Execute a tool via MCP protocol. Pass user_id to specify which connection to use.',
    auth: 'api_key',
    request: `{
  "name": "gmail_send_email",
  "arguments": { "to": "...", "subject": "...", "body": "..." },
  "user_id": "customer-123"
}`,
    response: `{
  "content": [{ "type": "text", "text": "{ ... result JSON ... }" }]
}`,
    category: 'MCP',
  },

  // Entities
  {
    method: 'GET',
    path: '/v1/entities',
    title: 'List Entities',
    description: 'List all unique end-users (entities) with their connection and trigger counts.',
    auth: 'api_key',
    response: `{
  "entities": [
    {
      "user_id": "customer-123",
      "providers": ["google", "slack"],
      "connection_count": 2,
      "trigger_count": 1
    }
  ],
  "total": 1
}`,
    category: 'Entities',
  },
  {
    method: 'GET',
    path: '/v1/entities/{user_id}',
    title: 'Get Entity Detail',
    description: 'Get full detail for a specific end-user: connections, triggers, recent activity.',
    auth: 'api_key',
    response: `{
  "user_id": "customer-123",
  "connections": [...],
  "triggers": [...],
  "recent_activity": [...],
  "connection_count": 2,
  "trigger_count": 1
}`,
    category: 'Entities',
  },
]

const CATEGORIES = ['Authentication', 'Connections', 'Execution', 'Triggers', 'MCP', 'Entities']

export function ApiDocsPage() {
  const [activeCategory, setActiveCategory] = useState('Connections')
  const apiKey = getStoredApiKey() || 'YOUR_API_KEY'

  const filteredEndpoints = ENDPOINTS.filter((e) => e.category === activeCategory)

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">API Reference</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Complete REST API documentation. All endpoints accept JSON and require{' '}
            <code className="text-xs bg-muted px-1 py-0.5 rounded">Authorization: Bearer {'<api_key>'}</code>
          </p>
        </div>
        <Button variant="outline" size="sm" asChild>
          <a href="/docs" target="_blank" rel="noopener noreferrer">
            <ExternalLink className="mr-2 size-3" />
            OpenAPI Docs
          </a>
        </Button>
      </div>

      {/* Base URL */}
      <Card>
        <CardContent className="py-3 px-4">
          <div className="flex items-center gap-3">
            <span className="text-xs text-muted-foreground">Base URL</span>
            <code className="text-sm font-mono bg-muted px-2 py-0.5 rounded">
              {window.location.origin}/v1
            </code>
            <span className="text-xs text-muted-foreground ml-4">Authentication</span>
            <code className="text-xs font-mono bg-muted px-2 py-0.5 rounded">
              Authorization: Bearer {apiKey.slice(0, 10)}...
            </code>
          </div>
        </CardContent>
      </Card>

      <div className="flex gap-6">
        {/* Category sidebar */}
        <div className="w-48 shrink-0">
          <nav className="flex flex-col gap-0.5 sticky top-6">
            {CATEGORIES.map((cat) => {
              const count = ENDPOINTS.filter((e) => e.category === cat).length
              return (
                <button
                  key={cat}
                  onClick={() => setActiveCategory(cat)}
                  className={cn(
                    'flex items-center justify-between rounded-md px-3 py-1.5 text-sm font-medium transition-colors text-left',
                    activeCategory === cat
                      ? 'bg-accent text-accent-foreground'
                      : 'text-muted-foreground hover:bg-accent/50 hover:text-accent-foreground',
                  )}
                >
                  {cat}
                  <Badge variant="secondary" className="text-[10px] ml-2">
                    {count}
                  </Badge>
                </button>
              )
            })}
          </nav>
        </div>

        {/* Endpoints */}
        <ScrollArea className="flex-1 h-[calc(100vh-280px)]">
          <div className="flex flex-col gap-4">
            {filteredEndpoints.map((ep, i) => (
              <Card key={i}>
                <CardHeader className="pb-2">
                  <div className="flex items-center gap-3">
                    <Badge className={cn('font-mono text-xs', METHOD_COLORS[ep.method])}>
                      {ep.method}
                    </Badge>
                    <code className="text-sm font-mono">{ep.path}</code>
                    {ep.auth === 'none' && (
                      <Badge variant="outline" className="text-[10px] ml-auto">
                        No Auth
                      </Badge>
                    )}
                  </div>
                  <CardTitle className="text-base mt-1">{ep.title}</CardTitle>
                  <CardDescription className="text-sm">
                    {ep.description}
                  </CardDescription>
                </CardHeader>
                <CardContent className="flex flex-col gap-3">
                  {ep.request && (
                    <div>
                      <p className="text-xs font-medium text-muted-foreground mb-1">Request Body</p>
                      <CodeBlock language="json" code={ep.request} />
                    </div>
                  )}
                  {ep.response && (
                    <div>
                      <p className="text-xs font-medium text-muted-foreground mb-1">Response</p>
                      <CodeBlock language="json" code={ep.response} />
                    </div>
                  )}

                  {/* cURL example */}
                  <div>
                    <p className="text-xs font-medium text-muted-foreground mb-1">cURL</p>
                    <CodeBlock
                      language="bash"
                      code={`curl -X ${ep.method} ${window.location.origin}${ep.path.split('?')[0]}${ep.auth !== 'none' ? ` \\\n  -H "Authorization: Bearer ${apiKey}"` : ''}${ep.request ? ` \\\n  -H "Content-Type: application/json" \\\n  -d '${ep.request.replace(/\n\s*/g, ' ').trim()}'` : ''}`}
                    />
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </ScrollArea>
      </div>
    </div>
  )
}
