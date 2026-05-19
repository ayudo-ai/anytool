import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Separator } from '@/components/ui/separator'
import { listActions } from '@/lib/api'
import { Search } from 'lucide-react'
import { cn } from '@/lib/utils'

const APPS = [
  'all',
  'google',
  'slack',
  'hubspot',
  'github',
  'freshdesk',
  'docusign',
  'zendesk',
  'whatsapp',
]

const METHOD_COLORS: Record<string, string> = {
  GET: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  POST: 'bg-blue-50 text-blue-700 border-blue-200',
  PUT: 'bg-amber-50 text-amber-700 border-amber-200',
  PATCH: 'bg-orange-50 text-orange-700 border-orange-200',
  DELETE: 'bg-red-50 text-red-700 border-red-200',
}

export function ActionsPage() {
  const [selectedApp, setSelectedApp] = useState('all')
  const [search, setSearch] = useState('')
  const [expandedAction, setExpandedAction] = useState<string | null>(null)

  const { data, isLoading } = useQuery({
    queryKey: ['actions'],
    queryFn: () => listActions(),
  })

  const actions = data?.actions || []
  const filtered = actions.filter((a) => {
    if (selectedApp !== 'all' && a.app !== selectedApp) return false
    if (search && !a.name.toLowerCase().includes(search.toLowerCase()) &&
        !a.description.toLowerCase().includes(search.toLowerCase())) return false
    return true
  })

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Actions</h1>
        <p className="text-sm text-muted-foreground mt-1">
          {data ? `${data.total} actions across ${APPS.length - 1} apps.` : 'Loading...'} Browse and test API actions.
        </p>
      </div>

      {/* Filters */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search actions..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9"
          />
        </div>
        <div className="flex flex-wrap gap-1">
          {APPS.map((app) => (
            <Button
              key={app}
              variant={selectedApp === app ? 'default' : 'outline'}
              size="sm"
              onClick={() => setSelectedApp(app)}
              className="text-xs capitalize"
            >
              {app}
            </Button>
          ))}
        </div>
      </div>

      {/* Actions list */}
      {isLoading ? (
        <div className="flex flex-col gap-2">
          {[1, 2, 3, 4, 5].map((i) => (
            <Skeleton key={i} className="h-16 w-full rounded-lg" />
          ))}
        </div>
      ) : (
        <ScrollArea className="h-[calc(100vh-280px)]">
          <div className="flex flex-col gap-2">
            {filtered.map((action) => (
              <Card
                key={action.name}
                className={cn(
                  'cursor-pointer transition-colors hover:bg-muted/50',
                  expandedAction === action.name && 'ring-1 ring-border',
                )}
                onClick={() =>
                  setExpandedAction(
                    expandedAction === action.name ? null : action.name,
                  )
                }
              >
                <CardHeader className="py-3 px-4">
                  <div className="flex items-center gap-3">
                    <Badge variant="outline" className={cn('text-xs font-mono', METHOD_COLORS[action.method] || '')}>
                      {action.method}
                    </Badge>
                    <CardTitle className="text-sm font-mono">{action.name}</CardTitle>
                    <Badge variant="secondary" className="ml-auto text-xs capitalize">
                      {action.app}
                    </Badge>
                  </div>
                  <CardDescription className="text-xs mt-1 line-clamp-1">
                    {action.description}
                  </CardDescription>
                </CardHeader>

                {expandedAction === action.name && (
                  <CardContent className="pt-0 px-4 pb-4">
                    <Separator className="mb-3" />
                    <p className="text-sm text-muted-foreground mb-3">
                      {action.description}
                    </p>
                    {action.params.length > 0 && (
                      <div className="rounded-md border">
                        <div className="grid grid-cols-[1fr_80px_1fr] gap-2 p-2 bg-muted/50 text-xs font-medium text-muted-foreground">
                          <span>Parameter</span>
                          <span>Type</span>
                          <span>Description</span>
                        </div>
                        {action.params.map((p) => (
                          <div
                            key={p.name}
                            className="grid grid-cols-[1fr_80px_1fr] gap-2 p-2 border-t text-xs"
                          >
                            <div className="flex items-center gap-1">
                              <code className="font-mono">{p.name}</code>
                              {p.required && (
                                <span className="text-destructive">*</span>
                              )}
                            </div>
                            <Badge variant="outline" className="text-[10px] w-fit">
                              {p.type}
                            </Badge>
                            <span className="text-muted-foreground">
                              {p.description}
                            </span>
                          </div>
                        ))}
                      </div>
                    )}
                  </CardContent>
                )}
              </Card>
            ))}
            {filtered.length === 0 && (
              <p className="py-8 text-center text-sm text-muted-foreground">
                No actions match your search.
              </p>
            )}
          </div>
        </ScrollArea>
      )}
    </div>
  )
}
