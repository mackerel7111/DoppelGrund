// @vitest-environment jsdom
import { beforeEach, describe, expect, it } from 'vitest';
import { mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import Shortlist from '../src/components/Shortlist.vue';
import { useSession } from '../src/stores/session';
import { buildOverlays } from '../src/map/overlayLayers';
import type { Bundle } from '../src/data/types';

function setup(nTop: number): void {
  const n = 120;
  const s = useSession();
  const novelty = new Float32Array(n * 2);
  for (let i = 0; i < n; i++) novelty[i * 2] = i % 3 === 0 ? 500 : 50; // every third row is novel
  s.bundle = {
    manifest: { n_hex: n, params: { novelty_gate_km: 300 }, lenses: {} },
    latlng: new Float32Array(n * 2),
    novelty,
    flags: new Uint8Array(n),
  } as unknown as Bundle;
  const top = Int32Array.from({ length: nTop }, (_, i) => i);
  s.result = {
    version: 1,
    S: Float32Array.from({ length: n }, (_, i) => 100 - i * 0.5),
    coverage: new Float32Array(n).fill(1),
    groups: new Float32Array(n * 4),
    cards: [],
    top,
    eligible: new Uint8Array(n).fill(1),
  };
}

describe('Shortlist', () => {
  beforeEach(() => setActivePinia(createPinia()));

  it('shows the top 50 eligible rows', () => {
    setup(110);
    const w = mount(Shortlist);
    expect(w.findAll('.row')).toHaveLength(50);
    expect(w.get('.row').text()).toContain('100.0');
  });

  it('"Novel only" keeps rows ≥ novelty_gate_km and says how many came from the top pool', async () => {
    setup(110);
    const w = mount(Shortlist);
    await w.get('[data-test="novel-only"]').setValue(true);
    expect(useSession().novelOnly).toBe(true);
    expect(w.findAll('.row')).toHaveLength(37); // rows 0, 3, …, 108 of the best 110
    expect(w.get('[data-test="shortlist-count"]').text()).toContain('from the best 110');
    expect(w.findAll('.row').every((r) => r.text().includes('500 km'))).toBe(true);
  });

  it('opens the scorecard from a row', async () => {
    setup(10);
    const w = mount(Shortlist);
    await w.findAll('.row')[2].trigger('click');
    expect(useSession().selectedRow).toBe(2);
  });
});

describe('buildOverlays', () => {
  it('builds only toggled layers that belong to the panel and exist in the bundle', () => {
    const fc = { type: 'FeatureCollection' as const, features: [] };
    const toggles = {
      known_sites: true,
      volcanoes: false,
      lava_tubes: true,
      lunar_pits: true,
      sarawak_caves: true,
    };
    const earth = buildOverlays('earth', toggles, {
      known_sites: fc,
      volcanoes: fc,
      lunar_pits: fc,
    });
    expect(earth.map((l) => l.id)).toEqual(['overlay-known_sites']);
    expect(buildOverlays('body', toggles, { lunar_pits: fc }).map((l) => l.id)).toEqual([
      'overlay-lunar_pits',
    ]);
  });
});
