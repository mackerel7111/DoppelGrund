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
    // the Validation table has an Info column: each row says what was done and what it shows
    const info = w.findAll('span.info-line').map((x) => x.text());
    expect(info).toHaveLength(16); // 8 metrics x (Done + Shows)
    expect(info.filter((x) => x.startsWith('Done:'))).toHaveLength(8);
    expect(info.filter((x) => x.startsWith('Shows:'))).toHaveLength(8);
    expect(w.text()).not.toContain('Not yet validated'); // no status labels any more
    for (const metric of ['Focus presets', 'Per-feature tolerances', 'Rock composition similarity'])
      expect(w.text()).toContain(metric);
    expect(w.text()).toContain(
      'have been reviewed, but none of the metrics below counts as validated',
    );
    expect(w.text()).toContain('Not better than random on this list');
    expect(w.text()).toContain('No test has been run, so there is no result yet');
    // data gaps and licences are not validation rows: they live in Limitations and Sources
    expect(w.text()).toContain('Mars has no temperature or cold-and-ice measurements');
    expect(w.text()).toContain('awaiting human verification');
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
