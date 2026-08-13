import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell, LabelList } from 'recharts';
import useThemeColors from './useThemeColors';
import ChartCard from './ChartCard';

const shortName = (fn) => {
  const base = (fn || '').replace(/\.pdf$/i, '');
  return base.length > 18 ? base.slice(0, 17) + '…' : base;
};

/** horizontal bar chart of knowledge chunks per ingested paper. */
export default function LibraryChart({ documents = [] }) {
  const c = useThemeColors();
  /* A paper at 0 chunks used to be filtered out here. That hid the one row
     worth looking at: a paper ThinkStack read nothing from is either still
     being ingested or has failed, and dropping it from the chart made the
     library look complete when it was not. It stays, drawn as an empty row
     against its label. The chart as a whole still disappears when there is
     genuinely nothing to plot. */
  const data = documents
    .map((d) => ({ name: shortName(d.filename), full: d.filename, chunks: d.chunks || 0 }));

  if (data.length === 0) return null;

  return (
    <ChartCard title="Chunks per paper" height={Math.max(96, data.length * 30 + 30)} style={{ marginBottom: '1.6rem' }}>
      <ResponsiveContainer>
        <BarChart data={data} layout="vertical" margin={{ left: 6, right: 40, top: 2, bottom: 2 }} barCategoryGap="34%">
          <XAxis type="number" hide />
          <YAxis
            type="category"
            dataKey="name"
            width={150}
            tick={{ fill: c['ink-3'], fontSize: 11, fontFamily: 'IBM Plex Mono, monospace' }}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip
            cursor={{ fill: c['sheet-2'] }}
            contentStyle={{
              background: c.sheet, border: `1px solid ${c.rule}`, borderRadius: 2,
              color: c.ink, fontFamily: 'IBM Plex Mono, monospace', fontSize: 11,
            }}
            labelFormatter={(l, p) => p?.[0]?.payload?.full || l}
            formatter={(v) => [`${v} chunks`, '']}
          />
          {/* Bars are ink, not pigment. How much of a paper was read is a
              quantity, not a category -- and the red pen is spent on gaps. */}
          <Bar dataKey="chunks" radius={0} barSize={9} isAnimationActive={false}>
            {data.map((_, i) => (
              <Cell key={i} fill={c['ink-2']} />
            ))}
            <LabelList
              dataKey="chunks" position="right" fill={c['ink-3']}
              fontSize={11} fontFamily="IBM Plex Mono, monospace"
            />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}
