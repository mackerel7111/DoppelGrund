// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { mount } from '@vue/test-utils';
import ExplorerTutorial from '../src/components/ExplorerTutorial.vue';
import { narrationEnabled } from '../src/content/narration';
const wrappers: ReturnType<typeof mount>[] = [];
function tutorial(body: 'moon' | 'mars' = 'mars') {
  const w = mount(ExplorerTutorial, { props: { body } });
  wrappers.push(w);
  return w;
}
function mockSpeech() {
  class Utterance {
    constructor(public text: string) {}
  }
  const speak = vi.fn();
  const cancel = vi.fn();
  vi.stubGlobal('SpeechSynthesisUtterance', Utterance);
  vi.stubGlobal('speechSynthesis', { speak, cancel, getVoices: () => [] });
  return { speak, cancel };
}
beforeEach(() => vi.useFakeTimers());
afterEach(() => {
  wrappers.forEach((w) => w.unmount());
  wrappers.length = 0;
  narrationEnabled.value = false;
  vi.unstubAllGlobals();
  vi.useRealTimers();
});
describe('ExplorerTutorial', () => {
  it('gives muted visitors ten seconds to read then closes once', () => {
    const w = tutorial();
    expect(w.text()).toContain('Pick a place on Mars.');
    vi.advanceTimersByTime(9999);
    expect(w.emitted('close')).toBeUndefined();
    vi.advanceTimersByTime(1);
    expect(w.emitted('close')).toHaveLength(1);
    vi.advanceTimersByTime(30000);
    expect(w.emitted('close')).toHaveLength(1);
  });
  it('waits for the whole sentence to finish, then closes after a short pause', () => {
    const { speak } = mockSpeech();
    narrationEnabled.value = true;
    const w = tutorial();
    const u = speak.mock.calls[0][0];
    u.onstart();
    vi.advanceTimersByTime(12000);
    expect(w.emitted('close')).toBeUndefined();
    u.onend();
    vi.advanceTimersByTime(899);
    expect(w.emitted('close')).toBeUndefined();
    vi.advanceTimersByTime(1);
    expect(w.emitted('close')).toHaveLength(1);
  });
  it('changes the wording and replaces speech if the body changes', async () => {
    const { speak, cancel } = mockSpeech();
    narrationEnabled.value = true;
    const w = tutorial();
    const old = speak.mock.calls[0][0];
    await w.setProps({ body: 'moon' });
    expect(old.onend).toBeNull();
    expect(cancel).toHaveBeenCalledOnce();
    expect(speak.mock.calls.at(-1)?.[0].text).toContain('on the Moon.');
  });
  it('stops speaking immediately on mute, then uses reading time', async () => {
    const { cancel } = mockSpeech();
    narrationEnabled.value = true;
    const w = tutorial();
    await w.get('button').trigger('click');
    expect(cancel).toHaveBeenCalledOnce();
    expect(narrationEnabled.value).toBe(false);
    vi.advanceTimersByTime(10000);
    expect(w.emitted('close')).toHaveLength(1);
  });
  it('falls back to reading time when speech errors or autoplay never starts', () => {
    const { speak } = mockSpeech();
    narrationEnabled.value = true;
    const w = tutorial();
    speak.mock.calls[0][0].onerror();
    vi.advanceTimersByTime(10000);
    expect(w.emitted('close')).toHaveLength(1);
    const replay = tutorial();
    vi.advanceTimersByTime(10000);
    expect(replay.emitted('close')).toHaveLength(1);
  });
  it('cancels speech and timers on early dismissal or unmount', async () => {
    const { speak, cancel } = mockSpeech();
    narrationEnabled.value = true;
    const w = tutorial();
    await w.get('[aria-label="Dismiss tutorial"]').trigger('click');
    expect(cancel).toHaveBeenCalledOnce();
    expect(speak.mock.calls[0][0].onend).toBeNull();
    expect(w.emitted('close')).toHaveLength(1);
    const other = tutorial();
    other.unmount();
    vi.advanceTimersByTime(40000);
    expect(other.emitted('close')).toBeUndefined();
  });
});
