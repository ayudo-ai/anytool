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
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import { getDashboardLogs } from '@/lib/api'
import { ChevronLeft, ChevronRight, Search, AlertCircle } from 'lucide-react'

export function LogsPage() {
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
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Execution Logs</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Every API call made through your platform.
        </p>
      </div>

      <div className="flex items-center gap-3">
        <div className="relative max-w-sm flex-1">
          <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Filter by action name..."
            value={actionFilter}
            onChange={(e) => {
              setActionFilter(e.target.value)
              setOffset(0)
            }}
            className="pl-9"
          />
        </div>
        {data && (
          <span className="text-sm text-muted-foreground ml-auto">
            {data.total} total logs
          </span>
        )}
      </div>

      <Card>
        <CardContent className="p-0">
          {isLoading ? (
            <div className="flex flex-col gap-2 p-4">
              {[1, 2, 3, 4, 5].map((i) => (
                <Skeleton key={i} className="h-10 w-full" />
              ))}
            </div>
          ) : !data || data.logs.length === 0 ? (
            <p className="py-8 text-center text-sm text-muted-foreground">
              No logs yet. Execute an action to see results here.
            </p>
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
                      {log.successful ? (
                        <Badge variant="default" className="text-[10px]">
                          {log.status_code}
                        </Badge>
                      ) : (
                        <Badge variant="destructive" className="text-[10px]">
                          {log.status_code || 'ERR'}
                        </Badge>
                      )}
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {log.duration_ms}ms
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {log.created_at
                        ? new Date(log.created_at).toLocaleString(undefined, {
                            month: 'short',
                            day: 'numeric',
                            hour: '2-digit',
                            minute: '2-digit',
                          })
                        : '—'}
                    </TableCell>
                    <TableCell>
                      {log.error && (
                        <TooltipProvider>
                          <Tooltip>
                            <TooltipTrigger>
                              <AlertCircle className="size-4 text-destructive" />
                            </TooltipTrigger>
                            <TooltipContent className="max-w-xs">
                              <p className="text-xs">{log.error}</p>
                            </TooltipContent>
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

      {/* Pagination */}
      {data && data.total > limit && (
        <div className="flex items-center justify-between">
          <span className="text-sm text-muted-foreground">
            Showing {offset + 1}–{Math.min(offset + limit, data.total)} of {data.total}
          </span>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={offset === 0}
              onClick={() => setOffset(Math.max(0, offset - limit))}
            >
              <ChevronLeft className="size-4" />
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={offset + limit >= data.total}
              onClick={() => setOffset(offset + limit)}
            >
              <ChevronRight className="size-4" />
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}
