import { useQuery } from '@tanstack/react-query'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { getDashboardConnections } from '@/lib/api'

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

export function ConnectionsPage() {
  const { data, isLoading } = useQuery({
    queryKey: ['dashboard-connections'],
    queryFn: () => getDashboardConnections(),
  })

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Connections</h1>
        <p className="text-sm text-muted-foreground mt-1">
          OAuth connections across all your end-users.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">All Connections</CardTitle>
          <CardDescription>
            {data ? `${data.total} total` : 'Loading...'}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="flex flex-col gap-2">
              {[1, 2, 3].map((i) => (
                <Skeleton key={i} className="h-10 w-full" />
              ))}
            </div>
          ) : !data || data.connections.length === 0 ? (
            <p className="text-sm text-muted-foreground py-8 text-center">
              No connections yet. Use <code className="text-xs bg-muted px-1.5 py-0.5 rounded">POST /v1/connections</code> to connect your first user.
            </p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>User ID</TableHead>
                  <TableHead>Provider</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Connected At</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.connections.map((c, i) => (
                  <TableRow key={i}>
                    <TableCell className="font-mono text-sm">{c.user_id}</TableCell>
                    <TableCell>
                      <Badge
                        variant="outline"
                        className={PROVIDER_COLORS[c.provider] || ''}
                      >
                        {c.provider}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <Badge variant={c.status === 'active' ? 'default' : 'destructive'}>
                        {c.status}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {c.connected_at ? new Date(c.connected_at).toLocaleDateString() : '—'}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
