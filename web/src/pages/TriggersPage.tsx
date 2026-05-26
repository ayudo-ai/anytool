import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from '@/components/ui/tabs'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import { listTriggers, removeTrigger, getStoredApiKey } from '@/lib/api'
import {
  Plus, Zap, Clock, MoreHorizontal, Trash2,
  Copy, Check, Radio, RefreshCw,
} from 'lucide-react'

function timeAgo(dateStr: string | null): string {
  if (!dateStr) return 'Never'
  const date = new Date(dateStr)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffS = Math.floor(diffMs / 1000)
  if (diffS < 5) return 'Just now'
  if (diffS < 60) return `${diffS}s ago`
  const diffM = Math.floor(diffS / 60)
  if (diffM < 60) return `${diffM}m ago`
  const diffH = Math.floor(diffM / 60)
  if (diffH < 24) return `${diffH}h ago`
  return date.toLocaleDateString()
}

function CodeBlock({ code, language }: { code: string; language: string }) {
  const [copied, setCopied] = useState(false)
  const handleCopy = () => {
    navigator.clipboard.writeText(code)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }
  return (
    <div className="relative rounded-lg border bg-muted/50">
      <div className="flex items-center justify-between border-b px-3 py-1.5">
        <Badge variant="outline" className="text-[10px] font-mono">{language}</Badge>
        <Button variant="ghost" size="sm" className="h-6 px-2" onClick={handleCopy}>
          {copied ? <Check className="size-3" /> : <Copy className="size-3" />}
        </Button>
      </div>
      <pre className="overflow-x-auto p-4 text-xs leading-relaxed"><code>{code}</code></pre>
    </div>
  )
}

export function TriggersPage() {
  const queryClient = useQueryClient()
  const [open, setOpen] = useState(false)
  const apiKey = getStoredApiKey() || 'YOUR_API_KEY'
  const apiBase = import.meta.env.VITE_API_URL || 'http://localhost:8100/v1'

  const { data, isLoading } = useQuery({
    queryKey: ['triggers'],
    queryFn: () => listTriggers(),
    refetchInterval: 15000,
  })

  const removeMut = useMutation({
    mutationFn: removeTrigger,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['triggers'] }),
  })

  const pythonCode = `from anytool import AnyTool

at = AnyTool(api_key="${apiKey.slice(0, 12)}...")

# Deploy a trigger — polls Gmail for new emails every 60s
trigger = await at.deploy_trigger(
    trigger_type="gmail_new_message",
    user_id="customer-123",
    webhook_url="https://myapp.com/webhooks/inbox",
    poll_interval_seconds=60,
    filters={
        "from_contains": "vendor@example.com",
        "subject_contains": "invoice",
    },
)
print(f"Trigger deployed: {trigger['trigger_id']}")

# List active triggers
triggers = await at.list_triggers()
for t in triggers:
    print(f"  {t['trigger_type']} → {t['webhook_url']}")

# Remove a trigger
await at.remove_trigger(trigger_id="uuid-here")`

  const curlCode = `# Deploy a trigger
curl -X POST ${apiBase}/triggers \\
  -H "Authorization: Bearer ${apiKey.slice(0, 12)}..." \\
  -H "Content-Type: application/json" \\
  -d '{
    "trigger_type": "gmail_new_message",
    "user_id": "customer-123",
    "webhook_url": "https://myapp.com/webhooks/inbox",
    "poll_interval_seconds": 60,
    "filters": {
      "from_contains": "vendor@example.com"
    }
  }'

# List triggers
curl ${apiBase}/triggers \\
  -H "Authorization: Bearer ${apiKey.slice(0, 12)}..."

# Remove a trigger
curl -X DELETE ${apiBase}/triggers/TRIGGER_ID \\
  -H "Authorization: Bearer ${apiKey.slice(0, 12)}..."`

  const typescriptCode = `const response = await fetch("${apiBase}/triggers", {
  method: "POST",
  headers: {
    "Authorization": "Bearer ${apiKey.slice(0, 12)}...",
    "Content-Type": "application/json",
  },
  body: JSON.stringify({
    trigger_type: "gmail_new_message",
    user_id: "customer-123",
    webhook_url: "https://myapp.com/webhooks/inbox",
    poll_interval_seconds: 60,
    filters: {
      from_contains: "vendor@example.com",
    },
  }),
});

const { trigger_id } = await response.json();
console.log("Trigger deployed:", trigger_id);`

  return (
    <TooltipProvider>
      <div className="flex flex-col gap-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">Triggers</h1>
            <p className="text-sm text-muted-foreground mt-1">
              Poll connected apps for new events and POST them to your webhook.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => queryClient.invalidateQueries({ queryKey: ['triggers'] })}
            >
              <RefreshCw className="mr-1.5 size-3" /> Refresh
            </Button>
            <Dialog open={open} onOpenChange={setOpen}>
              <DialogTrigger asChild>
                <Button size="sm">
                  <Plus className="mr-1.5 size-4" /> Add Trigger
                </Button>
              </DialogTrigger>
              <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto">
                <DialogHeader>
                  <DialogTitle>Add Trigger</DialogTitle>
                  <p className="text-sm text-muted-foreground">
                    Use the API or SDK to create and manage triggers programmatically.
                  </p>
                </DialogHeader>
                <Tabs defaultValue="python" className="mt-2">
                  <TabsList>
                    <TabsTrigger value="python">Python</TabsTrigger>
                    <TabsTrigger value="typescript">TypeScript</TabsTrigger>
                    <TabsTrigger value="curl">cURL</TabsTrigger>
                  </TabsList>
                  <TabsContent value="python" className="mt-3">
                    <CodeBlock code={pythonCode} language="python" />
                  </TabsContent>
                  <TabsContent value="typescript" className="mt-3">
                    <CodeBlock code={typescriptCode} language="typescript" />
                  </TabsContent>
                  <TabsContent value="curl" className="mt-3">
                    <CodeBlock code={curlCode} language="bash" />
                  </TabsContent>
                </Tabs>

                {/* Available trigger types */}
                <div className="mt-4">
                  <p className="text-xs font-medium text-muted-foreground mb-2">Available Trigger Types</p>
                  <div className="flex flex-wrap gap-1.5">
                    {[
                      { name: 'gmail_new_message', type: 'polling' },
                      { name: 'slack_new_message', type: 'polling' },
                      { name: 'github_new_issue', type: 'webhook' },
                      { name: 'github_new_pr', type: 'webhook' },
                      { name: 'github_push', type: 'webhook' },
                      { name: 'github_star', type: 'webhook' },
                      { name: 'github_issue_comment', type: 'webhook' },
                      { name: 'hubspot_new_contact', type: 'polling' },
                      { name: 'hubspot_new_deal', type: 'polling' },
                      { name: 'freshdesk_new_ticket', type: 'polling' },
                      { name: 'zendesk_new_ticket', type: 'polling' },
                    ].map((t) => (
                      <Badge key={t.name} variant="outline" className="font-mono text-[10px] gap-1">
                        {t.type === 'webhook' ? <Zap className="size-2.5" /> : <RefreshCw className="size-2.5" />}
                        {t.name}
                      </Badge>
                    ))}
                  </div>
                </div>
              </DialogContent>
            </Dialog>
          </div>
        </div>

        {/* Triggers list */}
        {isLoading ? (
          <div className="flex flex-col gap-3">
            {[1, 2, 3].map((i) => <Skeleton key={i} className="h-20 w-full rounded-xl" />)}
          </div>
        ) : !data || data.triggers.length === 0 ? (
          <Card className="border-dashed">
            <CardContent className="flex flex-col items-center gap-3 py-16">
              <div className="rounded-full bg-muted p-3">
                <Zap className="size-6 text-muted-foreground" />
              </div>
              <p className="text-sm font-medium text-muted-foreground">No triggers deployed yet.</p>
              <p className="text-xs text-muted-foreground">
                Click "Add Trigger" to see code examples, or use{' '}
                <code className="bg-muted px-1.5 py-0.5 rounded text-[11px] font-mono">POST /v1/triggers</code>
              </p>
            </CardContent>
          </Card>
        ) : (
          <div className="flex flex-col gap-3">
            {data.triggers.map((t) => (
              <Card key={t.trigger_id} className="transition-colors hover:border-foreground/20">
                <CardContent className="p-5">
                  <div className="flex items-center gap-4">
                    {/* Icon */}
                    <div className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-muted">
                      <Zap className="size-4 text-muted-foreground" />
                    </div>

                    {/* Info */}
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <p className="font-mono text-sm font-medium">{t.trigger_type}</p>
                        <Badge
                          variant={t.enabled ? 'default' : 'secondary'}
                          className="text-[10px]"
                        >
                          {t.enabled ? 'Active' : 'Disabled'}
                        </Badge>
                      </div>
                      <div className="flex items-center gap-3 mt-1 text-xs text-muted-foreground">
                        <span className="font-mono truncate max-w-[180px]" title={t.user_id}>
                          {t.user_id}
                        </span>
                        <span>·</span>
                        <span className="truncate max-w-[200px]" title={t.webhook_url}>
                          {t.webhook_url}
                        </span>
                      </div>
                    </div>

                    {/* Poll info */}
                    <div className="hidden sm:flex items-center gap-4 text-xs text-muted-foreground">
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <div className="flex items-center gap-1">
                            <RefreshCw className="size-3" />
                            {t.poll_interval_seconds}s
                          </div>
                        </TooltipTrigger>
                        <TooltipContent>Poll interval</TooltipContent>
                      </Tooltip>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <div className="flex items-center gap-1">
                            <Clock className="size-3" />
                            {timeAgo(t.last_poll_at)}
                          </div>
                        </TooltipTrigger>
                        <TooltipContent>Last polled</TooltipContent>
                      </Tooltip>
                    </div>

                    {/* Actions */}
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button variant="ghost" size="icon" className="size-8 text-muted-foreground">
                          <MoreHorizontal className="size-4" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end" className="w-40">
                        <DropdownMenuItem
                          className="text-destructive focus:text-destructive gap-2 text-xs"
                          onClick={() => removeMut.mutate(t.trigger_id)}
                          disabled={removeMut.isPending}
                        >
                          <Trash2 className="size-3.5" />
                          Remove trigger
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>
    </TooltipProvider>
  )
}
