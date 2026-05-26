import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from 'recharts'

interface UsageDay {
  date: string
  total: number
  successful: number
  failed: number
}

export function UsageChart({ data }: { data: UsageDay[] }) {
  const sorted = [...data].reverse()

  return (
    <ResponsiveContainer width="100%" height={240}>
      <AreaChart data={sorted}>
        <defs>
          <linearGradient id="successGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#10b981" stopOpacity={0.2} />
            <stop offset="100%" stopColor="#10b981" stopOpacity={0} />
          </linearGradient>
          <linearGradient id="failGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#ef4444" stopOpacity={0.15} />
            <stop offset="100%" stopColor="#ef4444" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
        <XAxis
          dataKey="date"
          tick={{ fontSize: 11, fill: 'hsl(var(--muted-foreground))' }}
          tickFormatter={(v: string) => v.slice(5)}
          axisLine={false}
          tickLine={false}
        />
        <YAxis
          tick={{ fontSize: 11, fill: 'hsl(var(--muted-foreground))' }}
          axisLine={false}
          tickLine={false}
          width={32}
        />
        <Tooltip
          contentStyle={{
            backgroundColor: 'hsl(var(--card))',
            border: '1px solid hsl(var(--border))',
            borderRadius: '0.5rem',
            fontSize: '0.75rem',
            boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)',
          }}
          labelFormatter={(v: string) => v.slice(5)}
        />
        <Area
          type="monotone"
          dataKey="successful"
          stroke="#10b981"
          strokeWidth={2}
          fill="url(#successGrad)"
          dot={false}
          activeDot={{ r: 4, fill: '#10b981', strokeWidth: 0 }}
        />
        <Area
          type="monotone"
          dataKey="failed"
          stroke="#ef4444"
          strokeWidth={1.5}
          strokeDasharray="4 4"
          fill="url(#failGrad)"
          dot={false}
          activeDot={{ r: 4, fill: '#ef4444', strokeWidth: 0 }}
        />
      </AreaChart>
    </ResponsiveContainer>
  )
}
