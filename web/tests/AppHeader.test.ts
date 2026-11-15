// @vitest-environment jsdom
import { beforeEach, describe, expect, it } from 'vitest';
import { mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import AppHeader from '../src/components/AppHeader.vue';
import { useSession } from '../src/stores/session';

describe('Partial data badge', () => {
  beforeEach(() => setActivePinia(createPinia()));

  it('explains itself in a popover, and its link opens About on Sources', async () => {
    const store = useSession();
    store.synthetic = false;
    store.aboutOpen = true; // keeps the explorer nav (and its child panels) out of this test
    store.bundle = { manifest: { resolution: { mode: 'fast', stride: 20 } } } as never;
    const w = mount(AppHeader, { attachTo: document.body });

    const badge = w.get('[data-test="partial-badge"]');
    expect(w.find('#partial-popover').exists()).toBe(false);
    await badge.trigger('click');
    expect(badge.attributes('aria-expanded')).toBe('true');
    expect(w.get('#partial-popover').text()).toContain('1 in 20 hexagons');

    // a pointerdown inside the popover must not close it before the click lands
    w.get('[data-test="partial-sources"]').element.dispatchEvent(
      new Event('pointerdown', { bubbles: true }),
    );
    await w.vm.$nextTick();
    await w.get('[data-test="partial-sources"]').trigger('click');
    expect(store.aboutSection).toBe('sources');
    w.unmount();
  });
});
