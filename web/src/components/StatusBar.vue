<script setup lang="ts">
export interface StatusTimings {
  loadMs: number | null;
  rankMs: number | null;
  cardsMs: number | null;
  paintMs: number | null;
}

const props = defineProps<{
  synthetic: boolean | null;
  nHex: number | null;
  timings: StatusTimings;
  message?: string;
}>();

function ms(v: number | null): string {
  return v === null ? '—' : `${v.toFixed(v < 10 ? 1 : 0)} ms`;
}
</script>

<template>
  <footer class="status" role="status" aria-live="polite">
    <span>
      Data:
      <strong v-if="props.synthetic === true" class="synthetic">synthetic</strong>
      <strong v-else-if="props.synthetic === false">real bundle</strong>
      <span v-else>loading…</span>
      <span v-if="props.nHex !== null" class="num"> · {{ props.nHex.toLocaleString() }} hexes</span>
    </span>
    <span class="num">Load {{ ms(props.timings.loadMs) }}</span>
    <span class="num" :class="{ slow: (props.timings.rankMs ?? 0) > 150 }">
      Rank {{ ms(props.timings.rankMs) }}
    </span>
    <span class="num">Cards {{ ms(props.timings.cardsMs) }}</span>
    <span class="num">Paint {{ ms(props.timings.paintMs) }}</span>
    <span v-if="props.message" class="msg">{{ props.message }}</span>
  </footer>
</template>

<style scoped>
.status {
  display: flex;
  flex-wrap: wrap;
  gap: var(--s4);
  align-items: center;
  padding: var(--s1) var(--s3);
  font-size: var(--fs-meta);
  color: var(--text-muted);
  border-top: 1px solid var(--border);
  background: var(--surface);
}
.synthetic {
  color: var(--warn);
}
.slow {
  color: var(--danger);
}
.msg {
  margin-left: auto;
}
</style>
