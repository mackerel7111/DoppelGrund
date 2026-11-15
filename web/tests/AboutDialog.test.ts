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
    const status = w.findAll('span.pending').map((x) => x.text());
    expect(status).toHaveLength(8); // only metrics that have a validation step
    expect(
      status.every((x) => ['Not yet validated', 'Needs human review', 'Reviewed'].includes(x)),
    ).toBe(true);
    for (const metric of ['Focus presets', 'Per-feature tolerances', 'Rock composition similarity'])
      expect(w.text()).toContain(metric);
    expect(w.text()).toContain(
      'have been reviewed, but none of the metrics below counts as validated',
    );
    // the two rows with a real first-run result are reviewed; the crosswalk has no result and still needs a geologist
    expect(w.findAll('span.verdict')).toHaveLength(3);
    expect(status.filter((x) => x === 'Reviewed')).toHaveLength(2);
    expect(status.filter((x) => x === 'Needs human review')).toHaveLength(1);
    expect(w.text()).toContain('Verdict (reviewed):');
    expect(w.text()).not.toContain('not yet signed off');
    expect(w.text()).toContain('not better than random on the current list of 23 documented sites');
    // data gaps and licences are not "pending validation": they live in Limitations and Sources
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
