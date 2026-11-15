// Upright numbered badges for the match points on the 3D globe.
// Each badge sits ON its point (so the number is the point). When two points are close, the later
// badge steps aside, and a leader line from its point to the badge keeps it obvious which is which.

export const BADGE_R = 13; // px radius of a badge
const GAP = 3; // px kept between two badges

export interface BadgeIn {
  n: number;
  row: number;
  x: number; // the point's screen position, px
  y: number;
}
export interface Badge extends BadgeIn {
  bx: number; // badge centre, px
  by: number;
  displaced: boolean; // true: draw a leader line from (x, y) to (bx, by)
}

/** Candidate centres: on the point, then rings of 8 directions (up-right first) at growing distance. */
function candidates(x: number, y: number, r: number): [number, number][] {
  const out: [number, number][] = [[x, y]];
  for (let ring = 1; ring <= 3; ring++) {
    const d = ring * (2 * r + GAP + 2);
    for (let k = 0; k < 8; k++) {
      const a = (-Math.PI / 4) * (k + 1); // -45° (up-right in screen px), then clockwise round
      out.push([x + d * Math.cos(a), y + d * Math.sin(a)]);
    }
  }
  return out;
}

/** Place the badges in match order (1 first keeps its spot): none overlaps another. */
export function layoutBadges(points: BadgeIn[], r: number = BADGE_R): Badge[] {
  const placed: Badge[] = [];
  for (const p of [...points].sort((a, b) => a.n - b.n)) {
    const free = candidates(p.x, p.y, r).find(([cx, cy]) =>
      placed.every((q) => Math.hypot(q.bx - cx, q.by - cy) >= 2 * r + GAP),
    );
    const [bx, by] = free ?? [p.x, p.y]; // nowhere free within 3 rings: stay on the point
    placed.push({ ...p, bx, by, displaced: bx !== p.x || by !== p.y });
  }
  return placed;
}
