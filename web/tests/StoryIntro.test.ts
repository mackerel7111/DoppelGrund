// @vitest-environment jsdom
import { describe, expect, it } from 'vitest';
import { mount } from '@vue/test-utils';
import StoryIntro from '../src/components/StoryIntro.vue';

const click = (w: ReturnType<typeof mount>, id: string) =>
  w.get(`[data-test="${id}"]`).trigger('click');

describe('StoryIntro', () => {
  it('click-through: five scenes, then done with the picked world', async () => {
    const w = mount(StoryIntro);
    await click(w, 'next'); // telescope
    await click(w, 'mars'); // pick a world
    expect(w.text()).toContain('Doppel is shy');
    await click(w, 'next'); // Doppel
    await click(w, 'next'); // Earth
    expect(w.text()).toContain('DoppelGrund compares');
    await click(w, 'go');
    expect(w.emitted('done')).toEqual([['mars']]);
  });

  it('"instead" finishes with the other world', async () => {
    const w = mount(StoryIntro);
    await click(w, 'next');
    await click(w, 'moon');
    await click(w, 'next');
    await click(w, 'next');
    await click(w, 'other');
    expect(w.emitted('done')).toEqual([['mars']]);
  });

  it('Skip and Esc finish with moon, once', async () => {
    const a = mount(StoryIntro);
    await click(a, 'skip');
    expect(a.emitted('done')).toEqual([['moon']]);
    const b = mount(StoryIntro);
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
    expect(b.emitted('done')).toEqual([['moon']]);
    a.unmount();
    b.unmount();
  });
});
