<script setup lang="ts">
import { useSession } from '../stores/session';
import { SYNTHETIC_BANNER } from '../content/labels';

const s = useSession();
</script>

<template>
  <header class="header">
    <h1 class="title" title="Global Analogue Discovery Engine">DoppelGrund</h1>
    <span v-if="s.synthetic === true" class="pill" role="note">{{ SYNTHETIC_BANNER }}</span>
    <div class="controls">
      <div v-if="!s.aboutOpen" class="seg" role="group" aria-label="View">
        <button type="button" :aria-pressed="s.view === '3d'" @click="s.setView('3d')">3D</button>
        <button type="button" :aria-pressed="s.view === '2d'" @click="s.setView('2d')">2D</button>
      </div>
      <button
        v-if="s.aboutOpen"
        type="button"
        class="back-btn"
        @click="s.aboutOpen = false"
      >
        &larr; Back to Explorer
      </button>
      <button v-else type="button" @click="s.aboutOpen = true">About</button>
    </div>
  </header>
</template>

<style scoped>
.header {
  display: flex;
  align-items: center;
  gap: var(--s4);
  padding: var(--s2) var(--s4);
  pointer-events: none;
}
.title {
  font-size: var(--fs-section);
  letter-spacing: 0.04em;
}
.pill {
  padding: 2px var(--s3);
  border: 1px solid var(--warn);
  border-radius: 999px;
  background: rgba(242, 181, 68, 0.12);
  color: var(--warn);
  font-size: var(--fs-meta);
  font-weight: 600;
  pointer-events: auto;
}
.controls {
  display: flex;
  gap: var(--s3);
  margin-left: auto;
  pointer-events: auto;
}
.back-btn {
  border-color: var(--accent-earth);
  color: var(--accent-earth);
}
</style>