// Which layout the screen gets: the phone column, or the desktop table with
// everything on screen at once. Follows the window as it is resized. Outside
// a browser (tests, server rendering) the phone layout is assumed.

/** Below this the desktop table's three columns squeeze the felt too far. */
export const WIDE_QUERY = '(min-width: 1200px)';

class Viewport {
  wide = $state(false);

  constructor() {
    if (typeof window === 'undefined' || !window.matchMedia) return;
    const mq = window.matchMedia(WIDE_QUERY);
    this.wide = mq.matches;
    mq.addEventListener('change', (e) => (this.wide = e.matches));
  }
}

export const viewport = new Viewport();
