// @vitest-environment jsdom
import { beforeEach, describe, expect, it } from 'vitest';
import { mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import ABOUT from '../src/content/about.md?raw';
import AboutDialog from '../src/components/AboutDialog.vue';

describe('About & methods', () => {
  beforeEach(() => setActivePinia(createPinia()));

  it('renders the honest-labelling table and pending validation, with no invented numbers', () => {
    const w = mount(AboutDialog);
    const text = w.text();
    expect(text).toContain('Honest labelling');
    expect(text).toContain('Numerical method, not a trained model');
    expect(text).toContain('Unsupervised machine learning');
    expect(text).toContain('Weakly supervised learning');
    const pending = w.findAll('td.pending');
    expect(pending.length).toBe(3);
    expect(w.findAll('table')).toHaveLength(2);
  });

  it('avoids forbidden claims', () => {
    expect(ABOUT.toLowerCase()).not.toMatch(/\btwin\b|qualified site|probability/);
  });
});
