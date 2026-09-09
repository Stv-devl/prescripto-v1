import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

interface LotBreakdownProps {
  data: Record<string, number>;
}

export function LotBreakdown({ data }: LotBreakdownProps) {
  const chartData = Object.entries(data)
    .map(([name, value]) => ({ name: name || "—", count: value }))
    .sort((a, b) => b.count - a.count);

  return (
    <section className="rounded-lg border border-[hsl(var(--border))] bg-[hsl(var(--secondary))]/50 p-5">
      <h3 className="mb-4 text-sm font-semibold text-[hsl(var(--foreground))]">
        Chunks par lot
      </h3>
      <ResponsiveContainer width="100%" height={Math.max(200, chartData.length * 28)}>
        <BarChart data={chartData} layout="vertical" margin={{ left: 10 }}>
          <XAxis
            type="number"
            tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }}
            axisLine={false}
            tickLine={false}
          />
          <YAxis
            type="category"
            dataKey="name"
            width={140}
            tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip
            contentStyle={{
              borderRadius: "8px",
              border: "1px solid hsl(var(--border))",
              backgroundColor: "hsl(var(--secondary))",
              color: "hsl(var(--foreground))",
              fontSize: "12px",
            }}
          />
          <Bar dataKey="count" fill="#FFC300" radius={[0, 4, 4, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </section>
  );
}
