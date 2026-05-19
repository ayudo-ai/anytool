import { useQuery, useMutation } from '@tanstack/react-query'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'
import { Skeleton } from '@/components/ui/skeleton'
import { getMe, getDashboardOverview, request } from '@/lib/api'
import { CreditCard, ExternalLink, Shield, Copy } from 'lucide-react'
import { useState } from 'react'

function getBillingStatus() {
  return request<{
    plan: string
    has_subscription: boolean
    usage: { calls_this_month: number; max_calls: number }
    limits: Record<string, number>
    upgradeable: boolean
  }>('/billing/status')
}

function createCheckout(plan: string) {
  return request<{ checkout_url: string }>('/billing/checkout', {
    method: 'POST',
    body: JSON.stringify({ plan }),
  })
}

function createPortal() {
  return request<{ portal_url: string }>('/billing/portal', { method: 'POST' })
}

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

  const { data: billing } = useQuery({
    queryKey: ['billing-status'],
    queryFn: getBillingStatus,
  })

  const checkoutMut = useMutation({
    mutationFn: createCheckout,
    onSuccess: (data) => {
      if (data.checkout_url) window.location.href = data.checkout_url
    },
  })

  const portalMut = useMutation({
    mutationFn: createPortal,
    onSuccess: (data) => {
      if (data.portal_url) window.location.href = data.portal_url
    },
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

  const planLimits: Record<string, { calls: string; connections: string; triggers: string; price: string }> = {
    free: { calls: '1,000', connections: '10', triggers: '5', price: 'Free' },
    pro: { calls: '100,000', connections: '100', triggers: '50', price: '$49/mo' },
    enterprise: { calls: 'Unlimited', connections: 'Unlimited', triggers: 'Unlimited', price: '$299/mo' },
  }
  const limits = planLimits[me?.plan || 'free'] || planLimits.free

  const copyDebugInfo = () => {
    const info = [
      `@account_id ${me?.account_id || '—'}`,
      `@email ${me?.email || '—'}`,
      `@plan ${me?.plan || 'free'}`,
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

      {/* Plan & Billing */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <CreditCard className="size-4" /> Plan & Billing
          </CardTitle>
          <CardDescription>Current plan and billing management.</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <div className="flex items-center justify-between">
            <span className="text-sm text-muted-foreground">Current Plan</span>
            <div className="flex items-center gap-2">
              <Badge variant="secondary" className="uppercase text-xs">{me?.plan || 'free'}</Badge>
              <span className="text-sm font-medium">{limits.price}</span>
            </div>
          </div>
          <Separator />

          {/* Usage */}
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

          {/* Upgrade buttons */}
          <div className="flex gap-2 pt-2">
            {(me?.plan === 'free') && (
              <>
                <Button
                  size="sm"
                  onClick={() => checkoutMut.mutate('pro')}
                  disabled={checkoutMut.isPending}
                >
                  Upgrade to Pro — $49/mo
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => checkoutMut.mutate('enterprise')}
                  disabled={checkoutMut.isPending}
                >
                  Enterprise — $299/mo
                </Button>
              </>
            )}
            {me?.plan === 'pro' && (
              <Button
                size="sm"
                onClick={() => checkoutMut.mutate('enterprise')}
                disabled={checkoutMut.isPending}
              >
                Upgrade to Enterprise
              </Button>
            )}
            {billing?.has_subscription && (
              <Button
                size="sm"
                variant="outline"
                onClick={() => portalMut.mutate()}
                disabled={portalMut.isPending}
              >
                <ExternalLink className="mr-1 size-3" />
                Manage Subscription
              </Button>
            )}
          </div>
          {checkoutMut.isError && (
            <p className="text-sm text-destructive">{(checkoutMut.error as Error).message}</p>
          )}
        </CardContent>
      </Card>

      {/* Plan Comparison */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Plans</CardTitle>
          <CardDescription>Compare features across plans.</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-3 gap-4">
            {(['free', 'pro', 'enterprise'] as const).map((plan) => {
              const p = planLimits[plan]
              const isCurrent = me?.plan === plan
              return (
                <div
                  key={plan}
                  className={`rounded-lg border p-4 ${isCurrent ? 'border-primary bg-primary/5' : ''}`}
                >
                  <div className="flex items-center justify-between mb-3">
                    <h3 className="font-semibold capitalize">{plan}</h3>
                    <span className="text-sm font-medium">{p.price}</span>
                  </div>
                  <div className="flex flex-col gap-1.5 text-xs text-muted-foreground">
                    <span>✓ {p.calls} API calls/mo</span>
                    <span>✓ {p.connections} connections</span>
                    <span>✓ {p.triggers} triggers</span>
                    {plan !== 'free' && <span>✓ Priority support</span>}
                    {plan === 'enterprise' && <span>✓ Custom integrations</span>}
                    {plan === 'enterprise' && <span>✓ SLA guarantee</span>}
                  </div>
                  {isCurrent && (
                    <Badge className="mt-3 text-[10px]">Current Plan</Badge>
                  )}
                </div>
              )
            })}
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
@email ${me?.email || '—'}
@plan ${me?.plan || 'free'}`}
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
