// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { mount } from '@vue/test-utils';
import StoryIntro from '../src/components/StoryIntro.vue';
import { narrationEnabled } from '../src/content/narration';
const wrappers: ReturnType<typeof mount>[] = [];
function intro() {
  const w = mount(StoryIntro, { attachTo: document.body });
  wrappers.push(w);
  return w;
}
const click = (w: ReturnType<typeof mount>, id: string) =>
  w.get(`[data-test="${id}"]`).trigger('click');
afterEach(() => {
  wrappers.forEach((w) => w.unmount());
  wrappers.length = 0;
  narrationEnabled.value = false;
  vi.unstubAllGlobals();
  window.history.replaceState({}, '', '/');
});
describe('StoryIntro', () => {
  it.each(['moon', 'mars'] as const)(
    'takes the visitor directly from destination choice to the %s explorer',
    async (body) => {
      const w = intro();
      expect(w.text()).toContain('Click the telescope to begin');
      expect(w.find('[data-test="forward"]').exists()).toBe(false);
      expect(w.text()).not.toContain('Explore with Doppel');
      await click(w, 'next');
      expect(w.get('[data-test="go"]').attributes('disabled')).toBeDefined();
      await click(w, body);
      expect(w.emitted('done')).toBeUndefined();
      await click(w, 'go');
      expect(w.emitted('done')).toEqual([[body]]);
    },
  );
  it('retains the destination when going back', async () => {
    const w = intro();
    await click(w, 'next');
    await click(w, 'mars');
    await click(w, 'back');
    await click(w, 'next');
    expect(w.get('[data-test="mars"]').attributes('aria-pressed')).toBe('true');
  });
  it('Skip and Escape finish only once with the default Moon', async () => {
    const w = intro();
    await click(w, 'skip');
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
    expect(w.emitted('done')).toEqual([['moon']]);
  });
  it('keeps old deep links useful', async () => {
    window.history.replaceState({}, '', '/?intro=3.7&world=mars');
    const w = intro();
    await click(w, 'go');
    expect(w.emitted('done')).toEqual([['mars']]);
  });
  it('keeps keyboard focus inside the introduction', () => {
    const w = intro();
    const last = w.get('[data-test="next"]').element as HTMLButtonElement;
    last.focus();
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Tab', cancelable: true }));
    expect(document.activeElement).toBe(w.get('[data-test="skip"]').element);
  });
  it('passes narration preference to the explorer and stops intro speech before completing', async () => {
    class Utterance {
      constructor(public text: string) {}
    }
    const speak = vi.fn();
    const cancel = vi.fn();
    vi.stubGlobal('SpeechSynthesisUtterance', Utterance);
    vi.stubGlobal('speechSynthesis', { speak, cancel, getVoices: () => [] });
    const w = intro();
    expect(speak).not.toHaveBeenCalled();
    await click(w, 'narration');
    expect(narrationEnabled.value).toBe(true);
    expect(speak.mock.calls[0][0]).toMatchObject({ rate: 0.88, lang: 'en-US' });
    await click(w, 'skip');
    expect(cancel).toHaveBeenCalledOnce();
    expect(narrationEnabled.value).toBe(true);
  });
});
