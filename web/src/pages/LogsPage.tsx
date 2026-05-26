import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  Card,
  CardContent,
} from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from '@/components/ui/tabs'
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
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import { getDashboardLogs, getDashboardWebhookLogs } from '@/lib/api'
import {
  ChevronLeft, ChevronRight, Search, AlertCircle,
  Webhook, Eye, RefreshCw, Zap, ScrollText,
} from 'lucide-react'

function timeAgo(dateStr: string | null): string {
  if (!dateStr) return '—'
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

// ── Execution Logs Tab ──────────────────────────────────────────────

function ExecutionLogs() {
  const [offset, setOffset] = useState(0)
  const [actionFilter, setActionFilter] = useState('')
  const limit = 30

  const { data, isLoading } = useQuery({
    queryKey: ['logs', offset, actionFilter],
    queryFn: () =>
      getDashboardLogs({
        limit,
        offset,
        ...(actionFilter ? { action: actionFilter } : {}),
      }),
  })

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-3">
        <div className="relative max-w-sm flex-1">
          <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Filter by action name..."
            value={actionFilter}
            onChange={(e) => { setActionFilter(e.target.value); setOffset(0) }}
            className="pl-9"
          />
        </div>
        {data && (
          <span className="text-sm text-muted-foreground ml-auto">
            {data.total} total
          </span>
        )}
      </div>

      <Card>
        <CardContent className="p-0">
          {isLoading ? (
            <div className="flex flex-col gap-2 p-4">
              {[1, 2, 3, 4, 5].map((i) => <Skeleton key={i} className="h-10 w-full" />)}
            </div>
          ) : !data || data.logs.length === 0 ? (
            <div className="flex flex-col items-center gap-3 py-12">
              <ScrollText className="size-8 text-muted-foreground" />
              <p className="text-sm text-muted-foreground">No execution logs yet.</p>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Action</TableHead>
                  <TableHead>User ID</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Duration</TableHead>
                  <TableHead>Time</TableHead>
                  <TableHead className="w-10" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.logs.map((log) => (
                  <TableRow key={log.id}>
                    <TableCell className="font-mono text-xs">{log.action}</TableCell>
                    <TableCell className="font-mono text-xs">{log.user_id}</TableCell>
                    <TableCell>
                      <Badge variant={log.successful ? 'default' : 'destructive'} className="text-[10px]">
                        {log.status_code || 'ERR'}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">{log.duration_ms}ms</TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {log.created_at
                        ? new Date(log.created_at).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
                        : '—'}
                    </TableCell>
                    <TableCell>
                      {log.error && (
                        <TooltipProvider>
                          <Tooltip>
                            <TooltipTrigger><AlertCircle className="size-4 text-destructive" /></TooltipTrigger>
                            <TooltipContent className="max-w-xs"><p className="text-xs">{log.error}</p></TooltipContent>
                          </Tooltip>
                        </TooltipProvider>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {data && data.total > limit && (
        <div className="flex items-center justify-between">
          <span className="text-sm text-muted-foreground">
            {offset + 1}–{Math.min(offset + limit, data.total)} of {data.total}
          </span>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - limit))}>
              <ChevronLeft className="size-4" />
            </Button>
            <Button variant="outline" size="sm" disabled={offset + limit >= data.total} onClick={() => setOffset(offset + limit)}>
              <ChevronRight className="size-4" />
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}

// ── Webhook Logs Tab ────────────────────────────────────────────────

function WebhookLogs() {
  const [offset, setOffset] = useState(0)
  const [triggerFilter, setTriggerFilter] = useState('')
  const [selectedLog, setSelectedLog] = useState<Record<string, unknown> | null>(null)
  const limit = 30

  const { data, isLoading, refetch } = useQuery({
    queryKey: ['webhook-logs', offset, triggerFilter],
    queryFn: () =>
      getDashboardWebhookLogs({
        limit,
        offset,
        ...(triggerFilter ? { trigger_id: triggerFilter } : {}),
      }),
    refetchInterval: 15000,
  })

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-3">
        <div className="relative max-w-sm flex-1">
          <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Filter by trigger ID..."
            value={triggerFilter}
            onChange={(e) => { setTriggerFilter(e.target.value); setOffset(0) }}
            className="pl-9"
          />
        </div>
        <Button variant="outline" size="sm" onClick={() => refetch()} className="ml-auto">
          <RefreshCw className="mr-2 size-3" /> Refresh
        </Button>
        {data && (
          <span className="text-sm text-muted-foreground">{data.total} deliveries</span>
        )}
      </div>

      <Card>
        <CardContent className="p-0">
          {isLoading ? (
            <div className="flex flex-col gap-2 p-4">
              {[1, 2, 3, 4, 5].map((i) => <Skeleton key={i} className="h-10 w-full" />)}
            </div>
          ) : !data || data.logs.length === 0 ? (
            <div className="flex flex-col items-center gap-3 py-12">
              <Webhook className="size-8 text-muted-foreground" />
              <p className="text-sm text-muted-foreground">No webhook deliveries yet.</p>
              <p className="text-xs text-muted-foreground">Deploy a trigger and wait for events.</p>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Event Type</TableHead>
                  <TableHead>User ID</TableHead>
                  <TableHead>Webhook URL</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Duration</TableHead>
                  <TableHead>Time</TableHead>
                  <TableHead className="w-10" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.logs.map((log) => (
                  <TableRow key={log.id} className="cursor-pointer hover:bg-muted/50">
                    <TableCell className="font-mono text-xs">{log.event_type}</TableCell>
                    <TableCell className="font-mono text-xs">{log.user_id}</TableCell>
                    <TableCell className="text-xs max-w-[180px] truncate" title={log.webhook_url}>
                      {log.webhook_url}
                    </TableCell>
                    <TableCell>
                      <Badge variant={log.successful ? 'default' : 'destructive'} className="text-[10px]">
                        {log.successful ? log.status_code : (log.error || 'Failed')}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">{log.duration_ms}ms</TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      <TooltipProvider>
                        <Tooltip>
                          <TooltipTrigger>{timeAgo(log.created_at)}</TooltipTrigger>
                          <TooltipContent><p className="text-xs">{log.created_at ? new Date(log.created_at).toLocaleString() : '—'}</p></TooltipContent>
                        </Tooltip>
                      </TooltipProvider>
                    </TableCell>
                    <TableCell>
                      <Button variant="ghost" size="sm" onClick={() => setSelectedLog(log as unknown as Record<string, unknown>)}>
                        <Eye className="size-3.5" />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {data && data.total > limit && (
        <div className="flex items-center justify-between">
          <span className="text-sm text-muted-foreground">
            {offset + 1}–{Math.min(offset + limit, data.total)} of {data.total}
          </span>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - limit))}>
              <ChevronLeft className="size-4" />
            </Button>
            <Button variant="outline" size="sm" disabled={offset + limit >= data.total} onClick={() => setOffset(offset + limit)}>
              <ChevronRight className="size-4" />
            </Button>
          </div>
        </div>
      )}

      {/* Detail Dialog */}
      <Dialog open={!!selectedLog} onOpenChange={(open) => !open && setSelectedLog(null)}>
        <DialogContent className="max-w-lg max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="text-sm font-mono">Webhook Delivery Detail</DialogTitle>
          </DialogHeader>
          {selectedLog && (
            <div className="flex flex-col gap-4">
              <div className="grid grid-cols-2 gap-2 text-sm">
                <div>
                  <p className="text-xs text-muted-foreground">Event Type</p>
                  <p className="font-mono text-xs">{String(selectedLog.event_type)}</p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">User ID</p>
                  <p className="font-mono text-xs">{String(selectedLog.user_id)}</p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Status</p>
                  <Badge variant={selectedLog.successful ? 'default' : 'destructive'} className="text-[10px]">
                    {selectedLog.successful ? 'Delivered' : 'Failed'}
                  </Badge>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Duration</p>
                  <p className="text-xs">{String(selectedLog.duration_ms)}ms</p>
                </div>
              </div>
              <div>
                <p className="text-xs text-muted-foreground mb-1">Webhook URL</p>
                <code className="text-xs bg-muted rounded px-2 py-1 block break-all">{String(selectedLog.webhook_url)}</code>
              </div>
              {selectedLog.error != null && (
                <div>
                  <p className="text-xs text-muted-foreground mb-1">Error</p>
                  <pre className="text-xs bg-destructive/10 text-destructive rounded-md p-3 whitespace-pre-wrap">{String(selectedLog.error)}</pre>
                </div>
              )}
              <div>
                <p className="text-xs text-muted-foreground mb-1">Event Data</p>
                <pre className="text-xs bg-muted rounded-md p-3 overflow-auto max-h-[300px] whitespace-pre-wrap">
                  {JSON.stringify(selectedLog.event_data, null, 2)}
                </pre>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  )
}

// ── Main Page ───────────────────────────────────────────────────────

export function LogsPage() {
  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Logs</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Monitor API executions and webhook deliveries.
        </p>
      </div>

      <Tabs defaultValue="executions">
        <TabsList>
          <TabsTrigger value="executions" className="gap-1.5">
            <Zap className="size-3.5" />
            Executions
          </TabsTrigger>
          <TabsTrigger value="webhooks" className="gap-1.5">
            <Webhook className="size-3.5" />
            Webhooks
          </TabsTrigger>
        </TabsList>
        <TabsContent value="executions" className="mt-4">
          <ExecutionLogs />
        </TabsContent>
        <TabsContent value="webhooks" className="mt-4">
          <WebhookLogs />
        </TabsContent>
      </Tabs>
    </div>
  )
}
