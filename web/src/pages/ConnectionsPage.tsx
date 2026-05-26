import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Card,
  CardContent,
} from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import { getDashboardConnections, connectUser, connectApiKey, disconnectUser, listTriggers, listApps } from '@/lib/api'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Plus, Plug, Zap, Search, Trash2, Users, Link2, Clock, CheckCircle2, AlertCircle, MoreHorizontal } from 'lucide-react'
import { cn } from '@/lib/utils'

const CDN_BASE = import.meta.env.VITE_CDN_BASE || 'https://assets.ayudo.ai'

const API_KEY_PROVIDERS = ['freshdesk', 'zendesk', 'whatsapp']

interface UserEntity {
  user_id: string
  connections: { provider: string; status: string; connected_at: string }[]
  trigger_count: number
  providers: string[]
}

export function ConnectionsPage() {
  const queryClient = useQueryClient()
  const [open, setOpen] = useState(false)
  const userStr = localStorage.getItem('anytool_user')
  const devEmail = userStr ? (JSON.parse(userStr) as { email: string }).email : ''
  const [form, setForm] = useState({ provider: '', user_id: devEmail, api_key: '', domain: '' })
  const [search, setSearch] = useState('')

  const isApiKeyProvider = API_KEY_PROVIDERS.includes(form.provider)

  const { data: appsData } = useQuery({
    queryKey: ['apps'],
    queryFn: () => listApps(),
  })

  // Derive providers from apps API
  const providers = appsData?.apps
    ? [...new Set(appsData.apps.map((a: any) => a.provider as string))]
    : []

  // Build icon + name maps from apps API
  const providerIcons: Record<string, string> = {}
  const providerNames: Record<string, string> = {}
  if (appsData?.apps) {
    for (const app of appsData.apps) {
      const p = app.provider as string
      if (!providerIcons[p] && app.icon_path) {
        const icon = app.icon_path.startsWith('http') ? app.icon_path : `${CDN_BASE}/${app.icon_path}`
        providerIcons[p] = icon
      }
      if (!providerNames[p]) {
        providerNames[p] = p.charAt(0).toUpperCase() + p.slice(1)
      }
    }
  }

  const { data: connectionsData, isLoading: connectionsLoading } = useQuery({
    queryKey: ['dashboard-connections'],
    queryFn: () => getDashboardConnections(),
    refetchInterval: 10000,
  })

  const { data: triggersData } = useQuery({
    queryKey: ['triggers'],
    queryFn: () => listTriggers(),
  })

  const connectMut = useMutation({
    mutationFn: async () => {
      if (isApiKeyProvider) {
        return connectApiKey(form.provider, form.user_id, form.api_key, form.domain)
      }
      return connectUser(form.provider, form.user_id) as Promise<{ auth_url: string; user_id: string; provider: string }>
    },
    onSuccess: (result) => {
      if ('auth_url' in result && result.auth_url) {
        window.open(result.auth_url as string, '_blank')
      }
      queryClient.invalidateQueries({ queryKey: ['dashboard-connections'] })
      setOpen(false)
      setForm({ provider: '', user_id: devEmail, api_key: '', domain: '' })
    },
  })

  const disconnectMut = useMutation({
    mutationFn: ({ provider, userId }: { provider: string; userId: string }) =>
      disconnectUser(provider, userId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['dashboard-connections'] })
    },
  })

  // Group connections by user_id
  const entities: UserEntity[] = (() => {
    if (!connectionsData) return []
    const map = new Map<string, UserEntity>()
    for (const c of connectionsData.connections) {
      if (!map.has(c.user_id)) {
        map.set(c.user_id, {
          user_id: c.user_id,
          connections: [],
          trigger_count: 0,
          providers: [],
        })
      }
      const entity = map.get(c.user_id)!
      entity.connections.push({
        provider: c.provider,
        status: c.status,
        connected_at: c.connected_at,
      })
      if (!entity.providers.includes(c.provider)) {
        entity.providers.push(c.provider)
      }
    }
    if (triggersData) {
      for (const t of triggersData.triggers) {
        const entity = map.get(t.user_id)
        if (entity) entity.trigger_count++
      }
    }
    return Array.from(map.values())
  })()

  const filtered = entities.filter((e) => {
    if (!search) return true
    return e.user_id.toLowerCase().includes(search.toLowerCase())
  })

  const totalUsers = entities.length
  const activeConnections = connectionsData?.connections.filter((c: any) => c.status === 'active').length || 0
  const pendingConnections = connectionsData?.connections.filter((c: any) => c.status === 'pending').length || 0

  return (
    <TooltipProvider>
      <div className="flex flex-col gap-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">Connected Users</h1>
            <p className="text-sm text-muted-foreground mt-1">
              End-users who have connected their apps through your integration.
            </p>
          </div>
          <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild>
              <Button>
                <Plus className="mr-2 size-4" />
                Connect User
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Connect a User</DialogTitle>
                <DialogDescription>
                  Start an OAuth flow or enter API credentials for an end-user.
                </DialogDescription>
              </DialogHeader>
              <div className="flex flex-col gap-4 py-2">
                <div className="flex flex-col gap-2">
                  <Label>Provider</Label>
                  <select
                    value={form.provider}
                    onChange={(e) => setForm({ ...form, provider: e.target.value })}
                    className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  >
                    <option value="">Select a provider…</option>
                    {providers.map((p) => (
                      <option key={p} value={p}>
                        {providerNames[p] || p}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="flex flex-col gap-2">
                  <Label>User ID</Label>
                  <Input
                    value={form.user_id}
                    onChange={(e) => setForm({ ...form, user_id: e.target.value })}
                    placeholder="customer-123"
                  />
                  <p className="text-xs text-muted-foreground">
                    Your end-user's unique ID. Use your customer's ID in production.
                  </p>
                </div>
                {isApiKeyProvider && (
                  <>
                    <div className="flex flex-col gap-2">
                      <Label>API Key</Label>
                      <Input
                        type="password"
                        value={form.api_key}
                        onChange={(e) => setForm({ ...form, api_key: e.target.value })}
                        placeholder={form.provider === 'whatsapp' ? 'System User Token from Meta Business Suite' : 'Your API key'}
                      />
                    </div>
                    {form.provider !== 'whatsapp' && (
                      <div className="flex flex-col gap-2">
                        <Label>Domain</Label>
                        <Input
                          value={form.domain}
                          onChange={(e) => setForm({ ...form, domain: e.target.value })}
                          placeholder={form.provider === 'freshdesk' ? 'yourcompany.freshdesk.com' : 'yourcompany.zendesk.com'}
                        />
                      </div>
                    )}
                  </>
                )}
              </div>
              <DialogFooter>
                <Button
                  onClick={() => connectMut.mutate()}
                  disabled={connectMut.isPending || !form.user_id || !form.provider || (isApiKeyProvider && !form.api_key)}
                >
                  {connectMut.isPending ? 'Connecting...' : isApiKeyProvider ? 'Connect' : 'Start OAuth Flow'}
                </Button>
              </DialogFooter>
              {connectMut.isError && (
                <p className="text-sm text-destructive mt-2">
                  {(connectMut.error as Error).message}
                </p>
              )}
            </DialogContent>
          </Dialog>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-3 gap-4">
          <Card className="border-0 bg-muted/40">
            <CardContent className="pt-5 pb-4 px-5">
              <div className="flex items-center gap-3">
                <div className="rounded-lg bg-background p-2 shadow-sm">
                  <Users className="size-4 text-muted-foreground" />
                </div>
                <div>
                  <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Users</p>
                  <p className="text-2xl font-bold">{totalUsers}</p>
                </div>
              </div>
            </CardContent>
          </Card>
          <Card className="border-0 bg-muted/40">
            <CardContent className="pt-5 pb-4 px-5">
              <div className="flex items-center gap-3">
                <div className="rounded-lg bg-emerald-50 p-2 shadow-sm">
                  <Link2 className="size-4 text-emerald-600" />
                </div>
                <div>
                  <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Active</p>
                  <p className="text-2xl font-bold text-emerald-600">{activeConnections}</p>
                </div>
              </div>
            </CardContent>
          </Card>
          <Card className="border-0 bg-muted/40">
            <CardContent className="pt-5 pb-4 px-5">
              <div className="flex items-center gap-3">
                <div className="rounded-lg bg-amber-50 p-2 shadow-sm">
                  <Clock className="size-4 text-amber-600" />
                </div>
                <div>
                  <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Pending</p>
                  <p className="text-2xl font-bold text-amber-600">{pendingConnections}</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Search */}
        <div className="relative max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-muted-foreground" />
          <Input
            placeholder="Search by user ID..."
            className="pl-9"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>

        {/* Users list */}
        {connectionsLoading ? (
          <div className="flex flex-col gap-3">
            {[1, 2, 3].map((i) => (
              <Skeleton key={i} className="h-20 w-full rounded-xl" />
            ))}
          </div>
        ) : filtered.length === 0 ? (
          <Card className="border-dashed">
            <CardContent className="flex flex-col items-center gap-3 py-16">
              <div className="rounded-full bg-muted p-3">
                <Plug className="size-6 text-muted-foreground" />
              </div>
              <p className="text-sm font-medium text-muted-foreground">
                {search ? 'No users match your search.' : 'No connected users yet.'}
              </p>
              {!search && (
                <p className="text-xs text-muted-foreground">
                  Click "Connect User" or use <code className="bg-muted px-1.5 py-0.5 rounded text-[11px] font-mono">POST /v1/connections</code>
                </p>
              )}
            </CardContent>
          </Card>
        ) : (
          <div className="flex flex-col gap-3">
            {filtered.map((entity) => {
              const activeCount = entity.connections.filter(c => c.status === 'active').length
              const pendingCount = entity.connections.length - activeCount
              const latestConnection = entity.connections
                .filter(c => c.connected_at)
                .sort((a, b) => b.connected_at.localeCompare(a.connected_at))[0]

              return (
                <Card key={entity.user_id} className="transition-colors hover:border-foreground/20">
                  <CardContent className="p-5">
                    <div className="flex items-center gap-5">
                      {/* User ID */}
                      <div className="min-w-0 flex-1">
                        <p className="font-mono text-sm font-medium truncate">{entity.user_id}</p>
                        <p className="text-xs text-muted-foreground mt-0.5">
                          {latestConnection?.connected_at
                            ? `Connected ${new Date(latestConnection.connected_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}`
                            : 'Pending'}
                        </p>
                      </div>

                      {/* Connected apps — icons */}
                      <div className="flex items-center gap-1.5">
                        {entity.connections.map((c) => {
                          const icon = providerIcons[c.provider]
                          return (
                            <Tooltip key={c.provider}>
                              <TooltipTrigger asChild>
                                <div className={cn(
                                  "relative size-8 rounded-lg border bg-white flex items-center justify-center transition-colors",
                                  c.status === 'active' ? 'border-emerald-200' : 'border-amber-200',
                                )}>
                                  {icon ? (
                                    <img src={icon} alt={c.provider} className="size-5 object-contain" />
                                  ) : (
                                    <span className="text-[10px] font-medium text-muted-foreground uppercase">
                                      {c.provider.slice(0, 2)}
                                    </span>
                                  )}
                                  {/* Status dot */}
                                  <span className={cn(
                                    "absolute -bottom-0.5 -right-0.5 size-2.5 rounded-full border-2 border-white",
                                    c.status === 'active' ? 'bg-emerald-500' : 'bg-amber-400',
                                  )} />
                                </div>
                              </TooltipTrigger>
                              <TooltipContent side="bottom" className="text-xs">
                                <span className="capitalize">{c.provider}</span>
                                <span className="text-muted-foreground"> · {c.status}</span>
                              </TooltipContent>
                            </Tooltip>
                          )
                        })}
                      </div>

                      {/* Status summary */}
                      <div className="flex items-center gap-2">
                        {activeCount > 0 && (
                          <Badge variant="outline" className="bg-emerald-50 text-emerald-700 border-emerald-200 gap-1 text-xs font-medium">
                            <CheckCircle2 className="size-3" />
                            {activeCount}
                          </Badge>
                        )}
                        {pendingCount > 0 && (
                          <Badge variant="outline" className="bg-amber-50 text-amber-700 border-amber-200 gap-1 text-xs font-medium">
                            <AlertCircle className="size-3" />
                            {pendingCount}
                          </Badge>
                        )}
                      </div>

                      {/* Triggers */}
                      {entity.trigger_count > 0 && (
                        <Badge variant="outline" className="gap-1 text-xs font-medium">
                          <Zap className="size-3" />
                          {entity.trigger_count}
                        </Badge>
                      )}

                      {/* Actions menu */}
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button variant="ghost" size="icon" className="size-8 text-muted-foreground">
                            <MoreHorizontal className="size-4" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end" className="w-48">
                          {entity.connections.map((c) => (
                            <DropdownMenuItem
                              key={c.provider}
                              className="text-destructive focus:text-destructive gap-2 text-xs"
                              onClick={() => disconnectMut.mutate({ provider: c.provider, userId: entity.user_id })}
                              disabled={disconnectMut.isPending}
                            >
                              <Trash2 className="size-3.5" />
                              Disconnect {c.provider}
                            </DropdownMenuItem>
                          ))}
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </div>
                  </CardContent>
                </Card>
              )
            })}
          </div>
        )}
      </div>
    </TooltipProvider>
  )
}
