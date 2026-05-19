import { Outlet, NavLink, useNavigate } from 'react-router-dom'
import {
  LayoutDashboard,
  Plug,
  Zap,
  ScrollText,
  Key,
  BookOpen,
  LogOut,
  Wrench,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
import { clearApiKey } from '@/lib/api'
import { cn } from '@/lib/utils'

const NAV = [
  { to: '/dashboard', icon: LayoutDashboard, label: 'Overview', end: true },
  { to: '/dashboard/connections', icon: Plug, label: 'Connections' },
  { to: '/dashboard/actions', icon: Wrench, label: 'Actions' },
  { to: '/dashboard/triggers', icon: Zap, label: 'Triggers' },
  { to: '/dashboard/logs', icon: ScrollText, label: 'Logs' },
  { to: '/dashboard/keys', icon: Key, label: 'API Keys' },
  { to: '/dashboard/quickstart', icon: BookOpen, label: 'Quickstart' },
]

export function DashboardLayout() {
  const navigate = useNavigate()

  const userStr = localStorage.getItem('anytool_user')
  const user = userStr ? JSON.parse(userStr) as { name: string; email: string; picture: string } : null

  function handleLogout() {
    clearApiKey()
    localStorage.removeItem('anytool_user')
    navigate('/')
  }

  return (
    <div className="flex h-screen">
      {/* Sidebar */}
      <aside className="flex w-60 flex-col border-r bg-muted/30">
        <div className="flex h-14 items-center gap-2 px-4">
          <div className="flex size-7 items-center justify-center rounded-md bg-primary text-primary-foreground text-xs font-bold">
            AT
          </div>
          <span className="text-sm font-semibold tracking-tight">anytool</span>
        </div>

        <Separator />

        <ScrollArea className="flex-1 px-2 py-2">
          <nav className="flex flex-col gap-1">
            {NAV.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) =>
                  cn(
                    'flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors',
                    isActive
                      ? 'bg-accent text-accent-foreground'
                      : 'text-muted-foreground hover:bg-accent hover:text-accent-foreground',
                  )
                }
              >
                <item.icon className="size-4" />
                {item.label}
              </NavLink>
            ))}
          </nav>
        </ScrollArea>

        <Separator />

        <div className="p-2 flex flex-col gap-1">
          {user && (
            <div className="flex items-center gap-2 px-3 py-2">
              <Avatar className="size-7">
                <AvatarImage src={user.picture} alt={user.name} />
                <AvatarFallback className="text-xs">
                  {user.name?.slice(0, 2).toUpperCase() || '??'}
                </AvatarFallback>
              </Avatar>
              <div className="flex-1 min-w-0">
                <p className="text-xs font-medium truncate">{user.name}</p>
                <p className="text-[10px] text-muted-foreground truncate">{user.email}</p>
              </div>
            </div>
          )}
          <Button
            variant="ghost"
            size="sm"
            className="w-full justify-start gap-3 text-muted-foreground"
            onClick={handleLogout}
          >
            <LogOut className="size-4" />
            Sign out
          </Button>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto">
        <div className="mx-auto max-w-6xl px-6 py-6">
          <Outlet />
        </div>
      </main>
    </div>
  )
}
