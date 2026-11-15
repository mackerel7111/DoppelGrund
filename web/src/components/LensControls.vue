<script setup lang="ts">
import { computed } from 'vue';
import { useSession } from '../stores/session';
import { DISPLAY_GROUP_IDS, type GroupId } from '../data/types';
import { GROUP_NAMES, LENS_NAMES, TERMS } from '../content/labels';

const s = useSession();

function onSlider(g: GroupId, ev: Event): void {
  s.setWeight(g, Number((ev.target as HTMLInputElement).value) / 100);
}

function pct(g: GroupId): number {
  return Math.round(s.effective[g] * 100);
}

const active = computed(() => DISPLAY_GROUP_IDS.filter((g) => pct(g) > 0));
const summary = computed(() => active.value.map((g) => `${GROUP_NAMES[g]} ${pct(g)}`).join(' · '));
</script>

<template>
  <div class="lens-controls">
    <div class="bar" aria-hidden="true">
      <span v-for="g in active" :key="g" :style="{ flexGrow: s.effective[g] }"></span>
    </div>
    <p
      class="meta num"
      data-test="lens-label"
      :title="s.lens === 'custom' ? '' : LENS_NAMES[s.lens]"
    >
      <template v-if="s.lens === 'custom'">Custom weights · </template>{{ summary }} %
      <button
        v-if="s.lens === 'custom'"
        type="button"
        class="reset"
        @click="s.setLens(s.lastPreset)"
      >
        Reset
      </button>
    </p>
    <details class="more">
      <summary>{{ TERMS.adjust }}</summary>
      <div class="sliders">
        <div v-for="g in DISPLAY_GROUP_IDS" :key="g" class="slider">
          <label :for="`w-${g}`"
            >{{ GROUP_NAMES[g]
            }}<template v-if="!s.available[g]">
              (no {{ s.body === 'mars' ? 'Mars' : 'Moon' }} data)</template
            ></label
          >
          <input
            :id="`w-${g}`"
            :data-test="`slider-${g}`"
            type="range"
            min="0"
            max="100"
            step="1"
            :value="pct(g)"
            :disabled="!s.available[g]"
            :aria-valuetext="`${pct(g)} percent`"
            @input="onSlider(g, $event)"
          />
          <output class="num" :for="`w-${g}`">{{ pct(g) }}%</output>
        </div>
        <p class="meta">Weights always add up to 100%</p>
      </div>
    </details>
  </div>
</template>

<style scoped>
.lens-controls {
  display: grid;
  gap: var(--s2);
}
p {
  margin: 0;
}
.bar {
  display: flex;
  gap: 2px;
  height: 6px;
}
.bar span {
  flex-basis: 0;
  border-radius: 3px;
  background: color-mix(in srgb, var(--text-muted) 50%, transparent);
}
.reset {
  min-height: 0;
  margin-left: var(--s1);
  padding: 0;
  border: 0;
  background: none;
  color: var(--text);
  font: inherit;
  text-decoration: underline;
}
.sliders {
  display: grid;
  gap: var(--s2);
}
.slider {
  display: grid;
  grid-template-columns: 110px 1fr 48px;
  gap: var(--s2);
  align-items: center;
}
output {
  text-align: right;
}
</style>
