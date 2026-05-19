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
import { getDashboardOverview, getDashboardUsage } from '@/lib/api'
import { Plug, Zap, Activity, AlertTriangle } from 'lucide-react'
import { UsageChart } from '@/components/UsageChart'

function MetricCard({
  title,
  value,
  max,
  icon: Icon,
}: {
  title: string
  value: number
  max: number
  icon: React.ElementType
}) {
  const pct = max > 0 ? Math.round((value / max) * 100) : 0
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardDescription className="text-sm font-medium">{title}</CardDescription>
        <Icon className="size-4 text-muted-foreground" />
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-bold">{value.toLocaleString()}</div>
        <div className="flex items-center gap-2 mt-1">
          {max > 0 ? (
            <>
              <div className="h-1.5 flex-1 rounded-full bg-muted">
                <div
                  className={cn(
                    'h-1.5 rounded-full transition-all',
                    pct > 80 ? 'bg-destructive' : 'bg-primary',
                  )}
                  style={{ width: `${Math.min(pct, 100)}%` }}
                />
              </div>
              <span className="text-xs text-muted-foreground">
                {max === -1 ? '∞' : max.toLocaleString()}
              </span>
            </>
          ) : (
            <span className="text-xs text-muted-foreground">unlimited</span>
          )}
        </div>
      </CardContent>
    </Card>
  )
}

import { cn } from '@/lib/utils'

export function OverviewPage() {
  const { data: overview, isLoading } = useQuery({
    queryKey: ['dashboard-overview'],
    queryFn: getDashboardOverview,
  })

  const { data: usage } = useQuery({
    queryKey: ['dashboard-usage'],
    queryFn: () => getDashboardUsage(14),
  })

  if (isLoading) {
    return (
      <div className="flex flex-col gap-6">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Your anytool platform at a glance.
          </p>
        </div>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {[1, 2, 3, 4].map((i) => (
            <Skeleton key={i} className="h-[120px] rounded-lg" />
          ))}
        </div>
      </div>
    )
  }

  const o = overview!

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Your anytool platform at a glance.
          </p>
        </div>
        <Badge variant="secondary" className="uppercase text-xs">
          {o.plan} plan
        </Badge>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard
          title="API Calls"
          value={o.calls_this_month}
          max={o.max_calls}
          icon={Activity}
        />
        <MetricCard
          title="Connections"
          value={o.active_connections}
          max={o.max_connections}
          icon={Plug}
        />
        <MetricCard
          title="Active Triggers"
          value={o.active_triggers}
          max={o.max_triggers}
          icon={Zap}
        />
        <MetricCard
          title="Trigger Errors"
          value={o.triggers_with_errors}
          max={-1}
          icon={AlertTriangle}
        />
      </div>

      {/* Usage chart */}
      {usage && usage.days.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">API Usage (last 14 days)</CardTitle>
          </CardHeader>
          <CardContent>
            <UsageChart data={usage.days} />
          </CardContent>
        </Card>
      )}
    </div>
  )
}
