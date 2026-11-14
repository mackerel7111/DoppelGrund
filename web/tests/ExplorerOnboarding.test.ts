// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import App from '../src/App.vue';
import { useSession } from '../src/stores/session';
import ExplorerTutorial from '../src/components/ExplorerTutorial.vue';
import ControlPanel from '../src/components/ControlPanel.vue';
const wrappers: ReturnType<typeof mount>[] = [];
function app() {
  const w = mount(App, {
    global: {
      stubs: {
        StoryIntro: {
          template: '<button class="enter" @click="$emit(\'done\', \'mars\')">Enter Mars</button>',
        },
        AboutDialog: true,
        ResultsPanel: true,
        GlobeView: true,
        TargetPanel: true,
        EarthMap: true,
      },
    },
  });
  wrappers.push(w);
  return w;
}
beforeEach(() => {
  localStorage.clear();
  setActivePinia(createPinia());
  vi.useFakeTimers();
});
afterEach(() => {
  wrappers.forEach((w) => w.unmount());
  wrappers.length = 0;
  vi.useRealTimers();
});
describe('explorer onboarding', () => {
  it('waits for intro and data, highlights the selector, remembers completion and returns to the intro with Back', async () => {
    const w = app();
    const s = useSession();
    vi.spyOn(s, 'ensureLayer').mockResolvedValue();
    expect(w.findComponent(ExplorerTutorial).exists()).toBe(false);
    await w.get('.enter').trigger('click');
    expect(w.findComponent(ExplorerTutorial).exists()).toBe(false);
    s.loading.phase = 'ready';
    await w.vm.$nextTick();
    expect(w.findComponent(ExplorerTutorial).text()).toContain('Pick a place on Mars.');
    expect(w.findComponent(ControlPanel).get('select').classes()).toContain('tutorial-highlight');
    s.body = 'moon';
    await w.vm.$nextTick();
    expect(w.findComponent(ExplorerTutorial).text()).toContain('the Moon');
    vi.advanceTimersByTime(10000);
    await w.vm.$nextTick();
    expect(w.findComponent(ExplorerTutorial).exists()).toBe(false);
    expect(localStorage.getItem('doppelgrund.tutorialSeen')).toBe('1');
    expect(w.findComponent(ControlPanel).get('select').classes()).not.toContain(
      'tutorial-highlight',
    );
    expect(w.find('#explorer-help').exists()).toBe(false);
    await w.get('#explorer-back').trigger('click');
    expect(w.find('.enter').exists()).toBe(true);
    expect(s.introOpen).toBe(true);
    await w.get('.enter').trigger('click');
    expect(w.findComponent(ExplorerTutorial).exists()).toBe(false);
  });
  it('shows the welcome page for returning visitors, but does not repeat the completed tutorial', async () => {
    localStorage.setItem('doppelgrund.introSeen', '1');
    localStorage.setItem('doppelgrund.tutorialSeen', '1');
    const s = useSession();
    s.loading.phase = 'ready';
    const w = app();
    expect(w.find('.enter').exists()).toBe(true);
    expect(s.introOpen).toBe(true);
    await w.get('.enter').trigger('click');
    expect(w.findComponent(ExplorerTutorial).exists()).toBe(false);
    await w.get('#explorer-back').trigger('click');
    expect(w.find('.enter').exists()).toBe(true);
    expect(s.introOpen).toBe(true);
  });
});
