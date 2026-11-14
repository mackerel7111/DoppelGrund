<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import type { Body } from '../data/types';

const emit = defineEmits<{ done: [world: Body] }>();

const img = (name: string): string => `${import.meta.env.BASE_URL}story/${name}.webp`;
const NAME: Record<Body, string> = { moon: 'Moon', mars: 'Mars' };
const HINTS = ['Click the telescope', 'Pick a world', 'Click Doppel', 'Click Earth'];
const CAPTIONS = [
  'This is Doppel. He lives on Earth and dreams of space missions',
  'The Moon and Mars. Doppel wants to explore both',
  'Doppel is shy, and a little nervous',
  'Earth has deserts, ice, lava fields and craters too',
  'DoppelGrund compares every patch of land on Earth with a place on the Moon or Mars and finds the closest matches.',
];

// `?intro=<1-5>` starts at that scene and `&world=mars` presets the world (screenshots)
const q = new URLSearchParams(window.location.search);
const scene = ref(Math.min(5, Math.max(1, Number(q.get('intro')) || 1)));
const world = ref<Body | null>(q.get('world') === 'mars' ? 'mars' : null);
const w = (): Body => world.value ?? 'moon';
const other = (): Body => (w() === 'moon' ? 'mars' : 'moon');

const root = ref<HTMLElement | null>(null);
const hint = ref(false);
let timer = 0;
let finished = false;
let first = true;

function finish(b: Body): void {
  if (finished) return;
  finished = true;
  emit('done', b);
}
function pick(b: Body): void {
  world.value = b;
  scene.value = 3;
}
function hop(ev: Event): void {
  (ev.currentTarget as HTMLElement).classList.add('hop');
  scene.value++;
}
function onKey(ev: KeyboardEvent): void {
  if (ev.key === 'Escape') finish(w());
}

watch(
  scene,
  async () => {
    hint.value = false;
    window.clearTimeout(timer);
    timer = window.setTimeout(() => (hint.value = true), 4000);
    await nextTick();
    // first scene: focus the dialog itself (no ring); later scenes: the new target
    const t = root.value?.querySelector<HTMLElement>('.scene:not(.fade-leave-active) [data-test]');
    (first ? root.value : t)?.focus();
    first = false;
  },
  { immediate: true },
);
onMounted(() => window.addEventListener('keydown', onKey));
onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKey);
  window.clearTimeout(timer);
});
</script>

<template>
  <div ref="root" class="intro" tabindex="-1" role="dialog" aria-modal="true" aria-label="Intro">
    <Transition name="fade">
      <div v-if="scene === 1" key="1" class="scene">
        <img class="bg" :src="img('space')" alt="" />
        <div class="pair">
          <button
            type="button"
            class="target telescope"
            data-test="next"
            aria-label="Look through the telescope"
            @click="scene = 2"
          >
            <img :src="img('telescope')" alt="" draggable="false" />
          </button>
          <img class="doppel slide" :src="img('doppel')" alt="Doppel" draggable="false" />
        </div>
      </div>

      <div v-else-if="scene === 2" key="2" class="scene">
        <div class="eyepiece">
          <img class="bg" :src="img('space')" alt="" />
          <div class="worlds">
            <button
              v-for="b in ['moon', 'mars'] as const"
              :key="b"
              type="button"
              class="target world"
              :data-test="b"
              :aria-label="NAME[b]"
              @click="pick(b)"
            >
              <img :src="img(b)" alt="" draggable="false" />
              <span class="name">{{ NAME[b] }}</span>
            </button>
          </div>
        </div>
      </div>

      <div v-else-if="scene === 3" key="3" class="scene">
        <img class="bg" :src="img(`${w()}-surface`)" alt="" />
        <div class="stack low">
          <p class="bubble">
            {{
              w() === 'moon'
                ? 'Craters, dust, freezing nights. What if I get stuck?'
                : 'Red dust, rocks, thin cold air. What if I get stuck?'
            }}
          </p>
          <button
            type="button"
            class="target doppel-btn"
            data-test="next"
            aria-label="Doppel"
            @click="hop"
          >
            <img :src="img('doppel-confused')" alt="" draggable="false" />
          </button>
        </div>
      </div>

      <div v-else-if="scene === 4" key="4" class="scene">
        <img class="bg" :src="img('space')" alt="" />
        <div class="stack mid">
          <p class="bubble right">
            I should practise at home first. Some place on Earth must feel like the
            {{ NAME[w()] }}. But where?
          </p>
          <div class="row">
            <button
              type="button"
              class="target earth"
              data-test="next"
              aria-label="Earth"
              @click="scene = 5"
            >
              <img :src="img('earth')" alt="" draggable="false" />
            </button>
            <img class="doppel-side" :src="img('doppel')" alt="Doppel" draggable="false" />
          </div>
        </div>
      </div>

      <div v-else key="5" class="scene">
        <img class="bg" :src="img('space')" alt="" />
        <div class="stack mid">
          <div class="row compare">
            <img :src="img(w())" alt="" draggable="false" />
            <span class="approx" aria-hidden="true">≈</span>
            <img :src="img('earth')" alt="" draggable="false" />
          </div>
          <img class="doppel-small" :src="img('doppel')" alt="Doppel" draggable="false" />
          <button type="button" class="primary" data-test="go" @click="finish(w())">
            Find {{ NAME[w()] }} practice grounds
          </button>
          <button type="button" class="quiet" data-test="other" @click="finish(other())">
            {{ NAME[other()] }} instead
          </button>
        </div>
      </div>
    </Transition>

    <div class="caption" aria-live="polite">
      <Transition name="rise">
        <p :key="scene">
          {{ CAPTIONS[scene - 1] }}
          <template v-if="scene === 5">
            <br />
            <span class="muted">Doppel's practice grounds</span>
          </template>
        </p>
      </Transition>
    </div>

    <Transition name="fade">
      <p v-if="hint && scene < 5" class="hint">{{ HINTS[scene - 1] }}</p>
    </Transition>
    <button type="button" class="quiet skip" data-test="skip" @click="finish(w())">
      Skip intro
    </button>
    <div class="dots" aria-hidden="true">
      <i v-for="n in 5" :key="n" :class="{ on: n === scene }" />
    </div>
  </div>
</template>

<style scoped>
.intro {
  position: fixed;
  inset: 0;
  z-index: 100;
  overflow: hidden;
  background: var(--bg);
  color: var(--text);
  pointer-events: auto;
  outline: none;
}
.scene {
  position: absolute;
  inset: 0;
}
img {
  display: block;
  max-width: 100%;
  user-select: none;
}
.bg {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
}

/* buttons that wrap an image: no chrome, quiet hover and focus */
.target {
  padding: 0;
  background: none;
  border: 0;
  border-radius: var(--radius-card);
  min-height: 0;
  cursor: pointer;
}
.target:hover img {
  filter: brightness(1.12);
}
.target:focus-visible,
.quiet:focus-visible,
.primary:focus-visible {
  outline: 2px solid var(--accent-earth);
  outline-offset: 2px;
}
.target img {
  width: 100%;
}

/* scene 1 */
.pair {
  --t: min(47vh, 42vw); /* telescope width; Doppel stands at about 60% of its height */
  position: absolute;
  left: 40%;
  bottom: 76px;
  width: max-content;
  transform: translateX(-50%);
  display: flex;
  align-items: flex-end;
  gap: var(--s4);
}
.telescope {
  flex: none;
  width: var(--t);
}
.doppel {
  flex: none;
  width: calc(var(--t) * 0.8);
}
.slide {
  animation: slide-in 600ms var(--ease) both;
}

/* scene 2 */
.eyepiece {
  position: absolute;
  left: 50%;
  top: 54%;
  width: min(90vw, 72vh);
  aspect-ratio: 1;
  transform: translate(-50%, -50%);
  border-radius: 50%;
  border: 1px solid var(--border);
  overflow: hidden;
}
.worlds {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6%;
}
.world {
  position: relative;
  width: 38%;
}
.name {
  position: absolute;
  top: 100%;
  left: 0;
  right: 0;
  margin-top: var(--s2);
  text-align: center;
  color: var(--text-muted);
  opacity: 0;
  transition: opacity var(--dur) var(--ease);
}
.world:hover .name,
.world:focus-visible .name {
  opacity: 1;
}

/* scenes 3 to 5: bubble and figures */
.stack {
  position: absolute;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--s4);
  width: min(560px, 92vw);
}
.stack.low {
  bottom: 76px;
}
.stack.mid {
  width: max-content;
  max-width: 92vw;
  top: 54%;
  transform: translate(-50%, -50%);
}
.doppel-btn {
  width: clamp(110px, 24vw, 200px);
}
.row {
  display: flex;
  align-items: flex-end;
  justify-content: center;
  gap: var(--s5);
  width: 100%;
}
.earth {
  width: min(52vw, 40vh, 340px);
}
.doppel-side {
  width: min(31vw, 23vh, 195px);
}
.compare {
  align-items: center;
  gap: var(--s4);
}
.compare img {
  width: min(28vw, 24vh, 220px);
}
.approx {
  font-size: 32px;
  color: var(--text-muted);
}
.doppel-small {
  width: min(21vw, 16vh, 130px);
}
.primary {
  background: var(--accent-earth);
  color: var(--bg);
  border: 0;
  border-radius: var(--radius-control);
  padding: var(--s3) var(--s5);
  font-weight: 600;
  min-height: 44px;
}
.primary:hover {
  filter: brightness(1.1);
}

.bubble {
  position: relative;
  margin: 0;
  max-width: min(380px, 86vw);
  text-wrap: pretty;
  padding: var(--s3) var(--s4);
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 12px;
  color: var(--text);
  font-size: var(--fs-card);
}
.bubble::after {
  content: '';
  position: absolute;
  top: 100%;
  left: var(--tail, 50%);
  width: 12px;
  height: 12px;
  margin: -7px 0 0 -6px;
  background: var(--surface);
  border: solid var(--border);
  border-width: 0 1px 1px 0;
  transform: rotate(45deg);
}
.bubble.right {
  --tail: calc(100% - min(15.5vw, 11.5vh, 97px));
  align-self: flex-end;
}

/* chrome shared by every scene */
.caption {
  position: absolute;
  top: var(--s6);
  left: 50%;
  transform: translateX(-50%);
  display: grid;
  width: min(640px, 90vw);
  pointer-events: none;
}
.caption p {
  grid-area: 1 / 1;
  justify-self: center;
  margin: 0;
  padding: var(--s2) var(--s4);
  background: rgba(4, 6, 11, 0.72);
  border-radius: var(--radius-card);
  text-align: center;
  text-wrap: pretty;
  font-size: var(--fs-section);
  line-height: 1.35;
}
.muted {
  color: var(--text-muted);
}
.hint {
  position: absolute;
  bottom: 40px;
  left: 50%;
  transform: translateX(-50%);
  margin: 0;
  padding: var(--s1) var(--s3);
  background: rgba(4, 6, 11, 0.72);
  border-radius: var(--radius-card);
  color: var(--text-muted);
  pointer-events: none;
}
.quiet {
  background: none;
  border: 0;
  color: var(--text-muted);
  min-height: 0;
  padding: var(--s2) var(--s3);
}
.quiet:hover {
  color: var(--text);
}
.skip {
  background: rgba(4, 6, 11, 0.72);
  position: absolute;
  top: var(--s3);
  right: var(--s3);
  z-index: 1;
}
.dots {
  position: absolute;
  bottom: var(--s4);
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  gap: var(--s2);
  padding: var(--s1) var(--s2);
  background: rgba(4, 6, 11, 0.72);
  border-radius: var(--radius-card);
}
.dots i {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--border);
}
.dots i.on {
  background: var(--text);
}

/* motion: opacity and transform only */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 400ms var(--ease);
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
.rise-enter-active {
  transition:
    opacity 400ms var(--ease),
    transform 400ms var(--ease);
}
.rise-leave-active {
  transition: opacity 200ms var(--ease);
}
.rise-enter-from {
  opacity: 0;
  transform: translateY(8px);
}
.rise-leave-to {
  opacity: 0;
}
.hop {
  animation: hop 200ms var(--ease);
}
@keyframes slide-in {
  from {
    opacity: 0;
    transform: translateX(48px);
  }
}
@keyframes hop {
  50% {
    transform: translateY(-8px);
  }
}
@media (max-width: 600px) {
  .caption {
    top: 52px;
  }
  .caption p {
    font-size: var(--fs-card);
  }
  .pair {
    left: 50%;
  }
}
@media (prefers-reduced-motion: reduce) {
  .slide,
  .hop {
    animation: none;
  }
  .rise-enter-from {
    transform: none;
  }
}
</style>
