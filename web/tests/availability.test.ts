// @vitest-environment jsdom
import { describe, expect, it } from 'vitest';
import { mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import ControlPanel from '../src/components/ControlPanel.vue';
import type { Bundle, DiscGrid } from '../src/data/types';
import { DEFAULT_LENSES, useSession } from '../src/stores/session';
import { effectiveWeights, groupAvailability } from '../src/stores/selectors';

// 2 discs: terrain varies, thermal all NaN, frac_below_0C NaN, aridity constant 0, no cave catalogue (NaN), lith valid.
function marsLikeGrid(): DiscGrid {
  const features = new Float32Array(22).fill(NaN);
  features[0] = 1;
  features[11] = 2; // slope_p50_deg varies
  for (const i of [0, 11]) features[i + 9] = 0; // aridity_index constant
  const lith = new Float32Array([1, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0]);
  return { n: 2, features, lith, latlon: new Float32Array(4) } as unknown as DiscGrid;
}

describe('group availability', () => {
  it('flags thermal and cold_ice as missing', () => {
    expect(groupAvailability(marsLikeGrid())).toEqual({
      terrain: true,
      thermal: false,
      cold_ice: false,
      composition: true,
      subsurface: false, // no catalogue on this body
    });
    expect(groupAvailability(undefined).thermal).toBe(true);
  });

  it('renormalises over available groups', () => {
    const w = effectiveWeights(DEFAULT_LENSES.balanced, groupAvailability(marsLikeGrid()));
    expect(w).toEqual({ terrain: 0.5, thermal: 0, cold_ice: 0, composition: 0.5, subsurface: 0 });
  });

  it('disables the cold_volatiles pill on Mars only', async () => {
    setActivePinia(createPinia());
    const s = useSession();
    s.bundle = {
      targets: [],
      discs: { mars: marsLikeGrid() },
      manifest: { lenses: DEFAULT_LENSES },
    } as unknown as Bundle;
    const w = mount(ControlPanel);
    expect(w.get('[data-test="lens-cold_volatiles"]').attributes('disabled')).toBeUndefined();
    s.setLens('cold_volatiles');
    s.selectBody('mars');
    await w.vm.$nextTick();
    expect(w.get('[data-test="lens-cold_volatiles"]').attributes('disabled')).toBeDefined();
    expect(w.get('[data-test="lens-cold_volatiles"]').attributes('title')).toContain('Thermal');
    expect(w.get('[data-test="lens-balanced"]').attributes('disabled')).toBeUndefined();
    expect(s.lens).toBe('balanced');
  });
});
