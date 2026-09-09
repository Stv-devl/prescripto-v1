import { Bar, BarChart, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

interface SizeDistributionProps {
  data: Record<string, number>;
}

const LABELS: Record<string, string> = {
  tiny_lt_100: "< 100",
  small_100_500: "100-500",
  medium_500_1500: "500-1.5k",
  large_1500_2500: "1.5k-2.5k",
  oversized_gt_2500: "> 2.5k",
};

const COLORS: Record<string, string> = {
  tiny_lt_100: "#ef4444",
  small_100_500: "#f59e0b",
  medium_500_1500: "#FFC300",
  large_1500_2500: "#22c55e",
  oversized_gt_2500: "#ef4444",
};

export function SizeDistribution({ data }: SizeDistributionProps) {
  const chartData = Object.entries(data).map(([key, value]) => ({
    name: LABELS[key] ?? key,
    count: value,
    key,
  }));

  return (
    <section className="rounded-lg border border-[hsl(var(--border))] bg-[hsl(var(--secondary))]/50 p-5">
      <h3 className="mb-4 text-sm font-semibold text-[hsl(var(--foreground))]">
        Distribution des tailles
      </h3>
      <ResponsiveContainer width="100%" height={200}>
        <BarChart data={chartData}>
          <XAxis
            dataKey="name"
            tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }}
            axisLine={{ stroke: "hsl(var(--border))" }}
            tickLine={false}
          />
          <YAxis
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
          <Bar dataKey="count" radius={[4, 4, 0, 0]}>
            {chartData.map((entry) => (
              <Cell key={entry.key} fill={COLORS[entry.key] ?? "#6b7280"} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </section>
  );
}
