import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
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
import { listApiKeys, createApiKey, revokeApiKey } from '@/lib/api'
import { Plus, Trash2, Copy, Check, Key } from 'lucide-react'

export function KeysPage() {
  const queryClient = useQueryClient()
  const [open, setOpen] = useState(false)
  const [label, setLabel] = useState('')
  const [newKey, setNewKey] = useState('')
  const [copied, setCopied] = useState(false)

  const { data, isLoading } = useQuery({
    queryKey: ['api-keys'],
    queryFn: listApiKeys,
  })

  const createMut = useMutation({
    mutationFn: () => createApiKey(label),
    onSuccess: (res) => {
      setNewKey(res.api_key)
      queryClient.invalidateQueries({ queryKey: ['api-keys'] })
    },
  })

  const revokeMut = useMutation({
    mutationFn: revokeApiKey,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['api-keys'] }),
  })

  function handleCopy() {
    navigator.clipboard.writeText(newKey)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">API Keys</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Manage your workspace API keys.
          </p>
        </div>
        <Dialog
          open={open}
          onOpenChange={(v) => {
            setOpen(v)
            if (!v) {
              setNewKey('')
              setLabel('')
            }
          }}
        >
          <DialogTrigger asChild>
            <Button size="sm">
              <Plus className="mr-2 size-4" />
              Create Key
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>{newKey ? 'Key Created' : 'Create API Key'}</DialogTitle>
              <DialogDescription>
                {newKey
                  ? 'Store this key securely — it won\'t be shown again.'
                  : 'Create a new API key for this workspace.'}
              </DialogDescription>
            </DialogHeader>

            {newKey ? (
              <div className="flex flex-col gap-3 py-2">
                <div className="flex items-center gap-2 rounded-md border bg-muted p-3">
                  <code className="flex-1 text-sm break-all font-mono">{newKey}</code>
                  <Button variant="ghost" size="sm" onClick={handleCopy}>
                    {copied ? <Check className="size-4" /> : <Copy className="size-4" />}
                  </Button>
                </div>
                <Alert>
                  <AlertDescription className="text-xs">
                    Copy this key now. You won't be able to see it again.
                  </AlertDescription>
                </Alert>
              </div>
            ) : (
              <div className="flex flex-col gap-4 py-2">
                <div className="flex flex-col gap-2">
                  <Label>Label (optional)</Label>
                  <Input
                    value={label}
                    onChange={(e) => setLabel(e.target.value)}
                    placeholder="Production key"
                  />
                </div>
              </div>
            )}

            <DialogFooter>
              {newKey ? (
                <Button onClick={() => setOpen(false)}>Done</Button>
              ) : (
                <Button
                  onClick={() => createMut.mutate()}
                  disabled={createMut.isPending}
                >
                  {createMut.isPending ? 'Creating...' : 'Create'}
                </Button>
              )}
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Active Keys</CardTitle>
          <CardDescription>
            {data ? `${data.total} keys` : 'Loading...'}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="flex flex-col gap-2">
              {[1, 2].map((i) => <Skeleton key={i} className="h-10 w-full" />)}
            </div>
          ) : !data || data.keys.length === 0 ? (
            <div className="flex flex-col items-center gap-3 py-8">
              <Key className="size-8 text-muted-foreground" />
              <p className="text-sm text-muted-foreground">No API keys.</p>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Key</TableHead>
                  <TableHead>Label</TableHead>
                  <TableHead>Created</TableHead>
                  <TableHead className="w-10" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.keys.map((k) => (
                  <TableRow key={k.key_id}>
                    <TableCell className="font-mono text-xs">{k.key_masked}</TableCell>
                    <TableCell className="text-sm">{k.label || '—'}</TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {k.created_at
                        ? new Date(k.created_at).toLocaleDateString()
                        : '—'}
                    </TableCell>
                    <TableCell>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => revokeMut.mutate(k.key_id)}
                        disabled={revokeMut.isPending}
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
