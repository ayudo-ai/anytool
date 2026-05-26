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
import { getDashboardOverview, getDashboardUsage, getMe } from '@/lib/api'
import { Plug, Zap, Activity, AlertTriangle, ArrowRight, BookOpen, Wrench, Key, Copy, Check } from 'lucide-react'
import { UsageChart } from '@/components/UsageChart'
import { useState } from 'react'
import { Button } from '@/components/ui/button'

function MetricCard({
  title,
  value,
  icon: Icon,
}: {
  title: string
  value: number
  icon: React.ElementType
}) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardDescription className="text-sm font-medium">{title}</CardDescription>
        <Icon className="size-4 text-muted-foreground" />
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-bold">{value.toLocaleString()}</div>
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

  const { data: me } = useQuery({
    queryKey: ['me'],
    queryFn: getMe,
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
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Your anytool platform at a glance.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard title="API Calls" value={o.calls_this_month} icon={Activity} />
        <MetricCard title="Connections" value={o.active_connections} icon={Plug} />
        <MetricCard title="Active Triggers" value={o.active_triggers} icon={Zap} />
        <MetricCard title="Trigger Errors" value={o.triggers_with_errors} icon={AlertTriangle} />
      </div>

      {/* Quick Actions for new users */}
      {o.calls_this_month === 0 && o.active_connections === 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">🚀 Get Started</CardTitle>
            <CardDescription>
              Set up your first integration in 5 minutes.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex flex-col gap-2">
              {[
                { label: 'Read the Quickstart', href: '/dashboard/quickstart', icon: BookOpen, desc: 'Code snippets with your API key' },
                { label: 'Get your API Key', href: '/dashboard/keys', icon: Key, desc: 'Create or copy your API key' },
                { label: 'Connect a User', href: '/dashboard/connections', icon: Plug, desc: 'Connect your first end-user\'s app' },
                { label: 'Browse & Test Actions', href: '/dashboard/actions', icon: Wrench, desc: 'Try any of the 98+ available actions' },
              ].map((item) => (
                <a
                  key={item.href}
                  href={item.href}
                  className="flex items-center gap-3 rounded-md border px-4 py-3 transition-colors hover:bg-muted/50"
                >
                  <item.icon className="size-4 text-muted-foreground" />
                  <div className="flex-1">
                    <p className="text-sm font-medium">{item.label}</p>
                    <p className="text-xs text-muted-foreground">{item.desc}</p>
                  </div>
                  <ArrowRight className="size-4 text-muted-foreground" />
                </a>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Webhook Test URL */}
      {me?.workspace_id && <WebhookTestUrlCard workspaceId={me.workspace_id} />}

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

function WebhookTestUrlCard({ workspaceId }: { workspaceId: string }) {
  const [copied, setCopied] = useState(false)
  const webhookUrl = `${window.location.origin}/v1/webhook-test/${workspaceId}`

  const handleCopy = () => {
    navigator.clipboard.writeText(webhookUrl)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">🧪 Test Webhook URL</CardTitle>
        <CardDescription>
          Use this URL as your webhook_url when testing triggers. Received events appear in Webhook Logs.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="flex items-center gap-2">
          <code className="flex-1 text-xs font-mono bg-muted rounded-md px-3 py-2 break-all">
            {webhookUrl}
          </code>
          <Button variant="outline" size="sm" onClick={handleCopy}>
            {copied ? <Check className="size-3" /> : <Copy className="size-3" />}
          </Button>
        </div>
        <p className="text-xs text-muted-foreground mt-2">
          This URL stores received webhooks so you can inspect payloads. Use it in the "Deploy Trigger" dialog.
        </p>
      </CardContent>
    </Card>
  )
}

