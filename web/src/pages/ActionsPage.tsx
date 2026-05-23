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
import { ScrollArea } from '@/components/ui/scroll-area'
import { Separator } from '@/components/ui/separator'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { listActions, executeAction, getDashboardConnections } from '@/lib/api'
import { Search, Play, CheckCircle2, XCircle, Loader2, Copy, Check } from 'lucide-react'
import { cn } from '@/lib/utils'

const APPS = [
  'all',
  'google',
  'slack',
  'hubspot',
  'github',
  'freshdesk',
  'docusign',
  'zendesk',
  'whatsapp',
]

const METHOD_COLORS: Record<string, string> = {
  GET: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  POST: 'bg-blue-50 text-blue-700 border-blue-200',
  PUT: 'bg-amber-50 text-amber-700 border-amber-200',
  PATCH: 'bg-orange-50 text-orange-700 border-orange-200',
  DELETE: 'bg-red-50 text-red-700 border-red-200',
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
  const [selectedApp, setSelectedApp] = useState('all')
  const [search, setSearch] = useState('')
  const [expandedAction, setExpandedAction] = useState<string | null>(null)

  // Try Action dialog state
  const [tryAction, setTryAction] = useState<Action | null>(null)
  const [tryUserId, setTryUserId] = useState('')
  const [tryParams, setTryParams] = useState<Record<string, string>>({})
  const [tryResult, setTryResult] = useState<unknown>(null)

  const { data, isLoading } = useQuery({
    queryKey: ['actions'],
    queryFn: () => listActions(),
  })

  // Fetch connected users for the dropdown
  const { data: connectionsData } = useQuery({
    queryKey: ['dashboard-connections'],
    queryFn: () => getDashboardConnections(),
  })

  const allConnectedUsers = connectionsData?.connections
    ?.filter((c) => c.status === 'active')
    ?.map((c) => ({ user_id: c.user_id, provider: c.provider })) || []

  // Filter users relevant to the current action's app
  const getMatchingUsers = (actionApp: string) => {
    const matching = allConnectedUsers.filter((c) => c.provider === actionApp)
    // Deduplicate by user_id
    return Array.from(new Map(matching.map((u) => [u.user_id, u])).values())
  }

  // All unique users (for fallback)
  const uniqueUsers = Array.from(
    new Map(allConnectedUsers.map((u) => [u.user_id, u])).values()
  )

  const executeMut = useMutation({
    mutationFn: (params: Record<string, string>) => executeAction(tryAction!.name, tryUserId, params),
    onSuccess: (result) => setTryResult(result),
    onError: (err) => setTryResult({ error: (err as Error).message, successful: false }),
  })

  const openTryDialog = (action: Action, e: React.MouseEvent) => {
    e.stopPropagation()
    setTryAction(action)
    const matchingUsers = getMatchingUsers(action.app)
    setTryUserId(matchingUsers[0]?.user_id || uniqueUsers[0]?.user_id || '')
    // Pre-populate params with empty strings
    const initialParams: Record<string, string> = {}
    action.params.forEach((p) => { initialParams[p.name] = '' })
    setTryParams(initialParams)
    setTryResult(null)
  }

  const closeTryDialog = () => {
    setTryAction(null)
    setTryResult(null)
    executeMut.reset()
  }

  const actions = data?.actions || []
  const filtered = actions.filter((a) => {
    if (selectedApp !== 'all' && a.app !== selectedApp) return false
    if (search && !a.name.toLowerCase().includes(search.toLowerCase()) &&
        !a.description.toLowerCase().includes(search.toLowerCase())) return false
    return true
  })

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Actions</h1>
        <p className="text-sm text-muted-foreground mt-1">
          {data ? `${data.total} actions across ${APPS.length - 1} apps.` : 'Loading...'} Browse and test API actions.
        </p>
      </div>

      {/* Filters */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search actions..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9"
          />
        </div>
        <div className="flex flex-wrap gap-1">
          {APPS.map((app) => (
            <Button
              key={app}
              variant={selectedApp === app ? 'default' : 'outline'}
              size="sm"
              onClick={() => setSelectedApp(app)}
              className="text-xs capitalize"
            >
              {app}
            </Button>
          ))}
        </div>
      </div>

      {/* Actions list */}
      {isLoading ? (
        <div className="flex flex-col gap-2">
          {[1, 2, 3, 4, 5].map((i) => (
            <Skeleton key={i} className="h-16 w-full rounded-lg" />
          ))}
        </div>
      ) : (
        <ScrollArea className="h-[calc(100vh-280px)]">
          <div className="flex flex-col gap-2">
            {filtered.map((action) => (
              <Card
                key={action.name}
                className={cn(
                  'cursor-pointer transition-colors hover:bg-muted/50',
                  expandedAction === action.name && 'ring-1 ring-border',
                )}
                onClick={() =>
                  setExpandedAction(
                    expandedAction === action.name ? null : action.name,
                  )
                }
              >
                <CardHeader className="py-3 px-4">
                  <div className="flex items-center gap-3">
                    <Badge variant="outline" className={cn('text-xs font-mono', METHOD_COLORS[action.method] || '')}>
                      {action.method}
                    </Badge>
                    <CardTitle className="text-sm font-mono">{action.name}</CardTitle>
                    <div className="ml-auto flex items-center gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        className="text-xs h-7"
                        onClick={(e) => openTryDialog(action, e)}
                      >
                        <Play className="mr-1 size-3" />
                        Try it
                      </Button>
                      <Badge variant="secondary" className="text-xs capitalize">
                        {action.app}
                      </Badge>
                    </div>
                  </div>
                  <CardDescription className="text-xs mt-1 line-clamp-1">
                    {action.description}
                  </CardDescription>
                </CardHeader>

                {expandedAction === action.name && (
                  <CardContent className="pt-0 px-4 pb-4">
                    <Separator className="mb-3" />
                    <p className="text-sm text-muted-foreground mb-3">
                      {action.description}
                    </p>
                    {action.params.length > 0 && (
                      <div className="rounded-md border">
                        <div className="grid grid-cols-[1fr_80px_1fr] gap-2 p-2 bg-muted/50 text-xs font-medium text-muted-foreground">
                          <span>Parameter</span>
                          <span>Type</span>
                          <span>Description</span>
                        </div>
                        {action.params.map((p) => (
                          <div
                            key={p.name}
                            className="grid grid-cols-[1fr_80px_1fr] gap-2 p-2 border-t text-xs"
                          >
                            <div className="flex items-center gap-1">
                              <code className="font-mono">{p.name}</code>
                              {p.required && (
                                <span className="text-destructive">*</span>
                              )}
                            </div>
                            <Badge variant="outline" className="text-[10px] w-fit">
                              {p.type}
                            </Badge>
                            <span className="text-muted-foreground">
                              {p.description}
                            </span>
                          </div>
                        ))}
                      </div>
                    )}
                  </CardContent>
                )}
              </Card>
            ))}
            {filtered.length === 0 && (
              <p className="py-8 text-center text-sm text-muted-foreground">
                No actions match your search.
              </p>
            )}
          </div>
        </ScrollArea>
      )}

      {/* Try Action Dialog */}
      <Dialog open={!!tryAction} onOpenChange={(open) => !open && closeTryDialog()}>
        <DialogContent className="max-w-lg max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="font-mono text-base">
              {tryAction?.name}
            </DialogTitle>
            <DialogDescription>
              {tryAction?.description}
            </DialogDescription>
          </DialogHeader>

          <div className="flex flex-col gap-4 py-2">
            {/* User ID selector — filtered by action's app */}
            <div className="flex flex-col gap-2">
              <Label>User ID</Label>
              <UserSelector
                actionApp={tryAction?.app || ''}
                allUsers={allConnectedUsers}
                value={tryUserId}
                onChange={setTryUserId}
              />
            </div>

            <Separator />

            {/* Action parameters */}
            {tryAction?.params && tryAction.params.length > 0 ? (
              tryAction.params.map((p) => (
                <div key={p.name} className="flex flex-col gap-1.5">
                  <Label className="text-sm">
                    {p.name}
                    {p.required && <span className="text-destructive ml-1">*</span>}
                    <span className="ml-2 text-xs font-normal text-muted-foreground">
                      {p.type}
                    </span>
                  </Label>
                  {p.type === 'string' && (p.name.includes('body') || p.name.includes('content') || p.name.includes('message') || p.name.includes('text')) ? (
                    <textarea
                      value={tryParams[p.name] || ''}
                      onChange={(e) => setTryParams({ ...tryParams, [p.name]: e.target.value })}
                      placeholder={p.description}
                      rows={3}
                      className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                    />
                  ) : (
                    <Input
                      value={tryParams[p.name] || ''}
                      onChange={(e) => setTryParams({ ...tryParams, [p.name]: e.target.value })}
                      placeholder={p.description}
                    />
                  )}
                </div>
              ))
            ) : (
              <p className="text-sm text-muted-foreground">No parameters required.</p>
            )}
          </div>

          <DialogFooter className="flex-col gap-2">
            <Button
              onClick={() => {
                // Filter out empty params
                const cleanParams: Record<string, string> = {}
                Object.entries(tryParams).forEach(([k, v]) => {
                  if (v.trim()) cleanParams[k] = v
                })
                executeMut.mutate(cleanParams)
              }}
              disabled={executeMut.isPending || !tryUserId}
              className="w-full sm:w-auto"
            >
              {executeMut.isPending ? (
                <>
                  <Loader2 className="mr-2 size-4 animate-spin" />
                  Executing...
                </>
              ) : (
                <>
                  <Play className="mr-2 size-4" />
                  Execute
                </>
              )}
            </Button>
          </DialogFooter>

          {/* Result */}
          {tryResult != null && (
            <ResultBlock result={tryResult as Record<string, unknown>} />
          )}
        </DialogContent>
      </Dialog>
    </div>
  )
}

function ResultBlock({ result }: { result: unknown }) {
  const [copied, setCopied] = useState(false)
  const jsonStr = JSON.stringify(result, null, 2)

  const handleCopy = () => {
    navigator.clipboard.writeText(jsonStr)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="mt-2">
      <Separator className="mb-3" />
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          {(result as { successful?: boolean }).successful ? (
            <>
              <CheckCircle2 className="size-4 text-emerald-600" />
              <span className="text-sm font-medium text-emerald-600">Success</span>
            </>
          ) : (
            <>
              <XCircle className="size-4 text-destructive" />
              <span className="text-sm font-medium text-destructive">
                {(result as { error?: string }).error || 'Failed'}
              </span>
            </>
          )}
        </div>
        <Button variant="ghost" size="sm" className="h-7 px-2" onClick={handleCopy}>
          {copied ? <Check className="size-3 mr-1" /> : <Copy className="size-3 mr-1" />}
          {copied ? 'Copied' : 'Copy'}
        </Button>
      </div>
      <pre className="text-xs bg-muted rounded-md p-3 overflow-auto max-h-[300px] whitespace-pre-wrap">
        {jsonStr}
      </pre>
    </div>
  )
}

function UserSelector({
  actionApp,
  allUsers,
  value,
  onChange,
}: {
  actionApp: string
  allUsers: { user_id: string; provider: string }[]
  value: string
  onChange: (v: string) => void
}) {
  // Show only users connected to this action's provider
  const matching = allUsers.filter((c) => c.provider === actionApp)
  const dedupedMatching = Array.from(new Map(matching.map((u) => [u.user_id, u])).values())

  if (dedupedMatching.length > 0) {
    return (
      <>
        <select
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          {dedupedMatching.map((u) => (
            <option key={u.user_id} value={u.user_id}>
              {u.user_id} ({u.provider})
            </option>
          ))}
        </select>
      </>
    )
  }

  return (
    <>
      <Input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder="customer-123"
      />
      <p className="text-xs text-amber-600">
        No users connected to {actionApp}. Connect a user with this provider first.
      </p>
    </>
  )
}
