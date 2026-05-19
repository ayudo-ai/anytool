import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
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
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { request } from '@/lib/api'
import { Users, Search, Plug, Zap, Activity } from 'lucide-react'

interface Entity {
  user_id: string
  connection_count: number
  trigger_count: number
  providers: string[]
  status: string
  first_seen: string
  connections: { provider: string; status: string; connected_at: string }[]
}

interface EntityDetail {
  user_id: string
  connections: { provider: string; status: string; connected_at: string; scopes: string[] }[]
  triggers: { trigger_id: string; trigger_type: string; enabled: boolean; error_count: number }[]
  recent_activity: { action: string; provider: string; successful: boolean; created_at: string }[]
  connection_count: number
  trigger_count: number
  providers: string[]
}

function listEntities(search?: string) {
  const params = search ? `?search=${encodeURIComponent(search)}` : ''
  return request<{ entities: Entity[]; total: number }>(`/entities${params}`)
}

function getEntity(userId: string) {
  return request<EntityDetail>(`/entities/${encodeURIComponent(userId)}`)
}

const PROVIDER_COLORS: Record<string, string> = {
  google: 'bg-red-50 text-red-700 dark:bg-red-950 dark:text-red-300',
  slack: 'bg-purple-50 text-purple-700 dark:bg-purple-950 dark:text-purple-300',
  hubspot: 'bg-orange-50 text-orange-700 dark:bg-orange-950 dark:text-orange-300',
  github: 'bg-neutral-50 text-neutral-700 dark:bg-neutral-900 dark:text-neutral-300',
  freshdesk: 'bg-green-50 text-green-700 dark:bg-green-950 dark:text-green-300',
  docusign: 'bg-blue-50 text-blue-700 dark:bg-blue-950 dark:text-blue-300',
  zendesk: 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300',
  whatsapp: 'bg-green-50 text-green-700 dark:bg-green-950 dark:text-green-300',
}

export function EntitiesPage() {
  const [search, setSearch] = useState('')
  const [selectedUser, setSelectedUser] = useState<string | null>(null)

  const { data, isLoading } = useQuery({
    queryKey: ['entities', search],
    queryFn: () => listEntities(search || undefined),
  })

  const { data: detail, isLoading: detailLoading } = useQuery({
    queryKey: ['entity-detail', selectedUser],
    queryFn: () => getEntity(selectedUser!),
    enabled: !!selectedUser,
  })

  const entities = data?.entities || []

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Entities</h1>
          <p className="text-sm text-muted-foreground mt-1">
            End-users who have connected their apps through your integration.
          </p>
        </div>
      </div>

      {/* Search */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-muted-foreground" />
        <Input
          placeholder="Search by user ID..."
          className="pl-9 max-w-sm"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      {/* Table */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Connected Users</CardTitle>
          <CardDescription>
            {data ? `${data.total} entities` : 'Loading...'}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="flex flex-col gap-2">
              {[1, 2, 3].map((i) => <Skeleton key={i} className="h-12 w-full" />)}
            </div>
          ) : entities.length === 0 ? (
            <div className="flex flex-col items-center gap-3 py-8">
              <Users className="size-8 text-muted-foreground" />
              <p className="text-sm text-muted-foreground">No entities yet.</p>
              <p className="text-xs text-muted-foreground">
                Users appear here after connecting their first app.
              </p>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>User ID</TableHead>
                  <TableHead>Providers</TableHead>
                  <TableHead>Connections</TableHead>
                  <TableHead>Triggers</TableHead>
                  <TableHead>First Seen</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {entities.map((e) => (
                  <TableRow
                    key={e.user_id}
                    className="cursor-pointer hover:bg-muted/50"
                    onClick={() => setSelectedUser(e.user_id)}
                  >
                    <TableCell className="font-mono text-sm">{e.user_id}</TableCell>
                    <TableCell>
                      <div className="flex gap-1 flex-wrap">
                        {e.providers.map((p) => (
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
                      <span className="flex items-center gap-1 text-sm">
                        <Plug className="size-3" /> {e.connection_count}
                      </span>
                    </TableCell>
                    <TableCell>
                      <span className="flex items-center gap-1 text-sm">
                        <Zap className="size-3" /> {e.trigger_count}
                      </span>
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {e.first_seen ? new Date(e.first_seen).toLocaleDateString() : '—'}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Detail Dialog */}
      <Dialog open={!!selectedUser} onOpenChange={(open) => !open && setSelectedUser(null)}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle className="font-mono text-sm">{selectedUser}</DialogTitle>
          </DialogHeader>
          {detailLoading ? (
            <Skeleton className="h-40" />
          ) : detail ? (
            <div className="flex flex-col gap-4">
              {/* Connections */}
              <div>
                <h3 className="text-sm font-medium mb-2 flex items-center gap-1">
                  <Plug className="size-3.5" /> Connections ({detail.connection_count})
                </h3>
                <div className="flex flex-col gap-1">
                  {detail.connections.map((c, i) => (
                    <div key={i} className="flex items-center justify-between rounded-md border px-3 py-2">
                      <span className="capitalize text-sm">{c.provider}</span>
                      <Badge variant={c.status === 'active' ? 'default' : 'secondary'} className="text-[10px]">
                        {c.status}
                      </Badge>
                    </div>
                  ))}
                </div>
              </div>

              {/* Triggers */}
              {detail.triggers.length > 0 && (
                <div>
                  <h3 className="text-sm font-medium mb-2 flex items-center gap-1">
                    <Zap className="size-3.5" /> Triggers ({detail.trigger_count})
                  </h3>
                  <div className="flex flex-col gap-1">
                    {detail.triggers.map((t) => (
                      <div key={t.trigger_id} className="flex items-center justify-between rounded-md border px-3 py-2">
                        <span className="text-xs font-mono">{t.trigger_type}</span>
                        <div className="flex gap-1">
                          {t.error_count > 0 && (
                            <Badge variant="destructive" className="text-[10px]">
                              {t.error_count} errors
                            </Badge>
                          )}
                          <Badge variant={t.enabled ? 'default' : 'secondary'} className="text-[10px]">
                            {t.enabled ? 'Active' : 'Disabled'}
                          </Badge>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Recent Activity */}
              {detail.recent_activity.length > 0 && (
                <div>
                  <h3 className="text-sm font-medium mb-2 flex items-center gap-1">
                    <Activity className="size-3.5" /> Recent Activity
                  </h3>
                  <div className="flex flex-col gap-1 max-h-40 overflow-y-auto">
                    {detail.recent_activity.map((a, i) => (
                      <div key={i} className="flex items-center justify-between rounded-md border px-3 py-1.5">
                        <span className="text-xs font-mono">{a.action}</span>
                        <Badge
                          variant={a.successful ? 'default' : 'destructive'}
                          className="text-[10px]"
                        >
                          {a.successful ? '✓' : '✗'}
                        </Badge>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : null}
        </DialogContent>
      </Dialog>
    </div>
  )
}
