// @vitest-environment jsdom
import { beforeEach, describe, expect, it } from 'vitest';
import { mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import LensControls from '../src/components/LensControls.vue';
import { useSession } from '../src/stores/session';

describe('LensControls', () => {
  beforeEach(() => setActivePinia(createPinia()));

  it('renders five labelled sliders at the balanced preset', () => {
    const w = mount(LensControls);
    for (const g of ['terrain', 'thermal', 'cold_ice', 'composition', 'subsurface']) {
      const input = w.get(`[data-test="slider-${g}"]`);
      const want = g === 'subsurface' ? '10' : '23'; // 22.5 → 23 on the integer slider
      expect((input.element as HTMLInputElement).value).toBe(want);
      expect(w.find(`label[for="w-${g}"]`).exists()).toBe(true);
    }
    expect(w.get('[data-test="lens-label"]').text()).toContain('Terrain 23 · Thermal 23');
  });

  it('moving a slider renormalises and shows "Custom"', async () => {
    const w = mount(LensControls);
    const s = useSession();
    await w.get('[data-test="slider-terrain"]').setValue('70');
    expect(s.lens).toBe('custom');
    expect(s.weights.terrain).toBeCloseTo(0.7);
    expect(s.weights.thermal).toBeCloseTo((0.3 * 0.225) / 0.775); // others keep their ratios
    expect(w.get('[data-test="lens-label"]').text()).toContain('Custom weights');
    expect((w.get('[data-test="slider-thermal"]').element as HTMLInputElement).value).toBe('9');
  });
});
