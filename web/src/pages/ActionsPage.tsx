import { useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { Separator } from '@/components/ui/separator'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { listApps, listActions, executeAction, getDashboardConnections } from '@/lib/api'
import {
  Search, Play, CheckCircle2, XCircle, Loader2, Copy, Check,
  ArrowLeft, ChevronRight, Zap,
} from 'lucide-react'
import { cn } from '@/lib/utils'

const CDN_BASE = import.meta.env.VITE_CDN_BASE || ''

const METHOD_COLORS: Record<string, string> = {
  GET: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  POST: 'bg-blue-50 text-blue-700 border-blue-200',
  PUT: 'bg-amber-50 text-amber-700 border-amber-200',
  PATCH: 'bg-orange-50 text-orange-700 border-orange-200',
  DELETE: 'bg-red-50 text-red-700 border-red-200',
}

interface AppInfo {
  slug: string
  name: string
  provider: string
  description: string
  icon_path: string
  action_count: number
  auth_type: string
  action_prefix: string
}

interface ActionParam {
  name: string
  type: string
  required: boolean
  description: string
  location: string
}

interface Action {
  name: string
  app: string
  description: string
  method: string
  params: ActionParam[]
}

export function ActionsPage() {
  const [selectedApp, setSelectedApp] = useState<AppInfo | null>(null)
  const [search, setSearch] = useState('')

  // Try Action dialog state
  const [tryAction, setTryAction] = useState<Action | null>(null)
  const [tryUserId, setTryUserId] = useState('')
  const [tryParams, setTryParams] = useState<Record<string, string>>({})
  const [tryResult, setTryResult] = useState<unknown>(null)
  const [copied, setCopied] = useState(false)

  // ── Apps list ─────────────────────────────────────────────────────
  const { data: appsData, isLoading: appsLoading } = useQuery({
    queryKey: ['apps'],
    queryFn: () => listApps(),
  })

  // ── Actions for selected app ──────────────────────────────────────
  const { data: actionsData, isLoading: actionsLoading } = useQuery({
    queryKey: ['actions', selectedApp?.provider],
    queryFn: () => listActions(selectedApp?.provider),
    enabled: !!selectedApp,
  })

  // ── Connected users ───────────────────────────────────────────────
  const { data: connectionsData } = useQuery({
    queryKey: ['dashboard-connections'],
    queryFn: () => getDashboardConnections(),
  })

  const allConnectedUsers = connectionsData?.connections
    ?.filter((c: { status: string }) => c.status === 'active')
    ?.map((c: { user_id: string; provider: string }) => ({ user_id: c.user_id, provider: c.provider })) || []

  const getMatchingUsers = (actionApp: string) => {
    const matching = allConnectedUsers.filter((c: { provider: string }) => c.provider === actionApp)
    return Array.from(new Map(matching.map((u: { user_id: string }) => [u.user_id, u])).values())
  }

  const uniqueUsers = Array.from(
    new Map(allConnectedUsers.map((u: { user_id: string }) => [u.user_id, u])).values()
  ) as { user_id: string; provider: string }[]

  const executeMut = useMutation({
    mutationFn: (params: Record<string, string>) => executeAction(tryAction!.name, tryUserId, params),
    onSuccess: (result) => setTryResult(result),
    onError: (err) => setTryResult({ error: (err as Error).message, successful: false }),
  })

  const openTryDialog = (action: Action, e: React.MouseEvent) => {
    e.stopPropagation()
    setTryAction(action)
    setTryUserId('')
    setTryResult(null)
    const defaults: Record<string, string> = {}
    action.params?.forEach((p) => {
      if (p.required) defaults[p.name] = ''
    })
    setTryParams(defaults)
  }

  const copyResult = () => {
    navigator.clipboard.writeText(JSON.stringify(tryResult, null, 2))
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  // ── Filter actions by prefix ──────────────────────────────────────
  const allActions = actionsData?.actions || []
  const filteredActions = allActions
    .filter((a: Action) => selectedApp ? a.name.startsWith(selectedApp.action_prefix) : true)
    .filter((a: Action) =>
      !search ||
      a.name.toLowerCase().includes(search.toLowerCase()) ||
      a.description.toLowerCase().includes(search.toLowerCase())
    )

  // ── Filter apps ───────────────────────────────────────────────────
  const apps = (appsData?.apps || []).filter((a: AppInfo) =>
    !search ||
    a.name.toLowerCase().includes(search.toLowerCase()) ||
    a.slug.toLowerCase().includes(search.toLowerCase())
  )

  const iconUrl = (path: string, appSlug?: string) => {
    if (path && path.startsWith('http')) return path
    if (path) return `${CDN_BASE}/${path}`
    // Fallback: Composio's public logo API (has every app)
    const slug = appSlug?.toLowerCase().replace('_', '') || ''
    if (slug) return `https://logos.composio.dev/api/${slug}`
    return ''
  }

  // ══════════════════════════════════════════════════════════════════
  // RENDER: App Detail (actions table)
  // ══════════════════════════════════════════════════════════════════
  if (selectedApp) {
    return (
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center gap-4">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => { setSelectedApp(null); setSearch('') }}
          >
            <ArrowLeft className="size-5" />
          </Button>
          <img
            src={iconUrl(selectedApp.icon_path, selectedApp.slug)}
            alt={selectedApp.name}
            className="size-10 rounded-lg object-contain"
            onError={(e) => { (e.target as HTMLImageElement).style.display = 'none' }}
          />
          <div>
            <h1 className="text-2xl font-bold">{selectedApp.name}</h1>
            <p className="text-sm text-muted-foreground">
              {selectedApp.provider} · {selectedApp.action_count} actions ·{' '}
              <Badge variant="outline" className="text-xs">{selectedApp.auth_type}</Badge>
            </p>
          </div>
        </div>

        {/* Search + count */}
        <div className="flex items-center gap-4">
          <div className="relative max-w-md flex-1">
            <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder="Search actions..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-10"
            />
          </div>
          <span className="text-sm text-muted-foreground">
            {filteredActions.length} action{filteredActions.length !== 1 ? 's' : ''}
          </span>
        </div>

        {/* Actions table */}
        {actionsLoading ? (
          <div className="space-y-3">
            {[1, 2, 3, 4, 5].map((i) => <Skeleton key={i} className="h-16 w-full" />)}
          </div>
        ) : (
          <div className="rounded-lg border">
            {/* Table header */}
            <div className="grid grid-cols-[80px_1fr_2fr_100px] gap-4 border-b bg-muted/50 px-4 py-2.5 text-xs font-medium text-muted-foreground">
              <div>Method</div>
              <div>Name</div>
              <div>Description</div>
              <div></div>
            </div>
            {/* Rows */}
            {filteredActions.map((action: Action) => {
              const displayName = action.name
                .replace(selectedApp.action_prefix, '')
                .split('_')
                .map((w: string) => w.charAt(0).toUpperCase() + w.slice(1))
                .join(' ')

              return (
                <div
                  key={action.name}
                  className="grid grid-cols-[80px_1fr_2fr_100px] items-center gap-4 border-b px-4 py-3 last:border-b-0 hover:bg-muted/30 transition-colors"
                >
                  <Badge
                    variant="outline"
                    className={cn('w-fit text-[10px] font-mono', METHOD_COLORS[action.method])}
                  >
                    {action.method}
                  </Badge>
                  <div>
                    <p className="text-sm font-medium">{displayName}</p>
                    <p className="text-xs font-mono text-muted-foreground">{action.name}</p>
                  </div>
                  <p className="text-sm text-muted-foreground line-clamp-2">
                    {action.description}
                  </p>
                  <Button
                    variant="outline"
                    size="sm"
                    className="h-8"
                    onClick={(e) => openTryDialog(action, e)}
                  >
                    <Play className="mr-1 size-3" />
                    Try it
                  </Button>
                </div>
              )
            })}
            {filteredActions.length === 0 && (
              <div className="px-4 py-8 text-center text-sm text-muted-foreground">
                No actions found.
              </div>
            )}
          </div>
        )}

        {/* Try Action Dialog */}
        <TryActionDialog
          action={tryAction}
          open={!!tryAction}
          onClose={() => { setTryAction(null); setTryResult(null) }}
          tryUserId={tryUserId}
          setTryUserId={setTryUserId}
          tryParams={tryParams}
          setTryParams={setTryParams}
          tryResult={tryResult}
          executeMut={executeMut}
          matchingUsers={tryAction ? getMatchingUsers(tryAction.app) as { user_id: string; provider: string }[] : []}
          uniqueUsers={uniqueUsers}
          copied={copied}
          copyResult={copyResult}
        />
      </div>
    )
  }

  // ══════════════════════════════════════════════════════════════════
  // RENDER: Apps Grid
  // ══════════════════════════════════════════════════════════════════
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Apps</h1>
        <p className="text-muted-foreground">
          {appsData?.total || 0} apps · {apps.reduce((sum: number, a: AppInfo) => sum + a.action_count, 0)} actions. Browse and test API actions.
        </p>
      </div>

      {/* Search */}
      <div className="relative max-w-md">
        <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          placeholder="Search apps..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="pl-10"
        />
      </div>

      {/* Apps grid */}
      {appsLoading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {[1, 2, 3, 4, 5, 6, 7, 8].map((i) => <Skeleton key={i} className="h-40" />)}
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {apps.map((app: AppInfo) => (
            <Card
              key={app.slug}
              className="cursor-pointer transition-all hover:shadow-md hover:border-foreground/20"
              onClick={() => { setSelectedApp(app); setSearch('') }}
            >
              <CardHeader className="pb-3">
                <div className="flex items-start justify-between">
                  <img
                    src={iconUrl(app.icon_path, app.slug)}
                    alt={app.name}
                    className="size-12 rounded-lg object-contain"
                    onError={(e) => {
                      const el = e.target as HTMLImageElement
                      el.style.display = 'none'
                    }}
                  />
                  <ChevronRight className="size-4 text-muted-foreground" />
                </div>
                <CardTitle className="mt-3 text-base">{app.name}</CardTitle>
                <CardDescription className="text-xs">{app.description}</CardDescription>
              </CardHeader>
              <CardContent className="pt-0">
                <div className="flex items-center gap-2">
                  <Badge variant="outline" className="text-xs">
                    <Zap className="mr-1 size-3" />
                    {app.action_count} actions
                  </Badge>
                  <Badge variant="outline" className="text-xs">
                    {app.auth_type}
                  </Badge>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}


// ── Try Action Dialog ─────────────────────────────────────────────────

function TryActionDialog({
  action,
  open,
  onClose,
  tryUserId,
  setTryUserId,
  tryParams,
  setTryParams,
  tryResult,
  executeMut,
  matchingUsers,
  uniqueUsers,
  copied,
  copyResult,
}: {
  action: Action | null
  open: boolean
  onClose: () => void
  tryUserId: string
  setTryUserId: (v: string) => void
  tryParams: Record<string, string>
  setTryParams: (v: Record<string, string>) => void
  tryResult: unknown
  executeMut: ReturnType<typeof useMutation<unknown, Error, Record<string, string>>>
  matchingUsers: { user_id: string; provider: string }[]
  uniqueUsers: { user_id: string; provider: string }[]
  copied: boolean
  copyResult: () => void
}) {
  if (!action) return null

  const users = matchingUsers.length > 0 ? matchingUsers : uniqueUsers
  const result = tryResult as Record<string, unknown> | null

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-h-[85vh] max-w-2xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Badge
              variant="outline"
              className={cn('text-[10px] font-mono', METHOD_COLORS[action.method])}
            >
              {action.method}
            </Badge>
            {action.name}
          </DialogTitle>
          <DialogDescription>{action.description}</DialogDescription>
        </DialogHeader>

        <Separator />

        {/* User ID */}
        <div className="space-y-2">
          <Label>User ID</Label>
          {users.length > 0 ? (
            <select
              className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm"
              value={tryUserId}
              onChange={(e) => setTryUserId(e.target.value)}
            >
              <option value="">Select a connected user...</option>
              {users.map((u) => (
                <option key={u.user_id} value={u.user_id}>
                  {u.user_id} ({u.provider})
                </option>
              ))}
            </select>
          ) : (
            <Input
              placeholder="Enter user_id"
              value={tryUserId}
              onChange={(e) => setTryUserId(e.target.value)}
            />
          )}
        </div>

        {/* Parameters */}
        {action.params?.length > 0 && (
          <div className="space-y-3">
            <Label>Parameters</Label>
            {action.params.map((p) => (
              <div key={p.name} className="space-y-1">
                <div className="flex items-center gap-2">
                  <Label className="text-xs font-mono">{p.name}</Label>
                  <Badge variant="outline" className="text-[10px]">{p.type}</Badge>
                  {p.required && (
                    <Badge variant="destructive" className="text-[10px]">required</Badge>
                  )}
                </div>
                {p.description && (
                  <p className="text-xs text-muted-foreground line-clamp-2">{p.description}</p>
                )}
                <Input
                  placeholder={p.name}
                  value={tryParams[p.name] || ''}
                  onChange={(e) => setTryParams({ ...tryParams, [p.name]: e.target.value })}
                />
              </div>
            ))}
          </div>
        )}

        {/* Result */}
        {result && (
          <>
            <Separator />
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Label>Result</Label>
                  {(result as Record<string, unknown>).successful ? (
                    <CheckCircle2 className="size-4 text-emerald-500" />
                  ) : (
                    <XCircle className="size-4 text-red-500" />
                  )}
                </div>
                <Button variant="ghost" size="sm" onClick={copyResult}>
                  {copied ? <Check className="mr-1 size-3" /> : <Copy className="mr-1 size-3" />}
                  {copied ? 'Copied' : 'Copy'}
                </Button>
              </div>
              <pre className="max-h-64 overflow-auto rounded-md bg-muted p-3 text-xs">
                {JSON.stringify(result, null, 2)}
              </pre>
            </div>
          </>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Close</Button>
          <Button
            onClick={() => {
              const cleanParams: Record<string, string> = {}
              Object.entries(tryParams).forEach(([k, v]) => {
                if (v.trim()) cleanParams[k] = v
              })
              executeMut.mutate(cleanParams)
            }}
            disabled={!tryUserId || executeMut.isPending}
          >
            {executeMut.isPending && <Loader2 className="mr-2 size-4 animate-spin" />}
            Execute
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
