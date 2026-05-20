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
import { getDashboardConnections, connectUser, connectApiKey, disconnectUser, listTriggers } from '@/lib/api'
import { Plus, Plug, Zap, Search, Trash2 } from 'lucide-react'

const API_KEY_PROVIDERS = ['freshdesk', 'zendesk', 'whatsapp']

const PROVIDER_COLORS: Record<string, string> = {
  google: 'bg-red-50 text-red-700 border-red-200',
  slack: 'bg-purple-50 text-purple-700 border-purple-200',
  hubspot: 'bg-orange-50 text-orange-700 border-orange-200',
  github: 'bg-neutral-50 text-neutral-700 border-neutral-200',
  freshdesk: 'bg-green-50 text-green-700 border-green-200',
  docusign: 'bg-blue-50 text-blue-700 border-blue-200',
  zendesk: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  whatsapp: 'bg-green-50 text-green-700 border-green-200',
}

const PROVIDERS = [
  'gmail',
  'google_drive',
  'google_calendar',
  'slack',
  'hubspot',
  'github',
  'freshdesk',
  'docusign',
  'zendesk',
  'whatsapp',
]

interface UserEntity {
  user_id: string
  connections: { provider: string; status: string; connected_at: string }[]
  trigger_count: number
  providers: string[]
}

export function ConnectionsPage() {
  const queryClient = useQueryClient()
  const [open, setOpen] = useState(false)
  // Default user_id to the developer's email for easy testing
  const userStr = localStorage.getItem('anytool_user')
  const devEmail = userStr ? (JSON.parse(userStr) as { email: string }).email : ''
  const [form, setForm] = useState({ provider: 'gmail', user_id: devEmail, api_key: '', domain: '' })
  const [search, setSearch] = useState('')

  const isApiKeyProvider = API_KEY_PROVIDERS.includes(form.provider)

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
    mutationFn: () => {
      if (isApiKeyProvider) {
        return connectApiKey(form.provider, form.user_id, form.api_key, form.domain)
      }
      return connectUser(form.provider, form.user_id)
    },
    onSuccess: (result) => {
      if ('auth_url' in result && result.auth_url) {
        window.open(result.auth_url as string, '_blank')
      }
      queryClient.invalidateQueries({ queryKey: ['dashboard-connections'] })
      setOpen(false)
      setForm({ provider: 'gmail', user_id: '', api_key: '', domain: '' })
    },
  })

  const disconnectMut = useMutation({
    mutationFn: ({ provider, userId }: { provider: string; userId: string }) =>
      disconnectUser(provider, userId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['dashboard-connections'] })
    },
  })

  // Group connections by user_id → entity view
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
    // Count triggers per user
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

  // Count stats
  const totalUsers = entities.length
  const activeConnections = connectionsData?.connections.filter(c => c.status === 'active').length || 0
  const pendingConnections = connectionsData?.connections.filter(c => c.status === 'pending').length || 0

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Connected Users</h1>
          <p className="text-sm text-muted-foreground mt-1">
            End-users who have connected their apps through your integration.
          </p>
        </div>
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button size="sm">
              <Plus className="mr-2 size-4" />
              Connect User
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Connect a User</DialogTitle>
              <DialogDescription>
                Start an OAuth flow for an end-user to connect an app. A new tab will open for authorization.
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
                  {PROVIDERS.map((p) => (
                    <option key={p} value={p}>
                      {p.replace(/_/g, ' ')}
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
                  Your end-user's unique ID. For testing, we've pre-filled your email.
                  In production, use your customer's ID (e.g. <code className="bg-muted px-1 rounded">customer-123</code>).
                </p>
              </div>

              {/* API Key fields — shown for Freshdesk, Zendesk, WhatsApp */}
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
                disabled={connectMut.isPending || !form.user_id || (isApiKeyProvider && !form.api_key)}
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
        <Card>
          <CardContent className="pt-4 pb-3 px-4">
            <p className="text-xs text-muted-foreground">Users</p>
            <p className="text-2xl font-bold">{totalUsers}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4 pb-3 px-4">
            <p className="text-xs text-muted-foreground">Active Connections</p>
            <p className="text-2xl font-bold text-emerald-600">{activeConnections}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4 pb-3 px-4">
            <p className="text-xs text-muted-foreground">Pending</p>
            <p className="text-2xl font-bold text-amber-600">{pendingConnections}</p>
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

      {/* Users table */}
      <Card>
        <CardContent className="p-0">
          {connectionsLoading ? (
            <div className="flex flex-col gap-2 p-4">
              {[1, 2, 3].map((i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          ) : filtered.length === 0 ? (
            <div className="flex flex-col items-center gap-3 py-12">
              <Plug className="size-8 text-muted-foreground" />
              <p className="text-sm text-muted-foreground">
                {search ? 'No users match your search.' : 'No connected users yet.'}
              </p>
              {!search && (
                <p className="text-xs text-muted-foreground">
                  Click "Connect User" or use <code className="bg-muted px-1 py-0.5 rounded text-[10px]">POST /v1/connections</code> from your code.
                </p>
              )}
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>User ID</TableHead>
                  <TableHead>Apps Connected</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Triggers</TableHead>
                  <TableHead>Connected</TableHead>
                  <TableHead className="w-10" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {filtered.map((entity) => {
                  const activeCount = entity.connections.filter(c => c.status === 'active').length
                  const latestConnection = entity.connections
                    .filter(c => c.connected_at)
                    .sort((a, b) => b.connected_at.localeCompare(a.connected_at))[0]

                  return (
                    <TableRow key={entity.user_id}>
                      <TableCell className="font-mono text-sm">{entity.user_id}</TableCell>
                      <TableCell>
                        <div className="flex gap-1 flex-wrap">
                          {entity.providers.map((p) => (
                            <Badge
                              key={p}
                              variant="outline"
                              className={`text-[10px] capitalize ${PROVIDER_COLORS[p] || ''}`}
                            >
                              {p}
                            </Badge>
                          ))}
                        </div>
                      </TableCell>
                      <TableCell>
                        {activeCount === entity.connections.length ? (
                          <Badge variant="default" className="text-[10px]">
                            {activeCount} active
                          </Badge>
                        ) : (
                          <div className="flex gap-1">
                            {activeCount > 0 && (
                              <Badge variant="default" className="text-[10px]">
                                {activeCount} active
                              </Badge>
                            )}
                            {entity.connections.length - activeCount > 0 && (
                              <Badge variant="secondary" className="text-[10px]">
                                {entity.connections.length - activeCount} pending
                              </Badge>
                            )}
                          </div>
                        )}
                      </TableCell>
                      <TableCell>
                        {entity.trigger_count > 0 ? (
                          <span className="flex items-center gap-1 text-sm">
                            <Zap className="size-3" /> {entity.trigger_count}
                          </span>
                        ) : (
                          <span className="text-xs text-muted-foreground">—</span>
                        )}
                      </TableCell>
                      <TableCell className="text-xs text-muted-foreground">
                        {latestConnection?.connected_at
                          ? new Date(latestConnection.connected_at).toLocaleDateString()
                          : '—'}
                      </TableCell>
                      <TableCell>
                        <div className="flex gap-1">
                          {entity.connections.map((c) => (
                            <Button
                              key={c.provider}
                              variant="ghost"
                              size="sm"
                              title={`Disconnect ${c.provider}`}
                              onClick={() => disconnectMut.mutate({ provider: c.provider, userId: entity.user_id })}
                              disabled={disconnectMut.isPending}
                            >
                              <Trash2 className="size-3.5 text-muted-foreground" />
                            </Button>
                          ))}
                        </div>
                      </TableCell>
                    </TableRow>
                  )
                })}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
