import { describe, expect, it } from 'vitest';
import { partialNotice, partialShort } from '../src/content/labels';

describe('partialNotice', () => {
  it('says fast mode and the sampling for a fast 1-in-20 bundle', () => {
    expect(partialNotice({ mode: 'fast', stride: 20 })).toBe(
      'Fast mode (coarser inputs), 1 in 20 hexagons',
    );
  });

  it('says only fast mode when every hexagon is computed', () => {
    expect(partialNotice({ mode: 'fast', stride: 1 })).toBe('Fast mode (coarser inputs)');
  });

  it('says only the sampling for a full-resolution sample', () => {
    expect(partialNotice({ mode: 'full', stride: 4 })).toBe('1 in 4 hexagons');
  });

  it('is null for a complete bundle or one with no resolution recorded', () => {
    expect(partialNotice({ mode: 'full', stride: 1 })).toBeNull();
    expect(partialNotice(undefined)).toBeNull();
  });
});

describe('partialShort', () => {
  it('gives the sampling for a stride above 1, else fast mode, else null', () => {
    expect(partialShort({ mode: 'fast', stride: 20 })).toBe('1 in 20 hexagons');
    expect(partialShort({ mode: 'fast', stride: 1 })).toBe('fast mode');
    expect(partialShort({ mode: 'full', stride: 1 })).toBeNull();
    expect(partialShort(undefined)).toBeNull();
  });
});
