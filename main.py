from __future__ import annotations
import sys

# Ensure suit symbols (♣♦♥♠) display correctly in Windows terminals
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from card import Card, SUITS, SUIT_SYMBOLS, SUIT_NAMES, RANKS, deal, auto_contract
from game  import clockwise_from, legal_plays, resolve_trick, score, TRICKS_NEEDED
from ai    import ai_play

HUMAN_PLAYERS = {'South', 'North'}  # South is declarer; North is dummy (also played by human)


# ── Display helpers ────────────────────────────────────────────────────────────

def fmt_hand(hand: list[Card]) -> str:
    """Format a hand grouped by suit: ♣ 4 7 J   ♦ 2 9   ♥ ..."""
    groups: dict[str, list[Card]] = {s: [] for s in SUITS}
    for c in hand:
        groups[c.suit].append(c)
    parts = []
    for s in SUITS:
        if groups[s]:
            ranks = ' '.join(c.rank for c in groups[s])
            parts.append(f"{SUIT_SYMBOLS[s]} {ranks}")
    return '   '.join(parts)


def fmt_trick(trick: list[tuple[str, Card]], order: list[str]) -> str:
    """Show each seat's card (or dash) in play order."""
    played = dict(trick)
    return '   '.join(
        f"{p}: {played[p]}" if p in played else f"{p}: -"
        for p in order
    )


def display_state(
    hands: dict[str, list[Card]],
    trump: str,
    ns: int,
    ew: int,
    trick_num: int,
    trick: list[tuple[str, Card]],
    order: list[str],
) -> None:
    print()
    print("=" * 62)
    print(f"  Trump: {SUIT_SYMBOLS[trump]} {SUIT_NAMES[trump]}   "
          f"Contract: 2{SUIT_SYMBOLS[trump]} (need {TRICKS_NEEDED} tricks)")
    print(f"  Trick {trick_num}/13   N/S: {ns}   E/W: {ew}")
    print("=" * 62)
    print(f"  NORTH (dummy): {fmt_hand(hands['North'])}")
    print(f"  SOUTH:         {fmt_hand(hands['South'])}")
    print()
    if trick:
        print(f"  Current trick:  {fmt_trick(trick, order)}")
    else:
        print(f"  {order[0]} leads.")


# ── Input ──────────────────────────────────────────────────────────────────────

def parse_card(text: str, hand: list[Card]) -> Card | None:
    """
    Parse player input into a Card from their hand.
    Accepted formats: AS, as, 10H, 10h, KD, kd  (rank then suit letter).
    """
    text = text.strip().upper()
    if len(text) < 2:
        return None
    suit = text[-1]
    rank = text[:-1]
    if suit not in SUIT_SYMBOLS or rank not in RANKS:
        return None
    for card in hand:
        if card.suit == suit and card.rank == rank:
            return card
    return None


def get_human_card(player: str, hand: list[Card], trick: list[tuple[str, Card]], trump: str) -> Card:
    led_suit = trick[0][1].suit if trick else None
    legal    = legal_plays(hand, led_suit)

    label = f"{player} (Dummy)" if player == 'North' else player
    print(f"\n  {label}'s hand:    {fmt_hand(hand)}")
    print(f"  Legal plays:    {' '.join(str(c) for c in legal)}")

    while True:
        raw  = input(f"  {label} plays: ").strip()
        card = parse_card(raw, hand)
        if card is None:
            print("  Not recognized. Type rank + suit letter, e.g.  AS  10H  KD")
        elif card not in legal:
            print(f"  {card} is not a legal play (must follow suit if able).")
        else:
            return card


# ── Game loop ──────────────────────────────────────────────────────────────────

def play_game() -> None:
    hands = deal()
    trump = auto_contract(hands['North'], hands['South'])

    ns_combined = [c for c in hands['North'] + hands['South'] if c.suit == trump]
    print(f"\nDealt!  Trump: {SUIT_SYMBOLS[trump]} {SUIT_NAMES[trump]}  "
          f"({len(ns_combined)} combined N/S cards)")
    print(f"Contract: 2{SUIT_SYMBOLS[trump]}  —  N/S need {TRICKS_NEEDED} tricks to make it.")
    print(f"You play South (and dummy North).  East & West are AI.\n")

    ns_tricks  = 0
    ew_tricks  = 0
    leader     = 'West'   # player to the left of South (declarer)
    played: list[Card] = []

    for trick_num in range(1, 14):
        order = clockwise_from(leader)
        trick: list[tuple[str, Card]] = []

        for player in order:
            display_state(hands, trump, ns_tricks, ew_tricks, trick_num, trick, order)

            if player in HUMAN_PLAYERS:
                card = get_human_card(player, hands[player], trick, trump)
            else:
                card = ai_play(player, hands[player], trick, trump, played)
                print(f"\n  {player} plays: {card}")

            hands[player].remove(card)
            trick.append((player, card))

        winner = resolve_trick(trick, trump)
        side   = 'N/S' if winner in ('North', 'South') else 'E/W'
        if winner in ('North', 'South'):
            ns_tricks += 1
        else:
            ew_tricks += 1

        print(f"\n  ── Trick {trick_num} result: {fmt_trick(trick, order)}")
        print(f"  ── {winner} wins  ({side})   [N/S: {ns_tricks}  E/W: {ew_tricks}]")
        input("\n  Press Enter for next trick...")
        played.extend(c for _, c in trick)
        leader = winner

    result = score(ns_tricks, trump)
    print("\n" + "=" * 62)
    print("  GAME OVER")
    print(f"  N/S tricks: {result['ns_tricks']}  |  Needed: {TRICKS_NEEDED}")
    print(f"  {'MADE!' if result['made'] else 'DOWN.'}")
    print(f"  {result['detail']}")
    print(f"  Winner: {result['winner']}")
    print("=" * 62)


if __name__ == '__main__':
    play_game()
