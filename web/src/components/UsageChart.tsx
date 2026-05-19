import {
  BarChart,
  Bar,
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
  // Reverse so oldest is on the left
  const sorted = [...data].reverse()

  return (
    <ResponsiveContainer width="100%" height={240}>
      <BarChart data={sorted} barGap={2}>
        <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
        <XAxis
          dataKey="date"
          tick={{ fontSize: 12 }}
          tickFormatter={(v: string) => v.slice(5)} // "01-15"
          className="text-muted-foreground"
        />
        <YAxis tick={{ fontSize: 12 }} className="text-muted-foreground" />
        <Tooltip
          contentStyle={{
            backgroundColor: 'hsl(var(--card))',
            border: '1px solid hsl(var(--border))',
            borderRadius: '0.5rem',
            fontSize: '0.75rem',
          }}
        />
        <Bar dataKey="successful" stackId="a" fill="hsl(var(--primary))" radius={[0, 0, 0, 0]} />
        <Bar dataKey="failed" stackId="a" fill="hsl(var(--destructive))" radius={[4, 4, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  )
}
