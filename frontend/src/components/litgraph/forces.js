/**
 * The force layout.
 *
 * LitGraph draws a static plate: the backend projects every paper's embedding
 * centroid to 2D with PCA, and the canvas draws those coordinates. That is the
 * product's central claim -- position encodes meaning -- and it is not up for
 * negotiation. What it is not is *touchable*: you can pan, zoom and lasso a
 * plate, but you cannot take hold of a paper and see what it is tied to.
 *
 * So this is not a second layout beside the projection. It is a RELAXATION of
 * it, and how far it is allowed to go is one number:
 *
 *     blend 0     every paper exactly where PCA put it (no simulation runs)
 *     blend 0.45  overlap relaxed, clusters intact, everything near its place
 *     blend 1     anchors released; position is shape, not meaning
 *
 * `anchor` is what makes that a dial rather than a switch: every particle keeps
 * a spring back to its own projected home. An earlier cut of this file used
 * d3's global `center` force instead, and a global pull towards one point with
 * nothing holding any paper anywhere is precisely how a nine-paper library
 * settles into a knot in the middle of an empty plate. Centring per paper, at
 * its own home, is both the fix and one fewer slider.
 *
 * No dependency. d3-force is the obvious reach and it is ~30 kB across
 * d3-force/d3-quadtree/d3-dispatch/d3-timer for four forces and an alpha
 * counter -- and this file is what is left after writing them. The same
 * argument retired framer-motion from the page transition for twelve lines of
 * CSS; the shape of the trade has not changed.
 *
 * Everything here is pure and DOM-free, which is what makes it testable and
 * what makes it safe to run inside a rAF the canvas owns.
 */

/** The three sliders in the cog, at the values the map opens on. */
export const FORCE_DEFAULTS = { repel: 0.35, link: 0.5, distance: 78 };

/**
 * Anchor strength at blend just above zero. Strong enough that a paper barely
 * leaves its projected position at the Meaning end of the dial, so sliding off
 * zero reads as "loosen" rather than "throw everything in the air".
 */
export const ANCHOR_MAX = 0.5;

/** blend -> the spring back to home. Linear: the dial should feel like a dial. */
export const anchorFor = (blend) => (1 - Math.min(Math.max(blend, 0), 1)) * ANCHOR_MAX;

/**
 * How the heat drains. 0.978 per tick from 1 reaches ALPHA_MIN in ~215 frames,
 * a little over three seconds at 60fps -- long enough to read the movement as
 * settling rather than snapping, short enough that nobody waits for it.
 */
export const ALPHA_DECAY = 0.978;

/**
 * Where the loop stops. This is the whole reason there is a floor at all: this
 * app ships beside a language model that wants every core it can get, and a
 * simulation that keeps ticking at alpha 1e-9 to move nothing is a tax on
 * inference for the rest of the session. Settled means STOPPED.
 */
export const ALPHA_MIN = 0.008;

/** Velocity kept between ticks. Below ~0.5 the graph sticks; above ~0.75 it rings. */
const DAMPING = 0.62;

/** Repulsion at slider 1.0. Tuned against MIN_SEP on the 1100x760 plate. */
const REPEL_SCALE = 4000;

/**
 * Relaxation passes per tick for the collision. Two is enough for a chain of
 * three overlapping papers to clear; more buys very little and costs an O(n^2)
 * pass each.
 */
const COLLIDE_PASSES = 2;

/**
 * How much of an overlap is removed per pass. A full 1 makes pairs jitter
 * against each other when three of them are mutually overlapping.
 */
const COLLIDE_STRENGTH = 0.6;

/**
 * Particles for every id, starting where the projection put them.
 *
 * `hx`/`hy` are home -- the projected position, kept for the life of the
 * simulation because the anchor pulls back to it on every tick.
 *
 * `rx`/`ry` are the paper's FOOTPRINT, not its dot. A title is ~150 world
 * units wide and the dot under it is nine, so a layout that separates dots
 * still lands titles across each other and across the edges. The caller passes
 * the half-width of the label and the half-height of dot-plus-label, and the
 * collision reserves that space up front rather than letting the label find
 * out afterwards. Missing sizes fall back to a small circle.
 *
 * `fx`/`fy` are the pin: null while the simulation owns a paper, set to a world
 * coordinate once a pointer has put it somewhere. Unlike Obsidian, a release
 * does NOT clear it -- see the pin handling in useCanvas.
 */
export function seed(ids, pos, sizes) {
  return ids
    .filter((id) => pos[id])
    .map((id) => {
      const size = sizes?.[id];
      return {
        id,
        x: pos[id].x,
        y: pos[id].y,
        hx: pos[id].x,
        hy: pos[id].y,
        vx: 0,
        vy: 0,
        fx: null,
        fy: null,
        rx: size?.rx ?? 12,
        ry: size?.ry ?? 12,
      };
    });
}

/**
 * Edge list in the form the tick loop wants: index pairs, resolved once.
 *
 * Looked up by id on every tick this would be two hash lookups per edge per
 * frame; the graph payload does not change under the simulation, so the
 * resolution is done here instead and the hot loop indexes an array.
 */
export function link(sim, edges) {
  const at = new Map(sim.map((p, i) => [p.id, i]));
  return edges
    .map((e) => ({ ai: at.get(e.source), bi: at.get(e.target), weight: e.weight }))
    .filter((e) => e.ai !== undefined && e.bi !== undefined);
}

/**
 * Push overlapping papers apart, treating each as an ELLIPSE around its title.
 *
 * Position-based rather than a velocity force, and run after the integration,
 * because "these two must not overlap" is a constraint and not a preference:
 * expressed as a velocity it is satisfied on average and violated in every
 * individual frame, which is exactly the jumble this exists to remove.
 *
 * The ellipse test is the circle test in scaled space: divide each axis by the
 * summed half-extents and the pair overlaps when the scaled distance is under
 * one. The correction is applied along the real delta, so papers separate the
 * way they are actually crowded rather than always sideways.
 *
 * Exported for its test.
 */
export function collide(sim, passes = COLLIDE_PASSES) {
  const n = sim.length;
  for (let pass = 0; pass < passes; pass++) {
    for (let i = 0; i < n; i++) {
      for (let j = i + 1; j < n; j++) {
        const a = sim[i];
        const b = sim[j];
        const sx = a.rx + b.rx;
        const sy = a.ry + b.ry;
        let dx = b.x - a.x;
        let dy = b.y - a.y;
        // Coincident, or so close the direction is noise. Deterministic nudge,
        // so a reload separates them the same way.
        if (Math.abs(dx) < 1e-6 && Math.abs(dy) < 1e-6) {
          dx = i % 2 ? 0.01 : -0.01;
          dy = j % 2 ? 0.01 : -0.01;
        }
        const ux = dx / sx;
        const uy = dy / sy;
        const d = Math.hypot(ux, uy);
        if (d >= 1 || d === 0) continue;

        // How far along the real delta the pair has to move to clear.
        const scale = ((1 / d) - 1) * COLLIDE_STRENGTH;
        const px = dx * scale;
        const py = dy * scale;

        // A pinned paper does not give way; the other one takes the whole
        // correction. Two pinned papers are the user's arrangement and are
        // left exactly as placed.
        const aFixed = a.fx != null;
        const bFixed = b.fx != null;
        if (aFixed && bFixed) continue;
        if (aFixed) { b.x += px; b.y += py; continue; }
        if (bFixed) { a.x -= px; a.y -= py; continue; }
        a.x -= px / 2;
        a.y -= py / 2;
        b.x += px / 2;
        b.y += py / 2;
      }
    }
  }
}

/**
 * One tick. Mutates `sim` in place; returns nothing, because the caller owns
 * the alpha counter and the frame.
 *
 * Velocity Verlet: accumulate every force into velocity, integrate once, then
 * resolve the collision constraint on the result.
 *
 * ponytail: O(n^2) repulsion and O(n^2) collision. 200 papers is 20k pairs a
 * tick each, which is nothing; 800 would be 320k and start to show. Past that,
 * swap both middle loops for a quadtree (Barnes-Hut, theta ~0.9) -- the
 * signature of this function does not change, and its tests stay valid.
 *
 * @param o { anchor, repel, link, distance }
 */
export function step(sim, links, o, alpha) {
  const n = sim.length;
  let i;
  let j;
  let a;
  let b;
  let dx;
  let dy;
  let d;
  let d2;
  let f;

  // anchor: every paper is pulled back to where the projection put it. This is
  // what keeps a relaxed layout a reading of the map rather than a new one --
  // and, at any anchor above zero, what makes a collapse to the centre
  // impossible, because there is no centre to collapse to.
  if (o.anchor > 0) {
    for (i = 0; i < n; i++) {
      a = sim[i];
      a.vx += (a.hx - a.x) * o.anchor * alpha;
      a.vy += (a.hy - a.y) * o.anchor * alpha;
    }
  }

  // repulsion: every paper pushes every other, falling off with the square
  for (i = 0; i < n; i++) {
    for (j = i + 1; j < n; j++) {
      a = sim[i];
      b = sim[j];
      dx = b.x - a.x;
      dy = b.y - a.y;
      d2 = dx * dx + dy * dy;
      // Two papers at exactly the same point have no direction to separate
      // along, and 1/0 would put them both at NaN for the rest of the session.
      // The parity nudge is deterministic, so a reload lands the same way.
      if (d2 < 1) {
        d2 = 1;
        dx = i % 2 ? 1 : -1;
        dy = j % 2 ? 1 : -1;
      }
      d = Math.sqrt(d2);
      f = (o.repel * REPEL_SCALE * alpha) / d2;
      a.vx -= (dx / d) * f;
      a.vy -= (dy / d) * f;
      b.vx += (dx / d) * f;
      b.vy += (dy / d) * f;
    }
  }

  // springs: an edge pulls towards `distance`, in proportion to how alike the
  // two papers actually are. A 0.92 edge should be shorter than a 0.36 one, or
  // the strength the backend computed is thrown away at the last step.
  for (i = 0; i < links.length; i++) {
    a = sim[links[i].ai];
    b = sim[links[i].bi];
    dx = b.x - a.x;
    dy = b.y - a.y;
    d = Math.sqrt(dx * dx + dy * dy) || 0.001;
    f = ((d - o.distance) / d) * alpha * o.link * links[i].weight;
    a.vx += dx * f;
    a.vy += dy * f;
    b.vx -= dx * f;
    b.vy -= dy * f;
  }

  // integrate. A pinned paper takes its position from where it was put and
  // keeps no velocity, so nothing accumulates behind the pin to fling it when
  // it is released.
  for (i = 0; i < n; i++) {
    a = sim[i];
    if (a.fx != null) {
      a.x = a.fx;
      a.y = a.fy;
      a.vx = 0;
      a.vy = 0;
      continue;
    }
    a.vx *= DAMPING;
    a.vy *= DAMPING;
    a.x += a.vx;
    a.y += a.vy;
  }

  collide(sim);
}

/** Total kinetic energy. The test's handle on "is this settling or ringing". */
export function energy(sim) {
  return sim.reduce((s, p) => s + p.vx * p.vx + p.vy * p.vy, 0);
}

/** The settled extent, in world units. The test's handle on "did it nucleate". */
export function bounds(sim) {
  const xs = sim.map((p) => p.x);
  const ys = sim.map((p) => p.y);
  return {
    w: Math.max(...xs) - Math.min(...xs),
    h: Math.max(...ys) - Math.min(...ys),
  };
}
