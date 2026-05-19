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
import { listTriggers, deployTrigger, removeTrigger } from '@/lib/api'
import { Plus, Trash2, Zap } from 'lucide-react'

export function TriggersPage() {
  const queryClient = useQueryClient()
  const [open, setOpen] = useState(false)
  const [form, setForm] = useState({
    trigger_type: 'gmail_new_message',
    user_id: '',
    webhook_url: '',
    poll_interval_seconds: 90,
  })

  const { data, isLoading } = useQuery({
    queryKey: ['triggers'],
    queryFn: () => listTriggers(),
  })

  const deployMut = useMutation({
    mutationFn: deployTrigger,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['triggers'] })
      setOpen(false)
      setForm({ trigger_type: 'gmail_new_message', user_id: '', webhook_url: '', poll_interval_seconds: 90 })
    },
  })

  const removeMut = useMutation({
    mutationFn: removeTrigger,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['triggers'] }),
  })

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Triggers</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Event-driven polling triggers that POST to your webhooks.
          </p>
        </div>
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button size="sm">
              <Plus className="mr-2 size-4" />
              Deploy Trigger
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Deploy a Trigger</DialogTitle>
              <DialogDescription>
                Poll a user's connected app and POST events to your webhook.
              </DialogDescription>
            </DialogHeader>
            <div className="flex flex-col gap-4 py-2">
              <div className="flex flex-col gap-2">
                <Label>Trigger Type</Label>
                <Input
                  value={form.trigger_type}
                  onChange={(e) => setForm({ ...form, trigger_type: e.target.value })}
                  placeholder="gmail_new_message"
                />
              </div>
              <div className="flex flex-col gap-2">
                <Label>User ID</Label>
                <Input
                  value={form.user_id}
                  onChange={(e) => setForm({ ...form, user_id: e.target.value })}
                  placeholder="customer-123"
                />
              </div>
              <div className="flex flex-col gap-2">
                <Label>Webhook URL</Label>
                <Input
                  value={form.webhook_url}
                  onChange={(e) => setForm({ ...form, webhook_url: e.target.value })}
                  placeholder="https://myapp.com/webhooks/inbox"
                />
              </div>
              <div className="flex flex-col gap-2">
                <Label>Poll Interval (seconds)</Label>
                <Input
                  type="number"
                  value={form.poll_interval_seconds}
                  onChange={(e) => setForm({ ...form, poll_interval_seconds: Number(e.target.value) })}
                />
              </div>
            </div>
            <DialogFooter>
              <Button
                onClick={() => deployMut.mutate(form)}
                disabled={deployMut.isPending || !form.user_id || !form.webhook_url}
              >
                {deployMut.isPending ? 'Deploying...' : 'Deploy'}
              </Button>
            </DialogFooter>
            {deployMut.isError && (
              <p className="text-sm text-destructive mt-2">
                {(deployMut.error as Error).message}
              </p>
            )}
          </DialogContent>
        </Dialog>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Active Triggers</CardTitle>
          <CardDescription>
            {data ? `${data.total} triggers` : 'Loading...'}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="flex flex-col gap-2">
              {[1, 2, 3].map((i) => <Skeleton key={i} className="h-10 w-full" />)}
            </div>
          ) : !data || data.triggers.length === 0 ? (
            <div className="flex flex-col items-center gap-3 py-8">
              <Zap className="size-8 text-muted-foreground" />
              <p className="text-sm text-muted-foreground">No triggers deployed yet.</p>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Type</TableHead>
                  <TableHead>User ID</TableHead>
                  <TableHead>Webhook</TableHead>
                  <TableHead>Interval</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="w-10" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.triggers.map((t) => (
                  <TableRow key={t.trigger_id}>
                    <TableCell className="font-mono text-xs">{t.trigger_type}</TableCell>
                    <TableCell className="font-mono text-xs">{t.user_id}</TableCell>
                    <TableCell className="text-xs max-w-[200px] truncate">
                      {t.webhook_url}
                    </TableCell>
                    <TableCell className="text-xs">{t.poll_interval_seconds}s</TableCell>
                    <TableCell>
                      <Badge variant={t.enabled ? 'default' : 'secondary'}>
                        {t.enabled ? 'active' : 'disabled'}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => removeMut.mutate(t.trigger_id)}
                        disabled={removeMut.isPending}
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
