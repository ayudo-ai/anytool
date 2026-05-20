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
import { Alert, AlertDescription } from '@/components/ui/alert'
import {
  listAuthConfigs,
  createAuthConfig,
  deleteAuthConfig,
  updateAuthConfig,
  listProviders,
  type AuthConfig,
} from '@/lib/api'
import { Plus, Trash2, KeyRound } from 'lucide-react'
import { cn } from '@/lib/utils'

const PROVIDER_COLORS: Record<string, string> = {
  google: 'bg-red-50 text-red-700 dark:bg-red-950 dark:text-red-300 border-red-200 dark:border-red-800',
  slack: 'bg-purple-50 text-purple-700 dark:bg-purple-950 dark:text-purple-300 border-purple-200 dark:border-purple-800',
  hubspot: 'bg-orange-50 text-orange-700 dark:bg-orange-950 dark:text-orange-300 border-orange-200 dark:border-orange-800',
  github: 'bg-neutral-50 text-neutral-700 dark:bg-neutral-900 dark:text-neutral-300 border-neutral-200 dark:border-neutral-700',
  freshdesk: 'bg-green-50 text-green-700 dark:bg-green-950 dark:text-green-300 border-green-200 dark:border-green-800',
  docusign: 'bg-blue-50 text-blue-700 dark:bg-blue-950 dark:text-blue-300 border-blue-200 dark:border-blue-800',
  zendesk: 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300 border-emerald-200 dark:border-emerald-800',
  whatsapp: 'bg-green-50 text-green-700 dark:bg-green-950 dark:text-green-300 border-green-200 dark:border-green-800',
}

const SCHEME_LABELS: Record<string, string> = {
  oauth2: 'OAuth2',
  api_key: 'API Key',
  bearer: 'Bearer',
}

export function AuthConfigsPage() {
  const queryClient = useQueryClient()
  const [open, setOpen] = useState(false)
  const [selectedProvider, setSelectedProvider] = useState('')
  const [form, setForm] = useState({
    name: '',
    client_id: '',
    client_secret: '',
    api_key: '',
    domain: '',
  })

  const { data, isLoading } = useQuery({
    queryKey: ['auth-configs'],
    queryFn: listAuthConfigs,
  })

  const { data: providersData } = useQuery({
    queryKey: ['providers'],
    queryFn: listProviders,
  })

  const createMut = useMutation({
    mutationFn: () => {
      const provider = providersData?.providers.find(p => p.slug === selectedProvider)
      return createAuthConfig({
        name: form.name || `${provider?.name || selectedProvider} Config`,
        provider: selectedProvider,
        auth_scheme: provider?.auth_scheme || 'oauth2',
        client_id: form.client_id,
        client_secret: form.client_secret,
        api_key: form.api_key,
        domain: form.domain,
      })
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['auth-configs'] })
      setOpen(false)
      setForm({ name: '', client_id: '', client_secret: '', api_key: '', domain: '' })
      setSelectedProvider('')
    },
  })

  const deleteMut = useMutation({
    mutationFn: deleteAuthConfig,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['auth-configs'] }),
  })

  const toggleMut = useMutation({
    mutationFn: ({ id, enabled }: { id: string; enabled: boolean }) =>
      updateAuthConfig(id, { enabled }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['auth-configs'] }),
  })

  const providers = providersData?.providers || []
  const selectedProviderInfo = providers.find(p => p.slug === selectedProvider)
  const isApiKey = selectedProviderInfo?.auth_scheme === 'api_key'
  const isBearer = selectedProviderInfo?.auth_scheme === 'bearer'

  // Group configs by provider
  const configs = data?.auth_configs || []
  const grouped: Record<string, AuthConfig[]> = {}
  for (const c of configs) {
    const key = c.provider
    if (!grouped[key]) grouped[key] = []
    grouped[key].push(c)
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Auth Configs</h1>
          <p className="text-sm text-muted-foreground mt-1">
            By default, anytool manages all OAuth credentials for you — your users connect with one click.
            Custom auth configs are an <strong>Enterprise feature</strong> for whitelabel OAuth (your own consent screen, your brand).
          </p>
        </div>
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button size="sm">
              <Plus className="mr-2 size-4" />
              Create
            </Button>
          </DialogTrigger>
          <DialogContent className="max-w-lg">
            <DialogHeader>
              <DialogTitle>Create Auth Config</DialogTitle>
              <DialogDescription>
                Add OAuth credentials for a provider. Secrets are encrypted at rest.
              </DialogDescription>
            </DialogHeader>

            <div className="flex flex-col gap-4 py-2">
              {/* Provider selection */}
              <div className="flex flex-col gap-2">
                <Label>Provider</Label>
                <div className="grid grid-cols-4 gap-2">
                  {providers.map((p) => (
                    <button
                      key={p.slug}
                      onClick={() => setSelectedProvider(p.slug)}
                      className={cn(
                        'rounded-md border px-3 py-2 text-xs font-medium transition-colors capitalize',
                        selectedProvider === p.slug
                          ? 'border-primary bg-primary text-primary-foreground'
                          : 'border-border hover:bg-muted',
                      )}
                    >
                      {p.name}
                    </button>
                  ))}
                </div>
              </div>

              {selectedProvider && (
                <>
                  <div className="flex flex-col gap-2">
                    <Label>Config Name</Label>
                    <Input
                      placeholder={`${selectedProviderInfo?.name || ''} Production`}
                      value={form.name}
                      onChange={(e) => setForm({ ...form, name: e.target.value })}
                    />
                  </div>

                  {!isApiKey && !isBearer && (
                    <>
                      <div className="flex flex-col gap-2">
                        <Label>Client ID</Label>
                        <Input
                          placeholder="xxx.apps.googleusercontent.com"
                          value={form.client_id}
                          onChange={(e) => setForm({ ...form, client_id: e.target.value })}
                        />
                      </div>
                      <div className="flex flex-col gap-2">
                        <Label>Client Secret</Label>
                        <Input
                          type="password"
                          placeholder="GOCSPX-xxx"
                          value={form.client_secret}
                          onChange={(e) => setForm({ ...form, client_secret: e.target.value })}
                        />
                      </div>
                    </>
                  )}

                  {isApiKey && (
                    <>
                      <div className="flex flex-col gap-2">
                        <Label>API Key</Label>
                        <Input
                          type="password"
                          placeholder="Your API key"
                          value={form.api_key}
                          onChange={(e) => setForm({ ...form, api_key: e.target.value })}
                        />
                      </div>
                      <div className="flex flex-col gap-2">
                        <Label>Domain</Label>
                        <Input
                          placeholder="yourcompany.freshdesk.com"
                          value={form.domain}
                          onChange={(e) => setForm({ ...form, domain: e.target.value })}
                        />
                      </div>
                    </>
                  )}

                  {isBearer && (
                    <div className="flex flex-col gap-2">
                      <Label>Bearer Token</Label>
                      <Input
                        type="password"
                        placeholder="System User Token from Meta Business Suite"
                        value={form.api_key}
                        onChange={(e) => setForm({ ...form, api_key: e.target.value })}
                      />
                    </div>
                  )}

                  <Alert>
                    <AlertDescription className="text-xs">
                      Scopes: {selectedProviderInfo?.default_scopes.join(', ') || 'none'}
                    </AlertDescription>
                  </Alert>
                </>
              )}
            </div>

            <DialogFooter>
              <Button
                onClick={() => createMut.mutate()}
                disabled={createMut.isPending || !selectedProvider}
              >
                {createMut.isPending ? 'Creating...' : 'Create Config'}
              </Button>
            </DialogFooter>
            {createMut.isError && (
              <p className="text-sm text-destructive">{(createMut.error as Error).message}</p>
            )}
          </DialogContent>
        </Dialog>
      </div>

      {/* Configs table */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Configurations</CardTitle>
          <CardDescription>
            {data ? `${data.total} auth configs` : 'Loading...'}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="flex flex-col gap-2">
              {[1, 2, 3].map((i) => <Skeleton key={i} className="h-12 w-full" />)}
            </div>
          ) : configs.length === 0 ? (
            <div className="flex flex-col items-center gap-3 py-8">
              <KeyRound className="size-8 text-muted-foreground" />
              <p className="text-sm text-muted-foreground">No auth configs yet.</p>
              <p className="text-xs text-muted-foreground">
                Create one to let end-users connect their apps.
              </p>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Provider</TableHead>
                  <TableHead>Management</TableHead>
                  <TableHead>Connections</TableHead>
                  <TableHead>Auth Scheme</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="w-20" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {configs.map((c) => (
                  <TableRow key={c.id}>
                    <TableCell className="font-medium text-sm">{c.name}</TableCell>
                    <TableCell>
                      <Badge variant="outline" className={cn('text-xs capitalize', PROVIDER_COLORS[c.provider] || '')}>
                        {c.provider}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <Badge variant="secondary" className="text-xs">
                        {c.management === 'managed' ? '⚙ Managed' : '🔑 Custom'}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-sm">{c.connections_count}</TableCell>
                    <TableCell>
                      <Badge variant="outline" className="text-xs">
                        {SCHEME_LABELS[c.auth_scheme] || c.auth_scheme}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <button
                        onClick={() => toggleMut.mutate({ id: c.id, enabled: !c.enabled })}
                        className="text-muted-foreground hover:text-foreground"
                      >
                        {c.enabled ? (
                          <Badge variant="default" className="text-[10px] cursor-pointer">Enabled</Badge>
                        ) : (
                          <Badge variant="secondary" className="text-[10px] cursor-pointer">Disabled</Badge>
                        )}
                      </button>
                    </TableCell>
                    <TableCell>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => deleteMut.mutate(c.id)}
                        disabled={deleteMut.isPending}
                      >
                        <Trash2 className="size-4 text-muted-foreground" />
                      </Button>
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
