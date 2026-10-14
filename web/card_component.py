from __future__ import annotations
import html
import streamlit as st
from card import Card, SUITS, SUIT_SYMBOLS, SUIT_NAMES, STRAIN_SYMBOLS, STRAIN_NAMES, parse_bid

# Two decks, matching what the mainstream online clients offer.
#
# "classic" is the familiar two-colour deck. "four" is the four-colour deck that
# BBO, RealBridge, IntoBridge and FunBridge all ship as a display option, and
# that many players leave on permanently: it is the standard fix for the spade
# and club pips being the same ink and hard to tell apart at card size.
#
# `face` is ink on the white card face, `dim` the same hue darkened for a greyed
# unplayable card, `lt` a light variant for the bidding grid on the dark panel.
# Every value clears WCAG AA (4.5:1) against the surface it is used on.
DECKS: dict[str, dict[str, dict[str, str]]] = {
    'classic': {
        'face': {'S': '#101820', 'H': '#c8102e', 'D': '#c8102e', 'C': '#101820'},
        'dim':  {'S': '#101820', 'H': '#8c0a20', 'D': '#8c0a20', 'C': '#101820'},
        'lt':   {'S': '#dbe3ea', 'H': '#ff8d9c', 'D': '#ff8d9c', 'C': '#dbe3ea'},
    },
    'four': {
        'face': {'S': '#101820', 'H': '#c8102e', 'D': '#c2410c', 'C': '#0b6e35'},
        'dim':  {'S': '#101820', 'H': '#8c0a20', 'D': '#7a2606', 'C': '#084d25'},
        'lt':   {'S': '#dbe3ea', 'H': '#ff8d9c', 'D': '#ffb073', 'C': '#6fd69b'},
    },
}

DECK_LABELS = {
    'four':    'Four-colour deck',
    'classic': 'Classic two-colour deck',
}

DECK_HELP = {
    'four':    'Spades black, hearts red, diamonds orange, clubs green.',
    'classic': 'Spades and clubs black, hearts and diamonds red.',
}


def deck_name() -> str:
    return st.session_state.get('deck', 'four')


def suit_colors() -> dict[str, str]:
    """Ink for each suit on a white card face, per the active deck."""
    colors = dict(DECKS[deck_name()]['face'])
    colors['NT'] = '#101820'
    return colors


def suit_colors_light() -> dict[str, str]:
    """Ink for each suit on a dark surface (the scoreboard, the felt, the bidding
    grid), where the card-face inks would be far too dark to read."""
    colors = dict(DECKS[deck_name()]['lt'])
    colors['NT'] = '#e7ebee'
    return colors


def deck_style_block() -> str:
    """A <style> block re-pointing the --suit-* custom properties at the active
    deck, so the CSS card and bidding-grid rules follow the setting."""
    d = DECKS[deck_name()]
    decls = []
    for short in ('s', 'h', 'd', 'c'):
        key = short.upper()
        decls.append(f'--suit-{short}:{d["face"][key]};')
        decls.append(f'--suit-{short}-dim:{d["dim"][key]};')
        decls.append(f'--suit-{short}-lt:{d["lt"][key]};')
    return '<style>:root{' + ''.join(decls) + '}</style>'


# One card unit per card, plus a narrow gutter between suit groups. The real
# widths are fixed in styles.css, so card width never shifts as cards are played.
_SPACER = 0.3

# Spades, hearts, diamonds, clubs — the order every bridge client displays a
# hand in, and the order printed hand records use.
_DISPLAY_ORDER = ['S', 'H', 'D', 'C']


def suit_order(trump: str | None) -> list[str]:
    """Display order for suits: the fixed spades-hearts-diamonds-clubs of a
    printed hand record, or the trump suit pulled to the front when the player
    has asked for that. Call sites pass trump=None to keep the fixed order."""
    if trump in SUITS:
        return [trump] + [s for s in _DISPLAY_ORDER if s != trump]
    return list(_DISPLAY_ORDER)


def suit_label(suit: str) -> str:
    """Screen-reader text for a suit pip, which otherwise reads as a bare glyph."""
    # The fallback echoes the caller's string, so escape it; a known suit
    # returns a literal from SUIT_NAMES and is unaffected.
    return SUIT_NAMES.get(suit) or html.escape(str(suit), quote=True)


def card_face_html(card: Card) -> str:
    """A single playing card rendered as a card face."""
    # `suit_colors()[card.suit]` fails closed on an unknown suit (KeyError), but
    # the RANK is interpolated, so it is escaped: a Card is a plain value object
    # with no validation, and a future importer (a saved board, a PBN file)
    # could build one from outside data.
    color = suit_colors()[card.suit]
    return (
        f'<div class="pcard">'
        f'<span class="pcard-rank" style="color:{color}">'
        f'{html.escape(str(card.rank), quote=True)}</span>'
        f'<span class="pcard-suit" style="color:{color}" aria-hidden="true">'
        f'{SUIT_SYMBOLS[card.suit]}</span>'
        f'<span class="sr-only"> of {suit_label(card.suit)}</span>'
        f'</div>'
    )


def strain_html(level: int, strain: str) -> str:
    """Contract text with the suit symbol in that suit's ink for the active deck.
    These sit on dark panels, so they use the light inks."""
    sym = STRAIN_SYMBOLS[strain]
    color = suit_colors_light().get(strain, 'inherit')
    name = STRAIN_NAMES.get(strain, strain)
    return (f'{level}<span style="color:{color}" aria-hidden="true">{sym}</span>'
            f'<span class="sr-only"> {name}</span>')


def doubled_suffix(doubled: str) -> str:
    """'X' or 'XX' to append to a contract, as in "3♦X"; nothing when undoubled
    (the contract stores that as the string 'None')."""
    return '' if doubled == 'None' else doubled


def card_text_html(card: Card) -> str:
    """A card as inline text ("Q♥") in its suit's ink for a dark surface, for
    tables such as the trick log. Rank escaped as in `card_face_html`."""
    color = suit_colors_light()[card.suit]
    return (f'<span style="color:{color}">'
            f'{html.escape(str(card.rank), quote=True)}'
            f'<span aria-hidden="true">{SUIT_SYMBOLS[card.suit]}</span>'
            f'<span class="sr-only"> of {suit_label(card.suit)}</span></span>')


def call_badge(call: str, alert: str | None = None) -> str:
    """Renders a colored badge for an auction call (e.g. 1S, Pass, Dbl, Redbl).

    With `alert`, the badge carries a marker and an explanation that appears on
    hover -- the table equivalent of alerting a bid, so a player can see what a
    robot call is supposed to show instead of guessing.
    """
    inner = _call_inner(call)
    if not alert:
        return inner
    safe = html.escape(alert, quote=True)
    return (f'<span class="bid-alerted" tabindex="0">{inner}'
            f'<span class="bid-alert-dot" aria-hidden="true">!</span>'
            f'<span class="bid-alert-tip" role="tooltip">{safe}</span></span>')


def _call_inner(call: str) -> str:
    """The badge itself, without any alert decoration."""
    if call == 'Pass':
        return '<span class="bid-pill bid-pass">Pass</span>'
    if call == 'X':
        return '<span class="bid-pill bid-dbl">Dbl</span>'
    if call == 'XX':
        return '<span class="bid-pill bid-rdbl">Rdbl</span>'
    parsed = parse_bid(call)
    if parsed:
        level, strain = parsed
        sym = STRAIN_SYMBOLS[strain]
        color = suit_colors().get(strain, '#101820')
        name = STRAIN_NAMES.get(strain, strain)
        return (f'<span class="bid-pill bid-contract" style="color:{color}">'
                f'<span aria-hidden="true">{level}{sym}</span>'
                f'<span class="sr-only">{level} {name}</span></span>')
    # Fallback for anything that is not a recognised call. Escaped because this
    # is the one branch that interpolates the caller's string straight into the
    # page -- every other branch emits a literal or a value derived from
    # `parse_bid`. Nothing hostile reaches it today (auction calls come from a
    # validated fixed set), but see tests/test_web_escaping.py for why it is
    # not left to luck.
    return f'<span class="bid-pill">{html.escape(call, quote=True)}</span>'


def _grouped(hand: list[Card], trump: str | None) -> list[tuple[str, list[Card]]]:
    """Cards bucketed by suit in display order, empty suits dropped."""
    groups: dict[str, list[Card]] = {s: [] for s in SUITS}
    for c in hand:
        groups[c.suit].append(c)
    return [(s, groups[s]) for s in suit_order(trump) if groups[s]]


def hand_html_static(hand: list[Card], trump: str | None) -> str:
    """Full hand as one flowing row of card faces, grouped by suit."""
    if not hand:
        return '<div class="pcard-empty">No cards remaining</div>'
    parts = ['<div class="pcard-row">']
    for i, (_suit, cards) in enumerate(_grouped(hand, trump)):
        if i:
            parts.append('<div class="pcard-gap"></div>')
        parts.extend(card_face_html(c) for c in cards)
    parts.append('</div>')
    return ''.join(parts)


def card_backs_html(count: int, seat: str) -> str:
    """A fan of card backs for a concealed hand, the way the online clients show
    an opponent. Decorative: the card count beside it carries the information."""
    backs = ''.join('<div class="cb"></div>' for _ in range(max(0, count)))
    # `seat` is not rendered here today, but the signature takes it, so a future
    # label must not be able to break out of the attribute.
    return f'<div class="card-backs" aria-hidden="true">{backs}</div>'


def hand_summary_html(hcp: int, sh_pts: float, shape: list[int]) -> str:
    """The strength strip the clients put beside your own hand. Shows standard
    high-card points for orientation alongside this variant's own valuation,
    because in Second-Highest Bridge HCP is a much weaker guide than usual."""
    shape_str = '-'.join(str(n) for n in shape)
    return (
        f'<div class="hand-summary">'
        f'<span>HCP <strong>{hcp}</strong></span>'
        f'<span class="hs-sep">|</span>'
        f'<span>2nd-highest value <strong>{sh_pts:g}</strong></span>'
        f'<span class="hs-sep">|</span>'
        f'<span>Shape <strong>{shape_str}</strong></span>'
        f'</div>'
    )


def hand_diagram_html(hand: list[Card]) -> str:
    """Compact hand-record style: one line per suit, ranks high to low, voids as a dash."""
    colors = suit_colors()
    lines = []
    for s in _DISPLAY_ORDER:
        cards = sorted((c for c in hand if c.suit == s), key=lambda c: c.value(), reverse=True)
        ranks = html.escape(''.join(str(c.rank) for c in cards), quote=True) or '—'
        lines.append(
            f'<div class="hd-line">'
            f'<span class="hd-suit" style="color:{colors[s]}" aria-hidden="true">'
            f'{SUIT_SYMBOLS[s]}</span>'
            f'<span class="sr-only">{suit_label(s)}: </span>'
            f'<span class="hd-ranks">{ranks}</span></div>'
        )
    return f'<div class="hand-diagram">{"".join(lines)}</div>'


def seat_box_html(seat: str, role: str, hand: list[Card]) -> str:
    """A labelled seat box holding a compact hand diagram."""
    role_cls = {'Declarer': ' is-declarer', 'Dummy': ' is-dummy'}.get(role, '')
    # `role_cls` is safe by construction -- it comes from a lookup with a '' default,
    # so an unexpected role yields no class rather than arbitrary attribute text.
    safe_seat = html.escape(str(seat), quote=True)
    safe_role = html.escape(str(role), quote=True)
    return (
        f'<div class="seat-box">'
        f'<div class="seat-box-head">'
        f'<span class="seat-letter">{safe_seat[:1]}</span>'
        f'<span class="seat-box-name">{safe_seat}</span>'
        f'<span class="seat-box-role{role_cls}">{safe_role}</span></div>'
        f'{hand_diagram_html(hand)}'
        f'</div>'
    )


def show_interactive_hand(label: str, hand: list[Card], trump: str | None,
                          is_turn: bool, legal: list[Card] | None, who: str, on_play=None,
                          concealed: bool = False) -> None:
    """Renders a hand as a single row of cards — clickable when it's this seat's turn.

    A concealed hand shows only its card count. Being on turn overrides it: the
    only seat the human plays besides South is dummy, which is face-up anyway.
    """
    if is_turn:
        st.markdown(
            f'<div class="hand-header active-header">'
            f'<span><strong>{label}</strong></span>'
            f'<span class="turn-pill">Your turn — play a card</span>'
            f'</div>',
            unsafe_allow_html=True
        )
    else:
        st.markdown(f'<div class="hand-header"><strong>{label}</strong></div>', unsafe_allow_html=True)

    if not hand:
        st.markdown('<div class="pcard-empty">No cards remaining</div>', unsafe_allow_html=True)
        return

    if concealed and not is_turn:
        st.markdown(
            card_backs_html(len(hand), who)
            + f'<div class="seat-count"><strong>{len(hand)} cards</strong> · concealed</div>',
            unsafe_allow_html=True
        )
        return

    if not is_turn:
        st.markdown(hand_html_static(hand, trump), unsafe_allow_html=True)
        return

    legal_set = set(legal) if legal else set()

    # Lay every card out in one row, with a narrow spacer between suit groups.
    widths: list[float] = []
    slots: list[Card | None] = []
    for i, (_suit, cards) in enumerate(_grouped(hand, trump)):
        if i:
            widths.append(_SPACER)
            slots.append(None)
        for card in cards:
            widths.append(1.0)
            slots.append(card)

    # The ratios only order the slots: styles.css gives every card a fixed
    # width and lets the row WRAP, so a hand wider than its column moves its
    # last cards onto a second line instead of clipping them. Ratios alone
    # clipped: with dummy in a side seat the centre column is too narrow for
    # thirteen cards, and Streamlit columns shrink rather than wrap.
    trick_len = len(st.session_state.get('trick', []))
    with st.container(key=f"handrow_{who}"):
        cols = st.columns(widths, gap="small")
        for col, card in zip(cols, slots):
            if card is None:
                with col:
                    st.markdown('<div class="hand-suit-gap"></div>', unsafe_allow_html=True)
                continue
            with col:
                # No Streamlit colour markup on the label: the suit ink comes
                # from CSS keyed on this button's own key, so it follows the deck
                # setting and can use four colours rather than only red.
                btn_label = f"{card.rank}{SUIT_SYMBOLS[card.suit]}"
                btn_key = f"play_{who}_{card.suit}_{card.rank}_{trick_len}"
                if st.button(btn_label, key=btn_key, disabled=(card not in legal_set),
                             use_container_width=True):
                    if on_play:
                        on_play(who, card)
                    st.rerun()
