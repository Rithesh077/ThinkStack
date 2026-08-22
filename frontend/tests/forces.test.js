import { describe, it, expect } from 'vitest';
import {
  FORCE_DEFAULTS, ANCHOR_MAX, anchorFor, ALPHA_DECAY, ALPHA_MIN,
  seed, link, step, collide, energy, bounds,
} from '../src/components/litgraph/forces';

/**
 * The force layout.
 *
 * These are the claims the canvas depends on and cannot check for itself: that
 * a run of the loop stops rather than ringing forever, that the layout does not
 * collapse into a knot, that nothing ends up overlapping anything, that a
 * pinned paper is immovable, and that the whole thing starts from the
 * projection rather than from anywhere else.
 */

/** Five papers across the plate, two of them deliberately on top of each other. */
const positions = () => ({
  a: { x: 100, y: 100 },
  b: { x: 140, y: 110 },
  c: { x: 900, y: 620 },
  d: { x: 905, y: 615 },
  e: { x: 500, y: 350 },
});

// The footprint of a title, which is what the collision actually reserves.
const sizes = () => ({
  a: { rx: 70, ry: 14 },
  b: { rx: 70, ry: 14 },
  c: { rx: 70, ry: 14 },
  d: { rx: 70, ry: 14 },
  e: { rx: 70, ry: 14 },
});

const edges = [
  { source: 'a', target: 'b', weight: 0.82 },
  { source: 'c', target: 'd', weight: 0.74 },
  { source: 'b', target: 'e', weight: 0.41 },
  { source: 'e', target: 'c', weight: 0.38 },
];

const ids = ['a', 'b', 'c', 'd', 'e'];

const opts = (blend, over = {}) => ({
  ...FORCE_DEFAULTS,
  anchor: anchorFor(blend),
  ...over,
});

/** Run the loop the way useCanvas does, and report how many frames it took. */
function settle(sim, links, o, cap = 4000) {
  let alpha = 1;
  let ticks = 0;
  while (alpha > ALPHA_MIN && ticks < cap) {
    alpha *= ALPHA_DECAY;
    step(sim, links, o, alpha);
    ticks++;
  }
  return ticks;
}

/** Two footprints overlap when the distance in scaled space is under one. */
const overlaps = (a, b) =>
  Math.hypot((b.x - a.x) / (a.rx + b.rx), (b.y - a.y) / (a.ry + b.ry)) < 1;

const worstOverlap = (sim) => {
  let worst = Infinity;
  for (let i = 0; i < sim.length; i++)
    for (let j = i + 1; j < sim.length; j++)
      worst = Math.min(
        worst,
        Math.hypot(
          (sim[j].x - sim[i].x) / (sim[i].rx + sim[j].rx),
          (sim[j].y - sim[i].y) / (sim[i].ry + sim[j].ry),
        ),
      );
  return worst;
};

const home = (sim, id) => {
  const p = sim.find((q) => q.id === id);
  return Math.hypot(p.x - p.hx, p.y - p.hy);
};

describe('anchorFor', () => {
  it('is the dial: full at Meaning, nothing at Force', () => {
    expect(anchorFor(0)).toBe(ANCHOR_MAX);
    expect(anchorFor(1)).toBe(0);
    expect(anchorFor(0.5)).toBeCloseTo(ANCHOR_MAX / 2, 10);
  });

  it('clamps rather than inverting on a value outside the slider', () => {
    expect(anchorFor(-3)).toBe(ANCHOR_MAX);
    expect(anchorFor(9)).toBe(0);
  });
});

describe('seed', () => {
  it('starts every particle where the projection put it, and remembers it', () => {
    const pos = positions();
    const sim = seed(ids, pos, sizes());
    expect(sim).toHaveLength(5);
    sim.forEach((p) => {
      expect(p.x).toBe(pos[p.id].x);
      expect(p.hx).toBe(pos[p.id].x);
      expect(p.hy).toBe(pos[p.id].y);
      expect(p.vx).toBe(0);
      expect(p.fx).toBeNull();
    });
  });

  it('falls back to a small footprint when no size is given', () => {
    const sim = seed(ids, positions());
    expect(sim[0].rx).toBeGreaterThan(0);
    expect(sim[0].ry).toBeGreaterThan(0);
  });

  it('skips ids the projection has no position for', () => {
    // A gap id, or a paper deleted between the payload and the seed.
    expect(seed([...ids, 'ghost'], positions(), sizes())).toHaveLength(5);
  });
});

describe('link', () => {
  it('resolves edges to indices and drops any that dangle', () => {
    const sim = seed(ids, positions(), sizes());
    const links = link(sim, [...edges, { source: 'a', target: 'ghost', weight: 0.9 }]);
    expect(links).toHaveLength(4);
    links.forEach((l) => {
      expect(sim[l.ai]).toBeDefined();
      expect(sim[l.bi]).toBeDefined();
    });
  });
});

describe('collide', () => {
  it('separates footprints that start on top of each other', () => {
    const sim = seed(ids, positions(), sizes());
    expect(worstOverlap(sim)).toBeLessThan(1);   // a/b and c/d start overlapping
    collide(sim, 40);
    expect(worstOverlap(sim)).toBeGreaterThanOrEqual(0.999);
  });

  it('separates along the axis the pair is actually crowded on', () => {
    // Two papers side by side clear sideways, not by jumping vertically.
    const sim = seed(['a', 'b'], { a: { x: 300, y: 300 }, b: { x: 320, y: 302 } }, {
      a: { rx: 70, ry: 14 }, b: { rx: 70, ry: 14 },
    });
    collide(sim, 40);
    expect(Math.abs(sim[1].x - sim[0].x)).toBeGreaterThan(Math.abs(sim[1].y - sim[0].y));
  });

  it('never moves a pinned paper, and makes the other one give way', () => {
    const sim = seed(['a', 'b'], { a: { x: 300, y: 300 }, b: { x: 305, y: 300 } }, {
      a: { rx: 70, ry: 14 }, b: { rx: 70, ry: 14 },
    });
    sim[0].fx = 300;
    sim[0].fy = 300;
    collide(sim, 40);
    expect(sim[0].x).toBe(300);
    expect(Math.abs(sim[1].x - 300)).toBeGreaterThan(100);
  });

  it('leaves two pinned papers exactly where they were put', () => {
    // The user's own arrangement. Overlapping or not, it is not ours to fix.
    const sim = seed(['a', 'b'], { a: { x: 300, y: 300 }, b: { x: 305, y: 300 } }, {
      a: { rx: 70, ry: 14 }, b: { rx: 70, ry: 14 },
    });
    sim.forEach((p) => { p.fx = p.x; p.fy = p.y; });
    collide(sim, 40);
    expect(sim[0].x).toBe(300);
    expect(sim[1].x).toBe(305);
  });

  it('does not put coincident papers at NaN', () => {
    const sim = seed(['a', 'b'], { a: { x: 300, y: 300 }, b: { x: 300, y: 300 } }, {
      a: { rx: 70, ry: 14 }, b: { rx: 70, ry: 14 },
    });
    collide(sim, 40);
    expect(sim.every((p) => Number.isFinite(p.x) && Number.isFinite(p.y))).toBe(true);
    expect(worstOverlap(sim)).toBeGreaterThan(0);
  });
});

describe('step', () => {
  it('settles: the loop ends and the graph is close to still', () => {
    const sim = seed(ids, positions(), sizes());
    const ticks = settle(sim, link(sim, edges), opts(0.45));

    // ALPHA_DECAY from 1 reaches ALPHA_MIN in a bounded number of frames --
    // this is the guarantee that the rAF loop cannot run forever.
    expect(ticks).toBeLessThan(400);
    expect(energy(sim)).toBeLessThan(1);
    expect(sim.every((p) => Number.isFinite(p.x) && Number.isFinite(p.y))).toBe(true);
  });

  it('does NOT collapse into a nucleus', () => {
    // The regression this whole force model was rewritten for. A global centre
    // force pulled nine papers into a knot in the middle of an empty plate;
    // anchoring each paper to its own projected home makes that impossible,
    // because there is no single point left to collapse towards.
    const before = bounds(seed(ids, positions(), sizes()));
    const sim = seed(ids, positions(), sizes());
    settle(sim, link(sim, edges), opts(0.45));
    const after = bounds(sim);

    expect(after.w).toBeGreaterThan(before.w * 0.5);
    expect(after.h).toBeGreaterThan(before.h * 0.5);
  });

  it('leaves nothing overlapping once it has settled', () => {
    const sim = seed(ids, positions(), sizes());
    settle(sim, link(sim, edges), opts(0.45));
    // Slightly under 1: the constraint is resolved on the last tick and the
    // springs get one more say. What matters is that no pair is still stacked.
    expect(worstOverlap(sim)).toBeGreaterThan(0.9);
  });

  it('the blend dial decides how far a paper may travel from its home', () => {
    const drift = (blend) => {
      const sim = seed(ids, positions(), sizes());
      settle(sim, link(sim, edges), opts(blend));
      return ids.reduce((s, id) => s + home(sim, id), 0) / ids.length;
    };
    // Meaning end holds tight, Force end lets go, and the middle is in between.
    expect(drift(0.05)).toBeLessThan(drift(0.5));
    expect(drift(0.5)).toBeLessThan(drift(1));
  });

  it('at the Meaning end every paper stays within sight of its projection', () => {
    const sim = seed(ids, positions(), sizes());
    settle(sim, link(sim, edges), opts(0.05));
    // Far enough to stop overlapping, near enough that the map still means it.
    ids.forEach((id) => expect(home(sim, id)).toBeLessThan(150));
  });

  it('never moves a pinned paper, and gives it no velocity to fling', () => {
    const sim = seed(ids, positions(), sizes());
    const held = sim.find((p) => p.id === 'e');
    held.fx = 900;
    held.fy = 90;

    settle(sim, link(sim, edges), opts(0.45));

    expect(held.x).toBe(900);
    expect(held.y).toBe(90);
    expect(held.vx).toBe(0);
    expect(held.vy).toBe(0);
  });

  it('a pin holds at every point on the dial, Meaning end included', () => {
    // The arrangement has to survive sliding back towards the projection, or
    // tidying the map by hand is a thing you can only do at one setting.
    [0.05, 0.5, 1].forEach((blend) => {
      const sim = seed(ids, positions(), sizes());
      const held = sim.find((p) => p.id === 'a');
      held.fx = 700;
      held.fy = 200;
      settle(sim, link(sim, edges), opts(blend));
      expect(held.x).toBe(700);
      expect(held.y).toBe(200);
    });
  });

  it('releasing a pin returns the paper to the simulation', () => {
    const sim = seed(ids, positions(), sizes());
    const held = sim.find((p) => p.id === 'a');
    held.fx = 900;
    held.fy = 90;
    settle(sim, link(sim, edges), opts(0.45));

    held.fx = null;
    held.fy = null;
    const wasAt = held.x;
    settle(sim, link(sim, edges), opts(0.45));
    expect(held.x).not.toBe(wasAt);
  });

  it('is deterministic: the same seed settles to the same layout', () => {
    const a = seed(ids, positions(), sizes());
    const b = seed(ids, positions(), sizes());
    settle(a, link(a, edges), opts(0.45));
    settle(b, link(b, edges), opts(0.45));
    a.forEach((p, i) => {
      expect(p.x).toBeCloseTo(b[i].x, 9);
      expect(p.y).toBeCloseTo(b[i].y, 9);
    });
  });

  const gapBetween = (over, a = 'a', b = 'b') => {
    const sim = seed(ids, positions(), sizes());
    settle(sim, link(sim, edges), opts(1, over));
    const pa = sim.find((p) => p.id === a);
    const pb = sim.find((p) => p.id === b);
    return Math.hypot(pb.x - pa.x, pb.y - pa.y);
  };

  it('a stronger link force pulls a linked pair towards the rest length', () => {
    // Asserted as a distance FROM `distance` rather than as "closer", because a
    // spring pulls both ways: a and b start 41 apart with a rest length of 78,
    // so a strong link pushes them out. Either way, more link force means
    // nearer the length the slider asks for.
    const strong = Math.abs(gapBetween({ link: 0.9 }) - FORCE_DEFAULTS.distance);
    const weak = Math.abs(gapBetween({ link: 0.02 }) - FORCE_DEFAULTS.distance);
    expect(strong).toBeLessThan(weak);
  });

  it('link distance sets how far apart a linked pair ends up', () => {
    expect(gapBetween({ link: 0.9, distance: 260 }))
      .toBeGreaterThan(gapBetween({ link: 0.9, distance: 60 }));
  });

  it('a stronger repel force spreads unlinked papers further apart', () => {
    // 'a' and 'd' share no edge, so only repulsion acts between them.
    expect(gapBetween({ repel: 0.9 }, 'a', 'd'))
      .toBeGreaterThan(gapBetween({ repel: 0.02 }, 'a', 'd'));
  });

  it('runs a 200-paper library without producing a non-finite coordinate', () => {
    // The ceiling named in forces.js. Not a benchmark -- just the assurance
    // that the two O(n^2) passes stay numerically sane at the size it ships for.
    const big = {};
    const bigSizes = {};
    const bigIds = [];
    for (let i = 0; i < 200; i++) {
      bigIds.push('p' + i);
      big['p' + i] = { x: (i * 37) % 1100, y: (i * 61) % 760 };
      bigSizes['p' + i] = { rx: 60, ry: 13 };
    }
    const sim = seed(bigIds, big, bigSizes);
    settle(sim, [], opts(0.45));
    expect(sim.every((p) => Number.isFinite(p.x) && Number.isFinite(p.y))).toBe(true);
  });
});
