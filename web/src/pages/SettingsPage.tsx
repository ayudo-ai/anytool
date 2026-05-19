import { useQuery } from '@tanstack/react-query'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import { Skeleton } from '@/components/ui/skeleton'
import { getMe, getDashboardOverview } from '@/lib/api'

export function SettingsPage() {
  const { data: me, isLoading: meLoading } = useQuery({
    queryKey: ['me'],
    queryFn: getMe,
  })

  const { data: overview, isLoading: overviewLoading } = useQuery({
    queryKey: ['dashboard-overview'],
    queryFn: getDashboardOverview,
  })

  const isLoading = meLoading || overviewLoading

  if (isLoading) {
    return (
      <div className="flex flex-col gap-6">
        <h1 className="text-2xl font-semibold tracking-tight">Settings</h1>
        <Skeleton className="h-[300px] rounded-lg" />
      </div>
    )
  }

  const planLimits: Record<string, { calls: string; connections: string; triggers: string }> = {
    free: { calls: '1,000', connections: '10', triggers: '5' },
    pro: { calls: '100,000', connections: '100', triggers: '50' },
    enterprise: { calls: 'Unlimited', connections: 'Unlimited', triggers: 'Unlimited' },
  }
  const limits = planLimits[me?.plan || 'free'] || planLimits.free

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-semibold tracking-tight">Settings</h1>

      {/* General */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">General</CardTitle>
          <CardDescription>Basic details about your account.</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <div className="flex items-center justify-between">
            <span className="text-sm text-muted-foreground">Name</span>
            <span className="text-sm font-medium">{me?.name || '—'}</span>
          </div>
          <Separator />
          <div className="flex items-center justify-between">
            <span className="text-sm text-muted-foreground">Email</span>
            <span className="text-sm font-medium">{me?.email || '—'}</span>
          </div>
          <Separator />
          <div className="flex items-center justify-between">
            <span className="text-sm text-muted-foreground">Account ID</span>
            <code className="text-xs font-mono bg-muted px-2 py-0.5 rounded">{me?.account_id || '—'}</code>
          </div>
        </CardContent>
      </Card>

      {/* Plan & Usage */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Plan & Usage</CardTitle>
          <CardDescription>Current plan and this month's usage.</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <div className="flex items-center justify-between">
            <span className="text-sm text-muted-foreground">Plan</span>
            <Badge variant="secondary" className="uppercase text-xs">{me?.plan || 'free'}</Badge>
          </div>
          <Separator />
          <div className="flex items-center justify-between">
            <span className="text-sm text-muted-foreground">API Calls this month</span>
            <span className="text-sm font-medium">
              {overview?.calls_this_month?.toLocaleString() || '0'} / {limits.calls}
            </span>
          </div>
          <Separator />
          <div className="flex items-center justify-between">
            <span className="text-sm text-muted-foreground">Active Connections</span>
            <span className="text-sm font-medium">
              {overview?.active_connections || 0} / {limits.connections}
            </span>
          </div>
          <Separator />
          <div className="flex items-center justify-between">
            <span className="text-sm text-muted-foreground">Active Triggers</span>
            <span className="text-sm font-medium">
              {overview?.active_triggers || 0} / {limits.triggers}
            </span>
          </div>
        </CardContent>
      </Card>

      {/* Plan Limits */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Plan Limits</CardTitle>
          <CardDescription>What's included in your current plan.</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-3 gap-4">
            <div className="rounded-md border p-4 text-center">
              <p className="text-2xl font-bold">{limits.calls}</p>
              <p className="text-xs text-muted-foreground mt-1">API calls / month</p>
            </div>
            <div className="rounded-md border p-4 text-center">
              <p className="text-2xl font-bold">{limits.connections}</p>
              <p className="text-xs text-muted-foreground mt-1">Connections</p>
            </div>
            <div className="rounded-md border p-4 text-center">
              <p className="text-2xl font-bold">{limits.triggers}</p>
              <p className="text-xs text-muted-foreground mt-1">Triggers</p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
