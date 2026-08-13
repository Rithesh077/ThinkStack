import { useEffect, useState } from 'react';

/**
 * resolved CSS theme tokens for use in JS-rendered charts (Recharts).
 *
 * Re-reads whenever <html data-earned> changes, so a chart takes a pigment at
 * the moment it is earned without the component having to know that earning
 * exists. (It used to watch data-theme, which was the light/dark flip; there
 * is one theme now, and the attribute that moves is the earned set.)
 */
const TOKENS = [
  '--accent', '--accent-2', '--accent-soft',
  '--success', '--warning', '--danger', '--info',
  '--text', '--text-2', '--text-3',
  '--border', '--surface',
  // paper tokens: charts draw in ink and reserve the pigments for meaning
  '--ink', '--ink-2', '--ink-3', '--ink-4',
  '--sheet', '--sheet-2', '--rule',
  '--mark', '--ochre', '--moss', '--slate',
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
      attributeFilter: ['data-earned'],
    });
    return () => obs.disconnect();
  }, []);

  return colors;
}
