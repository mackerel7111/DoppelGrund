<script setup lang="ts">
import type { FeatureRow } from '../stores/selectors';
import { formatValue } from '../stores/selectors';
import { FEATURE_LABELS, GROUP_NAMES, LITH_LABELS, NOT_MEASURED } from '../content/labels';
import { HIDDEN_GROUPS, LITH_CLASSES, type GroupId } from '../data/types';

const props = defineProps<{ rows: FeatureRow[]; targetLabel: string; bodyName: string }>();

function lithSummary(v: number[] | undefined): string {
  if (!v || v.some((x) => !Number.isFinite(x))) return NOT_MEASURED;
  return LITH_CLASSES.map((c, i) => [LITH_LABELS[c], v[i]] as const)
    .filter(([, f]) => f >= 0.05)
    .sort((a, b) => b[1] - a[1])
    .map(([name, f]) => `${name} ${(f * 100).toFixed(0)}%`)
    .join(', ');
}

function sim(v: number): string {
  return Number.isFinite(v) ? v.toFixed(2) : NOT_MEASURED;
}
</script>

<template>
  <table class="features">
    <caption class="visually-hidden">
      Measurements:
      {{
        props.targetLabel
      }}
      vs Earth place
    </caption>
    <thead>
      <tr>
        <th scope="col">Measurement</th>
        <th scope="col">{{ props.bodyName }}</th>
        <th scope="col">Earth</th>
        <th scope="col">Similarity</th>
      </tr>
    </thead>
    <tbody>
      <tr v-for="r in props.rows.filter((x) => !HIDDEN_GROUPS.includes(x.group))" :key="r.name">
        <th scope="row">
          {{ r.name === 'lith' ? 'Lithology' : FEATURE_LABELS[r.name] }}
          <span class="meta">{{ GROUP_NAMES[r.group as GroupId] }} · {{ r.unit }}</span>
          <span class="meta">{{
            r.sourceEarth === r.sourceTarget
              ? r.sourceEarth
              : `${r.sourceEarth} / ${r.sourceTarget}`
          }}</span>
        </th>
        <template v-if="r.name === 'lith'">
          <td :class="{ missing: lithSummary(r.targetLith) === NOT_MEASURED }">
            {{ lithSummary(r.targetLith) }}
          </td>
          <td :class="{ missing: lithSummary(r.earthLith) === NOT_MEASURED }">
            {{ lithSummary(r.earthLith) }}
          </td>
        </template>
        <template v-else>
          <td class="num" :class="{ missing: !Number.isFinite(r.target) }">
            {{ formatValue(r.target, r.unit) ?? NOT_MEASURED }}
          </td>
          <td class="num" :class="{ missing: !Number.isFinite(r.earth) }">
            {{ formatValue(r.earth, r.unit) ?? NOT_MEASURED }}
          </td>
        </template>
        <td
          class="num"
          :class="{ weak: r.similarity < 0.2, missing: !Number.isFinite(r.similarity) }"
        >
          {{ sim(r.similarity) }}<template v-if="r.similarity < 0.2"> weak</template>
        </td>
      </tr>
    </tbody>
  </table>
</template>

<style scoped>
.features {
  table-layout: fixed;
  font-size: var(--fs-meta);
}
th,
td {
  padding-inline: var(--s1);
  overflow-wrap: break-word;
}
th {
  font-weight: 500;
}
thead th:first-child {
  width: 34%; /* fixed layout takes column widths from the first row */
}
th[scope='row'] {
  color: var(--text);
}
th[scope='row'] .meta {
  display: block;
  font-weight: 400;
}
.missing {
  color: var(--text-muted);
}
.weak {
  color: var(--danger);
}
</style>
