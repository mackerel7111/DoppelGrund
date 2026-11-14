// @vitest-environment jsdom
import { beforeEach, describe, expect, it } from 'vitest';
import { createPinia, setActivePinia } from 'pinia';
import { mount } from '@vue/test-utils';
import MatchCards from '../src/components/MatchCards.vue';
import { emptyCardText } from '../src/content/labels';
import type { Card } from '../src/data/types';
import type { RowInfo } from '../src/stores/selectors';

const cards: Card[] = [
  { kind: 'overall', row: 4, S: 91.24, S_g: 91.24, coverage: 0.9 },
  { kind: 'terrain', row: 7, S: 88, S_g: 97.5, coverage: 1 },
  { kind: 'thermal', row: null, S: NaN, S_g: NaN, coverage: NaN, reason: 'no_eligible_match' },
  { kind: 'cold_ice', row: 9, S: 80, S_g: 70, coverage: 0.7 },
  { kind: 'composition', row: 11, S: 79, S_g: 99, coverage: 0.65 },
];

function info(row: number): RowInfo {
  return {
    row,
    lat: -23.5,
    lng: -69.1,
    noveltyKm: 412.4,
    featNovelty: 0.2,
    tags: row === 7 ? ['volcanic', 'periglacial'] : [],
    knownSite: false,
    stability: row === 4 ? 0.83 : null,
    stabilityAvailable: row !== 11,
    stabilityNote: row === 4 ? 'preset' : null,
  };
}

describe('MatchCards', () => {
  beforeEach(() => setActivePinia(createPinia()));

  it('renders five cards in C5 order with the agreed titles', () => {
    const w = mount(MatchCards, { props: { cards, rowInfo: info } });
    const titles = w.findAll('[data-test="title"]').map((h) => h.text());
    expect(titles).toEqual([
      'Best overall',
      'Best terrain match',
      'Best thermal match',
      'Best cold & ice match',
      'Best composition match',
    ]);
  });

  it('says in words when a card has no match', () => {
    const w = mount(MatchCards, { props: { cards, rowInfo: info } });
    expect(w.get('[data-test="card-thermal"] [data-test="empty"]').text()).toBe(
      emptyCardText('thermal'),
    );
  });

  it('shows the headline card in full and the others as one-button rows', () => {
    const w = mount(MatchCards, { props: { cards, rowInfo: info } });
    const overall = w.get('[data-test="card-overall"]').text();
    expect(overall).toContain('23.5°S, 69.1°W');
    expect(overall).toContain('91.2');
    expect(overall).toContain('90%');
    expect(overall).toContain('90% data coverage');
    expect(overall).toContain('412 km from known sites');
    const row = w.get('[data-test="card-terrain"]').text();
    expect(row).toContain('Best terrain match');
    expect(row).toContain('97.5');
    expect(row).toContain('23.5°S, 69.1°W');
    expect(row).toContain('overall 88.0');
  });

  it('explains data coverage with a title on the headline card', () => {
    const w = mount(MatchCards, { props: { cards, rowInfo: info } });
    expect(w.get('[data-test="card-overall"]').html()).toContain('title="Share of the weighted');
  });

  it('emits select(row) from a row button; aria-pressed follows selectedRow', async () => {
    const w = mount(MatchCards, { props: { cards, rowInfo: info, selectedRow: 9 } });
    expect(w.get('[data-test="open-cold_ice"]').attributes('aria-pressed')).toBe('true');
    expect(w.get('[data-test="open-terrain"]').attributes('aria-pressed')).toBe('false');
    await w.get('[data-test="open-terrain"]').trigger('click');
    await w.get('[data-test="open-overall"]').trigger('click');
    expect(w.emitted('select')).toEqual([[7], [4]]);
  });
});
