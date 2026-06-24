import { motion } from 'framer-motion';

/**
 * shared glass card wrapper for charts with a spring entrance + subtle
 * lift on hover (Apple-like). keeps chart components focused on the data.
 */
export default function ChartCard({ title, height, children, style }) {
  return (
    <motion.div
      className="card chart-card"
      style={style}
      initial={{ opacity: 0, y: 18, filter: 'blur(6px)' }}
      animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
      transition={{ type: 'spring', stiffness: 240, damping: 28, mass: 0.7 }}
      whileHover={{ y: -3 }}
    >
      {title && <div className="chart-title">{title}</div>}
      <div style={{ width: '100%', height }}>{children}</div>
    </motion.div>
  );
}
