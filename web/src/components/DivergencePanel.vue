<script setup lang="ts">
import { computed } from 'vue';
import type { Body } from '../data/types';
import type { FeatureRow } from '../stores/selectors';
import { divergenceItems, type DivergenceItem } from '../content/divergence';

const props = defineProps<{ body: Body; targetLat: number; rows: FeatureRow[] }>();
const items = computed(() => divergenceItems(props.body, props.targetLat, props.rows));

const SECTIONS: { kind: DivergenceItem['kind']; title?: string }[] = [
  { kind: 'not_replicable', title: 'Not replicable on Earth' },
  { kind: 'body', title: 'Body-specific limits' },
  { kind: 'weak', title: 'Weak matches (similarity < 0.2)' },
  { kind: 'missing' }, // one self-describing line
];
</script>

<template>
  <section class="divergence" aria-label="Where this analogy fails">
    <h3>Where this analogy fails</h3>
    <template v-for="sec in SECTIONS" :key="sec.kind">
      <div
        v-if="items.some((i) => i.kind === sec.kind)"
        class="group"
        :data-test="`div-${sec.kind}`"
      >
        <h4 v-if="sec.title">{{ sec.title }}</h4>
        <ul>
          <li
            v-for="(it, k) in items.filter((i) => i.kind === sec.kind)"
            :key="k"
            :class="sec.kind"
          >
            {{ it.text }}
          </li>
        </ul>
      </div>
    </template>
  </section>
</template>

<style scoped>
.divergence {
  display: grid;
  gap: var(--s2);
}
h4 {
  font-size: var(--fs-body);
  color: var(--text-muted);
  margin-bottom: var(--s1);
}
ul {
  margin: 0;
  padding-left: var(--s4);
  display: grid;
  gap: 2px;
}
li.not_replicable::marker {
  color: var(--danger);
}
li.weak {
  color: var(--warn);
}
li.missing {
  color: var(--text-muted);
}
</style>
