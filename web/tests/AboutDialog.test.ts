// @vitest-environment jsdom
import { beforeEach, describe, expect, it } from 'vitest';
import { mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import ABOUT from '../src/content/about.md?raw';
import AboutDialog from '../src/components/AboutDialog.vue';
import { useSession } from '../src/stores/session';

describe('About & methods', () => {
  beforeEach(() => setActivePinia(createPinia()));

  it('renders the honest-labelling table and pending validation, with no invented numbers', () => {
    const w = mount(AboutDialog);
    const text = w.text();
    expect(text).toContain('Honest labelling');
    expect(text).toContain('Numerical method, not a trained model');
    expect(text).toContain('Unsupervised machine learning');
    expect(text).toContain('Weakly supervised learning');
    const pending = w.findAll('td.pending').map((x) => x.text());
    expect(pending.length).toBeGreaterThanOrEqual(10); // every metric not yet validated is listed
    for (const metric of ['Focus presets', 'Per-feature tolerances', 'Rock composition similarity'])
      expect(w.text()).toContain(metric);
    expect(pending.filter((t) => t.startsWith('Pending validation')).length).toBeGreaterThan(6);
    expect(w.text()).toContain('nothing below counts as validated');
    expect(w.findAll('table')).toHaveLength(2);
  });

  it('avoids forbidden claims', () => {
    expect(ABOUT.toLowerCase()).not.toMatch(/\btwin\b|qualified site|probability/);
  });

  it('says so in Sources when the bundle is a fast-mode sample, and opens on Sources when asked', async () => {
    const store = useSession();
    store.bundle = { manifest: { resolution: { mode: 'fast', stride: 20 } } } as never;
    store.aboutSection = 'sources';
    const w = mount(AboutDialog);
    await w.vm.$nextTick(); // onMounted selects the Sources section
    expect(w.text()).toContain('Partial real data');
    expect(w.text()).toContain('1 in 20 hexagons');
    expect(w.find('.detail-header h3, h3').text()).toBe('Data sources');
    expect(store.aboutSection).toBeNull(); // consumed
  });

  it('has no partial-data note for a complete bundle', () => {
    const store = useSession();
    store.bundle = { manifest: {} } as never;
    expect(mount(AboutDialog).text()).not.toContain('Partial real data');
  });
});
