import { ref } from 'vue';

// Shared for this visit. The user opts into speech in the intro or tutorial.
export const narrationEnabled = ref(false);
export function speechEngine(): SpeechSynthesis | null {
  return typeof window.speechSynthesis !== 'undefined' &&
    typeof window.SpeechSynthesisUtterance !== 'undefined'
    ? window.speechSynthesis
    : null;
}
export function storyteller(text: string, speech: SpeechSynthesis): SpeechSynthesisUtterance {
  const utterance = new SpeechSynthesisUtterance(text);
  const english = speech.getVoices().filter((voice) => /^en(?:-|$)/i.test(voice.lang));
  const voice =
    english.find((voice) =>
      /natural|samantha|jenny|aria|google uk english female/i.test(voice.name),
    ) ??
    english.find((voice) => voice.default) ??
    english[0];
  if (voice) utterance.voice = voice;
  utterance.lang = voice?.lang ?? 'en-US';
  utterance.rate = 0.88;
  utterance.pitch = 1;
  return utterance;
}
