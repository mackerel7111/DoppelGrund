<script setup lang="ts">
import { onMounted, ref, watch } from 'vue';
import aboutSource from '../content/about.md?raw';
import { useSession } from '../stores/session';

/** Minimal block parser for our own static markdown (headings, paragraphs, lists, tables). */
type Block =
  | { kind: 'h1' | 'h2' | 'p'; text: string }
  | { kind: 'ul'; items: string[] }
  | { kind: 'table'; head: string[]; rows: string[][] };

function parseBlocks(src: string): Block[] {
  const blocks: Block[] = [];
  const lines = src.split(/\r?\n/);
  let i = 0;
  const cells = (l: string) =>
    l
      .trim()
      .replace(/^\||\|$/g, '')
      .split('|')
      .map((c) => c.trim());
  while (i < lines.length) {
    const l = lines[i];
    if (!l.trim()) {
      i++;
    } else if (l.startsWith('## ')) {
      blocks.push({ kind: 'h2', text: l.slice(3) });
      i++;
    } else if (l.startsWith('# ')) {
      blocks.push({ kind: 'h1', text: l.slice(2) });
      i++;
    } else if (l.startsWith('- ')) {
      const items: string[] = [];
      while (i < lines.length && lines[i].startsWith('- ')) items.push(lines[i++].slice(2));
      blocks.push({ kind: 'ul', items });
    } else if (l.startsWith('|')) {
      const head = cells(l);
      i += 2; // skip the |---| separator
      const rows: string[][] = [];
      while (i < lines.length && lines[i].startsWith('|')) rows.push(cells(lines[i++]));
      blocks.push({ kind: 'table', head, rows });
    } else {
      const parts: string[] = [];
      while (i < lines.length && lines[i].trim() && !/^(#|- |\|)/.test(lines[i]))
        parts.push(lines[i++]);
      blocks.push({ kind: 'p', text: parts.join(' ') });
    }
  }
  return blocks;
}

const blocks = parseBlocks(aboutSource);
const s = useSession();
const dialog = ref<HTMLDialogElement | null>(null);

function sync(open: boolean): void {
  const d = dialog.value;
  if (!d) return;
  if (open && !d.open) d.showModal();
  if (!open && d.open) d.close();
}

function replay(): void {
  s.aboutOpen = false;
  s.introOpen = true;
}

onMounted(() => sync(s.aboutOpen));
watch(() => s.aboutOpen, sync);
</script>

<template>
  <dialog ref="dialog" class="about" aria-labelledby="about-title" @close="s.aboutOpen = false">
    <form method="dialog" class="close-row">
      <button type="button" class="replay" @click="replay">Replay intro</button>
      <button type="submit" aria-label="Close About and methods">Close ✕</button>
    </form>
    <template v-for="(b, k) in blocks" :key="k">
      <h2 v-if="b.kind === 'h1'" id="about-title">{{ b.text }}</h2>
      <h3 v-else-if="b.kind === 'h2'">{{ b.text }}</h3>
      <p v-else-if="b.kind === 'p'">{{ b.text }}</p>
      <ul v-else-if="b.kind === 'ul'">
        <li v-for="(it, j) in b.items" :key="j">{{ it }}</li>
      </ul>
      <table v-else-if="b.kind === 'table'">
        <thead>
          <tr>
            <th v-for="h in b.head" :key="h" scope="col">{{ h }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(r, j) in b.rows" :key="j">
            <td v-for="(c, m) in r" :key="m" :class="{ pending: c === 'Pending validation' }">
              {{ c }}
            </td>
          </tr>
        </tbody>
      </table>
    </template>
  </dialog>
</template>

<style scoped>
.about {
  width: min(820px, 94vw);
  max-height: 86vh;
  overflow: auto;
  background: var(--surface);
  color: var(--text);
  border: 1px solid var(--border);
  border-radius: var(--radius-card);
  padding: var(--s5);
  pointer-events: auto; /* .app sets none (globe pass-through) and it inherits */
}
.about::backdrop {
  background: rgba(5, 8, 14, 0.7);
}
.close-row {
  float: right;
}
.replay {
  background: none;
  border: 0;
  color: var(--text-muted);
}
h3 {
  margin-top: var(--s4);
  margin-bottom: var(--s2);
}
p,
li {
  line-height: 1.55;
}
.pending {
  color: var(--warn);
  font-weight: 600;
}
</style>
