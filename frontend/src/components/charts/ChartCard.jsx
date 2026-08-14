/**
 * Shared wrapper for charts. A titled block on the page, not a card.
 *
 * It used to be a glass card that sprang in on a blur filter and lifted 3px
 * when pointed at. A chart is a figure printed on the page: it does not float,
 * and it does not move when you look at it. Dropping framer-motion here also
 * drops a spring and a per-frame blur pass from the first paint of Library.
 */
export default function ChartCard({ title, height, children, style }) {
  return (
    <figure className="chart-card" style={style}>
      {title && <figcaption className="chart-title">{title}</figcaption>}
      <div style={{ width: '100%', height }}>{children}</div>
    </figure>
  );
}
