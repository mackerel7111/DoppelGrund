import { describe, expect, it } from 'vitest';
import { BADGE_R, layoutBadges } from '../src/globe/badges';

const pt = (n: number, x: number, y: number) => ({ n, row: n, x, y });
const dist = (a: { bx: number; by: number }, b: { bx: number; by: number }) =>
  Math.hypot(a.bx - b.bx, a.by - b.by);

describe('layoutBadges', () => {
  it('puts a lone badge on its point, with no leader line', () => {
    const [b] = layoutBadges([pt(1, 100, 80)]);
    expect([b.bx, b.by, b.displaced]).toEqual([100, 80, false]);
  });

  it('keeps badge 1 on its point and steps a close badge aside with a leader line', () => {
    const [a, b] = layoutBadges([pt(2, 103, 80), pt(1, 100, 80)]);
    expect(a.n).toBe(1);
    expect(a.displaced).toBe(false);
    expect(b.displaced).toBe(true);
    expect(dist(a, b)).toBeGreaterThanOrEqual(2 * BADGE_R); // no overlap
    expect([b.x, b.y]).toEqual([103, 80]); // the leader line still starts at its own point
  });

  it('leaves badges that are far apart on their own points', () => {
    const out = layoutBadges([pt(1, 10, 10), pt(2, 200, 10), pt(3, 10, 200)]);
    expect(out.every((b) => !b.displaced)).toBe(true);
  });

  it('never overlaps six points piled on the same spot', () => {
    const out = layoutBadges([1, 2, 3, 4, 5, 6].map((n) => pt(n, 50, 50)));
    for (let i = 0; i < out.length; i++)
      for (let j = i + 1; j < out.length; j++)
        expect(dist(out[i], out[j])).toBeGreaterThanOrEqual(2 * BADGE_R);
  });
});
