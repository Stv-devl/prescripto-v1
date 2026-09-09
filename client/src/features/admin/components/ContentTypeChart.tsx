import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip, Legend } from "recharts";

interface ContentTypeChartProps {
  data: Record<string, number>;
}

const COLORS: Record<string, string> = {
  specification: "#3b82f6",
  description: "#22c55e",
  mixed: "#FFC300",
  heading: "#6b7280",
  quantity: "#10b981",
  admin: "#f97316",
  unknown: "#4b5563",
};

export function ContentTypeChart({ data }: ContentTypeChartProps) {
  const chartData = Object.entries(data)
    .map(([name, value]) => ({ name, value }))
    .sort((a, b) => b.value - a.value);

  return (
    <section className="rounded-lg border border-[hsl(var(--border))] bg-[hsl(var(--secondary))]/50 p-5">
      <h3 className="mb-4 text-sm font-semibold text-[hsl(var(--foreground))]">
        Par content_type
      </h3>
      <ResponsiveContainer width="100%" height={200}>
        <PieChart>
          <Pie
            data={chartData}
            dataKey="value"
            nameKey="name"
            cx="50%"
            cy="50%"
            outerRadius={70}
            innerRadius={35}
            paddingAngle={2}
            strokeWidth={0}
          >
            {chartData.map((entry) => (
              <Cell key={entry.name} fill={COLORS[entry.name] ?? "#4b5563"} />
            ))}
          </Pie>
          <Tooltip
            contentStyle={{
              borderRadius: "8px",
              border: "1px solid hsl(var(--border))",
              backgroundColor: "hsl(var(--secondary))",
              color: "hsl(var(--foreground))",
              fontSize: "12px",
            }}
          />
          <Legend
            wrapperStyle={{ fontSize: "11px" }}
            formatter={(value: string) => (
              <span style={{ color: "hsl(var(--muted-foreground))" }}>{value}</span>
            )}
          />
        </PieChart>
      </ResponsiveContainer>
    </section>
  );
}
