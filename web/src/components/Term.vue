<script setup lang="ts">
import { GLOSSARY } from '../content/labels';

defineProps<{ k: keyof typeof GLOSSARY }>();
// ponytail: native title tooltip (mouse only), hidden text serves screen readers; add a popover if touch users need it
</script>

<template>
  <span class="term" :title="GLOSSARY[k]"
    ><slot /><span class="visually-hidden"> ({{ GLOSSARY[k] }})</span></span
  >
</template>

<style scoped>
.term {
  cursor: help;
  text-decoration: underline dotted var(--text-muted);
  text-underline-offset: 3px;
}
</style>
