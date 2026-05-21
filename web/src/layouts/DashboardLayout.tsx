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
  Settings,
  Sun,
  Moon,
  Monitor,
  Webhook,
  FileText,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { clearSession } from '@/lib/api'
import { useTheme } from '@/lib/theme'
import { cn } from '@/lib/utils'

const NAV_SECTIONS = [
  {
    label: 'Get Started',
    items: [
      { to: '/dashboard', icon: LayoutDashboard, label: 'Overview', end: true },
      { to: '/dashboard/quickstart', icon: BookOpen, label: 'Quickstart' },
      { to: '/dashboard/keys', icon: Key, label: 'API Keys' },
    ],
  },
  {
    label: 'Integrate',
    items: [
      { to: '/dashboard/connections', icon: Plug, label: 'Connected Users' },
    ],
  },
  {
    label: 'Build',
    items: [
      { to: '/dashboard/actions', icon: Wrench, label: 'Actions' },
      { to: '/dashboard/triggers', icon: Zap, label: 'Triggers' },
      { to: '/dashboard/webhook-logs', icon: Webhook, label: 'Webhook Logs' },
      { to: '/dashboard/api-docs', icon: FileText, label: 'API Reference' },
    ],
  },
  {
    label: 'Monitor',
    items: [
      { to: '/dashboard/logs', icon: ScrollText, label: 'Logs' },
      { to: '/dashboard/settings', icon: Settings, label: 'Settings' },
      // Auth Configs hidden — Enterprise-only feature
      // { to: '/dashboard/auth-configs', icon: KeyRound, label: 'Auth Configs' },
    ],
  },
]

export function DashboardLayout() {
  const navigate = useNavigate()
  const { theme, resolved, setTheme } = useTheme()

  const userStr = localStorage.getItem('anytool_user')
  const user = userStr ? JSON.parse(userStr) as { name: string; email: string; picture: string } : null

  function handleLogout() {
    clearSession()
    navigate('/')
  }

  const ThemeIcon = theme === 'system' ? Monitor : resolved === 'dark' ? Moon : Sun

  return (
    <div className="flex h-screen">
      {/* Sidebar */}
      <aside className="flex w-60 flex-col border-r bg-muted/30">
        <div className="flex h-14 items-center justify-between px-4">
          <div className="flex items-center gap-2">
            <div className="flex size-7 items-center justify-center rounded-md bg-primary text-primary-foreground text-xs font-bold">
              AT
            </div>
            <span className="text-sm font-semibold tracking-tight">anytool</span>
          </div>

          {/* Theme toggle */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon" className="size-7">
                <ThemeIcon className="size-3.5" />
                <span className="sr-only">Toggle theme</span>
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-32">
              <DropdownMenuItem onClick={() => setTheme('light')}>
                <Sun className="mr-2 size-3.5" />
                Light
                {theme === 'light' && <span className="ml-auto text-xs">✓</span>}
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => setTheme('dark')}>
                <Moon className="mr-2 size-3.5" />
                Dark
                {theme === 'dark' && <span className="ml-auto text-xs">✓</span>}
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => setTheme('system')}>
                <Monitor className="mr-2 size-3.5" />
                System
                {theme === 'system' && <span className="ml-auto text-xs">✓</span>}
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>

        <Separator />

        <ScrollArea className="flex-1 px-2 py-2">
          <nav className="flex flex-col gap-3">
            {NAV_SECTIONS.map((section) => (
              <div key={section.label}>
                <p className="px-3 mb-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground/60">
                  {section.label}
                </p>
                <div className="flex flex-col gap-0.5">
                  {section.items.map((item) => (
                    <NavLink
                      key={item.to}
                      to={item.to}
                      end={'end' in item ? (item as { end?: boolean }).end : undefined}
                      className={({ isActive }) =>
                        cn(
                          'flex items-center gap-3 rounded-md px-3 py-1.5 text-sm font-medium transition-colors',
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
                </div>
              </div>
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
