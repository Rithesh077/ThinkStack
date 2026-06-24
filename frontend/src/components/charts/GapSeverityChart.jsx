import { PieChart, Pie, Cell, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import useThemeColors from './useThemeColors';
import ChartCard from './ChartCard';

/** donut of identified research gaps grouped by severity. */
export default function GapSeverityChart({ gaps = [] }) {
  const c = useThemeColors();
  if (!gaps.length) return null;

  const counts = { high: 0, medium: 0, low: 0 };
  gaps.forEach((g) => {
    const s = (g.severity || 'medium').toLowerCase();
    if (counts[s] !== undefined) counts[s] += 1;
    else counts.medium += 1;
  });

  const data = [
    { name: 'High', value: counts.high, color: c.danger },
    { name: 'Medium', value: counts.medium, color: c.warning },
    { name: 'Low', value: counts.low, color: c.success },
  ].filter((d) => d.value > 0);

  if (!data.length) return null;

  return (
    <ChartCard title="Gap severity distribution" height={220} style={{ marginBottom: '1.5rem' }}>
      <ResponsiveContainer>
        <PieChart>
          <Pie
            data={data}
            dataKey="value"
            nameKey="name"
            innerRadius={55}
            outerRadius={86}
            paddingAngle={3}
            stroke="none"
            isAnimationActive
            animationDuration={650}
          >
            {data.map((d, i) => (
              <Cell key={i} fill={d.color} />
            ))}
          </Pie>
          <Tooltip contentStyle={{ background: c.surface, border: `1px solid ${c.border}`, borderRadius: 12, color: c.text }} />
          <Legend formatter={(v) => <span style={{ color: c['text-2'], fontSize: 12 }}>{v}</span>} />
        </PieChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}
