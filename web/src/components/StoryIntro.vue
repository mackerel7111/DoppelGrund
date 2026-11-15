<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import type { Body } from '../data/types';
import { narrationEnabled, speechEngine, storyteller } from '../content/narration';
const emit = defineEmits<{ done: [world: Body] }>();
const img = (name: string): string => `${import.meta.env.BASE_URL}story/${name}.webp`;
const q = new URLSearchParams(window.location.search);
// Old scene links still open the destination choice.
const scene = ref(Number(q.get('intro')) > 1 ? 2 : 1);
const world = ref<Body | null>(
  q.get('world') === 'mars' ? 'mars' : q.get('world') === 'moon' ? 'moon' : null,
);
const root = ref<HTMLElement | null>(null);
const heading = ref<HTMLElement | null>(null);
const speech = speechEngine();
const speechError = ref('');
const titles = [
  'Let’s find another world on Earth.',
  'Where shall we explore together?',
  'Doppel is shy, and a little nervous',
];
const surfaceCaption = computed(() =>
  world.value === 'mars'
    ? 'Red dust, rocks, thin cold air. What if I get stuck?'
    : 'Craters, dust, freezing nights. What if I get stuck?',
);
const captions = [
  'I’m Doppel. Come with me to discover places on Earth that resemble the Moon and Mars.',
  'Choose the Moon or Mars. Then we’ll find its closest matches on Earth.',
];
let utterance: SpeechSynthesisUtterance | null = null;
let finished = false;
let previousFocus: HTMLElement | null = null;
function stopSpeech(): void {
  if (!utterance) return;
  utterance.onerror = null;
  speech?.cancel();
  utterance = null;
}
function narrate(): void {
  stopSpeech();
  speechError.value = '';
  if (!speech || !narrationEnabled.value || finished) return;
  try {
    utterance = storyteller(
      `${titles[scene.value - 1]} ${scene.value === 3 ? surfaceCaption.value : captions[scene.value - 1]}`,
      speech,
    );
    utterance.onerror = () => {
      speechError.value = 'You can follow the text or try narration again.';
    };
    speech.speak(utterance);
  } catch {
    speechError.value = 'Narration is unavailable. You can still follow the text.';
  }
}
function finish(): void {
  if (finished) return;
  finished = true;
  stopSpeech();
  emit('done', world.value ?? 'moon');
}
function next(): void {
  if (scene.value === 1) scene.value = 2;
  else if (scene.value === 2 && world.value) scene.value = 3;
  else if (scene.value === 3) finish();
}
function onKey(ev: KeyboardEvent): void {
  if (ev.key === 'Escape') {
    ev.preventDefault();
    finish();
  }
  if (ev.key !== 'Tab') return;
  const controls = Array.from(
    root.value?.querySelectorAll<HTMLElement>('button:not(:disabled)') ?? [],
  );
  const first = controls[0];
  const last = controls.at(-1);
  if (
    ev.shiftKey &&
    (document.activeElement === first || !controls.includes(document.activeElement as HTMLElement))
  ) {
    ev.preventDefault();
    last?.focus();
  } else if (!ev.shiftKey && document.activeElement === last) {
    ev.preventDefault();
    first?.focus();
  }
}
watch([scene, narrationEnabled], narrate);
watch(scene, async () => {
  await nextTick();
  heading.value?.focus();
});
onMounted(() => {
  previousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
  heading.value?.focus();
  window.addEventListener('keydown', onKey);
  narrate();
});
onBeforeUnmount(() => {
  finished = true;
  stopSpeech();
  window.removeEventListener('keydown', onKey);
  if (previousFocus?.isConnected) previousFocus.focus();
});
</script>
<template>
  <div
    ref="root"
    class="intro"
    :class="{ surface: scene === 3 }"
    role="dialog"
    aria-modal="true"
    aria-labelledby="intro-heading"
    aria-describedby="intro-caption"
  >
    <img class="backdrop" :src="img(scene === 3 ? `${world ?? 'moon'}-surface` : 'space')" alt="" />
    <header class="intro-header">
      <span class="brand">DoppelGrund</span>
      <div class="header-actions">
        <button
          v-if="speech"
          type="button"
          class="quiet"
          data-test="narration"
          :aria-pressed="narrationEnabled"
          @click="narrationEnabled = !narrationEnabled"
        >
          {{ narrationEnabled ? 'Mute narration' : 'Play narration' }}
        </button>
        <button type="button" class="quiet" data-test="skip" @click="finish">Skip intro</button>
      </div>
    </header>
    <main class="story" :class="{ choosing: scene === 2, 'surface-story': scene === 3 }">
      <div class="copy">
        <p v-if="scene < 3" class="eyebrow">
          {{ scene === 1 ? 'An invitation from Doppel' : 'Through Doppel’s eyes' }}
        </p>
        <h1 id="intro-heading" ref="heading" tabindex="-1">{{ titles[scene - 1] }}</h1>
        <p v-if="scene < 3" id="intro-caption" class="caption">{{ captions[scene - 1] }}</p>
        <p v-if="speechError" role="status">{{ speechError }}</p>
      </div>
      <div v-if="scene === 1" class="pair">
        <img
          class="doppel"
          :src="img('doppel')"
          alt="Doppel, your friendly rover guide"
          draggable="false"
        />
        <button
          type="button"
          class="target telescope"
          data-test="next"
          aria-label="Look through the telescope"
          @click="next"
        >
          <img :src="img('telescope')" alt="" draggable="false" /><span class="callout"
            >Click the telescope ↗</span
          >
        </button>
      </div>
      <div v-else-if="scene === 2" class="worlds" role="group" aria-label="Choose our destination">
        <button
          v-for="b in ['moon', 'mars'] as const"
          :key="b"
          type="button"
          class="target world"
          :data-test="b"
          :aria-pressed="world === b"
          @click="
            world = b;
            scene = 3;
          "
        >
          <img :src="img(b)" alt="" draggable="false" />
          <span class="world-name">{{ b === 'moon' ? 'The Moon' : 'Mars' }}</span>
          <span class="world-description">{{
            b === 'moon' ? 'Craters & lunar plains' : 'Red deserts & ancient valleys'
          }}</span>
          <span v-if="world === b" class="selected">✓ Our destination</span>
        </button>
      </div>
      <div v-else class="surface-rover">
        <p id="intro-caption" class="speech-bubble">{{ surfaceCaption }}</p>
        <button
          type="button"
          class="target rover"
          data-test="surface-next"
          aria-label="Continue with Doppel to the explorer"
          @click="finish"
        >
          <img
            :src="img('doppel-confused')"
            alt="Doppel feeling nervous on the surface"
            draggable="false"
          />
        </button>
      </div>
    </main>
    <footer class="navigation" :class="{ opening: scene === 1 }">
      <button type="button" class="back" data-test="back" :disabled="scene === 1" @click="scene--">
        ← Back
      </button>
      <p class="instruction">
        {{
          scene === 1
            ? 'Click the telescope to begin'
            : scene === 2
              ? 'Choose the Moon or Mars'
              : 'Click Doppel to find practice grounds on Earth'
        }}
      </p>
      <button
        v-if="scene > 1"
        type="button"
        class="primary"
        data-test="go"
        :disabled="!world"
        @click="next"
      >
        {{ scene === 2 ? 'Visit this world' : 'Find Earth matches' }} →
      </button>
    </footer>
  </div>
</template>
<style scoped>
.surface .backdrop {
  opacity: 1;
}
.surface .intro-header {
  background: #080f1cdb;
  border-radius: 0 0 12px 12px;
  padding-inline: 16px;
}
.surface-story {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  gap: 32px;
  min-height: 440px;
}
.surface-story .copy {
  max-width: 850px;
  text-align: center;
  background: #0b111deb;
  padding: 18px 24px;
  border: 1px solid var(--border);
  border-radius: 14px;
}
.surface-story h1 {
  font-size: clamp(24px, 2.5vw, 36px);
}
.surface-rover {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 20px;
}
.speech-bubble {
  position: relative;
  max-width: 560px;
  margin: 0;
  padding: 16px 22px;
  border-radius: 16px;
  background: #0b1526;
  border: 1px solid #50647b;
  font-size: clamp(18px, 1.6vw, 24px);
  line-height: 1.5;
  text-align: center;
}
.speech-bubble::after {
  content: '';
  position: absolute;
  top: 100%;
  left: calc(50% - 10px);
  border: 10px solid transparent;
  border-top-color: #0b1526;
}
.rover {
  width: clamp(150px, 20vw, 250px);
}
@media (max-width: 899px) {
  .surface-story {
    min-height: 460px;
  }
}

.intro {
  position: fixed;
  inset: 0;
  z-index: 100;
  display: flex;
  flex-direction: column;
  overflow-y: auto;
  isolation: isolate;
  background: #080f1c;
  color: #f6f0e5;
  pointer-events: auto;
}
.backdrop {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
  z-index: -1;
  opacity: 0.5;
  pointer-events: none;
}
.intro-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin: 0 clamp(20px, 4vw, 72px);
  padding: 16px 0;
  border-bottom: 1px solid #ffffff26;
}
.brand {
  font-size: 22px;
  font-weight: 700;
}
.header-actions {
  display: flex;
  gap: 12px;
}
button {
  min-height: 44px;
  font-size: 16px;
}
.quiet {
  border-color: transparent;
  background: transparent;
  padding: 10px 14px;
}
.quiet:hover {
  background: #ffffff0d;
}
.story {
  flex: 1;
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1.1fr);
  align-items: center;
  gap: 40px;
  padding: 40px clamp(20px, 6vw, 100px);
}
.copy {
  max-width: 560px;
}
.eyebrow {
  color: #a4d9ee;
  font-size: 16px;
  margin: 0 0 20px;
}
h1 {
  font-size: clamp(34px, 4.2vw, 64px);
  line-height: 1.12;
  font-weight: 650;
  letter-spacing: -0.035em;
  text-wrap: balance;
  outline: none;
}
.caption {
  color: #d4dce5;
  font-size: clamp(18px, 1.6vw, 24px);
  line-height: 1.6;
  margin: 24px 0 0;
}
img {
  display: block;
  max-width: 100%;
  user-select: none;
}
.pair {
  display: flex;
  align-items: flex-end;
  gap: 16px;
}
.doppel {
  width: 44%;
  padding-bottom: 16px;
}
.target {
  background: transparent;
  border: 1px solid transparent;
  border-radius: 18px;
  padding: 0;
  color: inherit;
}
.target:hover img {
  filter: brightness(1.12);
}
.telescope {
  width: 54%;
}
.callout {
  display: block;
  margin-top: 16px;
  padding: 12px;
  border: 1px solid #9fdcf5;
  border-radius: 999px;
  background: #0d1b2c;
  font-size: 18px;
  color: #c0eaff;
}
.choosing {
  grid-template-columns: 1fr;
  gap: 24px;
  text-align: center;
}
.choosing .copy {
  max-width: 850px;
  margin-inline: auto;
}
.choosing h1 {
  font-size: clamp(30px, 3vw, 44px);
}
.choosing .caption {
  margin-top: 12px;
  font-size: 18px;
}
.worlds {
  display: flex;
  justify-content: center;
  align-items: stretch;
  gap: clamp(24px, 6vw, 90px);
}
.world {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: min(35vw, 280px);
  padding: 12px;
  gap: 10px;
}
.world img {
  width: min(100%, 230px);
  aspect-ratio: 1;
  object-fit: contain;
}
.world:hover,
.world[aria-pressed='true'] {
  border-color: #9fdcf5;
  color: inherit;
  background: #12233499;
}
.world-name {
  font-size: 26px;
  font-weight: 650;
}
.world-description {
  font-size: 15px;
  color: #cad3df;
}
.selected {
  font-size: 14px;
  color: #a4d9ee;
}
.navigation {
  display: grid;
  grid-template-columns: auto 1fr auto;
  gap: 24px;
  align-items: center;
  padding: 22px clamp(20px, 4vw, 72px) max(22px, env(safe-area-inset-bottom));
  background: #0a1322ed;
  border-top: 1px solid #ffffff26;
}
.opening {
  grid-template-columns: 1fr auto 1fr;
}
.opening .back {
  justify-self: start;
}
.instruction {
  text-align: center;
  font-size: clamp(20px, 1.7vw, 26px);
  margin: 0;
}
.back {
  background: transparent;
  border-color: #ffffff59;
  border-radius: 999px;
  padding: 12px 20px;
}
.primary {
  background: #a4d9ee;
  color: #0a1829;
  border-color: transparent;
  border-radius: 999px;
  padding: 12px 24px;
  font-weight: 650;
}
.primary:hover:not(:disabled) {
  background: #c1ebfa;
}
@media (max-width: 899px) {
  .story {
    grid-template-columns: 1fr;
    padding: 28px 24px;
    gap: 28px;
  }
  .copy {
    max-width: 680px;
  }
  .pair {
    max-width: 520px;
    justify-self: center;
  }
  .worlds {
    gap: 16px;
  }
  .world {
    width: min(42vw, 260px);
  }
  .world img {
    max-width: 180px;
  }
  .navigation {
    gap: 16px;
  }
  .instruction {
    grid-column: 1 / -1;
    grid-row: 1;
  }
  .primary {
    grid-column: 3;
  }
}
@media (max-width: 520px) {
  .intro-header {
    flex-wrap: wrap;
    gap: 8px;
  }
  .header-actions {
    width: 100%;
    justify-content: space-between;
  }
  .quiet {
    padding: 8px;
    font-size: 14px;
  }
  .world-name {
    font-size: 23px;
  }
  .world-description {
    font-size: 13px;
  }
  .callout {
    font-size: 14px;
    padding: 10px;
  }
  .navigation {
    padding: 18px 16px max(18px, env(safe-area-inset-bottom));
  }
  .back,
  .primary {
    padding: 10px 14px;
    font-size: 14px;
  }
}
@media (max-height: 650px) and (min-width: 900px) {
  .story {
    padding-block: 20px;
    gap: 16px;
  }
  .choosing h1 {
    font-size: 34px;
  }
  .world img {
    max-width: 150px;
  }
  .eyebrow {
    margin-bottom: 12px;
  }
}
</style>
