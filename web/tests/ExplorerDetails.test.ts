// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import App from '../src/App.vue';
import SiteDetailsModal from '../src/components/SiteDetailsModal.vue';
import { useSession } from '../src/stores/session';
import { GROUP_IDS } from '../src/data/types';

const wrappers: ReturnType<typeof mount>[] = [];
beforeEach(() => {
  setActivePinia(createPinia());
  localStorage.setItem('doppelgrund.tutorialSeen', '1');
});
afterEach(() => {
  wrappers.forEach((w) => w.unmount());
  wrappers.length = 0;
  localStorage.clear();
});
function ranked() {
  const s = useSession();
  s.result = {
    version: 1,
    S: new Float32Array([87.5]),
    coverage: new Float32Array([0.8]),
    groups: new Float32Array(GROUP_IDS.map((_, i) => (i === 1 ? NaN : 90 - i * 10))),
    eligible: new Uint8Array([1]),
    top: new Int32Array([0]),
    cards: [{ kind: 'overall', row: 0, S: 87.5, S_g: 87.5, coverage: 0.8 }],
  };
  return s;
}
describe('explorer detail flow', () => {
  it('does not open a popup after rankings, point selection or dismissal; opens only on request', async () => {
    const s = useSession();
    s.loading.phase = 'ready';
    const w = mount(App, {
      global: {
        stubs: {
          AppHeader: true,
          StoryIntro: true,
          AboutDialog: true,
          GlobeView: { name: 'GlobeView', props: ['showMarkerHint'], template: '<div />' },
          EarthMap: true,
          TargetPanel: true,
          BottomMatchDock: {
            template:
              '<button class="inspect" @click="$emit(\'view-details\')">View details</button>',
          },
          SiteDetailsModal: {
            template: '<button class="close" @click="$emit(\'close\')">Close</button>',
          },
        },
      },
    });
    wrappers.push(w);
    s.introOpen = false;
    ranked();
    await w.vm.$nextTick();
    expect(s.selectedRow).toBe(0);
    expect(w.findComponent({ name: 'GlobeView' }).props('showMarkerHint')).toBe(true);
    expect(w.find('.briefing-card').exists()).toBe(false);
    expect(w.find('.close').exists()).toBe(false);
    w.findComponent({ name: 'GlobeView' }).vm.$emit('viewDetails', 0);
    await w.vm.$nextTick();
    expect(w.get('.explorer-workspace').classes()).toContain('inspecting');
    expect(localStorage.getItem('doppelgrund.markerGuidanceSeen')).toBe('1');
    expect(w.findComponent({ name: 'GlobeView' }).props('showMarkerHint')).toBe(false);
    await w.get('.close').trigger('click');
    expect(s.selectedRow).toBe(0);
    if (s.result) s.result.version++;
    await w.vm.$nextTick();
    expect(w.find('.close').exists()).toBe(false);
    await w.get('[data-test="view-details"]').trigger('click');
    expect(w.find('.close').exists()).toBe(true);
    await w.get('.close').trigger('click');
    s.selectRow(0);
    await w.vm.$nextTick();
    expect(w.find('.close').exists()).toBe(false);
  });
  it('the Tutorial button shows Doppel and the location tip on the points together, even if both were seen', async () => {
    localStorage.setItem('doppelgrund.markerGuidanceSeen', '1');
    const s = useSession();
    s.loading.phase = 'ready';
    const w = mount(App, {
      global: {
        stubs: {
          AppHeader: { name: 'AppHeader', template: '<div />' },
          StoryIntro: true,
          AboutDialog: true,
          GlobeView: { name: 'GlobeView', props: ['showMarkerHint'], template: '<div />' },
          EarthMap: true,
          TargetPanel: true,
          BottomMatchDock: true,
          SiteDetailsModal: true,
        },
      },
    });
    wrappers.push(w);
    s.introOpen = false;
    ranked();
    await w.vm.$nextTick();
    const globe = () => w.findComponent({ name: 'GlobeView' });
    expect(globe().props('showMarkerHint')).toBe(false);
    expect(w.find('.explorer-tutorial').exists()).toBe(false);
    w.findComponent({ name: 'AppHeader' }).vm.$emit('tutorial');
    await w.vm.$nextTick();
    expect(w.find('.explorer-tutorial').exists()).toBe(true);
    expect(globe().props('showMarkerHint')).toBe(true); // shown while the tutorial is up
    await w.get('.explorer-tutorial [aria-label="Dismiss tutorial"]').trigger('click');
    expect(w.find('.explorer-tutorial').exists()).toBe(false);
    expect(globe().props('showMarkerHint')).toBe(true); // stays until the user dismisses it
    globe().vm.$emit('dismissMarkerHint');
    await w.vm.$nextTick();
    expect(globe().props('showMarkerHint')).toBe(false);
  });
  it('starts with a short summary and keeps measurements and sources in their own tabs', async () => {
    ranked();
    const w = mount(SiteDetailsModal, { props: { row: 0 } });
    wrappers.push(w);
    expect(w.text()).toContain('87.5');
    expect(w.text()).toContain('Gravity');
    expect(w.find('table').exists()).toBe(false);
    await w.get('#site-tab-measurements').trigger('click');
    expect(w.find('table').exists()).toBe(true);
    await w.get('#site-tab-sources').trigger('click');
    expect(w.text()).toContain('Data sources');
    expect(w.find('table').exists()).toBe(false);
    await w.get('[data-test="close-details"]').trigger('click');
    expect(w.emitted('close')).toHaveLength(1);
  });
  it('shows missing traits in words and does not replace them with zero', () => {
    ranked();
    const w = mount(SiteDetailsModal, { props: { row: 0 } });
    wrappers.push(w);
    expect(w.get('details').text()).toContain('Thermal');
    expect(w.get('details').text()).toContain('No data');
  });
  it('does not show excluded cells as valid comparisons', () => {
    const s = ranked();
    if (s.result) s.result.eligible[0] = 0;
    const w = mount(SiteDetailsModal, { props: { row: 0 } });
    wrappers.push(w);
    expect(w.text()).toContain('Not scored');
    expect(w.text()).toContain('Not ranked');
    expect(w.text()).not.toContain('Strongest similarities');
  });
  it('lets visitors switch numbered matches and disables unavailable locations', async () => {
    const s = ranked();
    if (!s.result) throw new Error('Missing test ranking');
    const overall = s.result.cards[0];
    s.result.cards = [
      overall,
      { ...overall, kind: 'terrain', row: 1 },
      { ...overall, kind: 'thermal', row: null },
      { ...overall, kind: 'cold_ice', row: 2 },
      { ...overall, kind: 'composition', row: 0 },
    ];
    const w = mount(SiteDetailsModal, { props: { row: 0 } });
    wrappers.push(w);
    expect(w.findAll('[data-test="match-number"] option')).toHaveLength(5);
    expect(
      w.get('[data-test="match-number"] option[value="2"]').attributes('disabled'),
    ).toBeDefined();
    await w.get('[data-test="match-number"]').setValue('1');
    expect(s.selectedRow).toBe(1);
    await w.setProps({ row: 1 });
    expect((w.get('[data-test="match-number"]').element as HTMLSelectElement).value).toBe('1');
    await w.get('[data-test="match-number"]').setValue('4');
    expect(s.selectedRow).toBe(0);
    await w.setProps({ row: 0 });
    expect((w.get('[data-test="match-number"]').element as HTMLSelectElement).value).toBe('4');
  });

  it('supports keyboard tab navigation and Escape, and restores focus on close', async () => {
    ranked();
    const button = document.createElement('button');
    document.body.append(button);
    button.focus();
    const w = mount(SiteDetailsModal, { props: { row: 0 }, attachTo: document.body });
    wrappers.push(w);
    await w.get('#site-tab-summary').trigger('keydown', { key: 'ArrowRight' });
    expect(w.get('#site-tab-measurements').attributes('aria-selected')).toBe('true');
    await w.trigger('keydown', { key: 'Escape' });
    expect(w.emitted('close')).toHaveLength(1);
    w.unmount();
    expect(document.activeElement).toBe(button);
    button.remove();
  });
});
