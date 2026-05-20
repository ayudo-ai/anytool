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
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { listTriggers, deployTrigger, removeTrigger, getDashboardConnections, getDashboardWebhookLogs, getMe } from '@/lib/api'
import { Plus, Trash2, Zap, Clock, AlertCircle } from 'lucide-react'

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

export function TriggersPage() {
  const queryClient = useQueryClient()
  const [open, setOpen] = useState(false)
  const [form, setForm] = useState({
    trigger_type: 'gmail_new_message',
    user_id: '',
    webhook_url: '',
    poll_interval_seconds: 90,
    filters: {} as Record<string, string>,
  })

  const { data, isLoading } = useQuery({
    queryKey: ['triggers'],
    queryFn: () => listTriggers(),
    refetchInterval: 15000, // auto-refresh every 15s to show last_poll_at updates
  })

  // Fetch connected users for the dropdown
  const { data: connectionsData } = useQuery({
    queryKey: ['dashboard-connections'],
    queryFn: () => getDashboardConnections(),
  })

  const connectedUsers = connectionsData?.connections
    ?.filter((c) => c.status === 'active')
    ?.map((c) => ({ user_id: c.user_id, provider: c.provider })) || []
  const uniqueUsers = Array.from(
    new Map(connectedUsers.map((u) => [u.user_id, u])).values()
  )

  // Fetch recent webhook delivery logs
  const { data: webhookLogsData } = useQuery({
    queryKey: ['webhook-logs'],
    queryFn: () => getDashboardWebhookLogs({ limit: 20 }),
    refetchInterval: 15000,
  })

  // Fetch workspace_id for test webhook URL
  const { data: me } = useQuery({
    queryKey: ['me'],
    queryFn: getMe,
  })
  const testWebhookUrl = me?.workspace_id
    ? `${window.location.origin}/v1/webhook-test/${me.workspace_id}`
    : `${window.location.origin}/v1/webhook-test/test`

  const deployMut = useMutation({
    mutationFn: deployTrigger,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['triggers'] })
      setOpen(false)
      setForm({ trigger_type: 'gmail_new_message', user_id: '', webhook_url: '', poll_interval_seconds: 90, filters: {} })
    },
  })

  const removeMut = useMutation({
    mutationFn: removeTrigger,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['triggers'] }),
  })

  // Filter definitions per trigger type
  const TRIGGER_FILTERS: Record<string, { name: string; label: string; placeholder: string }[]> = {
    gmail_new_message: [
      { name: 'from_contains', label: 'From (contains)', placeholder: 'vendor@example.com' },
      { name: 'to_contains', label: 'To (contains)', placeholder: 'support@yourcompany.com' },
      { name: 'subject_contains', label: 'Subject (contains)', placeholder: 'invoice' },
      { name: 'label', label: 'Label', placeholder: 'INBOX, IMPORTANT, CATEGORY_UPDATES' },
      { name: 'has_attachment', label: 'Has attachment', placeholder: 'true' },
    ],
    slack_new_message: [
      { name: 'channel_id', label: 'Channel ID (required)', placeholder: 'C1234567890' },
      { name: 'from_user', label: 'From user ID', placeholder: 'U1234567890' },
      { name: 'contains', label: 'Text contains', placeholder: 'keyword' },
    ],
    github_new_issue: [
      { name: 'owner', label: 'Repo owner (required)', placeholder: 'octocat' },
      { name: 'repo', label: 'Repo name (required)', placeholder: 'hello-world' },
      { name: 'labels', label: 'Labels (comma-separated)', placeholder: 'bug, high-priority' },
      { name: 'state', label: 'State', placeholder: 'open' },
    ],
    github_new_pr: [
      { name: 'owner', label: 'Repo owner (required)', placeholder: 'octocat' },
      { name: 'repo', label: 'Repo name (required)', placeholder: 'hello-world' },
    ],
    github_push: [
      { name: 'owner', label: 'Repo owner (required)', placeholder: 'octocat' },
      { name: 'repo', label: 'Repo name (required)', placeholder: 'hello-world' },
    ],
    github_star: [
      { name: 'owner', label: 'Repo owner (required)', placeholder: 'octocat' },
      { name: 'repo', label: 'Repo name (required)', placeholder: 'hello-world' },
    ],
    github_issue_comment: [
      { name: 'owner', label: 'Repo owner (required)', placeholder: 'octocat' },
      { name: 'repo', label: 'Repo name (required)', placeholder: 'hello-world' },
    ],
    hubspot_new_contact: [
      { name: 'property', label: 'Filter property', placeholder: 'lifecyclestage' },
      { name: 'value', label: 'Property value', placeholder: 'lead' },
    ],
    hubspot_new_deal: [
      { name: 'pipeline', label: 'Pipeline', placeholder: 'default' },
      { name: 'dealstage', label: 'Deal stage', placeholder: 'appointmentscheduled' },
    ],
    freshdesk_new_ticket: [
      { name: 'status', label: 'Status (2=open, 3=pending, 4=resolved)', placeholder: '2' },
      { name: 'priority', label: 'Priority (1=low, 2=med, 3=high, 4=urgent)', placeholder: '3' },
    ],
    zendesk_new_ticket: [
      { name: 'status', label: 'Status', placeholder: 'open' },
      { name: 'priority', label: 'Priority', placeholder: 'high' },
    ],
  }

  const currentFilters = TRIGGER_FILTERS[form.trigger_type] || []

  const TRIGGER_TYPES = [
    'gmail_new_message',
    'slack_new_message',
    'github_new_issue',
    'github_new_pr',
    'github_push',
    'github_star',
    'github_issue_comment',
    'hubspot_new_contact',
    'hubspot_new_deal',
    'freshdesk_new_ticket',
    'zendesk_new_ticket',
  ]

  // Webhook-based triggers (real-time, no polling)
  const WEBHOOK_TRIGGERS = new Set(['github_new_issue', 'github_new_pr', 'github_push', 'github_star', 'github_issue_comment'])

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Triggers</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Event-driven polling triggers that POST to your webhooks.
          </p>
        </div>
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button size="sm">
              <Plus className="mr-2 size-4" />
              Deploy Trigger
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Deploy a Trigger</DialogTitle>
              <DialogDescription>
                Poll a user's connected app and POST events to your webhook.
              </DialogDescription>
            </DialogHeader>
            <div className="flex flex-col gap-4 py-2">
              <div className="flex flex-col gap-2">
                <Label>Trigger Type</Label>
                <select
                  value={form.trigger_type}
                  onChange={(e) => setForm({ ...form, trigger_type: e.target.value, filters: {} })}
                  className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  {TRIGGER_TYPES.map((t) => (
                    <option key={t} value={t}>
                      {t}{WEBHOOK_TRIGGERS.has(t) ? ' ⚡ (real-time)' : ' 🔄 (polling)'}
                    </option>
                  ))}
                </select>
              </div>
              <div className="flex flex-col gap-2">
                <Label>User ID</Label>
                {uniqueUsers.length > 0 ? (
                  <select
                    value={form.user_id}
                    onChange={(e) => setForm({ ...form, user_id: e.target.value })}
                    className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  >
                    <option value="">Select a user...</option>
                    {uniqueUsers.map((u) => (
                      <option key={u.user_id} value={u.user_id}>
                        {u.user_id} ({u.provider})
                      </option>
                    ))}
                  </select>
                ) : (
                  <Input
                    value={form.user_id}
                    onChange={(e) => setForm({ ...form, user_id: e.target.value })}
                    placeholder="customer-123"
                  />
                )}
              </div>
              <div className="flex flex-col gap-2">
                <Label>Webhook URL</Label>
                <Input
                  value={form.webhook_url}
                  onChange={(e) => setForm({ ...form, webhook_url: e.target.value })}
                  placeholder="https://myapp.com/webhooks/inbox"
                />
                <p className="text-xs text-muted-foreground">
                  For testing, use the built-in echo server:{' '}
                  <button
                    type="button"
                    className="text-primary underline-offset-2 hover:underline"
                    onClick={() => setForm({ ...form, webhook_url: testWebhookUrl })}
                  >
                    Use test webhook URL
                  </button>
                </p>
              </div>
              <div className="flex flex-col gap-2">
                <Label>Poll Interval (seconds)</Label>
                <Input
                  type="number"
                  value={form.poll_interval_seconds}
                  onChange={(e) => setForm({ ...form, poll_interval_seconds: Number(e.target.value) })}
                />
              </div>

              {/* Filters */}
              {currentFilters.length > 0 && (
                <>
                  <div className="pt-1">
                    <p className="text-xs font-medium text-muted-foreground mb-2">Filters (optional)</p>
                  </div>
                  {currentFilters.map((f) => (
                    <div key={f.name} className="flex flex-col gap-1">
                      <Label className="text-xs">{f.label}</Label>
                      <Input
                        value={form.filters[f.name] || ''}
                        onChange={(e) => setForm({
                          ...form,
                          filters: { ...form.filters, [f.name]: e.target.value },
                        })}
                        placeholder={f.placeholder}
                        className="h-8 text-xs"
                      />
                    </div>
                  ))}
                </>
              )}
            </div>
            <DialogFooter>
              <Button
                onClick={() => {
                  // Clean empty filter values
                  const cleanFilters: Record<string, string> = {}
                  Object.entries(form.filters).forEach(([k, v]) => {
                    if (v.trim()) cleanFilters[k] = v.trim()
                  })
                  deployMut.mutate({ ...form, filters: cleanFilters })
                }}
                disabled={deployMut.isPending || !form.user_id || !form.webhook_url}
              >
                {deployMut.isPending ? 'Deploying...' : 'Deploy'}
              </Button>
            </DialogFooter>
            {deployMut.isError && (
              <p className="text-sm text-destructive mt-2">
                {(deployMut.error as Error).message}
              </p>
            )}
          </DialogContent>
        </Dialog>
      </div>

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="text-base">Active Triggers</CardTitle>
              <CardDescription>
                {data ? `${data.total} triggers` : 'Loading...'}
                {' · '}
                <span className="text-xs">Auto-refreshes every 15s</span>
              </CardDescription>
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => queryClient.invalidateQueries({ queryKey: ['triggers'] })}
            >
              <Clock className="mr-1 size-3" />
              Refresh
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="flex flex-col gap-2">
              {[1, 2, 3].map((i) => <Skeleton key={i} className="h-10 w-full" />)}
            </div>
          ) : !data || data.triggers.length === 0 ? (
            <div className="flex flex-col items-center gap-3 py-8">
              <Zap className="size-8 text-muted-foreground" />
              <p className="text-sm text-muted-foreground">No triggers deployed yet.</p>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Type</TableHead>
                  <TableHead>User ID</TableHead>
                  <TableHead>Webhook</TableHead>
                  <TableHead>Interval</TableHead>
                  <TableHead>Last Poll</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="w-10" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.triggers.map((t) => (
                  <TableRow key={t.trigger_id}>
                    <TableCell className="font-mono text-xs">{t.trigger_type}</TableCell>
                    <TableCell className="font-mono text-xs">{t.user_id}</TableCell>
                    <TableCell className="text-xs max-w-[200px] truncate" title={t.webhook_url}>
                      {t.webhook_url}
                    </TableCell>
                    <TableCell className="text-xs">{t.poll_interval_seconds}s</TableCell>
                    <TableCell className="text-xs">
                      <span className={t.last_poll_at ? 'text-foreground' : 'text-muted-foreground'}>
                        {timeAgo(t.last_poll_at)}
                      </span>
                    </TableCell>
                    <TableCell>
                      <Badge variant={t.enabled ? 'default' : 'secondary'}>
                        {t.enabled ? 'active' : 'disabled'}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => removeMut.mutate(t.trigger_id)}
                        disabled={removeMut.isPending}
                      >
                        <Trash2 className="size-4 text-muted-foreground" />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Webhook Delivery Logs */}
      {webhookLogsData && webhookLogsData.logs.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <AlertCircle className="size-4" />
              Webhook Deliveries
            </CardTitle>
            <CardDescription>
              Recent event deliveries from trigger polls · {webhookLogsData.total} total
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Event Type</TableHead>
                  <TableHead>User ID</TableHead>
                  <TableHead>Webhook</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Retries</TableHead>
                  <TableHead>Duration</TableHead>
                  <TableHead>Time</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {webhookLogsData.logs.map((log) => (
                  <TableRow key={log.id}>
                    <TableCell className="font-mono text-xs">{log.event_type}</TableCell>
                    <TableCell className="font-mono text-xs">{log.user_id}</TableCell>
                    <TableCell className="text-xs max-w-[150px] truncate" title={log.webhook_url}>
                      {log.webhook_url}
                    </TableCell>
                    <TableCell>
                      <Badge variant={log.successful ? 'default' : 'destructive'}>
                        {log.successful ? 'delivered' : 'failed'}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-xs">{log.retry_count}</TableCell>
                    <TableCell className="text-xs">{log.duration_ms}ms</TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {timeAgo(log.created_at)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
