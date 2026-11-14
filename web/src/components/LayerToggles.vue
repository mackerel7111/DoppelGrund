<script setup lang="ts">
import { useSession, type LayerId } from '../stores/session';
import { LAYER_ORDER, OVERLAY_STYLES, cssColor } from '../map/overlayLayers';

const s = useSession();

function toggle(id: LayerId): void {
  s.toggleLayer(id);
  if (s.layers[id]) void s.ensureLayer(id);
}
</script>

<template>
  <fieldset class="layers">
    <legend>Layers <span class="meta">(context only, never scored)</span></legend>
    <label v-for="id in LAYER_ORDER" :key="id" class="toggle">
      <input
        type="checkbox"
        :checked="s.layers[id]"
        :data-test="`layer-${id}`"
        @change="toggle(id)"
      />
      <span
        class="swatch"
        :class="{ hollow: OVERLAY_STYLES[id].hollow }"
        :style="{ '--c': cssColor(OVERLAY_STYLES[id].color) }"
        aria-hidden="true"
      />
      <span>{{ OVERLAY_STYLES[id].label }}</span>
      <span v-if="s.layers[id] && !s.layerData[id]" class="meta">(not in bundle)</span>
    </label>
  </fieldset>
</template>

<style scoped>
.layers {
  border: 0;
  margin: 0;
  padding: 0;
  display: flex;
  flex-wrap: wrap;
  gap: var(--s2) var(--s4);
}
legend {
  padding: 0;
  margin-bottom: var(--s1);
  font-weight: 600;
}
.toggle {
  display: inline-flex;
  gap: var(--s2);
  align-items: center;
  cursor: pointer;
}
.swatch {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: var(--c);
}
.swatch.hollow {
  background: transparent;
  border: 2px solid var(--c);
}
</style>
