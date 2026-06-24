import { useEffect, useState } from 'react';

/**
 * resolved CSS theme tokens for use in JS-rendered charts (Recharts).
 * re-reads whenever the <html data-theme> attribute flips so charts
 * recolor instantly when the user toggles light/dark.
 */
const TOKENS = [
  '--accent', '--accent-2', '--accent-soft',
  '--success', '--warning', '--danger', '--info',
  '--text', '--text-2', '--text-3',
  '--border', '--surface',
];

function readColors() {
  if (typeof window === 'undefined') return {};
  const cs = getComputedStyle(document.documentElement);
  const out = {};
  for (const t of TOKENS) out[t.slice(2)] = cs.getPropertyValue(t).trim();
  return out;
}

export default function useThemeColors() {
  const [colors, setColors] = useState(readColors);

  useEffect(() => {
    const obs = new MutationObserver(() => setColors(readColors()));
    obs.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ['data-theme'],
    });
    return () => obs.disconnect();
  }, []);

  return colors;
}
