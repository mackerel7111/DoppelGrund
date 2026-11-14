import { describe, expect, it } from 'vitest';
import * as h3 from 'h3-js';

describe('smoke', () => {
  it('runs vitest', () => {
    expect(1 + 1).toBe(2);
  });

  it('has the h3-js v4 API', () => {
    const cell = h3.latLngToCell(0, 0, 4);
    expect(h3.getResolution(cell)).toBe(4);
  });
});
