<script setup lang="ts">
import { computed, onBeforeUnmount, watch } from 'vue';
import type { Body } from '../data/types';
import { narrationEnabled, speechEngine, storyteller } from '../content/narration';
const props = defineProps<{ body: Body }>();
const emit = defineEmits<{ close: [] }>();
const speech = speechEngine();
const message = computed(
  () =>
    `Pick a place on ${props.body === 'mars' ? 'Mars' : 'the Moon'}. Let’s discover its closest matches on Earth.`,
);
const robot = `${import.meta.env.BASE_URL}story/doppel.webp`;
let utterance: SpeechSynthesisUtterance | null = null;
let timer: ReturnType<typeof setTimeout> | undefined;
let closed = false;
function stop(): void {
  clearTimeout(timer);
  if (utterance) {
    utterance.onstart = null;
    utterance.onend = null;
    utterance.onerror = null;
    speech?.cancel();
    utterance = null;
  }
}
function close(): void {
  if (closed) return;
  closed = true;
  stop();
  emit('close');
}
function dismissAfter(ms: number): void {
  clearTimeout(timer);
  timer = setTimeout(close, ms);
}
function start(): void {
  stop();
  if (closed) return;
  dismissAfter(10000); // reading time when muted, unsupported or autoplay is blocked
  if (!speech || !narrationEnabled.value) return;
  try {
    utterance = storyteller(message.value, speech);
    utterance.onstart = () => dismissAfter(30000); // guard against a missing end event
    utterance.onend = () => dismissAfter(900);
    utterance.onerror = () => dismissAfter(10000);
    speech.speak(utterance);
  } catch {
    dismissAfter(10000);
  }
}
watch([message, narrationEnabled], start, { immediate: true });
onBeforeUnmount(() => {
  closed = true;
  stop();
  if (document.activeElement?.closest('.explorer-tutorial'))
    document.getElementById('explorer-back')?.focus();
});
</script>
<template>
  <section class="explorer-tutorial" aria-label="Doppel's quick tutorial">
    <img :src="robot" alt="" class="guide" />
    <div class="guidance">
      <span class="guide-name">Doppel · Quick tutorial</span>
      <p role="status">{{ message }}</p>
      <span class="tip"
        >Choose a landmark in the panel or click {{ body === 'mars' ? 'Mars' : 'the Moon' }}.</span
      >
    </div>
    <div class="actions">
      <button
        v-if="speech"
        type="button"
        :aria-pressed="narrationEnabled"
        @click="narrationEnabled = !narrationEnabled"
      >
        {{ narrationEnabled ? 'Mute' : 'Listen' }}
      </button>
      <button type="button" aria-label="Dismiss tutorial" @click="close">×</button>
    </div>
  </section>
</template>
<style scoped>
.explorer-tutorial {
  position: fixed;
  top: 64px;
  left: calc(var(--panel-w) + 20px);
  right: 24px;
  z-index: 4;
  display: flex;
  align-items: center;
  gap: 16px;
  max-width: 790px;
  padding: 16px 20px;
  background: rgba(18, 24, 38, 0.97);
  border: 1px solid #577891;
  border-radius: 16px;
  box-shadow: 0 8px 28px #0005;
  pointer-events: auto;
}
.guide {
  width: 66px;
  height: 60px;
  object-fit: contain;
  flex-shrink: 0;
}
.guidance {
  flex: 1;
  min-width: 0;
}
.guide-name {
  color: #a4d9ee;
  font-size: 13px;
}
p {
  margin: 6px 0;
  font-size: 18px;
  line-height: 1.45;
  color: var(--text);
}
.tip {
  font-size: 13px;
  color: var(--text-muted);
}
.actions {
  display: flex;
  align-items: center;
  gap: 8px;
}
button {
  min-height: 44px;
  min-width: 44px;
}
@media (max-width: 1099px) {
  .explorer-tutorial {
    top: auto;
    bottom: max(16px, env(safe-area-inset-bottom));
    left: 16px;
    right: 16px;
    max-width: none;
  }
}
@media (max-width: 600px) {
  .explorer-tutorial {
    gap: 10px;
    padding: 12px;
    align-items: flex-start;
  }
  .guide {
    width: 40px;
    height: 44px;
  }
  .actions {
    flex-direction: column-reverse;
    gap: 4px;
  }
  p {
    font-size: 16px;
  }
}
</style>
