import { useQuery } from '@tanstack/react-query'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'
import { Skeleton } from '@/components/ui/skeleton'
import { getMe, getDashboardOverview } from '@/lib/api'
import { Shield, Copy } from 'lucide-react'
import { useState } from 'react'

export function SettingsPage() {
  const [copied, setCopied] = useState(false)

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

  const copyDebugInfo = () => {
    const info = [
      `@account_id ${me?.account_id || '—'}`,
      `@email ${me?.email || '—'}`,
    ].join('\n')
    navigator.clipboard.writeText(info)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

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

      {/* Usage */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Usage</CardTitle>
          <CardDescription>Current usage this month.</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <div className="flex items-center justify-between">
            <span className="text-sm text-muted-foreground">API Calls</span>
            <span className="text-sm font-medium">
              {overview?.calls_this_month?.toLocaleString() || '0'}
            </span>
          </div>
          <Separator />
          <div className="flex items-center justify-between">
            <span className="text-sm text-muted-foreground">Active Connections</span>
            <span className="text-sm font-medium">{overview?.active_connections || 0}</span>
          </div>
          <Separator />
          <div className="flex items-center justify-between">
            <span className="text-sm text-muted-foreground">Active Triggers</span>
            <span className="text-sm font-medium">{overview?.active_triggers || 0}</span>
          </div>
        </CardContent>
      </Card>

      {/* Debug Info */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <Shield className="size-4" /> Debug Info
          </CardTitle>
          <CardDescription>
            Contains non-secret identifiers. Share with support when requested.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-start justify-between">
            <pre className="text-xs font-mono bg-muted rounded-md p-3 flex-1">
{`@account_id ${me?.account_id || '—'}
@email ${me?.email || '—'}`}
            </pre>
            <Button size="sm" variant="outline" className="ml-3" onClick={copyDebugInfo}>
              <Copy className="size-3 mr-1" />
              {copied ? 'Copied!' : 'Copy'}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
