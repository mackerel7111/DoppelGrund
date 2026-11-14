// @vitest-environment jsdom
import { beforeEach, describe, expect, it } from 'vitest';
import { mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import ControlPanel from '../src/components/ControlPanel.vue';
import type { Bundle } from '../src/data/types';
import { DEFAULT_LENSES, useSession } from '../src/stores/session';

describe('ControlPanel', () => {
  beforeEach(() => setActivePinia(createPinia()));

  it('choosing a lens pill resets the weights', async () => {
    const w = mount(ControlPanel);
    const s = useSession();
    s.setWeight('terrain', 0.9);
    await w.get('[data-test="lens-geology_minerals"]').trigger('click');
    expect(s.lens).toBe('geology_minerals');
    expect(s.weights).toEqual(DEFAULT_LENSES.geology_minerals);
    expect(w.get('[data-test="lens-geology_minerals"]').attributes('aria-pressed')).toBe('true');
  });

  it('switches body; the landmark select is always shown, with a custom point when picked on the map', async () => {
    const w = mount(ControlPanel);
    const s = useSession();
    await w.findAll('.seg button')[1].trigger('click');
    expect(s.body).toBe('mars');
    expect(w.find('[data-test="landmark-select"]').exists()).toBe(true);
    s.bundle = {
      targets: [],
      discs: { mars: { latlon: new Float32Array([-10, 20]) } },
    } as unknown as Bundle;
    s.target = { kind: 'disc', body: 'mars', discIndex: 0 };
    await w.vm.$nextTick();
    expect(w.get('[data-test="landmark-select"]').text()).toContain('Custom point 10.0°S, 20.0°E');
  });
});
