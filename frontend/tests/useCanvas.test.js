import { describe, it, expect } from 'vitest';
import {
  makeAlpha, lassoFar, gestureFor, citedBy, edgeLit, hitRadius, hitRadiusAt,
  lodBand, placeLabels, loadPins, LOD_FAR, LOD_NEAR,
} from '../src/components/litgraph/useCanvas';

const m = (...ids) => new Map(ids.map((id) => [id, { score: 1 }]));

describe('makeAlpha', () => {
  it('dims everything that did not match, once a search is running', () => {
    const alpha = makeAlpha(m('a'), null, new Set());
    expect(alpha('a')).toBe(1);
    expect(alpha('b')).toBe(0.15);
  });

  it('leaves the scene alone when nothing is selected', () => {
    const alpha = makeAlpha(new Map(), null, new Set());
    expect(alpha('a')).toBe(1);
  });

  it('ranks focus above its neighbours above everything else', () => {
    const alpha = makeAlpha(new Map(), 'a', new Set(['b']));
    expect(alpha('a')).toBe(1);
    expect(alpha('b')).toBe(0.6);
    expect(alpha('c')).toBe(0.32);
  });

  // A search and a focus can be active at once; the search has to win, or a
  // node that did not match reads as merely "not adjacent" rather than "not a
  // result".
  it('lets a running search override the focus rules', () => {
    const alpha = makeAlpha(m('a'), 'b', new Set(['c']));
    expect(alpha('c')).toBe(0.15);
  });
});

describe('lassoFar', () => {
  const at = (x, y) => ({ x, y });

  it('drops points inside the threshold and keeps the ones outside', () => {
    expect(lassoFar(at(0, 0), at(3, 0), 1)).toBe(false);
    expect(lassoFar(at(0, 0), at(5, 0), 1)).toBe(true);
  });

  it('measures in screen pixels, not world units', () => {
    // Zoomed 4x in, 4 world units is 16 screen pixels: keep it.
    expect(lassoFar(at(0, 0), at(4, 0), 4)).toBe(true);
    // Zoomed out to a quarter, the same 4 units is 1 screen pixel: drop it.
    expect(lassoFar(at(0, 0), at(4, 0), 0.25)).toBe(false);
  });

  it('measures diagonally, not per axis', () => {
    expect(lassoFar(at(0, 0), at(3, 3), 1)).toBe(true);
  });
});

describe('gestureFor', () => {
  const empty = { closest: () => null };
  const node = { closest: (sel) => (sel === '.lg-node' ? {} : null) };
  const press = (shiftKey = false, target = empty, button = 0) => ({ target, button, shiftKey });

  // Plain drag pans. It selected for one release and made trackpads unusable:
  // every two-finger navigation gesture became a lasso.
  it('pans on a plain drag', () => {
    expect(gestureFor(press())).toBe('pan');
  });

  it('lassos only behind shift', () => {
    expect(gestureFor(press(true))).toBe('lasso');
  });

  // A press on a node must reach the node's own click listener untouched --
  // starting a gesture there flashes a lasso path that is then thrown away.
  it('leaves a press on a node alone, shift or not', () => {
    expect(gestureFor(press(false, node))).toBe('node');
    expect(gestureFor(press(true, node))).toBe('node');
  });

  it('ignores the right button, which belongs to the context menu', () => {
    expect(gestureFor(press(false, empty, 2))).toBe('none');
  });
});

/**
 * A gap is a node on the map that no edge touches: edges join papers, and a gap
 * is a claim about several of them. So focusing one used to dim the entire map
 * -- the papers it cites scored no better than papers it says nothing about,
 * and not one edge lit. The relation the marker exists to show was the one
 * thing selecting it hid.
 */
describe('citedBy', () => {
  const model = {
    gaps: [
      { gap_id: 'g1', doc_ids: ['a', 'b'] },
      { gap_id: 'g2', doc_ids: ['c'] },
    ],
  };

  it('gives the papers a gap cites', () => {
    expect([...citedBy(model, 'g1')]).toEqual(['a', 'b']);
  });

  it('gives nothing for a paper, which has edges of its own instead', () => {
    expect(citedBy(model, 'a')).toBe(null);
  });

  it('gives nothing when nothing is selected', () => {
    expect(citedBy(model, null)).toBe(null);
    expect(citedBy({}, 'g1')).toBe(null);
  });
});

describe('edgeLit', () => {
  const edge = (a, b) => ({ a, b });

  it('lights an edge touching the focused paper', () => {
    expect(edgeLit(edge('a', 'b'), 'a', null)).toBe(true);
    expect(edgeLit(edge('b', 'c'), 'a', null)).toBe(false);
  });

  // The point of selecting a gap: see how the papers it rests on relate.
  it('lights the edges between the papers a focused gap cites', () => {
    const cited = new Set(['a', 'b']);
    expect(edgeLit(edge('a', 'b'), 'g1', cited)).toBe(true);
  });

  it('leaves an edge with only one end in the gap alone', () => {
    const cited = new Set(['a', 'b']);
    expect(edgeLit(edge('b', 'z'), 'g1', cited)).toBe(false);
  });
});

// ─────────────────────────── D-18: hitting a node ───────────────────────────
//
// Two testers, on different operating systems, said the same thing without
// prompting: selecting a node needs more precision than it should. They are
// describing the geometry. A paper is drawn as a point of light with a radius
// of 4.5 to 8.5 units on a 1100x760 canvas, and the click listener sits on the
// group, so the target IS the dot. Zoomed out to 0.79x that is a four-pixel
// disc.
//
// The drawing is deliberate and stays: bubbles turned the plate into a bubble
// chart. What changes is that the TARGET stops being the drawing.

describe('hitRadius', () => {
  it('gives the smallest node a target far bigger than its dot', () => {
    expect(hitRadius(4.5)).toBeGreaterThanOrEqual(14);
  });

  it('never returns less than the dot it covers', () => {
    for (const r of [4.5, 6, 8.5, 20]) {
      expect(hitRadius(r)).toBeGreaterThanOrEqual(r);
    }
  });

  it('grows with the node, so a big node is not harder to hit than a small one', () => {
    expect(hitRadius(8.5)).toBeGreaterThan(hitRadius(4.5));
  });

  it('stays clear of the next node along', () => {
    // graph_builder.MIN_SEP is 0.055 of a 1100-unit canvas, so the closest two
    // nodes sit about 60 units apart. Two touching targets would make the
    // denser clusters ambiguous, which is a worse bug than a small target.
    expect(hitRadius(8.5) * 2).toBeLessThan(60);
  });
});

describe('hitRadiusAt', () => {
  it('holds the target at a usable size when the plate is zoomed out to fit', () => {
    // 22 papers fit at about 0.66, where a fixed 28-unit target measured 19px
    expect(hitRadiusAt(4.5, 0.66) * 2 * 0.66).toBeGreaterThanOrEqual(27);
  });

  it('clears the WCAG 2.2 minimum of 24px wherever that is geometrically possible', () => {
    // Not at every zoom, because below about 0.41 it cannot be: the nodes
    // themselves are only MIN_SEP * k apart on screen, so a 24px target would
    // overlap its neighbour. Not touching wins -- an ambiguous click is worse
    // than a small one, and at that zoom the dots overlap anyway.
    for (const k of [0.45, 0.66, 1, 1.6, 2.4]) {
      expect(hitRadiusAt(4.5, k) * 2 * k).toBeGreaterThanOrEqual(24);
    }
  });

  it('gets as close as it can when even that is impossible', () => {
    // at 0.15 the whole 60-unit gap is 9px; the target takes what it can
    expect(hitRadiusAt(4.5, 0.15) * 2 * 0.15).toBeGreaterThan(8);
  });

  it('never lets two targets touch, however far out', () => {
    // graph_builder.MIN_SEP is about 60 units on this canvas
    for (const k of [0.05, 0.15, 0.5]) {
      expect(hitRadiusAt(8.5, k) * 2).toBeLessThan(60);
    }
  });

  it('does not shrink below the un-zoomed target when zoomed in', () => {
    expect(hitRadiusAt(4.5, 3)).toBeGreaterThanOrEqual(hitRadius(4.5));
  });
});

/**
 * Level of detail.
 *
 * A map of two hundred papers cannot draw two hundred titles and stay a map.
 * The bands are named rather than continuous so the O(n^2) label placement can
 * be cached per band instead of running on every frame of a pan.
 */
describe('lodBand', () => {
  it('is territories only when zoomed out', () => {
    expect(lodBand(0.2)).toBe(0);
    expect(lodBand(0.3)).toBe(0);
    expect(lodBand(LOD_FAR - 0.01)).toBe(0);
  });

  it('names the biggest papers in the middle', () => {
    expect(lodBand(LOD_FAR)).toBe(1);
    expect(lodBand(0.8)).toBe(1);
    expect(lodBand(LOD_NEAR - 0.01)).toBe(1);
  });

  it('shows everything once you are in', () => {
    expect(lodBand(LOD_NEAR)).toBe(2);
    expect(lodBand(2)).toBe(2);
    expect(lodBand(6)).toBe(2);
  });

  it('is stable within a band, which is what makes the cache legal', () => {
    // If this were not constant across a pan's zoom jitter, the placement pass
    // would run per frame and the whole point of banding would be gone.
    expect(lodBand(0.6)).toBe(lodBand(1.05));
    expect(lodBand(1.2)).toBe(lodBand(5.9));
  });
});

/**
 * Label placement.
 *
 * The pass used to consider only other labels, so on a relaxed layout the
 * titles cleared each other and then landed squarely across the papers.
 */
describe('placeLabels', () => {
  const at = (text, x, y) => ({ text, x, y });

  it('keeps a label that hits nothing', () => {
    expect(placeLabels([at('Attention Is All You Need', 500, 400)])).toEqual([true]);
  });

  it('drops the second of two labels on top of each other', () => {
    expect(placeLabels([at('Dense Passage Retrieval', 500, 400), at('Sparse Attention', 505, 402)]))
      .toEqual([true, false]);
  });

  it('earlier entries win, so callers order by what matters most', () => {
    const [first, second] = placeLabels([at('theme', 500, 400), at('a paper title here', 502, 401)]);
    expect(first).toBe(true);
    expect(second).toBe(false);
  });

  it('drops a label that would land on a paper', () => {
    // The omission behind the jumble: a dot is an obstacle, not empty space.
    const dot = { x: 480, y: 392, w: 40, h: 40 };
    expect(placeLabels([at('Graph Attention Networks', 500, 400)], [dot])).toEqual([false]);
    expect(placeLabels([at('Graph Attention Networks', 500, 400)])).toEqual([true]);
  });

  it('an obstacle far away costs nothing', () => {
    expect(placeLabels([at('Node2Vec at Scale', 500, 400)], [{ x: 10, y: 10, w: 20, h: 20 }]))
      .toEqual([true]);
  });
});

/**
 * Pins. A paper the user has put somewhere outranks both the projection and
 * the simulation, so it has to survive a reload -- and must not resurrect a
 * paper that has since been deleted.
 */
describe('loadPins', () => {
  const ids = ['a', 'b', 'c'];

  it('reads back what was written', () => {
    const saved = JSON.stringify({ a: { x: 12, y: 34 }, b: { x: 5, y: 6 } });
    expect(loadPins(saved, ids)).toEqual({ a: { x: 12, y: 34 }, b: { x: 5, y: 6 } });
  });

  it('prunes papers that are no longer in the library', () => {
    const saved = JSON.stringify({ a: { x: 1, y: 2 }, gone: { x: 9, y: 9 } });
    expect(loadPins(saved, ids)).toEqual({ a: { x: 1, y: 2 } });
  });

  it('treats a corrupt store as no pins rather than taking the map down', () => {
    expect(loadPins('not json at all', ids)).toEqual({});
    expect(loadPins('[1,2,3]', ids)).toEqual({});
    expect(loadPins(null, ids)).toEqual({});
    expect(loadPins(undefined, ids)).toEqual({});
  });

  it('drops an entry whose coordinates are not numbers', () => {
    const saved = JSON.stringify({ a: { x: 'left', y: 3 }, b: null, c: { x: 1, y: 2 } });
    expect(loadPins(saved, ids)).toEqual({ c: { x: 1, y: 2 } });
  });
});
