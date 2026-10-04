"""Exact double dummy search: zero-window alpha-beta, transposition table,
rank-equivalence reduction.

Everything here is a *sound* reduction — no heuristics, no approximation. The
answers must match ``bridge/solver/brute.py`` exactly on every position in
tests/fixtures/endings.json, and each optimisation can be switched off
independently so a disagreement can be bisected to the one that caused it.

Three ideas, none of which needs any insight into Second-Highest strategy:

Zero-window search
    Ask "can N/S take at least `need` of the remaining tricks?" rather than
    "how many?". A boolean answer lets either side cut off the moment it finds
    one satisfying line, and the count falls out of a binary search over
    `need` that reuses one shared table.

Transposition table
    Card play transposes heavily: the same holdings reached by a different
    order of tricks are the same position. Bounds are stored per position, so
    successive binary-search probes answer each other.

Rank-equivalence reduction
    ``resolve`` reads only the *relative order* of cards in the winning suit,
    so relabelling ranks order-preservingly is a bijection on all future play.
    Two uses: normalising the table key, and collapsing interchangeable cards
    in a hand to a single move.

The equivalence gotcha
    Cards count as adjacent only if nothing live lies between them, and "live"
    means unplayed cards *plus* cards face-up on the current trick. Move
    reduction therefore takes the table into account. The table key does not
    need to: it is only ever probed at a trick boundary, where the table is
    empty by construction.
"""
from __future__ import annotations
from typing import Dict, Optional, Tuple

from bridge.solver.bitstate import (
    DECK_SIZE, NS_SEATS, RANKS_PER_SUIT, SEAT_COUNT, SECOND_HIGHEST,
    SUIT_COUNT, SUIT_MASK, SUIT_OF, Position, cards_in, legal_moves, resolve,
    tricks_available,
)


class Search:
    """One search, over one trump suit, owning one transposition table.

    The table is keyed on positions, not on the question asked about them, so
    it is worth reusing a single ``Search`` across the binary search for a
    deal's value — which ``solve`` does.
    """

    def __init__(self, trump: Optional[int], use_table: bool = True,
                 normalise_key: bool = True, reduce_moves: bool = True,
                 ordering: str = 'trick'):
        self.trump = trump
        self.use_table = use_table
        # Rank equivalence is used in two independent places, and they are
        # separately switchable so an ablation can attribute the win honestly.
        self.normalise_key = normalise_key
        self.reduce_moves = reduce_moves
        # Ordering cannot change an answer, only how fast it is found — so it
        # is judged on nodes AND wall time, since a cleverer order that costs
        # more per node than it saves is a loss. 'natural' is the Stage 2
        # baseline, kept as a control.
        self.ordering = ordering
        self.table: Dict[int, Tuple[int, int]] = {}
        self.nodes = 0
        self.probes = 0
        self.hits = 0

    # ── Rank equivalence ────────────────────────────────────────────────────

    def _key(self, hands: Tuple[int, ...], leader: int) -> int:
        """Position key with ranks compressed to their order among live cards.

        Only valid at a trick boundary: it derives the live set from the hands
        alone, which is exactly right when nothing is on the table.
        """
        if not self.normalise_key:
            key = leader
            for hand in hands:
                key = (key << DECK_SIZE) | hand
            return key

        # Not done here: folding the position onto its two-seat rotation, which
        # is sound (the partnerships hold the same cards, so the value is
        # unchanged) but measured worthless — within one deal North never holds
        # South's cards, so a position and its rotation never both arise.
        key = leader
        for suit in range(SUIT_COUNT):
            base = suit * RANKS_PER_SUIT
            h0 = (hands[0] >> base) & SUIT_MASK
            h1 = (hands[1] >> base) & SUIT_MASK
            h2 = (hands[2] >> base) & SUIT_MASK
            h3 = (hands[3] >> base) & SUIT_MASK

            c0 = c1 = c2 = c3 = 0
            bit = 0
            live = h0 | h1 | h2 | h3
            while live:
                low = live & -live
                if h0 & low:
                    c0 |= 1 << bit
                elif h1 & low:
                    c1 |= 1 << bit
                elif h2 & low:
                    c2 |= 1 << bit
                else:
                    c3 |= 1 << bit
                bit += 1
                live ^= low

            key = (((((key << RANKS_PER_SUIT | c0) << RANKS_PER_SUIT | c1)
                     << RANKS_PER_SUIT | c2) << RANKS_PER_SUIT) | c3)
        return key

    def _distinct_moves(self, hands: Tuple[int, ...], seat: int, moves: int,
                        table: int) -> int:
        """Drop moves that are interchangeable with a lower card of the same run.

        Two of my cards are interchangeable when no live card of the suit lies
        between them — live counting other players' unplayed cards *and* the
        cards already on this trick. One representative per run is enough,
        because the rest differ from it only by a relabelling.
        """
        elsewhere = ((hands[0] | hands[1] | hands[2] | hands[3])
                     & ~hands[seat]) | table
        keep = 0

        for suit in range(SUIT_COUNT):
            base = suit * RANKS_PER_SUIT
            mine = (moves >> base) & SUIT_MASK
            if not mine:
                continue
            others = (elsewhere >> base) & SUIT_MASK

            previous = -1
            while mine:
                low = mine & -mine
                rank = low.bit_length() - 1
                # A run breaks where a card I do not hold sits in the gap
                gap = ((1 << rank) - 1) & ~((1 << (previous + 1)) - 1)
                if previous < 0 or others & gap:
                    keep |= low << base
                previous = rank
                mine ^= low

        return keep

    # ── Move ordering ───────────────────────────────────────────────────────

    def _ordered(self, moves: int, hands: Tuple[int, ...], seat: int,
                 leader: int, trick: Tuple[int, ...]):
        """Sequence the legal moves. Sound by construction — order only.

        ``natural`` is ascending card index, which is what bare ``cards_in``
        yields and what Stage 2 measured.

        ``trick`` tries the cards that would take the trick for the mover's own
        side first. Both sides want this: N/S to gain a trick, E/W to deny one.
        At the fourth seat it is exact; earlier it is a guess that ignores the
        cards still to come. Measured at 1.35-1.63x fewer nodes.

        Two orderings were tried and rejected on measurement, both recorded in
        the stage plan: ranking leads by distance from the second-highest
        outstanding card (worse than leaving leads unordered), and killer moves
        (1.1x, and it degraded ``trick`` when combined).
        """
        if self.ordering == 'natural':
            return cards_in(moves)

        cards = list(cards_in(moves))
        if len(cards) < 2:
            return cards

        if self.ordering == 'trick':
            # On lead nothing is known: every card provisionally takes the
            # trick as the only one of its suit, so scoring cannot separate
            # them. Skip the work entirely — these are the widest nodes.
            if not trick:
                return cards

            trump = self.trump
            winning_suit = SUIT_OF[trick[0]]
            if trump is not None:
                for played in trick:
                    if SUIT_OF[played] == trump:
                        winning_suit = trump
                        break

            base = winning_suit * RANKS_PER_SUIT
            ceiling = base + RANKS_PER_SUIT
            ranks = 0
            holder = {}
            for offset, played in enumerate(trick):
                if base <= played < ceiling:
                    ranks |= 1 << (played - base)
                    holder[played - base] = (leader + offset) % SEAT_COUNT

            side = seat & 1          # seats 0/2 are N/S, 1/3 are E/W
            # Who holds the trick if I contribute nothing to the winning suit
            standing = holder[SECOND_HIGHEST[ranks]]
            # Ruffing when no one else has: my trump would stand alone and win
            can_ruff = trump is not None and winning_suit != trump

            scored = []
            for card in cards:
                if can_ruff and SUIT_OF[card] == trump:
                    winner = seat
                elif base <= card < ceiling:
                    rank = card - base
                    second = SECOND_HIGHEST[ranks | (1 << rank)]
                    winner = seat if second == rank else holder[second]
                else:
                    winner = standing
                scored.append((0 if (winner & 1) == side else 1, card))

            scored.sort()
            return [card for _, card in scored]

        raise ValueError(f"unknown ordering {self.ordering!r}")

    # ── Zero-window search ──────────────────────────────────────────────────

    def _reach(self, hands: Tuple[int, ...], leader: int, need: int,
               tricks_left: int) -> bool:
        """Can N/S still take at least `need` tricks? Called at trick boundaries."""
        if need <= 0:
            return True
        if need > tricks_left:
            return False

        key = None
        low, high = 0, tricks_left
        if self.use_table:
            self.probes += 1
            key = self._key(hands, leader)
            entry = self.table.get(key)
            if entry is not None:
                low, high = entry
                if need <= low:
                    self.hits += 1
                    return True
                if need > high:
                    self.hits += 1
                    return False

        result = self._in_trick(hands, leader, (), 0, need, tricks_left)

        if key is not None:
            if result:
                if need > low:
                    low = need
            elif need - 1 < high:
                high = need - 1
            self.table[key] = (low, high)
        return result

    def _in_trick(self, hands: Tuple[int, ...], leader: int,
                  trick: Tuple[int, ...], table: int, need: int,
                  tricks_left: int) -> bool:
        """Play out the trick in progress. No table probes: mid-trick only."""
        self.nodes += 1

        seat = (leader + len(trick)) % SEAT_COUNT
        led = SUIT_OF[trick[0]] if trick else None
        moves = legal_moves(hands[seat], led)
        if self.reduce_moves:
            moves = self._distinct_moves(hands, seat, moves, table)

        maximizing = seat in NS_SEATS

        for card in self._ordered(moves, hands, seat, leader, trick):
            rest = list(hands)
            rest[seat] &= ~(1 << card)
            played = trick + (card,)

            if len(played) == SEAT_COUNT:
                winner = resolve(played, leader, self.trump)
                gained = 1 if winner in NS_SEATS else 0
                ok = self._reach(tuple(rest), winner, need - gained,
                                 tricks_left - 1)
            else:
                ok = self._in_trick(tuple(rest), leader, played,
                                    table | (1 << card), need, tricks_left)

            # N/S need one line that works; E/W need one that refutes
            if maximizing:
                if ok:
                    return True
            elif not ok:
                return False

        return not maximizing

    # ── Entry points ────────────────────────────────────────────────────────

    def reaches(self, position: Position, need: int) -> bool:
        """Can N/S take at least `need` tricks from this position?"""
        tricks = tricks_available(position)
        if position.trick:
            table = 0
            for card in position.trick:
                table |= 1 << card
            return self._in_trick(position.hands, position.leader,
                                  position.trick, table, need, tricks)
        return self._reach(position.hands, position.leader, need, tricks)

    def value(self, position: Position) -> int:
        """Tricks N/S take with optimal play, by binary search on `reaches`.

        Each probe leaves bounds behind in the shared table, so later probes
        are answered by earlier ones rather than re-searched.
        """
        low, high = 0, tricks_available(position)
        while low < high:
            midpoint = (low + high + 1) // 2
            if self.reaches(position, midpoint):
                low = midpoint
            else:
                high = midpoint - 1
        return low

    def value_from(self, position: Position, guess: int) -> int:
        """Tricks N/S take, found by stepping outward from a first guess.

        The same answer as ``value``, and cheaper when the guess is close:
        measured 1.3-1.4x fewer nodes with an exact guess, about 1.1x when off
        by two. Use it when a nearby answer is already known, such as the same
        strain just solved with the other side on lead.
        """
        total = tricks_available(position)
        estimate = max(0, min(total, guess))
        if self.reaches(position, estimate):
            while estimate < total and self.reaches(position, estimate + 1):
                estimate += 1
            return estimate
        estimate -= 1
        while estimate > 0 and not self.reaches(position, estimate):
            estimate -= 1
        return estimate


def solve(position: Position, use_table: bool = True,
          normalise_key: bool = True, reduce_moves: bool = True,
          ordering: str = 'trick') -> int:
    """Tricks N/S take from `position`. Matches ``brute.solve`` exactly."""
    return Search(position.trump, use_table, normalise_key, reduce_moves,
                  ordering).value(position)


def solve_with_nodes(position: Position, use_table: bool = True,
                     normalise_key: bool = True, reduce_moves: bool = True,
                     ordering: str = 'trick') -> Tuple[int, int]:
    """``solve``, plus nodes visited — comparable to ``brute.solve_with_nodes``."""
    engine = Search(position.trump, use_table, normalise_key, reduce_moves,
                    ordering)
    return engine.value(position), engine.nodes
