// Display preferences, remembered per browser. Storage can be unavailable
// (private windows, blocked site data), so every access is guarded and the
// defaults stand in.

export type DeckName = 'four' | 'classic';

// Ink per suit, per deck. Every value clears
// WCAG AA against the surface it is drawn on.
export const DECKS: Record<DeckName, Record<'face' | 'dim' | 'lt', Record<string, string>>> = {
  classic: {
    face: { S: '#101820', H: '#c8102e', D: '#c8102e', C: '#101820' },
    dim: { S: '#101820', H: '#8c0a20', D: '#8c0a20', C: '#101820' },
    lt: { S: '#dbe3ea', H: '#ff8d9c', D: '#ff8d9c', C: '#dbe3ea' },
  },
  four: {
    face: { S: '#101820', H: '#c8102e', D: '#c2410c', C: '#0b6e35' },
    dim: { S: '#101820', H: '#8c0a20', D: '#7a2606', C: '#084d25' },
    lt: { S: '#dbe3ea', H: '#ff8d9c', D: '#ffb073', C: '#6fd69b' },
  },
};

export const DECK_LABELS: Record<DeckName, string> = {
  four: 'Four-colour deck',
  classic: 'Classic two-colour deck',
};

export const DECK_HELP: Record<DeckName, string> = {
  four: 'Spades black, hearts red, diamonds orange, clubs green.',
  classic: 'Spades and clubs black, hearts and diamonds red.',
};

const KEY = 'shb-settings';

interface Stored {
  deck: DeckName;
  trumpFirst: boolean;
  showStrength: boolean;
  autoPlay: boolean;
  fastPlay: boolean;
}

function load(): Partial<Stored> {
  try {
    return JSON.parse(localStorage.getItem(KEY) ?? '{}');
  } catch {
    return {};
  }
}

class Settings {
  deck = $state<DeckName>('four');
  trumpFirst = $state(false);
  showStrength = $state(true);
  /** Play a card for you when it's the only legal one. */
  autoPlay = $state(false);
  /** Move on to the next trick by itself after a short pause. */
  fastPlay = $state(false);

  constructor() {
    const s = load();
    if (s.deck === 'four' || s.deck === 'classic') this.deck = s.deck;
    if (typeof s.trumpFirst === 'boolean') this.trumpFirst = s.trumpFirst;
    if (typeof s.showStrength === 'boolean') this.showStrength = s.showStrength;
    if (typeof s.autoPlay === 'boolean') this.autoPlay = s.autoPlay;
    if (typeof s.fastPlay === 'boolean') this.fastPlay = s.fastPlay;
  }

  save(): void {
    try {
      localStorage.setItem(KEY, JSON.stringify({
        deck: this.deck, trumpFirst: this.trumpFirst,
        showStrength: this.showStrength,
        autoPlay: this.autoPlay, fastPlay: this.fastPlay,
      }));
    } catch {
      // Not remembered; the page still works.
    }
  }

  /** Re-point the --suit-* custom properties at the chosen deck. */
  applyDeck(): void {
    const d = DECKS[this.deck];
    const style = document.documentElement.style;
    for (const s of ['S', 'H', 'D', 'C']) {
      const k = s.toLowerCase();
      style.setProperty(`--suit-${k}`, d.face[s]);
      style.setProperty(`--suit-${k}-dim`, d.dim[s]);
      style.setProperty(`--suit-${k}-lt`, d.lt[s]);
    }
  }
}

export const settings = new Settings();
