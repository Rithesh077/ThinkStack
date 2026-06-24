import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts';
import useThemeColors from './useThemeColors';
import ChartCard from './ChartCard';

/** horizontal bar chart of result relevance scores, colored by threshold. */
export default function SearchScoreChart({ results = [] }) {
  const c = useThemeColors();
  if (!results.length) return null;

  const scoreColor = (s) => (s >= 0.02 ? c.success : s >= 0.015 ? c.warning : c['text-3']);
  const data = results.slice(0, 8).map((r, i) => ({
    name: r.source || r.metadata?.title || r.doc_id || `#${i + 1}`,
    score: Number(r.score) || 0,
  }));

  return (
    <ChartCard title="Relevance scores" height={Math.max(140, data.length * 38)} style={{ marginBottom: '1.5rem' }}>
      <ResponsiveContainer>
        <BarChart data={data} layout="vertical" margin={{ left: 6, right: 28, top: 4, bottom: 4 }}>
          <XAxis type="number" hide />
          <YAxis
            type="category"
            dataKey="name"
            width={120}
            tick={{ fill: c['text-2'], fontSize: 12 }}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip
            cursor={{ fill: c['accent-soft'] }}
            contentStyle={{ background: c.surface, border: `1px solid ${c.border}`, borderRadius: 12, color: c.text }}
            formatter={(v) => [v, 'score']}
          />
          <Bar dataKey="score" radius={[6, 6, 6, 6]} isAnimationActive animationDuration={650}>
            {data.map((d, i) => (
              <Cell key={i} fill={scoreColor(d.score)} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}
