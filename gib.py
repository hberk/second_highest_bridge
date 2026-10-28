"""GIB 2/1 game force: the robots' default bidding system.

Source: BBO's GIB system notes, https://www.bridgebase.com/doc/gib_system_notes.php
(GIB version 40). "2/1 Game Force with 5 card majors, strong NT, strong (17+)
jump shift, weak 2 bids and a strong artificial 2C."

Adopted IN FULL and by default, at the user's request, because it is the system
players already know -- including the parts this project had measured as
costing points in the second-highest variant (game-forcing 2/1, notrump,
slam conventions, cuebids). The measurements are kept in docs/BIDDING.md; the meaning
of every call here is GIB's.

`gib_bid` returns (call, alert) for every situation the system describes, and
None only for contested auctions the notes leave to judgment, where `ai.py`'s
natural competitive logic takes over. Every alert says what the call SHOWS --
the same text whoever holds the hand -- and every number it quotes is enforced
by the branch that makes it (see tests/test_bidding_calibration.py).

Units: "HCP" is Milton Work high-card points. "points" is the guide count
(HCP plus one per card past the fourth in a suit, minus one for 4-3-3-3), the
same `ai._points` uses -- GIB's "total points".
"""
from __future__ import annotations

from card import Card, SUITS, parse_bid
from bridge.auction import AuctionState, PARTNERS

SYM = {'S': '♠', 'H': '♥', 'D': '♦', 'C': '♣'}
MAJORS = ('H', 'S')
MINORS = ('C', 'D')
_HCP = {'A': 4, 'K': 3, 'Q': 2, 'J': 1}

# ── The numbers in GIB's notes ────────────────────────────────────────────────
OPEN_MIN = 11                 # 12+, or 11 by the rule of 20
NT1 = (15, 17)                # 1NT: balanced 15-17, may hold a five-card major
NT2 = (20, 21)                # 2NT: balanced 20-21
NT_AFTER_2C = (22, 24)        # 2C-2D-2NT
STRONG_2C = 22                # 2C: strong, artificial, 22+ HCP
WEAK = (5, 10)                # weak twos and pre-empts
FOURTH_SEAT = (11, 15)        # a fourth-seat two-bid is sound (house, user's call)
#: The fewest HCP that respond to a one-level opening (the user's call,
#: 2026-10-23: 7, not GIB's 6; +0.52 a board on its own). See BIDDING.md.
RESPONSE_MIN = 7
RAISE = (7, 10)               # 1M-2M shows 7-10
LIMIT = (11, 12)              # 1M-3M limit raise, four-card support
JACOBY_MIN = 13
SPLINTER = (13, 16)
#: Opener's splinter after a single raise, 1M-2M-3♠/4x: a singleton or void,
#: game forcing (the user's call, roadmap 3.8). 18+ is where opener already
#: bids game over the raise; the splinter says where its shortness is.
SELF_SPLINTER_MIN = 18
#: Opener makes that splinter (measurement switch; responder answers it
#: either way, since a human opener can bid it).
SELF_SPLINTER = True
TWO_OVER_ONE = 12
JUMP_SHIFT_POINTS = 17        # Soloway: 17+ total points, 4+ controls
DRURY = (10, 12)
INVERTED_MIN = 10
OVERCALL_1 = (8, 17)
OVERCALL_2 = (10, 17)
WJO = (3, 9)                  # weak jump overcalls, aggressive
NT_OVERCALL = (15, 18)
TAKEOUT_MIN = 12
NEGATIVE = {1: 6, 2: 8, 3: 10}
TWO_SUITED_MIN = 8
#: Game by judgement points (the user's call, 2026-10-23). GAME is every
#: game but a major suit's: 3NT, a minor, and the "game values" line. 3NT
#: makes about 13% of the time here at almost any HCP, so it is 32, not
#: GIB's 25; a major game, which follows the fit, is GAME_MAJOR. Opposite
#: our 1NT/2NT it is NT_GAME: at 32, one point under SLAM, responder would
#: never invite or use Stayman, and 28 scores the same. See "Game by
#: points" in BIDDING.md.
GAME = 32
GAME_MAJOR = 26
NT_GAME = 28
#: Judge level on the variant's card values (True) or on HCP (False).
JUDGE_BY_VARIANT = True
#: A three-level cuebid raise needs 4 trumps or 12+ judgement points.
CUE_LIMIT_AT_3 = True
#: Advancer's cuebid raise can pass three of partner's suit (1♦ (2♣) 2♦ 3♦),
#: forcing 3NT or four. So when their suit ranks above ours, 2NT is the
#: limit raise or better (artificial), leaving three as partner's sign-off,
#: and the cuebid only asks for a stopper for 3NT: CUE_ASK_HCP+ and none of
#: my own (the user's call, 2026-10-28, Challenge deal 276). Fresh deals,
#: head to head: +0.07 a board, t = +1.7.
CUE_2NT = True
CUE_ASK_HCP = 13
#: Double, then a new suit: 18+ HCP and 5+ cards, too strong to overcall (the
#: user's call, 2026-10-28, Bidding training: 1♥ P P X 2♥ P P 2♠ was read as a
#: plain overcall). A takeout doubler without them does not bid a new suit,
#: and advancer raises it, to game on DOUBLER_SUIT_JUDGE (an 18-count's mean
#: judgement points) plus its own.
DOUBLE_THEN_SUIT = False
DOUBLER_SUIT_HCP = 18
DOUBLER_SUIT_JUDGE = 14
DOUBLER_RAISE_HCP = 6
DOUBLER_SUIT_LEVEL = 3
SLAM = 33
GRAND = 37


# ── Hands ─────────────────────────────────────────────────────────────────────

class Hand:
    def __init__(self, cards: list[Card]):
        self.cards = cards
        self.groups = {s: [c for c in cards if c.suit == s] for s in SUITS}
        self.len = {s: len(self.groups[s]) for s in SUITS}
        self.hcp = sum(_HCP.get(c.rank, 0) for c in cards)
        self.shape = sorted(self.len.values(), reverse=True)
        self.points = (self.hcp + sum(max(0, n - 4) for n in self.len.values())
                       - (1 if self.shape == [4, 3, 3, 3] else 0))
        self.balanced = self.shape in ([4, 3, 3, 3], [4, 4, 3, 2], [5, 3, 3, 2])
        self.controls = sum(2 if c.rank == 'A' else 1 if c.rank == 'K' else 0
                            for c in cards)
        # Judgement points: honours valued the way THIS game values them
        # (fitted on 400 deals: K +0.44 tricks, Q +0.37, J +0.23, 10 and 9
        # +0.20, A +0.08), as K=Q=3, A=J=10=9=1: a deck still holds 40. The
        # jack counted 0 until 2026-10-23, from a 100-deal fit; at 1 it
        # scored +1.17 a board (BIDDING.md, "Game by points"). GIB's ranges stay in HCP -- what a bid SHOWS -- but whether to
        # stop, invite or bid game is judged on these. A 15-count of aces and
        # kings is a 1NT opening and still a poor dummy for game here.
        judge = sum(3 if c.rank in ('K', 'Q') else 1 if c.rank in ('A', 'J', '10', '9') else 0
                    for c in cards)
        self.judge = judge if JUDGE_BY_VARIANT else self.hcp

    def has(self, suit: str, rank: str) -> bool:
        return any(c.rank == rank for c in self.groups[suit])

    def top(self, suit: str, ranks: tuple) -> int:
        return sum(1 for c in self.groups[suit] if c.rank in ranks)

    def good_suit(self, suit: str) -> bool:
        """Two of the top three honours, or three of the top five."""
        return (self.top(suit, ('A', 'K', 'Q')) >= 2
                or self.top(suit, ('A', 'K', 'Q', 'J', '10')) >= 3)

    def stopper(self, suit: str) -> bool:
        n = self.len[suit]
        return (self.has(suit, 'A') or (self.has(suit, 'K') and n >= 2)
                or (self.has(suit, 'Q') and n >= 3) or (self.has(suit, 'J') and n >= 4))

    def short(self, exclude: str | None = None) -> list[str]:
        """Side suits held as a singleton or void, shortest first."""
        return sorted((s for s in SUITS if s != exclude and self.len[s] <= 1),
                      key=lambda s: (self.len[s], SUITS.index(s)))

    def keycards(self, trump: str | None) -> int:
        aces = sum(1 for s in SUITS if self.has(s, 'A'))
        return aces + (1 if trump in SUITS and self.has(trump, 'K') else 0)

    def aces(self) -> int:
        return sum(1 for s in SUITS if self.has(s, 'A'))

    def longest(self, among=SUITS) -> str:
        return max(among, key=lambda s: (self.len[s], SUITS.index(s)))


# ── Calls ─────────────────────────────────────────────────────────────────────

def level_of(call: str | None) -> int:
    parsed = parse_bid(call) if call else None
    return parsed[0] if parsed else 0


def strain_of(call: str | None) -> str | None:
    parsed = parse_bid(call) if call else None
    return parsed[1] if parsed else None


def rank_of(call: str) -> int:
    """Position on the bidding ladder, 1C = 0 ... 7NT = 34."""
    lvl, strain = parse_bid(call)
    return (lvl - 1) * 5 + ['C', 'D', 'H', 'S', 'NT'].index(strain)


class Ctx:
    """Everything a decision needs, read once."""

    def __init__(self, player: str, cards: list[Card], auction: AuctionState):
        self.me = player
        self.pd = PARTNERS[player]
        self.h = Hand(cards)
        self.auction = auction
        self.calls = list(auction.calls)
        self.legal = auction.legal_calls()
        self.ours = [(w, c) for w, c in self.calls
                     if w in (self.me, self.pd) and c != 'Pass']
        self.theirs = [(w, c) for w, c in self.calls
                       if w not in (self.me, self.pd) and c != 'Pass']
        self.seq = [c for _, c in self.ours]
        first = next(((w, c) for w, c in self.calls if c != 'Pass'), None)
        self.we_opened = first is not None and first[0] in (self.me, self.pd)
        self.opener = self.ours[0][0] if self.ours else None
        # Our 1NT overcall of a one-level opening, and they have only passed
        # since: systems on, the 1NT opening's whole structure, every round.
        self.nt_overcall = False
        if not self.we_opened and self.seq and self.seq[0] == '1NT'                 and level_of(first[1]) == 1:
            at = next(i for i, (w, c) in enumerate(self.calls)
                      if w in (self.me, self.pd) and c == '1NT')
            self.nt_overcall = all(c == 'Pass' for w, c in self.calls[at + 1:]
                                   if w not in (self.me, self.pd))

    def ok(self, call: str | None) -> bool:
        return call is not None and call in self.legal

    def cheapest(self, strain: str, floor: int = 1) -> str | None:
        for lvl in range(floor, 8):
            call = f"{lvl}{strain}"
            if call in self.legal:
                return call
        return None

    def passed_hand(self, seat: str) -> bool:
        first = next((c for w, c in self.calls if w == seat), None)
        return first == 'Pass'

    def mine(self) -> list[str]:
        return [c for w, c in self.ours if w == self.me]

    def partners(self) -> list[str]:
        return [c for w, c in self.ours if w == self.pd]

    def i_am_opener(self) -> bool:
        return self.opener == self.me

    def current(self) -> str | None:
        """The highest bid on the table."""
        hb = self.auction.highest_bid
        return f"{hb[0]}{hb[1]}" if hb else None


# ── Alerts that recur ─────────────────────────────────────────────────────────

TO_PLAY = "To play."


def natural(suit: str) -> str:
    return f"Natural, {SYM[suit]}."


def placed(ctx: Ctx, decision: tuple) -> tuple:
    """`decision`, unless partner has already bid past it. Only a human partner
    does that, by not answering a convention (2NT-3♣-3NT): the contract is theirs."""
    return decision if ctx.ok(decision[0]) else ('Pass', "Partner placed the contract.")


# ── Entry point ───────────────────────────────────────────────────────────────

#: Calls a branch produced that were not legal, caught by the guard below.
#: Tests assert this stays at zero, robots alone and with a random human at the
#: table (test_gib.py); in play the guard keeps the table moving.
ILLEGAL = []


def gib_bid(player: str, cards: list[Card], auction: AuctionState) -> tuple | None:
    ctx = Ctx(player, cards, auction)
    if not ctx.legal:
        return None
    decision = _decide(ctx)
    placed = _after_jam(ctx)
    if placed and JAM_NEVER_AGAIN and (not decision or decision[0] != 'X'):
        return placed
    if placed and not JAM_NEVER_AGAIN:
        decision = placed
    if not decision or decision[0] not in ('X', 'XX'):     # a penalty double outranks the jam
        decision = _jam_game(ctx) or decision
    decision = _total_tricks(ctx, decision) or decision
    decision = _major_over_notrump(ctx, decision) or decision
    if decision is None:
        return None
    if decision[0] not in ctx.legal:
        ILLEGAL.append((tuple(ctx.calls), decision))
        decision = continuation(ctx)
        if decision[0] not in ctx.legal:
            decision = ('Pass', "Nothing to add.")
    return decision[0], _name_the_suit(*decision)


def _name_the_suit(call: str, alert: str) -> str:
    """A natural suit bid's alert names its suit ("To play, ♥."). The
    text depends only on the call, so it cannot read the hand out."""
    s = strain_of(call)
    if s in SUITS and SYM[s] not in alert and 'artificial' not in alert.lower():
        return alert.rstrip('.') + f", {SYM[s]}."
    return alert


def _owns(ctx: Ctx) -> bool:
    """Has our side made a call only this module can read: notrump, or a
    suit bid that does not show its suit?"""
    return any(strain_of(c) == 'NT' or (strain_of(c) in SUITS and
                                        shown_suit(ctx.seq, i) != strain_of(c))
               for i, c in enumerate(ctx.seq))


def _decide(ctx: Ctx) -> tuple | None:
    for step in (answer_ask, after_my_ask):
        decision = step(ctx)
        if decision:
            return decision
    if not ctx.theirs:
        if not ctx.seq:
            return opening(ctx)
        return uncontested(ctx)
    decision = contested(ctx)
    if decision is None and _owns(ctx):
        decision = continuation(ctx)
    return decision


# ── Openings ──────────────────────────────────────────────────────────────────

def _opens(h: Hand) -> bool:
    two = sum(sorted(h.len.values(), reverse=True)[:2])
    return h.hcp >= 12 or (h.hcp >= OPEN_MIN and h.hcp + two >= 20)


def opening_suit(h: Hand) -> str:
    longest = max(h.len.values())
    if longest >= 5:
        # The longest suit; with 5-5 the higher (GIB opens 1S with spades-clubs).
        return max((s for s in SUITS if h.len[s] == longest), key=SUITS.index)
    c, d = h.len['C'], h.len['D']
    if d > c:
        return 'D'
    if c > d:
        return 'C'
    return 'D' if c >= 4 else 'C'


def one_level_alert(suit: str) -> str:
    if suit in MAJORS:
        return f"5+ {SYM[suit]}, 11-21 HCP."
    if suit == 'D':
        return f"3+ {SYM['D']}, usually 4. 11-21 HCP."
    return f"3+ {SYM['C']}, 11-21 HCP."


def opening(ctx: Ctx) -> tuple:
    h = ctx.h
    fourth = len(ctx.calls) == 3
    if h.hcp >= STRONG_2C and ctx.ok('2C'):
        return '2C', "22+ HCP. Strong, forcing. Artificial."
    if h.balanced and NT2[0] <= h.hcp <= NT2[1]:
        return '2NT', "20-21 HCP, balanced."
    if h.balanced and NT1[0] <= h.hcp <= NT1[1]:
        return '1NT', "15-17 HCP, balanced."
    best = h.longest()
    if (fourth and best != 'C' and h.len[best] >= 6
            and FOURTH_SEAT[0] <= h.points <= FOURTH_SEAT[1] and ctx.ok(f"2{best}")):
        return f"2{best}", (f"6+ {SYM[best]}, {FOURTH_SEAT[0]}-{FOURTH_SEAT[1]} "
                            f"points. Fourth seat.")
    if _opens(h):
        suit = opening_suit(h)
        return f"1{suit}", one_level_alert(suit)
    if not fourth and WEAK[0] <= h.hcp <= WEAK[1]:
        n = h.len[best]
        if best in MAJORS and n >= 8 and ctx.ok(f"4{best}"):
            return f"4{best}", f"8+ {SYM[best]}, 5-10 HCP. Pre-emptive."
        if n >= 7 and ctx.ok(f"3{best}"):
            return f"3{best}", f"7+ {SYM[best]}, 5-10 HCP. Pre-emptive."
        if n == 6 and best != 'C' and h.good_suit(best) and ctx.ok(f"2{best}"):
            return f"2{best}", f"6 {SYM[best]}, 5-10 HCP, good suit. Weak two."
    return 'Pass', "Not an opening hand."


# ── Uncontested auctions ──────────────────────────────────────────────────────

def uncontested(ctx: Ctx) -> tuple:
    seq = ctx.seq
    first = seq[0]
    if first in ('1NT', '2NT'):
        return notrump(ctx, 0)
    if first == '2C':
        return strong_two(ctx)
    if level_of(first) == 1:
        return one_suit(ctx)
    return preempt(ctx)


# ── 1-of-a-suit openings ──────────────────────────────────────────────────────

def one_suit(ctx: Ctx) -> tuple:
    seq = ctx.seq
    n = len(seq)
    x = strain_of(seq[0])
    if n == 1:
        return respond_major(ctx, x) if x in MAJORS else respond_minor(ctx, x)
    if n == 2:
        return opener_rebid(ctx, x, seq[1])
    if n == 3:
        decision = responder_rebid(ctx, x)
        if decision:
            return decision
    if n == 4:
        decision = opener_third(ctx, x)
        if decision:
            return decision
    return continuation(ctx)


def _jump_shift(ctx: Ctx, x: str) -> tuple | None:
    """Soloway: a strong jump shift, 17+ points with 4+ controls and a good
    five-card suit, jumping from the one level to the two."""
    h = ctx.h
    if ctx.passed_hand(ctx.me) or h.points < JUMP_SHIFT_POINTS or h.controls < 4:
        return None
    for y in sorted(SUITS, key=lambda s: (h.len[s], SUITS.index(s)), reverse=True):
        if (SUITS.index(y) > SUITS.index(x) and h.len[y] >= 5 and h.good_suit(y)
                and ctx.ok(f"2{y}")):
            return f"2{y}", f"5+ {SYM[y]}, {JUMP_SHIFT_POINTS}+ points. Strong jump shift."
    return None


#: Count the trump length in a raise of 1M (the user's call, 2026-10-28:
#: ♠K5 ♥K9864 ♦K84 ♣832 raised 1♥ to 2♥): it is chosen on HCP plus one
#: point for each trump past three, so four and five trumps reach the limit
#: raise and game a point and two sooner. +0.13 a board, t = +2.9; bidding
#: 4M on any five trumps instead measured 0.00.
RAISE_TRUMP_POINTS = True


def _raise_on_trump_points(ctx: Ctx, x: str) -> tuple | None:
    """1M-2M / 3M / 4M on four or more trumps, judged on HCP + trumps past three."""
    value = ctx.h.hcp + ctx.h.len[x] - 3
    passed = ctx.passed_hand(ctx.me)
    if value > LIMIT[1] and ctx.ok(f"4{x}"):
        return f"4{x}", f"4+ {SYM[x]}, game values."
    if value >= LIMIT[0] and not passed:
        return f"3{x}", f"4+ {SYM[x]}. Limit raise."
    if value >= RAISE[0] and not (passed and value >= DRURY[0]):
        return f"2{x}", f"3+ {SYM[x]}. Single raise."
    return None


def respond_major(ctx: Ctx, x: str) -> tuple:
    h = ctx.h
    hcp, sup = h.hcp, h.len[x]
    passed = ctx.passed_hand(ctx.me)
    shortness = h.short(x)
    if sup >= 5 and hcp < 10 and shortness and ctx.ok(f"4{x}"):
        return f"4{x}", f"5+ {SYM[x]}, under 10 HCP. Pre-emptive raise."
    if RAISE_TRUMP_POINTS and sup >= 4 and hcp < JACOBY_MIN:
        raise_ = _raise_on_trump_points(ctx, x)
        if raise_:
            return raise_
    if hcp < RESPONSE_MIN:
        return 'Pass', f"Fewer than {RESPONSE_MIN} HCP."
    if sup >= 4 and not passed and hcp >= JACOBY_MIN:
        if shortness and hcp <= SPLINTER[1]:
            s = shortness[0]
            call = _splinter_call(x, s)
            if ctx.ok(call):
                return call, (f"Splinter: 4+ {SYM[x]}, short {SYM[s]}, "
                              f"{SPLINTER[0]}-{SPLINTER[1]} HCP.")
        return '2NT', f"Jacoby: 4+ {SYM[x]}, {JACOBY_MIN}+ HCP, game forcing."
    if passed and sup >= 3 and DRURY[0] <= hcp <= DRURY[1]:
        return '2C', f"Drury: 3+ {SYM[x]}, {DRURY[0]}-{DRURY[1]} HCP. Artificial."
    if sup >= 4 and LIMIT[0] <= hcp <= LIMIT[1] and not passed:
        if RAISE_TRUMP_POINTS:
            return f"3{x}", f"4+ {SYM[x]}. Limit raise."
        return f"3{x}", f"4+ {SYM[x]}, {LIMIT[0]}-{LIMIT[1]} HCP. Limit raise."
    if sup >= 3 and RAISE[0] <= hcp <= RAISE[1]:
        if RAISE_TRUMP_POINTS:
            return f"2{x}", f"3+ {SYM[x]}. Single raise."
        return f"2{x}", f"3+ {SYM[x]}, {RAISE[0]}-{RAISE[1]} HCP."
    js = _jump_shift(ctx, x)
    if js:
        return js
    if x == 'H' and h.len['S'] >= 4:
        return '1S', f"4+ {SYM['S']}, {RESPONSE_MIN}+ HCP."
    if not passed and hcp >= TWO_OVER_ONE:
        if x == 'S' and h.len['H'] >= 5:
            return '2H', f"5+ {SYM['H']}, 12+ HCP. Game forcing."
        if h.len['D'] >= 4 and h.len['D'] > h.len['C']:
            return '2D', f"4+ {SYM['D']}, 12+ HCP. Game forcing."
        if h.len['C'] >= 3:
            return '2C', f"3+ {SYM['C']}, 12+ HCP. Game forcing."
        return '2D', f"4+ {SYM['D']}, 12+ HCP. Game forcing."
    if passed:
        return '1NT', f"{RESPONSE_MIN}-11 HCP, no fit."
    return '1NT', f"{RESPONSE_MIN}-11 HCP. Forcing."


def respond_minor(ctx: Ctx, x: str) -> tuple:
    h = ctx.h
    hcp, sup = h.hcp, h.len[x]
    passed = ctx.passed_hand(ctx.me)
    if hcp < RESPONSE_MIN:
        return 'Pass', f"Fewer than {RESPONSE_MIN} HCP."
    js = _jump_shift(ctx, x)
    if js:
        return js
    majors = [s for s in MAJORS if h.len[s] >= 4]
    if (x == 'D' and not passed and hcp >= TWO_OVER_ONE and h.len['C'] >= 5
            and all(h.len['C'] > h.len[m] for m in MAJORS)):
        return '2C', f"4+ {SYM['C']}, 12+ HCP. Game forcing."
    if majors:
        m = 'S' if (len(majors) == 2 and h.len['S'] > h.len['H']) else majors[0]
        return f"1{m}", f"4+ {SYM[m]}, {RESPONSE_MIN}+ HCP."
    if x == 'C' and h.len['D'] >= 4:
        return '1D', f"4+ {SYM['D']}, {RESPONSE_MIN}+ HCP."
    if x == 'D' and not passed and hcp >= TWO_OVER_ONE and h.len['C'] >= 4:
        return '2C', f"4+ {SYM['C']}, 12+ HCP. Game forcing."
    need = 5 if x == 'C' else 4
    if sup >= need and hcp >= INVERTED_MIN:
        return f"2{x}", f"{need}+ {SYM[x]}, {INVERTED_MIN}+ HCP. Inverted, forcing."
    if sup >= 5 and hcp <= 9:
        return f"3{x}", f"5+ {SYM[x]}, {RESPONSE_MIN}-9 HCP. Weak raise."
    if hcp <= 10:
        return '1NT', f"{RESPONSE_MIN}-10 HCP, no 4-card major."
    if hcp <= 12:
        return '2NT', "11-12 HCP, invitational."
    return '3NT', "13+ HCP, no 4-card major."


def opener_rebid(ctx: Ctx, x: str, r: str) -> tuple:
    h = ctx.h
    hcp = h.judge
    passed_resp = ctx.passed_hand(ctx.pd)
    rl, rs = level_of(r), strain_of(r)

    # Responder's conventions first.
    if x in MAJORS and r == '2NT' and not passed_resp:
        return _jacoby_rebid(ctx, x)
    if x in MAJORS and _is_splinter(x, r):
        if hcp >= 16 and h.top(rs, ('K', 'Q', 'J')) == 0:
            return '4NT', f"Keycard Blackwood for {SYM[x]}. Artificial."
        return f"4{x}", TO_PLAY
    if x in MAJORS and r == '2C' and passed_resp:
        if hcp <= 11:
            return f"2{x}", f"Sub-minimum opening, {SYM[x]}."
        if hcp <= 14:
            return '2D', "Full opening values. Artificial."
        return f"4{x}", TO_PLAY
    if r == f"2{x}" and x in MAJORS:
        return _game_try(ctx, x)
    if r == f"3{x}" and x in MAJORS:
        return (f"4{x}", TO_PLAY) if hcp + _fit_bonus(h, x, 4) >= 14 \
            else ('Pass', "Declining the invitation.")
    if r == f"4{x}" or r == '3NT':
        return 'Pass', "Partner placed the contract."
    if x in MINORS and r == f"2{x}":
        return _inverted_rebid(ctx, x)
    if x in MINORS and r == f"3{x}":
        return ('3NT', TO_PLAY) if hcp >= 18 else ('Pass', "Partner's raise is weak.")
    if x in MINORS and r == '2NT':
        if hcp >= 14:
            return '3NT', TO_PLAY
        if h.len[x] >= 6:
            return f"3{x}", f"6+ {SYM[x]}, minimum."
        return 'Pass', "Minimum."
    if rl == 2 and rs in SUITS and rs != x and (
            _is_two_over_one(x, rs) or (x == 'D' and rs == 'C')) and not passed_resp:
        return _gf_rebid(ctx, x, rs)
    if rl == 2 and rs in SUITS and rs != x and SUITS.index(rs) > SUITS.index(x):
        return _gf_rebid(ctx, x, rs)          # strong jump shift: game forcing
    if r == '1NT':
        return _rebid_over_1nt(ctx, x, passed_resp)
    if rl == 1:
        return _rebid_over_new_suit(ctx, x, rs)
    return continuation(ctx)


def _is_two_over_one(x: str, y: str) -> bool:
    return y in SUITS and SUITS.index(y) < SUITS.index(x)


def _splinter_call(x: str, s: str) -> str:
    """The jump in `s` that splinters for `x`: 3♠ over hearts, else the four level."""
    return f"3{s}" if (x == 'H' and s == 'S') else f"4{s}"


def _is_splinter(x: str, r: str) -> bool:
    if x == 'H':
        return r in ('3S', '4C', '4D')
    if x == 'S':
        return r in ('4C', '4D', '4H')
    return False


def _jacoby_rebid(ctx: Ctx, x: str) -> tuple:
    h = ctx.h
    short = h.short(x)
    if short and ctx.ok(f"3{short[0]}"):
        s = short[0]
        return f"3{s}", f"Shortness in {SYM[s]}."
    for s in SUITS:
        if s != x and h.len[s] >= 5 and h.good_suit(s) and ctx.ok(f"4{s}"):
            return f"4{s}", f"5+ {SYM[s]}, good second suit."
    if h.hcp >= 18:
        return f"3{x}", "18+ HCP, no shortness."
    if h.hcp >= 15:
        return '3NT', "15-17 HCP, no shortness."
    return f"4{x}", "Minimum, no shortness."


def _game_try(ctx: Ctx, x: str) -> tuple:
    h = ctx.h
    hcp = h.hcp
    short = h.short(x)
    fit = hcp + _fit_bonus(h, x, 3)
    if hcp <= 14 and fit < 18:
        return 'Pass', "Minimum."
    if SELF_SPLINTER and hcp >= SELF_SPLINTER_MIN and short:
        s = short[0]
        call = _splinter_call(x, s)
        if ctx.ok(call):
            return call, f"Splinter: short {SYM[s]}, {SELF_SPLINTER_MIN}+ HCP. Game forcing."
    if hcp >= 18 or fit >= 18 or (hcp >= 17 and not short):
        return f"4{x}", TO_PLAY
    if short:
        step = '2S' if x == 'H' else '2NT'
        return step, "Short-suit game try. Artificial."
    for s in SUITS:
        call = f"3{s}"
        if (s != x and h.len[s] >= 3 and h.top(s, ('A', 'K')) <= 1
                and ctx.ok(call) and rank_of(call) < rank_of(f"3{x}")):
            return call, f"3+ {SYM[s]}, 15-16 HCP. Help-suit game try."
    return f"3{x}", "15-16 HCP, invitational."


def _inverted_rebid(ctx: Ctx, x: str) -> tuple:
    h = ctx.h
    if h.balanced and h.hcp <= 14:
        return '2NT', "11-14 HCP, balanced."
    if h.balanced and h.hcp >= 18:
        return '3NT', TO_PLAY
    if h.hcp <= 14:
        return f"3{x}", "Minimum, unbalanced."
    for s in SUITS:
        if s != x and h.len[s] >= 4 and ctx.ok(f"2{s}"):
            return f"2{s}", f"4+ {SYM[s]}, 15+ HCP."
    return '3NT', TO_PLAY


def _gf_rebid(ctx: Ctx, x: str, y: str) -> tuple:
    """Opener's rebid after a game-forcing response (2/1, 1D-2C, jump shift)."""
    h = ctx.h
    if y in MAJORS and h.len[y] >= 3:
        call = ctx.cheapest(y, 3)
        if call:
            return call, f"3+ {SYM[y]} support, game forcing."
    if y in MINORS and h.len[y] >= 4:
        call = ctx.cheapest(y, 3)
        if call and level_of(call) <= 4:
            return call, f"4+ {SYM[y]} support, game forcing."
    if h.len[x] >= 6:
        call = ctx.cheapest(x, 2)
        if call:
            return call, f"5+ {SYM[x]}. Game forcing."
    for s in sorted(SUITS, key=lambda s: SUITS.index(s), reverse=True):
        if s not in (x, y) and h.len[s] >= 4:
            call = ctx.cheapest(s, 2)
            if call and level_of(call) == 2:
                return call, f"4+ {SYM[s]}. Game forcing."
    if h.balanced and ctx.ok('2NT'):
        return '2NT', "Balanced or no other bid. Game forcing."
    call = ctx.cheapest(x, 2)
    if call and level_of(call) == 2:
        return call, f"5+ {SYM[x]}. Game forcing."
    for s in SUITS:
        if s not in (x, y) and h.len[s] >= 4:
            call = ctx.cheapest(s, 3)
            if call and level_of(call) == 3 and rank_of(call) < rank_of('3NT'):
                return call, f"4+ {SYM[s]}. Game forcing."
    if ctx.ok('2NT'):
        return '2NT', "Balanced or no other bid. Game forcing."
    return continuation(ctx)


def _rebid_over_1nt(ctx: Ctx, x: str, passed_resp: bool) -> tuple:
    """1M-1NT (forcing unless responder is a passed hand) and 1m-1NT."""
    h = ctx.h
    hcp = h.hcp
    if h.balanced and hcp <= 14 and (passed_resp or x in MINORS):
        return 'Pass', "Minimum, balanced."
    if h.balanced and 18 <= hcp <= 19:
        return ('3NT', TO_PLAY) if x in MINORS else ('2NT', "18-19 HCP, balanced.")
    if h.len[x] >= 6 and hcp >= 16:
        if hcp <= 18 and ctx.ok(f"3{x}"):
            return f"3{x}", f"6+ {SYM[x]}, 16-18 HCP."
        if x in MAJORS and ctx.ok(f"4{x}"):
            return f"4{x}", TO_PLAY
        return '3NT', TO_PLAY
    if h.len[x] >= 6 and hcp <= 15:
        return f"2{x}", _rebid_1nt_alert(x)
    for z in sorted(SUITS, key=lambda s: (h.len[s], SUITS.index(s)), reverse=True):
        if z == x or h.len[z] < 4:
            continue
        if SUITS.index(z) < SUITS.index(x):
            if hcp >= 19 and ctx.ok(f"3{z}"):
                return f"3{z}", f"4+ {SYM[z]}, 19+ HCP. Game forcing."
            if ctx.ok(f"2{z}") and hcp <= 18:
                return f"2{z}", _new_suit_over_1nt(z)
        elif hcp >= 16 and ctx.ok(f"2{z}"):
            return f"2{z}", f"4+ {SYM[z]}, 16+ HCP. Reverse."
    if (h.len[x] >= 5 or (x in MINORS and h.len[x] >= 4)) and hcp <= 15:
        return f"2{x}", _rebid_1nt_alert(x)
    minors = [m for m in MINORS if m != x and h.len[m] >= 3]
    if minors:
        m = max(minors, key=lambda s: (h.len[s], -SUITS.index(s)))
        if ctx.ok(f"2{m}"):
            return f"2{m}", _new_suit_over_1nt(m)
    if ctx.ok('2NT') and hcp >= 16:
        return '2NT', "18-19 HCP, balanced."
    return 'Pass', "Minimum, balanced."


def _rebid_1nt_alert(x: str) -> str:
    """Opener's 2x after 1x-1NT. An unbalanced minor opening holds four:
    only 4-4-3-2 shapes open on three, and those pass 1NT or bid 3NT."""
    return f"{5 if x in MAJORS else 4}+ {SYM[x]}, 11-15 HCP."


def _new_suit_over_1nt(z: str) -> str:
    return f"3+ {SYM[z]}, 11-18 HCP." if z in MINORS else f"4+ {SYM[z]}, 11-18 HCP."


def _rebid_over_new_suit(ctx: Ctx, x: str, y: str) -> tuple:
    """1x-1y: raise, a one-level suit, notrump, rebid, new suit, reverse."""
    h = ctx.h
    hcp = h.hcp
    if y in MAJORS and h.len[y] >= 4:
        if hcp <= 14:
            return f"2{y}", f"4+ {SYM[y]}, 11-14 HCP."
        if hcp <= 17:
            return f"3{y}", f"4+ {SYM[y]}, 15-17 HCP."
        return f"4{y}", f"4+ {SYM[y]}, 18+ HCP."
    for z in ('H', 'S'):
        if (SUITS.index(z) > SUITS.index(y) and z != x and h.len[z] >= 4
                and hcp <= 18 and ctx.ok(f"1{z}")):
            return f"1{z}", f"4+ {SYM[z]}, 11-18 HCP."
    if h.balanced and hcp <= 14:
        return '1NT', "11-14 HCP, balanced."
    if h.balanced and 18 <= hcp <= 19:
        return '2NT', "18-19 HCP, balanced."
    if y == 'D' and x == 'C' and h.len['D'] >= 4 and hcp <= 14:
        return '2D', f"4+ {SYM['D']}, 11-14 HCP."
    if h.len[x] >= 6:
        if hcp >= 17 and ctx.ok(f"3{x}"):
            return f"3{x}", f"6+ {SYM[x]}, 17-21 HCP."
        return f"2{x}", f"5+ {SYM[x]}, 11-18 HCP."
    for z in sorted(SUITS, key=lambda s: (h.len[s], SUITS.index(s)), reverse=True):
        if z in (x, y) or h.len[z] < 4:
            continue
        if SUITS.index(z) < SUITS.index(x):
            if hcp >= 19 and ctx.ok(f"3{z}"):
                return f"3{z}", f"4+ {SYM[z]}, 19+ HCP. Game forcing."
            if ctx.ok(f"2{z}") and hcp <= 18:
                return f"2{z}", f"4+ {SYM[z]}, 11-18 HCP."
        elif hcp >= 16 and ctx.ok(f"2{z}"):
            return f"2{z}", f"4+ {SYM[z]}, 16+ HCP. Reverse."
    if hcp <= 18:
        return f"2{x}", f"5+ {SYM[x]}, 11-18 HCP."
    return '3NT', TO_PLAY


# ── Responder's second call, opener's third ───────────────────────────────────

# What opener's rebid showed, (low, high) HCP.
def opener_range(seq: list[str]) -> tuple[int, int]:
    x = strain_of(seq[0])
    r, o = seq[1], seq[2]
    ol, os_ = level_of(o), strain_of(o)
    y = strain_of(r)
    if o == '1NT':
        return (11, 14)
    if o == '2NT':
        return (18, 19)
    if os_ == y and y in SUITS and r != '1NT':
        return {2: (11, 14), 3: (15, 17)}.get(ol, (18, 21))
    if os_ == x:
        if ol == 2:
            return (11, 16) if r != '1NT' else (11, 15)
        return (17, 21) if r != '1NT' else (16, 18)
    if os_ in SUITS and ol == 2 and SUITS.index(os_) > SUITS.index(x):
        return (16, 21)
    if os_ in SUITS and ol == 3:
        return (19, 21)
    return (11, 18)


def responder_rebid(ctx: Ctx, x: str) -> tuple | None:
    seq = ctx.seq
    h = ctx.h
    hcp = h.judge
    r, o = seq[1], seq[2]
    y = strain_of(r)
    os_, ol = strain_of(o), level_of(o)

    # Answers to conventions this hand started.
    if r == '2NT' and x in MAJORS:                       # Jacoby
        shown = {f"4{x}": 11, '3NT': 15, f"3{x}": 18}.get(o, 11)
        if hcp + shown >= SLAM and ctx.ok('4NT'):
            return '4NT', f"Keycard Blackwood for {SYM[x]}. Artificial."
        if ctx.ok(f"4{x}"):
            return f"4{x}", TO_PLAY
        return 'Pass', "Partner placed the contract."
    if x in MAJORS and _is_splinter(x, r):
        return 'Pass', "Partner placed the contract."
    if x in MAJORS and r == '2C' and ctx.passed_hand(ctx.me):   # Drury
        if o == '2D':
            return (f"3{x}", "Invitational.") if hcp >= 11 else (f"2{x}", "Sign-off.")
        return 'Pass', "Partner placed the contract."
    if r == f"2{x}" and x in MAJORS:                     # after a game try
        fit = hcp + _fit_bonus(h, x, 5)
        if _is_splinter(x, o):                           # opener's splinter: game forcing
            return f"4{x}", TO_PLAY
        if o == '3NT':                                   # a choice of games (roadmap 3.7)
            if h.len[x] >= 4 or h.short(x):
                return f"4{x}", "Choice of games: a fourth trump or a short suit."
            return 'Pass', "Choice of games: three trumps, no short suit."
        if o in ('2S', '2NT') and o != f"2{x}":
            return (f"4{x}", TO_PLAY) if fit >= 9 else (f"3{x}", "Declining the game try.")
        if ol == 3 and os_ in SUITS and os_ != x:
            accept = fit >= 9 or (fit >= 8 and (h.len[os_] <= 1 or h.top(os_, ('A', 'K', 'Q')) >= 1))
            return (f"4{x}", TO_PLAY) if accept else (f"3{x}", "Declining the game try.")
        if o == f"3{x}":
            return (f"4{x}", TO_PLAY) if fit >= 9 else ('Pass', "Declining the invitation.")
        return 'Pass', "Partner placed the contract."
    if x in MINORS and r == f"2{x}":                     # inverted
        if o == '2NT':
            return ('3NT', TO_PLAY) if hcp >= 13 else ('Pass', "No game.")
        if o == f"3{x}":
            return ('3NT', TO_PLAY) if hcp >= 13 else ('Pass', "No game.")
        return None
    if level_of(r) == 2 and y in SUITS and y != x:       # game forcing auctions
        return None

    lo, hi = opener_range(seq)
    if r == '1NT':
        return _after_1nt_response(ctx, x, o, lo, hi)

    # 1x-1y-rebid: the most common sequences in bridge.
    if os_ == y and y in SUITS:                          # opener raised
        if y in MAJORS:
            if hcp + lo >= SLAM and ctx.ok('4NT'):
                return '4NT', f"Keycard Blackwood for {SYM[y]}. Artificial."
            if ol >= 4:
                return 'Pass', "Partner placed the contract."
            fit = hcp + _fit_bonus(h, y, 4)
            if fit + lo >= GAME_MAJOR:
                return f"4{y}", TO_PLAY
            if fit + hi >= GAME_MAJOR and ol == 2:
                return f"3{y}", "Invitational."
            return 'Pass', "No game."
        if hcp + lo >= GAME:
            return placed(ctx, ('3NT', TO_PLAY))
        return 'Pass', "No game."
    if o == '1NT':
        if y in MAJORS and h.len[y] >= 5 and hcp >= 11:
            nmf = '2D' if x == 'C' else '2C'
            if ctx.ok(nmf):
                return nmf, "New minor forcing. Artificial."
        if hcp + lo >= GAME:
            if y in MAJORS and h.len[y] >= 6:
                if hcp + lo >= GAME_MAJOR:
                    return f"4{y}", TO_PLAY
                if ctx.ok(f"3{y}"):
                    return f"3{y}", f"6+ {SYM[y]}, invitational."
            if hcp + lo >= SLAM:
                return '6NT', TO_PLAY
            if hcp + hi >= SLAM and ctx.ok('4NT'):
                return '4NT', "Quantitative: invites 6NT."
            return '3NT', TO_PLAY
        if hcp + hi >= GAME:
            if y in SUITS and h.len[y] >= 6 and ctx.ok(f"3{y}"):
                return f"3{y}", f"6+ {SYM[y]}, invitational."
            return '2NT', "Invitational."
        if y in SUITS and h.len[y] >= 6 and ctx.ok(f"2{y}"):
            return f"2{y}", f"6+ {SYM[y]}, to play."
        return 'Pass', "No game."
    if o == '2NT':
        if hcp + lo >= SLAM:
            return '6NT', TO_PLAY
        if y in MAJORS and h.len[y] >= 6:
            return f"4{y}", TO_PLAY
        if x in MAJORS and h.len[x] >= 3:
            return f"4{x}", TO_PLAY
        return '3NT', TO_PLAY
    if os_ == x:                                         # opener rebid the suit
        fit = h.len[x] >= (2 if ol == 3 else 3)
        if ol == 3:
            if x in MAJORS and fit:
                return f"4{x}", TO_PLAY
            return '3NT', TO_PLAY
        if fit:
            g = GAME_MAJOR if x in MAJORS else GAME
            if hcp + lo >= g:
                return (f"4{x}", TO_PLAY) if x in MAJORS else ('3NT', TO_PLAY)
            if hcp + hi >= g:
                return f"3{x}", "Invitational."
            return 'Pass', "No game."
        if y in SUITS and h.len[y] >= 6:
            if hcp + lo >= GAME_MAJOR and y in MAJORS:
                return f"4{y}", TO_PLAY
            if hcp + hi >= GAME_MAJOR and ctx.ok(f"3{y}"):
                return f"3{y}", f"6+ {SYM[y]}, invitational."
            if ctx.ok(f"2{y}"):
                return f"2{y}", f"6+ {SYM[y]}, to play."
        if hcp + lo >= GAME:
            return '3NT', TO_PLAY
        if hcp + hi >= GAME and ctx.ok('2NT'):
            return '2NT', "Invitational."
        return 'Pass', "No game."
    if os_ in SUITS:                                     # a new suit by opener
        z = os_
        reverse = ol == 2 and SUITS.index(z) > SUITS.index(x)
        forcing = reverse or ol == 3
        if forcing:
            return _after_forcing_rebid(ctx, x, y, z)
        if hcp + lo >= GAME:
            for m, n in ((z, 4), (x, 3), (y, 6)):
                if m in MAJORS and h.len[m] >= n:
                    if hcp + lo >= GAME_MAJOR:
                        return placed(ctx, (f"4{m}", TO_PLAY))
                    if ctx.ok(f"3{m}"):
                        return f"3{m}", "Invitational."
                    break
            fourth = [s for s in SUITS if s not in (x, y, z)]
            if fourth:
                call = ctx.cheapest(fourth[0])
                if call and level_of(call) <= 3 and rank_of(call) < rank_of('3NT'):
                    return call, "Fourth suit forcing. Artificial."
            return placed(ctx, ('3NT', TO_PLAY))
        if hcp + hi >= GAME:
            if z in MAJORS and h.len[z] >= 4 and ctx.ok(f"3{z}"):
                return f"3{z}", "Invitational."
            if h.len[x] >= 3 and ctx.ok(f"3{x}"):
                return f"3{x}", "Invitational."
            if ctx.ok('2NT'):
                return '2NT', "Invitational."
        if z in MAJORS and h.len[z] >= 4 and ctx.ok(f"2{z}"):
            return f"2{z}", f"4+ {SYM[z]}, minimum."
        if y in SUITS and h.len[y] >= 6 and ctx.ok(f"2{y}"):
            return f"2{y}", f"6+ {SYM[y]}, to play."
        if h.len[z] >= 4 and ol == 2:
            return 'Pass', "Happy in opener's second suit."
        if h.len[x] >= 2 and ctx.ok(f"2{x}") and h.len[x] >= h.len[z]:
            return f"2{x}", f"Preference to {SYM[x]}."
        if ol == 1 and ctx.ok('1NT'):
            return '1NT', "Minimum."
        return 'Pass', "No game."
    return None


def _after_1nt_response(ctx: Ctx, x: str, o: str, lo: int, hi: int) -> tuple:
    h = ctx.h
    hcp = h.judge
    os_, ol = strain_of(o), level_of(o)
    if o == 'Pass':
        return 'Pass', "Partner passed."
    if o == '2NT':
        if x in MAJORS and h.len[x] >= 3:
            return f"4{x}", TO_PLAY
        return ('3NT', TO_PLAY) if hcp >= 7 else ('Pass', "No game.")
    if os_ == x and ol == 3:
        if x in MAJORS:
            return (f"4{x}", TO_PLAY) if hcp >= 8 or h.len[x] >= 3 else ('Pass', "No game.")
        return ('3NT', TO_PLAY) if hcp >= 8 else ('Pass', "No game.")
    if ol >= 3 or o in (f"4{x}", '3NT'):
        if ol == 3 and os_ != x and os_ in SUITS:
            return continuation(ctx)
        return 'Pass', "Partner placed the contract."
    if os_ in SUITS and SUITS.index(os_) > SUITS.index(x):     # reverse
        if hcp >= 9:
            if x in MAJORS and h.len[x] >= 2:
                return f"4{x}", TO_PLAY
            return '3NT', TO_PLAY
        if x in MAJORS and h.len[x] >= 2 and ctx.ok(f"3{x}"):
            return f"3{x}", f"Preference to {SYM[x]}."
        return '2NT', "Weak, no fit."
    if x in MAJORS and h.len[x] >= 3 and 10 <= h.hcp <= 11 and ctx.ok(f"3{x}"):
        return f"3{x}", f"3+ {SYM[x]} support, 10-11 HCP. Limit raise."
    if os_ == x:
        return 'Pass', "No game."
    if x in MAJORS and h.len[x] >= 2 and h.len[x] >= h.len[os_] and ctx.ok(f"2{x}"):
        return f"2{x}", f"Preference to {SYM[x]}."
    if 10 <= h.hcp <= 11 and ctx.ok('2NT'):
        return '2NT', "10-11 HCP, invitational."
    for s in SUITS:
        if s not in (x, os_) and h.len[s] >= 6 and ctx.ok(f"2{s}"):
            return f"2{s}", f"6+ {SYM[s]}, to play."
    return 'Pass', "Happy in opener's suit."


def _after_forcing_rebid(ctx: Ctx, x: str, y: str, z: str) -> tuple:
    """Opener reversed or jump-shifted. Weak hands find the cheapest
    sensible spot; anything better goes to game."""
    h = ctx.h
    if h.judge >= 8 or level_of(ctx.seq[2]) == 3:
        if z in MAJORS and h.len[z] >= 4 and ctx.ok(f"4{z}"):
            return f"4{z}", TO_PLAY
        if x in MAJORS and h.len[x] >= 3 and ctx.ok(f"4{x}"):
            return f"4{x}", TO_PLAY
        if y in MAJORS and h.len[y] >= 6 and ctx.ok(f"4{y}"):
            return f"4{y}", TO_PLAY
        if ctx.ok('3NT'):
            return '3NT', TO_PLAY
        return continuation(ctx)
    if y in SUITS and h.len[y] >= 5:
        call = ctx.cheapest(y, 2)
        if call and level_of(call) <= 3:
            return call, f"5+ {SYM[y]}, weak."
    call = ctx.cheapest(x, 2)
    if call and h.len[x] >= 2 and level_of(call) <= 3:
        return call, f"Preference to {SYM[x]}."
    if ctx.ok('2NT'):
        return '2NT', "Weak, no fit."
    return continuation(ctx)


def opener_third(ctx: Ctx, x: str) -> tuple | None:
    seq = ctx.seq
    h = ctx.h
    hcp = h.judge
    r, o, last = seq[1], seq[2], seq[3]
    y = strain_of(r)
    if last in ('3NT', '6NT'):
        return 'Pass', "Partner placed the contract."
    if level_of(last) >= 4 and strain_of(last) in SUITS and not _is_splinter(x, last):
        if strain_of(last) in MINORS and last != f"4{x}":
            return None
        return 'Pass', "Partner placed the contract."
    if last == '2NT' and level_of(o) <= 2:
        if hcp >= 13:
            if x in MAJORS and h.len[x] >= 6:
                return f"4{x}", TO_PLAY
            return '3NT', TO_PLAY
        return 'Pass', "Minimum."
    if level_of(last) == 3 and strain_of(last) in SUITS and last != o:
        # Responder's three-level suit here is invitational: game needs a
        # little more than a minimum.
        s = strain_of(last)
        if hcp >= 14 or (hcp >= 13 and level_of(o) == 2):
            if s in MAJORS:
                return f"4{s}", TO_PLAY
            return '3NT', TO_PLAY
        return 'Pass', "Declining the invitation."
    if last == '4NT' and o in ('1NT', '2NT'):
        lo, hi = opener_range(seq[:3])
        return ('6NT', TO_PLAY) if hcp >= hi - 1 else ('Pass', "Minimum, declining.")
    nmf = '2D' if x == 'C' else '2C'
    if o == '1NT' and last == nmf and y in MAJORS:
        if h.len[y] >= 3:
            return (f"3{y}", f"3 {SYM[y]}, 13-14 HCP.") if h.hcp >= 13 else \
                (f"2{y}", f"3 {SYM[y]}, 11-12 HCP.")
        other = 'H' if y == 'S' else 'S'
        if h.len[other] >= 4 and ctx.ok(f"2{other}"):
            return f"2{other}", f"4 {SYM[other]}."
        return ('3NT', TO_PLAY) if h.hcp >= 13 else ('2NT', "11-12 HCP, no fit.")
    if (y in SUITS and strain_of(o) in SUITS and strain_of(last) in SUITS
            and len({x, y, strain_of(o), strain_of(last)}) == 4):
        w = strain_of(last)                                  # fourth suit forcing
        if h.len[y] >= 3:
            call = ctx.cheapest(y, 2)
            if call:
                return call, f"3+ {SYM[y]} support, game forcing."
        if h.len[x] >= 5:
            call = ctx.cheapest(x, 2)
            if call:
                return call, f"5+ {SYM[x]}. Game forcing."
        call = '2NT' if ctx.ok('2NT') else '3NT'
        if ctx.ok(call):
            return call, "Game forcing, no better bid."
    return None


# ── Strong 2C ─────────────────────────────────────────────────────────────────

def strong_two(ctx: Ctx) -> tuple:
    seq = ctx.seq
    h = ctx.h
    n = len(seq)
    if n == 1:
        for s in ('S', 'H', 'D', 'C'):
            call = f"2{s}" if s in MAJORS else f"3{s}"
            if h.hcp >= 8 and h.len[s] >= 5 and h.good_suit(s) and ctx.ok(call):
                return call, f"5+ {SYM[s]}, 8+ HCP. Positive."
        if h.hcp >= 8 and h.balanced:
            return '2NT', "8+ HCP, balanced. Positive."
        return '2D', "Waiting. Artificial."
    if n == 2:
        if seq[1] == '2D':
            if h.balanced and NT_AFTER_2C[0] <= h.hcp <= NT_AFTER_2C[1]:
                return '2NT', "22-24 HCP, balanced."
            if h.balanced and h.hcp >= 25:
                return '3NT', "25+ HCP, balanced."
            s = h.longest()
            call = ctx.cheapest(s, 2)
            return call, f"4+ {SYM[s]}. Game forcing."
        return continuation(ctx)
    if seq[1] == '2D' and seq[2] == '2NT':
        return notrump(ctx, 2)
    if seq[1] == '2D' and seq[2] == '3NT' and n == 3:
        if ctx.h.judge >= 8:
            return '6NT', TO_PLAY
        return 'Pass', "Partner placed the contract."
    if n == 3 and seq[1] == '2D':
        s = strain_of(seq[2])
        if s in SUITS and h.len[s] >= 3:
            if h.judge >= 5:
                call = ctx.cheapest(s, 3)
                if call and level_of(call) == 3:
                    return call, f"3+ {SYM[s]} support, some values."
            if ctx.ok(f"4{s}") and s in MAJORS:
                return f"4{s}", f"3+ {SYM[s]} support, weak."
    return continuation(ctx)


# ── Weak twos and pre-empts ───────────────────────────────────────────────────

def preempt(ctx: Ctx) -> tuple:
    seq = ctx.seq
    h = ctx.h
    x = strain_of(seq[0])
    if len(seq) == 1:
        if x in MAJORS and h.len[x] >= 2 and h.judge >= 16 and ctx.ok(f"4{x}"):
            return f"4{x}", TO_PLAY
        if x in MAJORS and h.len[x] >= 3 and h.judge <= 15:
            call = ctx.cheapest(x, 3)
            if call and level_of(call) == 3 and level_of(seq[0]) == 2:
                return call, f"3+ {SYM[x]}, pre-emptive raise."
        if h.judge >= 16 and h.balanced and ctx.ok('3NT'):
            return '3NT', TO_PLAY
        return 'Pass', "Nothing to add."
    return continuation(ctx)


# ── Notrump systems ───────────────────────────────────────────────────────────

def _nt_range(seq: list[str], start: int) -> tuple[int, int]:
    if start == 2:
        return NT_AFTER_2C
    return NT1 if seq[start] == '1NT' else NT2


def notrump(ctx: Ctx, start: int) -> tuple:
    """1NT, 2NT and 2C-2D-2NT: Stayman, Jacoby and Texas transfers, minor
    suit Stayman, minor transfers (over 1NT), shortness bids, Gerber,
    quantitative 4NT."""
    seq = ctx.seq[start:]
    n = len(seq)
    base = level_of(seq[0])
    lo, hi = NT_OVERCALL if ctx.nt_overcall else _nt_range(ctx.seq, start)
    if n == 1:
        return _nt_response(ctx, base, lo, hi)
    if n == 2:
        return _nt_opener_answer(ctx, base, seq[1], lo, hi)
    if n == 3:
        return _nt_responder_second(ctx, base, seq, lo, hi)
    if n == 4:
        return _nt_opener_third(ctx, base, seq, lo, hi)
    return continuation(ctx)


def _nt_codes(base: int) -> dict:
    if base == 1:
        return {'stayman': '2C', 'to_h': '2D', 'to_s': '2H', 'mss': '2S',
                'to_c': '2NT', 'to_d': '3C'}
    return {'stayman': '3C', 'to_h': '3D', 'to_s': '3H', 'mss': '3S',
            'to_c': None, 'to_d': None}


def _nt_response(ctx: Ctx, base: int, lo: int, hi: int) -> tuple:
    h = ctx.h
    hcp = h.judge
    code = _nt_codes(base)
    m4 = [s for s in MAJORS if h.len[s] == 4]
    m5 = [s for s in MAJORS if h.len[s] >= 5]
    if hcp + lo >= SLAM:
        if m5 and h.len[h.longest(MAJORS)] >= 6:
            s = h.longest(MAJORS)
            texas = '4D' if s == 'H' else '4H'
            if ctx.ok(texas):
                return texas, f"Texas: 6+ {SYM[s]}. Artificial."
        if hcp + lo >= GRAND and ctx.ok('4C'):
            return '4C', "Gerber: asks for aces. Artificial."
        return '6NT', TO_PLAY
    if hcp + hi >= SLAM and not m5 and ctx.ok('4NT'):
        return '4NT', "Quantitative: invites 6NT."
    if hcp + lo >= NT_GAME:
        if m5:
            s = h.longest(MAJORS)
            if h.len[s] >= 6:
                texas = '4D' if s == 'H' else '4H'
                return texas, f"Texas: 6+ {SYM[s]}. Artificial."
            call = code['to_h'] if s == 'H' else code['to_s']
            return call, f"Transfer: 5+ {SYM[s]}. Artificial."
        if m4 and h.shape != [4, 3, 3, 3]:
            return code['stayman'], "Stayman: asks for a 4-card major. Artificial."
        minors5 = [m for m in MINORS if h.len[m] >= 5]
        if (minors5 and all(h.len[m] >= 4 for m in MINORS) and not h.balanced
                and ctx.ok(code['mss'])):
            return code['mss'], "Minor Stayman: 5-4+ minors, game forcing. Artificial."
        short = h.short()
        if (base == 1 and short and not m5 and h.shape[0] <= 5
                and all(h.len[s] >= 4 for s in SUITS if s != short[0])):
            s = short[0]
            call = f"3{s}"
            if s != 'C' and ctx.ok(call):
                return call, f"Short {SYM[s]}, 4+ in the others, game forcing."
        return '3NT', TO_PLAY
    if hcp + hi >= NT_GAME and base == 1:
        if m5:
            s = h.longest(MAJORS)
            call = code['to_h'] if s == 'H' else code['to_s']
            return call, f"Transfer: 5+ {SYM[s]}. Artificial."
        return code['stayman'], "Stayman: asks for a 4-card major. Artificial."
    if m5:
        s = h.longest(MAJORS)
        call = code['to_h'] if s == 'H' else code['to_s']
        return call, f"Transfer: 5+ {SYM[s]}. Artificial."
    if base == 1 and h.len['C'] >= 6:
        return code['to_c'], f"Transfer: 6+ {SYM['C']}. Artificial."
    if base == 1 and h.len['D'] >= 6:
        return code['to_d'], f"Transfer: 6+ {SYM['D']}. Artificial."
    return 'Pass', "No game."


def _nt_opener_answer(ctx: Ctx, base: int, r: str, lo: int, hi: int) -> tuple:
    h = ctx.h
    code = _nt_codes(base)
    lvl = 2 if base == 1 else 3
    if r == code['stayman']:
        if h.len['H'] >= 4:
            return f"{lvl}H", f"4+ {SYM['H']}."
        if h.len['S'] >= 4:
            return f"{lvl}S", f"4+ {SYM['S']}, fewer than 4 {SYM['H']}."
        return f"{lvl}D", "No 4-card major. Artificial."
    for key, s in (('to_h', 'H'), ('to_s', 'S')):
        if r == code[key]:
            if base == 1 and h.len[s] >= 4 and h.judge >= hi:
                return f"3{s}", f"4+ {SYM[s]}, maximum. Super-accept."
            return f"{lvl}{s}", f"Completing the transfer to {SYM[s]}."
    if r == code['to_c'] and r:
        return '3C', f"Completing the transfer to {SYM['C']}."
    if r == code['to_d'] and r:
        return '3D', f"Completing the transfer to {SYM['D']}."
    if r == code['mss']:
        minors = [m for m in MINORS if h.len[m] >= 4]
        if minors:
            m = max(minors, key=lambda s: (h.len[s], SUITS.index(s)))
            return ctx.cheapest(m, 3), f"4+ {SYM[m]}."
        return ('2NT' if ctx.ok('2NT') else '3NT'), "No 4-card minor."
    if r in ('4D', '4H'):
        s = 'H' if r == '4D' else 'S'
        return f"4{s}", f"Completing the transfer to {SYM[s]}."
    if r == '4C':
        return _gerber_answer(ctx)
    if r == '4NT':
        if h.judge >= hi:
            return '6NT', TO_PLAY
        return 'Pass', "Minimum, declining."
    if base == 1 and r in ('3D', '3H', '3S'):
        s = strain_of(r)
        if h.stopper(s):
            return '3NT', TO_PLAY
        for m in MAJORS:
            if m != s and h.len[m] >= 4 and ctx.ok(f"4{m}"):
                return f"4{m}", TO_PLAY
        m = h.longest(tuple(x for x in MINORS if x != s))
        call = ctx.cheapest(m, 4)
        if call and level_of(call) <= 5:
            return call, natural(m)
        return '3NT', TO_PLAY
    return 'Pass', "Partner placed the contract."


def _nt_responder_second(ctx: Ctx, base: int, seq: list[str], lo: int, hi: int) -> tuple:
    h = ctx.h
    hcp = h.judge
    code = _nt_codes(base)
    r, o = seq[1], seq[2]
    if r == code['stayman']:
        s = strain_of(o)
        if s in MAJORS and h.len[s] >= 4:
            if hcp + lo >= GAME_MAJOR:
                return placed(ctx, (f"4{s}", TO_PLAY))
            return placed(ctx, (f"3{s}", "Invitational."))
        if hcp + lo >= NT_GAME:
            m5 = [m for m in MAJORS if h.len[m] >= 5]
            if m5 and o != '2S' and ctx.ok(f"3{m5[0]}"):
                return f"3{m5[0]}", f"5+ {SYM[m5[0]]}, game forcing."
            return placed(ctx, ('3NT', TO_PLAY))
        if ctx.ok('2NT'):
            return '2NT', "Invitational."
        return 'Pass', "No game."
    for key, s in (('to_h', 'H'), ('to_s', 'S')):
        if r == code[key]:
            if o == f"3{s}" and base == 1:                     # super-accept
                return (f"4{s}", TO_PLAY) if hcp >= 4 else ('Pass', "Weak.")
            if hcp + lo >= SLAM and ctx.ok('4NT'):
                return '4NT', "Quantitative: invites 6NT."
            if hcp + lo >= NT_GAME:
                return placed(ctx, ('3NT', f"5 {SYM[s]}, choice of games."))
            if hcp + hi >= NT_GAME and ctx.ok('2NT'):
                return '2NT', f"5 {SYM[s]}, invitational."
            return 'Pass', "Weak."
    if r in ('4D', '4H') and o in ('4H', '4S'):
        s = strain_of(o)
        if hcp + lo >= SLAM and ctx.ok('4NT'):
            return '4NT', f"Keycard Blackwood for {SYM[s]}. Artificial."
        return 'Pass', "Partner placed the contract."
    if r == code['mss']:
        m = strain_of(o)
        if m in MINORS and hcp + lo >= 29 and ctx.ok(f"5{m}"):
            return f"5{m}", TO_PLAY
        if ctx.ok('3NT'):
            return '3NT', TO_PLAY
        return 'Pass', "Partner placed the contract."
    return 'Pass', "Partner placed the contract."


def _nt_opener_third(ctx: Ctx, base: int, seq: list[str], lo: int, hi: int) -> tuple:
    h = ctx.h
    code = _nt_codes(base)
    r, last = seq[1], seq[3]
    if last == '2NT' or (last in ('3H', '3S') and r == code['stayman']):
        if h.judge >= hi - 1:
            if last in ('3H', '3S'):
                return f"4{strain_of(last)}", TO_PLAY
            target = strain_of(seq[2])
            if r in (code['to_h'], code['to_s']) and h.len[target] >= 3:
                return f"4{target}", TO_PLAY
            return '3NT', TO_PLAY
        if r in (code['to_h'], code['to_s']):
            target = strain_of(seq[2])
            if h.len[target] >= 3 and ctx.ok(f"3{target}"):
                return f"3{target}", "Minimum, 3-card support."
        return 'Pass', "Minimum, declining."
    if last == '3NT' and r in (code['to_h'], code['to_s']):
        target = strain_of(seq[2])
        if h.len[target] >= 3:
            return f"4{target}", TO_PLAY
        return 'Pass', "Partner placed the contract."
    if last == '4NT':
        return ('6NT', TO_PLAY) if h.judge >= hi else ('Pass', "Minimum, declining.")
    if r == code['stayman'] and level_of(last) == 3 and strain_of(last) in MAJORS:
        s = strain_of(last)
        if h.len[s] >= 3 and ctx.ok(f"4{s}"):
            return f"4{s}", TO_PLAY
        return '3NT', TO_PLAY
    return 'Pass', "Partner placed the contract."


# ── Slam conventions ──────────────────────────────────────────────────────────

def shown_suit(seq: list[str], i: int) -> str | None:
    """The suit call i of our side SHOWS, or None for an artificial call or
    notrump. Support-showing conventions show partner's suit."""
    call = seq[i]
    s = strain_of(call)
    if s is None or s == 'NT':
        if i == 1 and call == '2NT' and strain_of(seq[0]) in MAJORS \
                and level_of(seq[0]) == 1:
            return strain_of(seq[0])                         # Jacoby
        return None
    first = seq[0]
    if first in ('1NT', '2NT') or (first == '2C' and len(seq) > 2 and seq[2] == '2NT'):
        start = 0 if first in ('1NT', '2NT') else 2
        base = level_of(seq[start])
        code = _nt_codes(base)
        if i == start + 1:
            if call == code['stayman'] or call == code['mss'] or call == '4C':
                return None
            if call == code['to_h'] or call == '4D':
                return 'H'
            if call == code['to_s'] or call == '4H':
                return 'S'
            if call in (code['to_c'], code['to_d']):
                return 'C' if call == code['to_c'] else 'D'
            if base == 1 and call in ('3D', '3H', '3S'):
                return None
        if i == start + 2 and seq[start + 1] in (code['stayman'], code['mss']):
            return None if call in ('2D', '3D') and seq[start + 1] == code['stayman'] else s
        if i < start:
            return None
    if first == '2C' and i == 0:
        return None
    if first == '2C' and i == 1 and call == '2D':
        return None
    if i == 1 and level_of(first) == 1 and strain_of(first) in MAJORS:
        x = strain_of(first)
        if _is_splinter(x, call):
            return x
    if i == 2 and seq[1] == '2NT' and strain_of(first) in MAJORS and level_of(first) == 1:
        return None                                          # Jacoby rebids
    if i == 3 and len(seq) > 3 and len({strain_of(c) for c in seq[:4]} & set(SUITS)) == 4:
        return None                                          # fourth suit forcing
    return s


def agreed_trump(seq: list[str]) -> str | None:
    """The suit both partners have shown, latest first."""
    shown = {0: set(), 1: set()}
    agreed = None
    for i in range(len(seq)):
        s = shown_suit(seq, i)
        if s is None:
            continue
        side = i % 2
        if s in shown[1 - side]:
            agreed = s
        shown[side].add(s)
    return agreed


def answer_ask(ctx: Ctx) -> tuple | None:
    """Partner asked: keycards (RKCB 0314), aces (Gerber), the trump queen,
    or kings. DOPI when they interfere over 4NT."""
    seq = ctx.seq
    if len(seq) < 2 or ctx.ours[-1][0] != ctx.pd:
        return None
    h = ctx.h
    last = seq[-1]
    prior = seq[:-1]
    trump = agreed_trump(prior)
    if last == '4NT' and trump and not _quantitative(prior):
        interfered = ctx.calls and ctx.calls[-1][0] not in (ctx.me, ctx.pd) \
            and ctx.calls[-1][1] != 'Pass'
        keys = h.keycards(trump)
        if interfered:
            if keys % 3 == 0 and ctx.ok('X'):
                return 'X', "DOPI: 0 or 3 keycards."
            if keys % 3 == 1:
                return 'Pass', "DOPI: 1 or 4 keycards."
            call = ctx.cheapest(trump, 5)
            if call:
                return call, "DOPI: 2 or 5 keycards."
            return 'Pass', "DOPI: no room."
        voids = [s for s in SUITS if s != trump and h.len[s] == 0]
        if voids and keys in (2, 4) and ctx.ok('5NT'):
            return '5NT', "Even keycards and a void. Artificial."
        if voids and keys in (1, 3):
            v = voids[0]
            call = f"6{v}" if rank_of(f"6{v}") < rank_of(f"6{trump}") else f"6{trump}"
            if ctx.ok(call):
                return call, "Odd keycards and a void. Artificial."
        if keys in (0, 3):
            return '5C', "0 or 3 keycards. Artificial."
        if keys in (1, 4):
            return '5D', "1 or 4 keycards. Artificial."
        if h.has(trump, 'Q'):
            return '5S', "2 or 5 keycards, with the trump queen. Artificial."
        return '5H', "2 or 5 keycards, no trump queen. Artificial."
    if len(prior) >= 2 and prior[-1] in ('5C', '5D') and _asked_rkcb(prior[:-1]):
        trump = agreed_trump(prior[:-2])
        if trump and last == _queen_ask(prior[-1], trump):
            if h.has(trump, 'Q'):
                return '5NT', "Trump queen. Artificial."
            call = ctx.cheapest(trump, 5)
            if call:
                return call, "No trump queen."
            return 'Pass', "No trump queen."
    if (len(prior) >= 2 and last == '5NT' and _asked_rkcb(prior[:-1])
            and prior[-1] in ('5C', '5D', '5H', '5S')):
        trump = agreed_trump(prior[:-2])
        if trump:
            for s in SUITS:
                call = f"6{s}"
                if (s != trump and h.has(s, 'K') and ctx.ok(call)
                        and rank_of(call) < rank_of(f"6{trump}")):
                    return call, f"King of {SYM[s]}."
            return f"6{trump}", "No side king to show."
    if last == '4C' and _is_gerber(prior) and (ctx.we_opened and not ctx.theirs or ctx.nt_overcall):
        return _gerber_answer(ctx)
    return None


def _quantitative(prior: list[str]) -> bool:
    """4NT straight over partner's notrump is quantitative."""
    return bool(prior) and prior[-1] in ('1NT', '2NT', '3NT') and \
        not any(strain_of(c) in SUITS for c in prior[-1:])


def _asked_rkcb(prior: list[str]) -> bool:
    return bool(prior) and prior[-1] == '4NT' and agreed_trump(prior[:-1]) is not None \
        and not _quantitative(prior[:-1])


def _queen_ask(response: str, trump: str) -> str:
    order = ['5D', '5H', '5S'] if response == '5C' else ['5H', '5S']
    for call in order:
        if strain_of(call) != trump:
            return call
    return '5NT'


def _is_gerber(prior: list[str]) -> bool:
    return bool(prior) and prior[-1] in ('1NT', '2NT') and len(prior) in (1, 3)


def _gerber_answer(ctx: Ctx) -> tuple:
    aces = ctx.h.aces()
    if aces in (0, 4):
        return '4D', "0 or 4 aces. Artificial."
    return {1: ('4H', "1 ace. Artificial."), 2: ('4S', "2 aces. Artificial."),
            3: ('4NT', "3 aces.")}[aces]


def after_my_ask(ctx: Ctx) -> tuple | None:
    """I asked with 4NT or 4C; place the contract from the answer."""
    seq = ctx.seq
    if len(seq) < 2 or ctx.ours[-1][0] != ctx.pd:
        return None
    h = ctx.h
    last, prior = seq[-1], seq[:-1]
    my_ask = prior[-1] if prior else None
    if my_ask == '4NT' and _asked_rkcb(prior):
        trump = agreed_trump(prior[:-1])
        mine = h.keycards(trump)
        sets = {'5C': (0, 3), '5D': (1, 4), '5H': (2, 5), '5S': (2, 5),
                '5NT': (2, 4)}
        options = sets.get(last)
        if options is None and level_of(last) == 6:
            options = (1, 3)
        if options is None:
            return None
        theirs = options[1] if mine + options[1] <= 5 and mine <= 1 else options[0]
        missing = 5 - mine - theirs
        queen = h.has(trump, 'Q') or last == '5S'
        if missing >= 2:
            call = ctx.cheapest(trump, 5)
            return (call, TO_PLAY) if call else ('Pass', TO_PLAY)
        if missing == 1 or level_of(last) == 6:
            call = ctx.cheapest(trump, 6)
            if call and level_of(call) == 6:
                return call, TO_PLAY
            return 'Pass', TO_PLAY
        if last in ('5C', '5D') and not queen:
            ask = _queen_ask(last, trump)
            if ctx.ok(ask):
                return ask, "Asks for the trump queen. Artificial."
        if ctx.ok('5NT') and h.judge >= 20:
            return '5NT', "All keycards present; asks for kings. Artificial."
        return f"6{trump}", TO_PLAY
    if len(prior) >= 3 and prior[-2] in ('5C', '5D') and _asked_rkcb(prior[:-2]):
        trump = agreed_trump(prior[:-3])
        if trump and prior[-1] == _queen_ask(prior[-2], trump):
            if last == '5NT':
                return (f"7{trump}" if h.judge >= 22 else f"6{trump}"), TO_PLAY
            if level_of(last) == 5:
                return f"6{trump}", TO_PLAY
            return 'Pass', TO_PLAY
    if len(prior) >= 3 and prior[-1] == '5NT' and _asked_rkcb(prior[:-2]):
        trump = agreed_trump(prior[:-3])
        if trump and level_of(last) == 6:
            if strain_of(last) != trump and h.judge >= 20 and ctx.ok(f"7{trump}"):
                return f"7{trump}", TO_PLAY
            if strain_of(last) == trump:
                return 'Pass', TO_PLAY
            return f"6{trump}", TO_PLAY
    if my_ask == '4C' and _is_gerber(prior[:-1]) and (ctx.we_opened and not ctx.theirs or ctx.nt_overcall):
        theirs = {'4D': 0, '4H': 1, '4S': 2, '4NT': 3}.get(last)
        if theirs is None:
            return None
        mine = h.aces()
        if last == '4D' and mine == 0:
            theirs = 4
        missing = 4 - mine - theirs
        if missing >= 2:
            return ('4NT', TO_PLAY) if ctx.ok('4NT') else ('5NT', TO_PLAY)
        if missing == 1:
            return '6NT', TO_PLAY
        return ('7NT', TO_PLAY) if h.judge >= 20 else ('6NT', TO_PLAY)
    return None


# ── Generic continuation ──────────────────────────────────────────────────────

def _partner_min(seq: list[str], partner_index_parity: int) -> int:
    """A floor on partner's HCP from what they have bid."""
    best = 0
    first = seq[0]
    for i, call in enumerate(seq):
        if i % 2 != partner_index_parity:
            continue
        if i == 0:
            best = max(best, {'1NT': 15, '2NT': 20, '2C': 22}.get(
                call, 11 if level_of(call) == 1 else 5))
        elif i == 1:
            x = strain_of(first)
            if level_of(first) == 1 and x in SUITS:
                if call == '2NT' and x in MAJORS:
                    v = 13
                elif level_of(call) == 2 and strain_of(call) in SUITS and \
                        strain_of(call) != x and _is_two_over_one(x, strain_of(call)):
                    v = 12
                elif call == f"3{x}":
                    v = 11 if x in MAJORS else 6
                else:
                    v = 6
                best = max(best, v)
            elif first == '2C':
                best = max(best, 8 if call != '2D' else 0)
    return best


def _shown_lengths(seq: list[str], parity: int) -> dict:
    lengths = {s: 0 for s in SUITS}
    for i in range(len(seq)):
        if i % 2 != parity:
            continue
        s = shown_suit(seq, i)
        if s is None:
            continue
        times = sum(1 for j in range(i + 1) if j % 2 == parity and shown_suit(seq, j) == s)
        base = 5 if (i == 0 and s in MAJORS) else 4
        if i == 0 and s in MINORS:
            base = 3
        if seq[i] in ('2D', '2H', '2S') and i == 0:
            base = 6
        if level_of(seq[i]) >= 3 and i == 0:
            base = 7
        lengths[s] = max(lengths[s], base + (1 if times >= 2 else 0))
    return lengths


def _game_forced(seq: list[str], ctx: Ctx) -> bool:
    if not seq:
        return False
    if OVERCALL_READ and not ctx.we_opened and _their_opening_suit(ctx):
        return False                 # an opening's forcing rules, not an overcall's
    first = seq[0]
    x = strain_of(first)
    if first == '2C':
        return not (len(seq) > 2 and seq[1] == '2D' and seq[2] == '2NT')
    if level_of(first) == 1 and x in SUITS and len(seq) >= 2:
        r = seq[1]
        rs = strain_of(r)
        responder = ctx.ours[1][0]
        if not ctx.passed_hand(responder):
            if r == '2NT' and x in MAJORS:
                return True
            if level_of(r) == 2 and rs in SUITS and rs != x and (
                    _is_two_over_one(x, rs) or SUITS.index(rs) > SUITS.index(x)):
                return True
            if x in MAJORS and _is_splinter(x, r):
                return True
        if len(seq) >= 4 and len({strain_of(c) for c in seq[:4]} & set(SUITS)) == 4:
            return True
        if len(seq) >= 3 and level_of(seq[2]) == 3 and strain_of(seq[2]) in SUITS \
                and strain_of(seq[2]) not in (x, rs):
            return True
    return False


#: Our two-suited overcall (Unusual 2NT, Michaels), 8+ HCP and 5-5:
#: advancer with 3+ in one of the suits and game values (judge + 8 >= 25)
#: bids game in it instead of the cheapest preference (deal 163).
TWO_SUITER_GAME = True
#: ...and the later rounds read it as two suits, not as a 2NT opening
#: whose next bids are Stayman and transfers.
TWO_SUITER_READ = True


def _our_two_suiter(ctx: Ctx) -> tuple | None:
    """The suits our first call showed, when it was a two-suited overcall
    straight over their one-level opening."""
    if ctx.we_opened or not ctx.seq:
        return None
    i = next((k for k, (_, c) in enumerate(ctx.calls) if c != 'Pass'), None)
    if i is None or len(ctx.calls) <= i + 1 or ctx.calls[i + 1][1] != ctx.seq[0]:
        return None
    return _two_suits_shown(ctx, ctx.seq[0], ctx.calls[i][1])


#: Our natural two-level overcall, (1x) 2y, is 5+ y and 10-17 HCP. The later
#: rounds read it as an opening: (1♦) 2♣ as a strong 2♣, game forcing, so
#: on deal 67 South bid 3NT on 10 HCP over their 2NT and went six down; and
#: 2♦/2♥/2♠ as a weak two. The opening's forcing rules apply only when we
#: opened.
OVERCALL_READ = True


def _their_opening_suit(ctx: Ctx) -> str | None:
    """Their opening's suit, when they opened at the one level in a suit."""
    first = next(((w, c) for w, c in ctx.calls if c != 'Pass'), None)
    if ctx.we_opened or first is None or level_of(first[1]) != 1:
        return None
    s = strain_of(first[1])
    return s if s in SUITS else None


def _our_two_level_overcall(ctx: Ctx) -> tuple | None:
    """(y, None) when our first call was a natural, non-jump two-level suit
    overcall straight over their one-level opening."""
    if ctx.we_opened or not ctx.seq:
        return None
    i = next((k for k, (_, c) in enumerate(ctx.calls) if c != 'Pass'), None)
    if i is None or len(ctx.calls) <= i + 1 or ctx.calls[i + 1][1] != ctx.seq[0]:
        return None
    opening, call = ctx.calls[i][1], ctx.seq[0]
    y = strain_of(call)
    if not _their_opening_suit(ctx) or level_of(call) != 2 or y not in SUITS \
            or y == strain_of(opening) or rank_of(f"1{y}") > rank_of(opening):
        return None
    return (y, None)


def _two_suiter_lengths(seq: list[str], parity: int, two: tuple) -> dict:
    """Overcaller (parity 0): 5 in each shown suit, 6 once rebid, 4 in a new
    suit. Advancer: 3 in the suit preferred, 5 in a suit of their own."""
    lengths = {s: 0 for s in SUITS}
    shown = [s for s in two if s]
    for i in range(parity, len(seq), 2):
        s = strain_of(seq[i])
        if parity == 0:
            if i == 0:
                for t in shown:
                    lengths[t] = 5
            elif s in shown:
                lengths[s] = 6
            elif s in SUITS:
                lengths[s] = max(lengths[s], 4)
        elif s in SUITS:
            lengths[s] = max(lengths[s], 3 if s in shown else 5)
    return lengths


#: When THEY hold the contract at 3NT or the four level, it is not our game
#: reached: double for penalty if our side has shown game values (bid
#: game, a game-forcing auction, or judge + partner's minimum >= GAME),
#: else pass. Before, the robots passed it as "Game reached".
THEIR_CONTRACT_DOUBLE = True
OVER_THEIRS = "Their contract; nothing more to show."
#: ...and our side bidding to the four level counts as those values.
VALUES_AT_FOUR = True


def _is_game_bid(call: str) -> bool:
    return call == '3NT' or (level_of(call) >= 4 and strain_of(call) in ('H', 'S', 'NT')) \
        or (level_of(call) >= 5 and strain_of(call) in ('C', 'D'))


#: Count the fit (the user's call, 2026-10-22). Here tricks follow the trumps
#: the partnership holds together, about 0.8 a card, against 0.12 a
#: judgement point: on the library an 8-card fit makes game 18% of the time,
#: a 10-card fit 51%. Once a fit is known, game is judged on judgement points
#: plus FIT_POINTS for each trump the two hands are known to hold past
#: FIT_BASE, minus as many for each trump short of it, plus VOID_POINTS for a
#: side void in a hand with three or more trumps. Only where a call is
#: judged, never in a range a call shows. Head to head it pays by stopping
#: short on 8- and 9-card fits: a FIT_BASE of 8, which only adds, lost
#: 1.5-2.0 points a board (t = -3.4 to -4.3).
FIT_COUNT = True
FIT_POINTS = 3
FIT_BASE = 10
VOID_POINTS = 3


def _fit_bonus(h: Hand, trump: str | None, partner_len: int) -> int:
    """Judgement points the known fit in `trump` is worth to this hand."""
    if not FIT_COUNT or trump not in SUITS or not partner_len:
        return 0
    bonus = FIT_POINTS * (h.len[trump] + partner_len - FIT_BASE)
    if h.len[trump] >= 3 and any(h.len[s] == 0 for s in SUITS if s != trump):
        bonus += VOID_POINTS
    return bonus


#: The Law of Total Tricks in competition (the user's call, 2026-10-22):
#: when they hold the contract and we would pass, bid our fit to the level
#: of the trumps we hold together (8 trumps the two level, 9 the three,
#: 10 the four), never past LOTT_MAX. In this game the law is close to
#: exact: a fit of 8, 9 and 10 takes 8.3, 9.0 and 9.9 tricks on the library.
#: A raise of partner's suit keeps to GIB's free raise, LOTT_RAISE HCP, so
#: it reads as the raise GIB's own branches make (a weaker or a stronger
#: hand bidding it would make their "6+" or "6-9 HCP" untrue); a hand
#: rebidding its own suit needs only to have bid it.
LOTT = True
LOTT_MAX = 5                  # 2026-10-23: 11 trumps compete to five (was 4)
LOTT_RAISE = (6, 9)
LOTT_ALERT = "Competing to the level of our fit."
#: ...and below LOTT_RAISE, a raise with 3+ trumps and a side singleton or
#: void (the user's call: a weak raise is fine with distribution). GIB's free
#: raises, the same call in the same auctions, then read COMPETITIVE_RAISE
#: instead of quoting HCP, so one alert stays true of both.
LOTT_SHORT = True


def _raise_alert(x: str, text: str) -> str:
    return f"3+ {SYM[x]}, competitive." if LOTT and LOTT_SHORT else text


#: A cuebid raise (our bid in their suit after the other partner bid a suit)
#: shows 3+ of that suit to the LoTT, both for the partner who cuebid and for
#: the one who reads it (2026-10-24, deal 338: 1♦ 1♠ X 2♦ - 2♠ 3♥ passed
#: out with ten spades). Fresh deals, head to head: +0.24 a board, t = +2.9.
CUE_RAISE_FIT = True


def _cue_raise(ctx: Ctx, i: int) -> str | None:
    """The suit our call i raised by cuebidding their suit, or None."""
    if not CUE_RAISE_FIT:
        return None
    who, call = ctx.ours[i]
    if strain_of(call) not in _their_suits(ctx):
        return None
    for j in range(i - 1, -1, -1):
        if ctx.ours[j][0] != who:
            s = shown_suit(ctx.seq, j)
            return s if s in SUITS and s not in _their_suits(ctx) else None
    return None


def _partner_length(ctx: Ctx, s: str) -> int:
    """The fewest cards in `s` partner's natural bids have shown."""
    theirs = _their_suits(ctx)
    if s in theirs:
        return 0
    n = 0
    mine_first = None
    for i, (who, call) in enumerate(ctx.ours):
        if who != ctx.me and _cue_raise(ctx, i) == s:
            n = max(n, 3)
            continue
        if shown_suit(ctx.seq, i) != s:
            continue
        if who == ctx.me:
            mine_first = i if mine_first is None else mine_first
            continue
        if n:
            n += 1                       # partner bid it again
        elif mine_first is not None:
            n = 3                        # a raise of my suit
        elif i == 0:
            lvl = level_of(call)
            if ctx.we_opened:
                n = {1: 5 if s in MAJORS else 3, 2: 6}.get(lvl, 7)
            else:
                n = 6 if _jump(ctx, i) else 5    # an overcall
        else:
            n = 4                        # a new suit
    return n


def _jump(ctx: Ctx, i: int) -> bool:
    """Was our side's call i a jump over the bid before it?"""
    who, call = ctx.ours[i]
    at = next(k for k, (w, c) in enumerate(ctx.calls) if w == who and c == call)
    before = [c for _, c in ctx.calls[:at] if level_of(c)]
    if not before:
        return False
    s = strain_of(call)
    need = next(lvl for lvl in range(1, 8) if rank_of(f"{lvl}{s}") > rank_of(before[-1]))
    return level_of(call) > need


def _total_tricks(ctx: Ctx, decision: tuple | None) -> tuple | None:
    if not LOTT or not ctx.theirs or (decision and decision[0] != 'Pass'):
        return None
    hb = ctx.auction.highest_bid
    if hb is None or hb[2] in (ctx.me, ctx.pd) or ctx.auction.doubled != 'None':
        return None
    best = None
    for s in SUITS:
        p = _partner_length(ctx, s)
        n = ctx.h.len[s] + p
        if not p or n < 8:
            continue
        mine = any(w == ctx.me and s in (shown_suit(ctx.seq, i), _cue_raise(ctx, i))
                   for i, (w, _) in enumerate(ctx.ours))
        weak = LOTT_SHORT and ctx.h.hcp < LOTT_RAISE[0] and ctx.h.len[s] >= 3 \
            and ctx.h.short(s)
        if not mine and not weak and not LOTT_RAISE[0] <= ctx.h.hcp <= LOTT_RAISE[1]:
            continue
        call = ctx.cheapest(s, 1)
        if call is None or level_of(call) > min(n - 6, LOTT_MAX):
            continue
        key = (n, s in MAJORS, SUITS.index(s))
        if best is None or key > best[0]:
            best = (key, call)
    if best is None:
        return None
    s = strain_of(best[1])
    mine = any(w == ctx.me and s in (shown_suit(ctx.seq, i), _cue_raise(ctx, i))
               for i, (w, _) in enumerate(ctx.ours))
    if not mine and ctx.h.len[s] >= 3:
        return best[1], _raise_alert(s, LOTT_ALERT)
    return best[1], LOTT_ALERT


#: Jam to game on a ten-card fit (the user's call, 2026-10-28, a Challenge
#: deal: 2♠ (X) with ♠A10652 ♥853 ♦J8 ♣Q96 passed, then bid 4♠ and 5♠ a
#: round late, and E/W found 6♥). When partner's pre-empt is the only bid
#: our side has made and they have come in, my first call is game in it if
#: my length and partner's shown length make JAM_FIT. JAM_OPENINGS are the
#: opening levels it answers; JAM_OVER_BIDS lets it answer an overcall too,
#: not only a double; JAM_MINORS lets it bid five of a minor. The user
#: chose (2026-10-28) to let both partners compete again later
#: (JAM_NEVER_AGAIN off): +1.50 a board against +1.38 with it on.
JAM_GAME = True
JAM_FIT = 10
JAM_OPENINGS = (1, 2, 3)
JAM_OVER_BIDS = True
JAM_UNCONTESTED = True
JAM_MINORS = True
JAM_NEVER_AGAIN = False
JAM_ALERT = "Game in {}: to make or to jam the auction."


def _jam_spot(ctx: Ctx) -> str | None:
    """The game call partner's pre-empt asks of my first call, or None."""
    if not JAM_GAME or not ctx.we_opened or ctx.i_am_opener() or ctx.seq[1:] or not ctx.seq:
        return None
    if any(w == ctx.me for w, _ in ctx.calls[ctx.calls.index(ctx.ours[0]) + 1:]):
        return None                      # not my first call: the jam is now or never
    x = strain_of(ctx.seq[0])
    if x not in SUITS or level_of(ctx.seq[0]) not in JAM_OPENINGS or ctx.seq[0] == '2C' \
            or (x in MINORS and not JAM_MINORS):
        return None
    if not ctx.theirs and (not JAM_UNCONTESTED or level_of(ctx.seq[0]) == 1):
        return None
    if not JAM_OVER_BIDS and any(c != 'X' for _, c in ctx.theirs):
        return None
    game = f"4{x}" if x in MAJORS else f"5{x}"
    return game if ctx.ok(game) else None


def _jam_game(ctx: Ctx) -> tuple | None:
    game = _jam_spot(ctx)
    if game is None:
        return None
    x = strain_of(game)
    if ctx.h.len[x] + _partner_length(ctx, x) >= JAM_FIT:
        return game, JAM_ALERT.format(SYM[x])
    return None


def _after_jam(ctx: Ctx) -> tuple | None:
    """After the jump to game in the jam seat the contract is placed: the
    pre-empter passes over what they bid next (else 3♦ X 5♦ went on to 6♦
    and 7♦). With JAM_NEVER_AGAIN both of us pass whatever they bid, for
    the rest of the auction."""
    if not JAM_GAME or len(ctx.seq) < 2 or not ctx.legal:
        return None
    if not JAM_NEVER_AGAIN and (not ctx.i_am_opener() or len(ctx.seq) != 2):
        return None
    jammer = ctx.ours[1][0]
    if ctx.ours[0][0] == jammer:
        return None
    at = ctx.calls.index(ctx.ours[1])
    before = Ctx(jammer, [], _replay(ctx.auction, at))
    if ctx.seq[1] == _jam_spot(before):
        return 'Pass', "The contract is placed." if JAM_NEVER_AGAIN else "Partner placed the contract."
    return None


def _replay(auction: AuctionState, n: int) -> AuctionState:
    a = AuctionState(dealer=auction.dealer, vulnerability=auction.vulnerability)
    for who, call in auction.calls[:n]:
        a.apply_call(who, call)
    return a


def jam_alert(player: str, cards: list[Card], auction: AuctionState, decision: tuple) -> tuple:
    """Any branch's game bid in the jam seat reads JAM_ALERT, so the same call
    in the same auction says the same thing whoever holds it."""
    if JAM_GAME and decision[0] == _jam_spot(Ctx(player, cards, auction)):
        return decision[0], JAM_ALERT.format(SYM[strain_of(decision[0])])
    return decision


#: A major game, not 3NT, on a known eight-card major fit (the user's call,
#: 2026-10-23): instead of bidding 3NT, or passing partner's 3NT, bid 4M when
#: my length and what partner's bids have shown (a natural notrump bid shows
#: two) make eight. A fit both of us have bid is left alone: 1M-2M-3NT is
#: already a choice of games (roadmap 3.7). +1.72 a board; see BIDDING.md.
MAJOR_OVER_3NT = True


def _major_over_notrump(ctx: Ctx, decision: tuple | None) -> tuple | None:
    if not MAJOR_OVER_3NT or decision is None:
        return None
    hb = ctx.auction.highest_bid
    standing = (decision[0] == 'Pass' and hb is not None and (hb[0], hb[1]) == (3, 'NT')
                and hb[2] == ctx.pd and ctx.auction.doubled == 'None')
    if decision[0] != '3NT' and not standing:
        return None
    best = None
    for s in MAJORS:
        if _agreed(ctx, s):
            continue
        nt = _nt_length(ctx)
        n = ctx.h.len[s] + (nt if _transferred(ctx, s) else (_partner_length(ctx, s) or nt))
        if n >= 8 and ctx.ok(f"4{s}") and (best is None or n > best[0]):
            best = (n, s)
    if best is None:
        return None
    return f"4{best[1]}", TO_PLAY


def _agreed(ctx: Ctx, s: str) -> bool:
    """Have both of us bid `s` naturally?"""
    return all(any(w == who and strain_of(c) == s and shown_suit(ctx.seq, i) == s
                   for i, (w, c) in enumerate(ctx.ours)) for who in (ctx.me, ctx.pd))


def _transferred(ctx: Ctx, s: str) -> bool:
    """Did I show `s` with a transfer? Then partner's bid of it completed the
    transfer and shows no length of its own."""
    return any(w == ctx.me and shown_suit(ctx.seq, i) == s and strain_of(c) != s
               for i, (w, c) in enumerate(ctx.ours))


def _nt_length(ctx: Ctx) -> int:
    """Partner's natural notrump bid shows a balanced hand: 2+ in every suit."""
    return 2 if any(w == ctx.pd and strain_of(c) == 'NT' for w, c in ctx.ours) else 0


def _over_their_contract(ctx: Ctx, values: bool) -> tuple:
    if values and ctx.ok('X'):
        return 'X', "Penalty: our side has the values for game."
    return 'Pass', OVER_THEIRS


def continuation(ctx: Ctx) -> tuple:
    """Anything the explicit tables above do not cover: find the fit, then
    the level -- game forced, invited, or a partscore."""
    seq = ctx.seq
    h = ctx.h
    me_parity = 0 if ctx.i_am_opener() else 1
    if not ctx.we_opened:
        me_parity = 0 if ctx.ours and ctx.ours[0][0] == ctx.me else 1
    p_parity = 1 - me_parity
    pmin = _partner_min(seq, p_parity)
    plen = _shown_lengths(seq, p_parity)
    mylen = _shown_lengths(seq, me_parity)
    trump = agreed_trump(seq)
    two = _our_two_suiter(ctx) if TWO_SUITER_READ else None
    shows = TWO_SUITED_MIN
    if not two and OVERCALL_READ:
        two = _our_two_level_overcall(ctx)
        shows = OVERCALL_2[0]
    if two:
        pmin = shows if p_parity == 0 else 0
        plen = _two_suiter_lengths(seq, p_parity, two)
        mylen = _two_suiter_lengths(seq, me_parity, two)
        trump = next((s for s in SUITS if plen[s] and mylen[s]
                      and plen[s] + mylen[s] >= 8), None)
    comb = h.judge + pmin
    gf = _game_forced(seq, ctx) and not two
    current = ctx.current()
    cur_rank = rank_of(current) if current else -1
    partner_last = ctx.partners()[-1] if ctx.partners() else None

    fits = [s for s in SUITS if plen[s] and plen[s] + h.len[s] >= 8]
    if trump and trump not in fits:
        fits.append(trump)
    fit = None
    if fits:
        fit = max(fits, key=lambda s: (s in MAJORS, plen[s] + h.len[s], SUITS.index(s)))

    if partner_last and level_of(partner_last) >= 6:
        return 'Pass', "Partner placed the contract."
    hb = ctx.auction.highest_bid
    theirs_hold = THEIR_CONTRACT_DOUBLE and hb is not None and hb[2] not in (ctx.me, ctx.pd)
    values = gf or comb >= GAME or any(_is_game_bid(c) for c in seq) \
        or (VALUES_AT_FOUR and any(level_of(c) >= 4 for c in seq))
    if fit:
        if trump == fit and comb >= SLAM and ctx.ok('4NT') and cur_rank < rank_of('4NT') \
                and '4NT' not in seq:
            return '4NT', f"Keycard Blackwood for {SYM[fit]}. Artificial."
        comb += _fit_bonus(h, fit, plen[fit])
        if fit in MAJORS:
            if comb >= GAME_MAJOR or gf:
                if cur_rank >= rank_of(f"4{fit}"):
                    if theirs_hold:
                        return _over_their_contract(ctx, values)
                    return 'Pass', "Game reached."
                return f"4{fit}", TO_PLAY
            call = ctx.cheapest(fit, 2)
            if comb >= GAME_MAJOR - 2 and call and level_of(call) <= 3:
                return call, natural(fit)
            if partner_last and strain_of(partner_last) == fit:
                return 'Pass', "No game."
            if call and level_of(call) <= 2:
                return call, natural(fit)
            return 'Pass', "No game."
        if comb >= GAME or gf:
            if cur_rank < rank_of('3NT') and h.balanced:
                return '3NT', TO_PLAY
            if comb >= 29 and cur_rank < rank_of(f"5{fit}"):
                return f"5{fit}", TO_PLAY
            if cur_rank < rank_of('3NT'):
                return '3NT', TO_PLAY
            if theirs_hold:
                return _over_their_contract(ctx, values)
            return 'Pass', "Game reached."
        if partner_last and strain_of(partner_last) == fit:
            return 'Pass', "No game."
        call = ctx.cheapest(fit, 2)
        if call and level_of(call) <= 3:
            return call, natural(fit)
        return 'Pass', "No game."

    if current and level_of(current) >= 4 or current in ('3NT',):
        if theirs_hold:
            return _over_their_contract(ctx, values)
        return 'Pass', "Game reached."
    if gf or comb >= GAME:
        for s in SUITS:
            if h.len[s] >= 6 and not mylen[s]:
                call = ctx.cheapest(s, 2)
                if call and rank_of(call) < rank_of('3NT'):
                    return call, natural(s)
        if ctx.ok('3NT'):
            return '3NT', TO_PLAY
        return 'Pass', "Game reached."
    if partner_last and _forcing(ctx, partner_last):
        s = h.longest()
        call = ctx.cheapest(s, 1)
        if call and level_of(call) <= 3:
            return call, natural(s)
    return 'Pass', "No game."


def _forcing(ctx: Ctx, call: str) -> bool:
    seq = ctx.seq
    i = len(seq) - 1
    if shown_suit(seq, i) is None and strain_of(call) in SUITS:
        return True
    return False


# ── Contested auctions ────────────────────────────────────────────────────────

def contested(ctx: Ctx) -> tuple | None:
    seq = ctx.seq
    # 1NT-(X) and friends: systems on.
    if ctx.we_opened and seq and seq[0] in ('1NT', '2NT', '2C') \
            and all(c == 'X' for _, c in ctx.theirs):
        return uncontested(ctx)
    # (1x)-1NT and they pass: systems on, as over our 1NT opening.
    if ctx.nt_overcall:
        return notrump(ctx, 0)
    if ctx.we_opened:
        return we_opened_contested(ctx)
    return they_opened(ctx)


def _their_suits(ctx: Ctx) -> list[str]:
    out = []
    for _, c in ctx.theirs:
        s = strain_of(c)
        if s in SUITS and s not in out:
            out.append(s)
    return out


def _last_their_bid(ctx: Ctx) -> str | None:
    for _, c in reversed(ctx.theirs):
        if parse_bid(c):
            return c
    return None


def we_opened_contested(ctx: Ctx) -> tuple | None:
    seq = ctx.seq
    h = ctx.h
    first = seq[0]
    x = strain_of(first)

    if first in ('1NT', '2NT', '2C'):
        return _nt_interference(ctx)
    if ctx.i_am_opener() and level_of(first) >= 2 and not ctx.partners():
        return 'Pass', "Pre-empted already."
    reopen = _reopening(ctx) or _answer_reopening(ctx) or _answer_extras_double(ctx)
    if reopen:
        return reopen
    splintered = _answer_competed_splinter(ctx)
    if splintered:
        return splintered
    support = _after_support_double(ctx)
    if support:
        return support
    forced = _opener_over_forcing_response(ctx)
    if forced:
        return forced

    # Responder's first call over interference.
    if len(seq) == 1 and not ctx.i_am_opener() and level_of(first) == 1:
        return _respond_over_interference(ctx, x)

    # Opener's rebid: answer a negative double, or show support with a double.
    if ctx.i_am_opener() and level_of(first) == 1 and seq[1:] == ['X'] and \
            ctx.ours[1][0] == ctx.pd:
        answer = _answer_negative(ctx, x)
        if answer:
            return answer
    cue = _cuebid_raise_reply(ctx)
    if cue:
        return cue
    hb = ctx.auction.highest_bid
    if (ctx.i_am_opener() and level_of(first) == 1 and len(seq) == 1
            and h.hcp >= 18 and ctx.ok('X') and hb and hb[2] not in (ctx.me, ctx.pd)):
        return 'X', "18+ HCP, extra values."
    if ctx.i_am_opener() and level_of(first) == 1 and len(seq) == 2:
        y = strain_of(seq[1])
        lb = _last_their_bid(ctx)
        if (y in SUITS and lb and level_of(seq[1]) == 1 and rank_of(lb) <= rank_of('2H')
                and h.len[y] == 3 and ctx.ok('X')
                and ctx.calls[-1][1] == lb):
            return 'X', f"Support double: exactly 3 {SYM[y]}."
    return _rebid_over_their_overcall(ctx)


#: Opener after 1x (P) 1y (2z): a new suit shows extras; 2NT is 18-19.
REBID_NEW_SUIT_HCP = 16
REBID_2NT = (18, 19)
#: ...and with four of partner's major and 0-1 of their suit, a jump in
#: their suit (4z) is a splinter, game forcing: HCP plus dummy points for
#: the shortness (void 5, singleton 3) reach 19. Deal 329: 1♣ (P) 1♥ (2♦)
#: with ♠K752 ♥Q753 ♦— ♣AKQ63 raised to 2♥ and defended 3♦; 7♥ makes.
COMPETED_SPLINTER = True
COMPETED_SPLINTER_MIN = 19
SHORT_POINTS = {0: 5, 1: 3}


def _competed_splinter_call(y: str, z: str) -> str | None:
    """1x (P) 1y (2z) 4z: the splinter for major y in their suit z, when it
    sits below game in y."""
    if y not in MAJORS or z not in SUITS:
        return None
    call = f"4{z}"
    return call if rank_of(call) < rank_of(f"4{y}") else None


def _answer_competed_splinter(ctx: Ctx) -> tuple | None:
    """Responder after 1x (P) 1y (2z) 4z: partner's splinter, game forcing.
    Bid game in y. If they have bid over it, leave it to the fallback."""
    if ctx.i_am_opener() or len(ctx.seq) != 3:
        return None
    i = next((k for k, (_, c) in enumerate(ctx.calls) if c != 'Pass'), None)
    if i is None or len(ctx.calls) < i + 5:
        return None
    (w0, c0), (_, c1), (w2, c2), (_, c3), (w4, c4) = ctx.calls[i:i + 5]
    y, z = strain_of(c2), strain_of(c3)
    if (w0 != ctx.pd or w2 != ctx.me or w4 != ctx.pd or level_of(c0) != 1
            or c1 != 'Pass' or level_of(c2) != 1 or level_of(c3) != 2
            or c4 != _competed_splinter_call(y, z)):
        return None
    game = f"4{y}"
    if ctx.ok(game):
        return game, TO_PLAY
    return None


def _rebid_over_their_overcall(ctx: Ctx) -> tuple | None:
    """1x (P) 1y (2z): they overcalled partner's one-level response. Raise
    with four -- cheapest with 12-14, a jump with 15-17, game in a major with
    18+; else 2NT on 18-19 balanced with z stopped; else rebid a six-card
    suit, jumping with 15+; else a new four-card suit at the two level with
    16+; else pass. Exactly three of partner's suit is the support double's.
    The fallback raised every fit to the two level, 12 HCP or 18."""
    i = next((k for k, (_, c) in enumerate(ctx.calls) if c != 'Pass'), None)
    if i is None or len(ctx.calls) != i + 4 or not ctx.i_am_opener():
        return None
    (_, c0), (_, c1), (w2, c2), (_, c3) = ctx.calls[i:]
    x, y, z = strain_of(c0), strain_of(c2), strain_of(c3)
    if (level_of(c0) != 1 or x not in SUITS or c1 != 'Pass' or w2 != ctx.pd
            or level_of(c2) != 1 or y not in SUITS or y == x
            or level_of(c3) != 2 or z not in SUITS or z in (x, y)):
        return None
    h = ctx.h
    if h.len[y] == 3:
        return None
    splinter = _competed_splinter_call(y, z)
    if (COMPETED_SPLINTER and splinter and h.len[y] >= 4 and h.len[z] <= 1
            and h.hcp + SHORT_POINTS[h.len[z]] >= COMPETED_SPLINTER_MIN
            and ctx.ok(splinter)):
        return splinter, f"Splinter: 4+ {SYM[y]}, 0-1 {SYM[z]}. Game forcing."
    if h.len[y] >= 4:
        cheap = ctx.cheapest(y, 2)
        if cheap and (level_of(cheap) <= 3 or h.hcp >= NEG_COMPETED_JUMP_HCP):
            lvl = level_of(cheap)
            if h.hcp >= NEG_COMPETED_GAME_HCP and y in MAJORS:
                lvl = max(lvl, 4)
            elif h.hcp >= NEG_COMPETED_JUMP_HCP:
                lvl = min(lvl + 1, 4)
            call = f"{lvl}{y}"
            if call == cheap:
                return call, f"4+ {SYM[y]} support."
            if ctx.ok(call):
                return call, f"4+ {SYM[y]} support, {NEG_COMPETED_JUMP_HCP}+ HCP."
            return cheap, f"4+ {SYM[y]} support."
    if (h.balanced and REBID_2NT[0] <= h.hcp <= REBID_2NT[1] and h.stopper(z)
            and ctx.ok('2NT')):
        return '2NT', f"{REBID_2NT[0]}-{REBID_2NT[1]} HCP, balanced, {SYM[z]} stopper."
    if h.len[x] >= 6:
        cheap = ctx.cheapest(x, 2)
        if cheap and level_of(cheap) <= 3:
            call = f"{level_of(cheap) + 1}{x}"
            if h.hcp >= NEG_COMPETED_JUMP_HCP and level_of(cheap) <= 3 and ctx.ok(call):
                return call, f"6+ {SYM[x]}, {NEG_COMPETED_JUMP_HCP}+ HCP."
            return cheap, f"6+ {SYM[x]}."
    if h.hcp >= REBID_NEW_SUIT_HCP:
        new = [s for s in SUITS if s not in (x, y, z) and h.len[s] >= 4]
        if new:
            s = max(new, key=lambda s: (h.len[s], -SUITS.index(s)))
            call = ctx.cheapest(s, 2)
            if call and level_of(call) == 2:
                return call, f"4+ {SYM[s]}, {REBID_NEW_SUIT_HCP}+ HCP."
    return 'Pass', "No fit, nothing more to show."


#: A reopening double on a doubleton in their suit needs extra values.
REOPEN_DOUBLETON_HCP = 15
REOPEN = "Reopening double: takeout. Partner may pass for penalty."


def _reopen_suit(ctx: Ctx, extra: int) -> str | None:
    """Their suit, when the auction began 1x (y) P (P) -- our one-level
    opening, their natural overcall at the one or two level, two passes --
    and `extra` more calls have followed."""
    i = next((k for k, (_, c) in enumerate(ctx.calls) if c != 'Pass'), None)
    if i is None or len(ctx.calls) != i + 4 + extra:
        return None
    (w0, c0), (_, c1), (_, c2), (_, c3) = ctx.calls[i:i + 4]
    x, y = strain_of(c0), strain_of(c1)
    if (w0 != ctx.opener or level_of(c0) != 1 or x not in SUITS or y not in SUITS
            or y == x or level_of(c1) > 2 or c2 != 'Pass' or c3 != 'Pass'):
        return None
    return y


def _reopening(ctx: Ctx) -> tuple | None:
    """1x (y) P (P): partner's pass may be a penalty double that a
    negative-doubling responder could not make, so opener short in their
    suit reopens with a double -- on 0-1 cards, or 2 with 15+ HCP. A
    six-card suit on less rebids it instead. 18+ HCP doubles on any length."""
    y = _reopen_suit(ctx, 0)
    if y is None or not ctx.i_am_opener() or not ctx.ok('X'):
        return None
    h = ctx.h
    x = strain_of(ctx.seq[0])
    if h.hcp >= 18:
        return 'X', REOPEN
    if h.len[x] >= 6 and h.hcp < REOPEN_DOUBLETON_HCP:
        return None
    if h.len[y] <= 1 or (h.len[y] == 2 and h.hcp >= REOPEN_DOUBLETON_HCP):
        return 'X', REOPEN
    return None


def _answer_reopening(ctx: Ctx) -> tuple | None:
    """1x (y) P (P) X (P): pass for penalty with length and honours in their
    suit; otherwise answer the takeout -- a four-card major, notrump with a
    stopper, partner's suit, or the longest unbid suit."""
    y = _reopen_suit(ctx, 2)
    if (y is None or ctx.i_am_opener() or len(ctx.seq) != 2 or ctx.seq[1] != 'X'
            or ctx.ours[1][0] != ctx.pd or ctx.calls[-1][1] != 'Pass'):
        return None
    h = ctx.h
    x = strain_of(ctx.seq[0])
    if h.len[y] >= 4 and h.top(y, ('A', 'K', 'Q', 'J', '10')) >= 2 and h.hcp >= 6:
        return 'Pass', f"Penalty: converting partner's double, length in {SYM[y]}."
    answer = "Natural, answering the reopening double."
    for z in sorted(MAJORS, key=lambda s: h.len[s], reverse=True):
        if z not in (x, y) and h.len[z] >= 4:
            call = ctx.cheapest(z, 1)
            if call:
                return call, answer
    if h.hcp >= 6 and h.stopper(y):
        call = ctx.cheapest('NT', 1)
        if call and level_of(call) <= 2:
            return call, f"{SYM[y]} stopper, 6+ HCP."
    preference = "Preference to partner's suit."
    if h.len[x] >= (2 if x in MAJORS else 3):
        call = ctx.cheapest(x, 1)
        if call:
            return call, preference
    call = ctx.cheapest(h.longest([z for z in SUITS if z not in (x, y)]), 1)
    if call:
        return call, answer
    return None


def _opener_over_forcing_response(ctx: Ctx) -> tuple | None:
    """In competition, responder's new suit is forcing for one round
    ("Forcing." in its alert): opener must bid. Raise with support, else
    rebid a long suit, show a stopper in notrump, or name a new suit."""
    seq = ctx.seq
    if not ctx.i_am_opener() or len(seq) != 2 or ctx.ours[1][0] != ctx.pd:
        return None
    y = strain_of(seq[1])
    x = strain_of(seq[0])
    if y not in SUITS or y == x or level_of(seq[1]) != 2:
        return None
    theirs = _their_suits(ctx)
    if y in theirs:
        return None
    h = ctx.h
    their = theirs[-1] if theirs else None
    game = h.judge >= 15
    if h.len[y] >= 3:
        if game and y in MAJORS and ctx.ok(f"4{y}"):
            return f"4{y}", TO_PLAY
        call = ctx.cheapest(y, 3)
        if call and level_of(call) == 3:
            return call, f"3+ {SYM[y]} support."
    if h.len[x] >= 6:
        call = ctx.cheapest(x, 2)
        if call and level_of(call) <= 3:
            return call, f"Rebidding {SYM[x]}."
    if their and h.stopper(their):
        call = '3NT' if game else ctx.cheapest('NT', 2)
        if call and ctx.ok(call) and level_of(call) <= 3:
            return call, f"{SYM[their]} stopper."
    for z in SUITS:
        if z not in (x, y) and z not in theirs and h.len[z] >= 4:
            call = ctx.cheapest(z, 2)
            if call and level_of(call) <= 3 and rank_of(call) < rank_of('3NT'):
                return call, f"4+ {SYM[z]}."
    call = ctx.cheapest(x, 2)
    if call and level_of(call) <= 3:
        return call, f"Rebidding {SYM[x]}."
    return None


def _after_support_double(ctx: Ctx) -> tuple | None:
    """Partner (opener) showed exactly three of my suit with a double."""
    seq = ctx.seq
    if (ctx.i_am_opener() or len(seq) != 3 or seq[2] != 'X'
            or ctx.ours[2][0] != ctx.pd or level_of(seq[1]) != 1):
        return None
    y = strain_of(seq[1])
    h = ctx.h
    if y not in SUITS:
        return None
    if h.judge >= 13:
        if y in MAJORS and ctx.ok(f"4{y}"):
            return f"4{y}", TO_PLAY
        if ctx.ok('3NT'):
            return '3NT', TO_PLAY
    call = ctx.cheapest(y, 2)
    if call and level_of(call) <= 3:
        if h.judge >= 10 and level_of(call) == 2 and ctx.ok(f"3{y}"):
            return f"3{y}", f"Invitational, {SYM[y]}."
        return call, f"Minimum, {SYM[y]}."
    return 'Pass', "No room."


def _overcalled(ctx: Ctx) -> bool:
    """They opened (not 1NT) and our side came in over it."""
    opening = next(((w, c) for w, c in ctx.calls if c != 'Pass'), None)
    return opening is not None and opening[0] not in (ctx.me, ctx.pd) and 'NT' not in opening[1]


def _bid_low(ctx: Ctx, x: str) -> bool:
    """Our side first bid x at the one or two level: three is a sign-off."""
    first = next((c for _, c in ctx.ours if strain_of(c) == x), None)
    return first is not None and level_of(first) <= 2


def _cue_asks(ctx: Ctx, cue: str, x: str) -> bool:
    """Advancer's cuebid that passes three of x is a stopper ask (CUE_2NT)."""
    return (CUE_2NT and _overcalled(ctx) and _bid_low(ctx, x)
            and rank_of(cue) > rank_of(f"3{x}"))


def _cue_2nt_on(ctx: Ctx, x: str, their: str | None) -> bool:
    """As advancer, 2NT is the limit raise or better of x: their suit ranks
    above ours, so the cuebid passes three of x, and 2NT is free."""
    if their not in SUITS or not ctx.ok('2NT'):
        return False
    cue = ctx.cheapest(their, 2)
    return (cue is not None and level_of(cue) == 3 and _cue_asks(ctx, cue, x)
            and ctx.cheapest(x, 2) == f"3{x}")


def _two_nt_raise_reply(ctx: Ctx) -> tuple | None:
    """Partner's 2NT was the limit raise or better of my overcall (CUE_2NT):
    game with extras, else sign off at three. After the sign-off partner
    passes, or with CUE_ASK_HCP+ bids game or asks for a stopper."""
    h = ctx.h
    mine, partners = ctx.mine(), ctx.partners()
    if not CUE_2NT or not mine or not partners or not _overcalled(ctx):
        return None
    theirs = _their_suits(ctx)
    their = theirs[0] if theirs else None
    if their not in SUITS:
        return None
    # I overcalled, partner bid 2NT, my turn.
    x = strain_of(mine[0])
    if (x in SUITS and len(mine) == 1 and partners == ['2NT']
            and ctx.ours[-1] == (ctx.pd, '2NT') and rank_of(f"1{their}") > rank_of(f"1{x}")
            and _bid_low(ctx, x)):
        if h.judge >= 14 or (h.judge >= 12 and h.len[x] >= 6):
            if x in MAJORS and ctx.ok(f"4{x}"):
                return f"4{x}", TO_PLAY
            if h.stopper(their) and ctx.ok('3NT'):
                return '3NT', TO_PLAY
        call = ctx.cheapest(x, 3)
        if call and level_of(call) == 3:
            return call, f"Minimum, {SYM[x]}."
        return 'Pass', "Minimum."
    # I bid 2NT, partner signed off; my turn.
    x = strain_of(partners[0])
    if (mine == ['2NT'] and len(partners) >= 2 and ctx.ours[-1][0] == ctx.pd
            and x in SUITS and strain_of(partners[-1]) == x
            and rank_of(f"1{their}") > rank_of(f"1{x}") and _bid_low(ctx, x)):
        if len(partners) == 2 and h.hcp >= CUE_ASK_HCP:
            if h.stopper(their) and ctx.ok('3NT'):
                return '3NT', TO_PLAY
            if x in MAJORS and ctx.ok(f"4{x}"):
                return f"4{x}", TO_PLAY
            if ctx.ok(f"3{their}"):
                return f"3{their}", f"Asks for a {SYM[their]} stopper for 3NT."
        return 'Pass', "No game."
    # Partner asked for a stopper after my sign-off.
    x = strain_of(mine[0])
    if (len(mine) == 2 and partners[0] == '2NT' and len(partners) == 2
            and ctx.ours[-1][0] == ctx.pd and strain_of(partners[-1]) == their and x in SUITS):
        if h.stopper(their) and ctx.ok('3NT'):
            return '3NT', f"{SYM[their]} stopper."
        call = ctx.cheapest(x, 4)
        if call and level_of(call) == 4:
            return call, f"No {SYM[their]} stopper."
        return 'Pass', "No stopper."
    return None


def _cuebid_raise_reply(ctx: Ctx) -> tuple | None:
    """Partner made a cuebid raise of my suit (limit raise or better, 10+):
    go to game with extras, else sign off at the cheapest level. And when I
    made the cuebid and partner signed off, go on to game with 13+. With
    CUE_2NT a cuebid past three of my suit asks for a stopper instead."""
    two_nt = _two_nt_raise_reply(ctx)
    if two_nt:
        return two_nt
    h = ctx.h
    mine, partners = ctx.mine(), ctx.partners()
    if not mine or not partners:
        return None
    theirs = _their_suits(ctx)
    # I bid my suit, partner cuebid theirs, my turn.
    x = strain_of(mine[0])
    p = partners[-1]
    if (x in SUITS and len(mine) == 1 and strain_of(p) in theirs and strain_of(p) != x
            and ctx.ours[-1] == (ctx.pd, p)):
        their = strain_of(p)
        if _cue_asks(ctx, p, x):
            if h.stopper(their) and ctx.ok('3NT'):
                return '3NT', f"{SYM[their]} stopper."
            if x in MAJORS and ctx.ok(f"4{x}"):
                return f"4{x}", TO_PLAY
            call = ctx.cheapest(x, 4)
            if call and level_of(call) <= 4:
                return call, f"No {SYM[their]} stopper."
        if h.judge >= 14 or (h.judge >= 12 and h.len[x] >= 6):
            if x in MAJORS and ctx.ok(f"4{x}"):
                return f"4{x}", TO_PLAY
            if h.stopper(their) and ctx.ok('3NT'):
                return '3NT', TO_PLAY
            if ctx.ok(f"5{x}"):
                return f"5{x}", TO_PLAY
        call = ctx.cheapest(x, 2)
        if call and level_of(call) <= 4:
            if call in (f"4{x}", f"5{x}"):
                return call, TO_PLAY          # the same call as the game bid
            return call, f"Minimum, {SYM[x]}."
        return 'Pass', "Minimum."
    # I cuebid, partner signed off in their suit; my turn.
    if (len(mine) == 1 and strain_of(mine[0]) in theirs and partners
            and ctx.ours[-1][0] == ctx.pd and len(partners) >= 2):
        x = strain_of(partners[-1])
        if (x in SUITS and strain_of(partners[0]) == x and level_of(partners[-1]) == 4
                and _cue_asks(ctx, mine[0], x)):
            return 'Pass', "No stopper: no game."
        if x in SUITS and strain_of(partners[0]) == x and h.judge >= 13:
            if x in MAJORS and ctx.ok(f"4{x}"):
                return f"4{x}", TO_PLAY
            if ctx.ok('3NT'):
                return '3NT', TO_PLAY
        if x in SUITS:
            return 'Pass', "No game."
    return None


#: Responder over 1M (3x), a three-level overcall: with 3+ support and 11+
#: HCP the cuebid is above three and 3M shows 6-9, so bid game. Before,
#: these hands passed (deal 346: ♠AK96 ♥K ♦QJ10432 ♣J6 over 1♠ (3♥)).
JUMP_OVERCALL_GAME = True


def _respond_over_interference(ctx: Ctx, x: str) -> tuple:
    h = ctx.h
    hcp = h.hcp
    sup = h.len[x]
    lb = _last_their_bid(ctx)
    if not lb:                                               # they doubled
        if x in MAJORS and sup >= 4 and hcp >= 10 and ctx.ok('2NT'):
            return '2NT', f"Jordan: 4+ {SYM[x]}, 10+ HCP."
        if hcp >= 10 and ctx.ok('XX'):
            return 'XX', "10+ HCP."
        if sup >= 4 and hcp <= 9 and ctx.ok(f"3{x}"):
            return f"3{x}", f"4+ {SYM[x]}, under 10 HCP. Pre-emptive."
        if sup >= 3 and hcp >= 6:
            call = ctx.cheapest(x, 2)
            if call and level_of(call) == 2:
                return call, f"3+ {SYM[x]}, 6-9 HCP."
        # Over the double a jump in a new suit is weak, like a weak jump overcall.
        long = [s for s in SUITS if s != x and h.len[s] >= 6]
        if long and WJO[0] <= hcp <= WJO[1]:
            s = max(long, key=lambda s: (h.len[s], SUITS.index(s)))
            cheap = ctx.cheapest(s, 1)
            if cheap:
                jump = f"{level_of(cheap) + 1}{s}"
                if level_of(jump) == 2 and ctx.ok(jump):
                    return jump, f"6+ {SYM[s]}, 3-9 HCP. Weak jump shift."
        for s in SUITS:
            if s != x and h.len[s] >= 4 and hcp >= 6 and ctx.ok(f"1{s}"):
                return f"1{s}", f"4+ {SYM[s]}, 6+ HCP."
        return 'Pass', "Nothing to show."
    lvl, their = parse_bid(lb)
    if lb == '2NT' and len(ctx.theirs) == 1:                 # unusual vs unusual
        shown = [s for s in SUITS if s != x][:2]             # their two suits
        rest = [s for s in SUITS if s != x and s not in shown]
        low, high = ctx.cheapest(shown[0], 3), ctx.cheapest(shown[1], 3)
        if sup >= 3 and hcp >= 10 and low and level_of(low) == 3:
            return low, f"Limit raise or better in {SYM[x]}. Artificial."
        if rest and h.len[rest[0]] >= 5 and hcp >= 12 and high and level_of(high) == 3:
            return high, f"5+ {SYM[rest[0]]}, game forcing. Artificial."
        if sup >= 3 and hcp >= 6 and ctx.ok(f"3{x}"):
            return f"3{x}", f"3+ {SYM[x]}, competitive."
        return 'Pass', "Nothing to show."
    if their == 'NT':
        if hcp >= 9 and ctx.ok('X'):
            return 'X', "9+ HCP. Penalty."
        return 'Pass', "Nothing to show."
    # Over a MINOR opening the unbid major comes first: partner's 1C may be
    # three cards, and a negative double finds the 4-4 major fit.
    if x in MINORS:
        neg = _negative_double(ctx, x, lvl)
        if neg:
            return neg
    # A cuebid raise: limit raise or better. Only of THEIR suit -- after a
    # Michaels cuebid of ours, a bid of our suit is just a raise.
    cue_too_high = False
    if sup >= 3 and hcp >= 10 and their != x and their in SUITS:
        call = ctx.cheapest(their, 2)
        # A cuebid that forces the THREE level needs more than a bare limit
        # raise here: on a user's board 1H-(2C)-3C on three trumps and 10 HCP
        # drove 28 HCP to 3H, where seven tricks were the most available.
        cue_too_high = (CUE_LIMIT_AT_3 and call is not None and level_of(call) == 3
                        and sup < 4 and h.judge < 12)
        if call and level_of(call) <= 3 and not cue_too_high:
            return call, f"Cuebid: 3+ {SYM[x]}, 10+ HCP. Artificial."
    if sup >= 4 and hcp <= 9 and ctx.ok(f"3{x}") and lvl <= 2 and \
            rank_of(f"3{x}") > rank_of(ctx.cheapest(x, 1) or '1C'):
        if ctx.cheapest(x, 2) != f"3{x}":
            return f"3{x}", f"4+ {SYM[x]}, under 10 HCP. Pre-emptive."
    if sup >= 3 and hcp >= 6:
        call = ctx.cheapest(x, 2)
        if call and level_of(call) <= 3 and (hcp <= 9 or cue_too_high):
            return call, _raise_alert(x, f"3+ {SYM[x]}, 6+ HCP.")
    if (JUMP_OVERCALL_GAME and x in MAJORS and lvl == 3 and their in SUITS
            and sup >= 3 and hcp >= 11 and ctx.ok(f"4{x}")):
        return f"4{x}", f"3+ {SYM[x]}, 11+ HCP. To play."
    for s in sorted(SUITS, key=lambda s: (h.len[s], SUITS.index(s)), reverse=True):
        if s in (x, their):
            continue
        call = ctx.cheapest(s, 1)
        if not call:
            continue
        if level_of(call) == 1 and h.len[s] >= 4 and hcp >= 6:
            return call, f"4+ {SYM[s]}, 6+ HCP."
        if level_of(call) == 2 and h.len[s] >= 5 and hcp >= 10:
            return call, f"5+ {SYM[s]}, 10+ HCP. Forcing."
    neg = _negative_double(ctx, x, lvl)
    if neg:
        return neg
    if h.stopper(their) and h.balanced:
        if 8 <= hcp <= 10 and ctx.ok('1NT'):
            return '1NT', f"8-10 HCP, {SYM[their]} stopper."
        if 11 <= hcp <= 12 and ctx.ok('2NT'):
            return '2NT', f"11-12 HCP, {SYM[their]} stopper."
        if hcp >= 13 and ctx.ok('3NT'):
            return '3NT', f"13+ HCP, {SYM[their]} stopper."
    return 'Pass', "Nothing to show."


def _negative_double(ctx: Ctx, x: str, lvl: int) -> tuple | None:
    """Negative double through 3S: the unbid major(s), four each -- or, with no
    major unbid, four in each unbid suit."""
    if lvl > 3 or not ctx.ok('X'):
        return None
    lb = _last_their_bid(ctx)
    if ctx.calls[-1][1] != lb or rank_of(lb) > rank_of('3S'):
        return None
    theirs = _their_suits(ctx)
    unbid = [s for s in SUITS if s != x and s not in theirs]
    if not unbid:
        return None
    majors = [s for s in unbid if s in MAJORS]
    shown = majors or unbid
    h = ctx.h
    if any(h.len[s] < 4 for s in shown):
        return None
    need = NEGATIVE[lvl]
    if h.hcp < need:
        return None
    return 'X', f"Negative: 4+ {' '.join(SYM[s] for s in shown)}, {need}+ HCP."


def _answer_negative(ctx: Ctx, x: str) -> tuple | None:
    h = ctx.h
    if ctx.calls[-1][0] not in (ctx.me, ctx.pd) and parse_bid(ctx.calls[-1][1]):
        return _negative_double_competed(ctx, x)
    # Only a double of a SUIT overcall is negative; over 1NT it is penalty.
    x_at = next(i for i, (w, c) in enumerate(ctx.calls) if w == ctx.pd and c == 'X')
    before = [c for w, c in ctx.calls[:x_at] if w not in (ctx.me, ctx.pd) and parse_bid(c)]
    if not before or strain_of(before[-1]) not in SUITS:
        return 'Pass', "Partner's double is for penalty."
    # Each answer says what it shows (a user asked for exactly this): a
    # four-card unbid suit; else the opening suit, five or more, denying four
    # in every unbid suit; else notrump, denying both. Rebidding a three- or
    # four-card minor would make "5+" false, so that is never the answer.
    theirs = _their_suits(ctx)
    unbid = [s for s in SUITS if s != x and s not in theirs]
    fours = sorted((s for s in unbid if h.len[s] >= 4),
                   key=lambda s: (s in MAJORS, h.len[s], SUITS.index(s)), reverse=True)
    for s in fours:
        call = ctx.cheapest(s, 1)
        if call and level_of(call) <= 3:
            return call, f"4+ {SYM[s]}."
    if fours:
        return 'Pass', "No room to show my suit."
    denied = ' or '.join(SYM[s] for s in reversed(unbid))
    if h.len[x] >= 5:
        call = ctx.cheapest(x, 1)
        if call and level_of(call) <= 3:
            return call, f"5+ {SYM[x]}, fewer than 4 {denied}."
    call = ctx.cheapest('NT', 1)
    if call and level_of(call) <= 2:
        return call, f"Fewer than 4 {denied}, fewer than 5 {SYM[x]}."
    return 'Pass', "Nothing to show."


#: Opener after 1x (1y) X (2y): jump in partner's suit, bid game in it, or
#: double with extra values and no fit.
NEG_COMPETED_JUMP_HCP = 15
NEG_COMPETED_GAME_HCP = 18
NEG_COMPETED_DOUBLE_HCP = 17


def _negative_promise(ctx: Ctx, x: str) -> tuple[list[str], str] | None:
    """(suits partner's negative double promised four of, their suit), or
    None if partner's double was not a negative double of a suit overcall."""
    x_at = next(i for i, (w, c) in enumerate(ctx.calls) if w == ctx.pd and c == 'X')
    before = [c for w, c in ctx.calls[:x_at] if w not in (ctx.me, ctx.pd) and parse_bid(c)]
    if not before or strain_of(before[-1]) not in SUITS:
        return None
    unbid = [s for s in SUITS if s != x and s not in [strain_of(c) for c in before]]
    return [s for s in unbid if s in MAJORS] or unbid, strain_of(before[-1])


def _negative_double_competed(ctx: Ctx, x: str) -> tuple | None:
    """1x (1y) X (2y): they bid over partner's negative double. With four in
    a suit the double promised, bid it -- cheapest with a minimum, a jump with
    15-17, game in a major with 18+; else rebid a six-card suit; else double
    with 17+ (extra values, no fit); else pass. The fallback used to read
    partner here as having passed, and never once bid the fit."""
    promise = _negative_promise(ctx, x)
    x_at = next(i for i, (w, c) in enumerate(ctx.calls) if w == ctx.pd and c == 'X')
    if promise is None or len(ctx.calls) != x_at + 2:
        return None
    shown, _ = promise
    h = ctx.h
    theirs = _their_suits(ctx)
    fits = [s for s in shown if s not in theirs and h.len[s] >= 4]
    if fits:
        s = max(fits, key=lambda s: (h.len[s], -SUITS.index(s)))   # ties: cheaper
        cheap = ctx.cheapest(s, 2)
        if cheap and (level_of(cheap) <= 3 or h.hcp >= NEG_COMPETED_JUMP_HCP):
            lvl = level_of(cheap)
            if h.hcp >= NEG_COMPETED_GAME_HCP and s in MAJORS:
                lvl = max(lvl, 4)
            elif h.hcp >= NEG_COMPETED_JUMP_HCP:
                lvl = min(lvl + 1, 4)
            call = f"{lvl}{s}"
            if call == cheap:
                return call, f"4+ {SYM[s]}, partner's suit."
            if ctx.ok(call):
                return call, f"4+ {SYM[s]}, partner's suit, {NEG_COMPETED_JUMP_HCP}+ HCP."
            return cheap, f"4+ {SYM[s]}, partner's suit."
    if h.len[x] >= 6:
        call = ctx.cheapest(x, 2)
        if call and level_of(call) <= 3:
            return call, f"6+ {SYM[x]}."
    # Only over a two-level bid: higher, partner has no cheap answer, and a
    # forced pass leaves the double in for penalty (deal 334: 3S doubled made).
    if h.hcp >= NEG_COMPETED_DOUBLE_HCP and level_of(ctx.calls[-1][1]) <= 2 and ctx.ok('X'):
        return 'X', f"{NEG_COMPETED_DOUBLE_HCP}+ HCP, extra values. Partner may pass for penalty."
    return 'Pass', "Minimum, nothing more to show."


def _answer_extras_double(ctx: Ctx) -> tuple | None:
    """1x (1y) X (2y) X (P): opener's double shows extra values without a fit
    for my suit. Pass for penalty with length and honours in their suit,
    else bid: a five-card suit I promised, partner's suit, my promised suit."""
    seq = ctx.seq
    if (ctx.i_am_opener() or len(seq) != 3 or seq[1:] != ['X', 'X']
            or ctx.ours[1][0] != ctx.me or ctx.ours[2][0] != ctx.pd
            or level_of(seq[0]) != 1 or strain_of(seq[0]) not in SUITS
            or ctx.calls[-1][1] != 'Pass'):
        return None
    x = strain_of(seq[0])
    i = next(k for k, (w, c) in enumerate(ctx.calls) if w == ctx.me and c == 'X')
    after = ctx.calls[i + 1:]
    if len(after) != 3 or not parse_bid(after[0][1]) or after[1][0] != ctx.pd:
        return None
    before = [c for w, c in ctx.calls[:i] if w not in (ctx.me, ctx.pd) and parse_bid(c)]
    if not before or strain_of(before[-1]) not in SUITS:
        return None
    y = strain_of(after[0][1])
    h = ctx.h
    if y in SUITS and h.len[y] >= 4 and h.top(y, ('A', 'K', 'Q', 'J', '10')) >= 2:
        return 'Pass', f"Penalty: converting partner's double, length in {SYM[y]}."
    unbid = [s for s in SUITS if s != x and s not in [strain_of(c) for c in before]]
    shown = [s for s in unbid if s in MAJORS] or unbid
    mine = [s for s in shown if s != y]
    answer = "Natural, answering partner's double."
    for s in sorted(mine, key=lambda s: h.len[s], reverse=True):
        if h.len[s] >= 5:
            call = ctx.cheapest(s, 2)
            if call and level_of(call) <= 3:
                return call, answer
    if h.len[x] >= 3:
        call = ctx.cheapest(x, 2)
        if call and level_of(call) <= 3:
            return call, "Preference to partner's suit."
    for s in sorted(mine, key=lambda s: h.len[s], reverse=True):
        call = ctx.cheapest(s, 2)
        if call and level_of(call) <= 3:
            return call, answer
    call = ctx.cheapest(x, 2)
    if call and level_of(call) <= 3:
        return call, "Preference to partner's suit."
    return 'Pass', "Nothing better than defending."


def _nt_interference(ctx: Ctx) -> tuple | None:
    """Our 1NT/2NT/2C was overcalled. Over 2C, a double is Stayman;
    otherwise Lebensohl: 2NT relays to 3C, a two-level suit is to play, a
    three-level suit forces to game."""
    seq = ctx.seq
    h = ctx.h
    lb = _last_their_bid(ctx)
    if not lb:
        return uncontested(ctx)
    first = seq[0]
    if first != '1NT':
        if len(seq) >= 1 and ctx.calls[-1][1] != 'Pass' and h.hcp >= 8:
            for s in SUITS:
                if h.len[s] >= 5:
                    call = ctx.cheapest(s, 1)
                    if call and level_of(call) <= 3:
                        return call, natural(s)
            if ctx.ok('3NT'):
                return '3NT', TO_PLAY
        return 'Pass', "Nothing to show."
    their = strain_of(lb)
    if len(seq) == 1 and not ctx.i_am_opener():
        if lb == '2C' and ctx.calls[-1][1] == '2C' and ctx.ok('X') and \
                any(h.len[m] >= 4 for m in MAJORS) and h.hcp >= 8:
            return 'X', "Stayman. Artificial."
        if (their in SUITS and lb != '2C' and h.len[their] >= 4 and h.hcp >= 8
                and ctx.ok('X')):
            return 'X', "Penalty: 8+ HCP."
        if h.hcp >= 10:
            for s in sorted(SUITS, key=lambda s: h.len[s], reverse=True):
                if s != their and h.len[s] >= 5:
                    call = ctx.cheapest(s, 3)
                    if call and level_of(call) == 3:
                        return call, f"5+ {SYM[s]}, game forcing."
            if (their not in SUITS or h.stopper(their)) and ctx.ok('3NT'):
                return '3NT', "Game values, stopper."
        for s in sorted(SUITS, key=lambda s: h.len[s], reverse=True):
            if s != their and h.len[s] >= 5:
                call = ctx.cheapest(s, 2)
                if call and level_of(call) == 2:
                    return call, f"5+ {SYM[s]}, to play."
                if call and level_of(call) == 3 and h.hcp <= 9 and ctx.ok('2NT'):
                    return '2NT', "Lebensohl: relay to 3C. Artificial."
        return 'Pass', "Nothing to show."
    if ctx.i_am_opener() and seq[-1] == '2NT' and len(seq) == 2:
        if ctx.ok('3C'):
            return '3C', f"Completing the Lebensohl relay, {SYM['C']}."
        return 'Pass', "Relay interrupted."
    if not ctx.i_am_opener() and len(seq) == 3 and seq[1] == '2NT' and seq[2] == '3C':
        for s in sorted(SUITS, key=lambda s: h.len[s], reverse=True):
            if h.len[s] >= 5:
                if s == 'C':
                    return 'Pass', "Clubs, to play."
                call = ctx.cheapest(s, 3)
                if call and level_of(call) == 3:
                    return call, f"5+ {SYM[s]}, to play."
        return 'Pass', "To play."
    if ctx.i_am_opener() and len(seq) >= 4 and seq[1] == '2NT' and seq[2] == '3C':
        # Lebensohl: whatever responder bids after the relay is to play. A
        # user caught opener raising 1NT-(2H)-2NT-3C-3D to 3NT.
        return 'Pass', "Partner signed off."
    if ctx.i_am_opener() and len(seq) == 2 and seq[1] == 'X' and lb == '2C':
        return _nt_opener_answer(ctx, 1, '2C', NT1[0], NT1[1])
    if len(seq) >= 2:
        p = ctx.partners()[-1] if ctx.partners() else None
        s = strain_of(p) if p else None
        if s in MAJORS and h.len[s] >= 3 and level_of(p) == 3 and ctx.ok(f"4{s}"):
            return f"4{s}", TO_PLAY
        if (p and level_of(p) == 3 and s in SUITS and ctx.ok('3NT')
                and their in SUITS and h.stopper(their)):
            return '3NT', TO_PLAY
    return 'Pass', "Nothing to add."


# ── When they opened ──────────────────────────────────────────────────────────

def they_opened(ctx: Ctx) -> tuple | None:
    seq = ctx.seq
    if not seq:
        return _defend(ctx)
    mine = ctx.mine()
    partners = ctx.partners()
    if DOUBLE_THEN_SUIT:
        s = _doubler_suit(ctx, ctx.pd)
        if s and len(partners) == 2 and ctx.ours[-1][0] == ctx.pd:
            return _raise_doubler_suit(ctx, s)
        if _takeout_doubler(ctx, ctx.me) and mine == ['X']:
            decision = _doubler_new_suit(ctx)
            if decision:
                return decision
    if partners and not mine:
        return _advance(ctx)
    if mine and not partners and _defend_was_weak(ctx, mine[0]):
        return 'Pass', "Already described: weak."
    return _cuebid_raise_reply(ctx)


def _takeout_doubler(ctx: Ctx, seat: str) -> bool:
    """Was `seat`'s first call a takeout double: they opened, its partner had
    not bid, and the double was of a suit bid through 4♥?"""
    if ctx.we_opened:
        return False
    for i, (w, c) in enumerate(ctx.calls):
        if w == PARTNERS[seat] and c != 'Pass':
            return False
        if w == seat and c != 'Pass':
            if c != 'X':
                return False
            bid = next(b for _, b in reversed(ctx.calls[:i]) if parse_bid(b))
            return strain_of(bid) in SUITS and rank_of(bid) <= rank_of('4H')
    return False


def _new_suit_at(ctx: Ctx, i: int) -> str | None:
    """The strain of the suit bid at call i, when no one has named it before."""
    s = strain_of(ctx.calls[i][1])
    if s not in SUITS or any(strain_of(c) == s for _, c in ctx.calls[:i]):
        return None
    return s


def _doubler_suit(ctx: Ctx, seat: str) -> str | None:
    """The new suit `seat` bid as its next call after a takeout double."""
    if not _takeout_doubler(ctx, seat):
        return None
    bids = [i for i, (w, c) in enumerate(ctx.calls) if w == seat and c != 'Pass']
    return _new_suit_at(ctx, bids[1]) if len(bids) >= 2 else None


def _doubler_alert(s: str) -> str:
    return f"5+ {SYM[s]}, {DOUBLER_SUIT_HCP}+ HCP. Doubled first: too strong to overcall."


def _doubler_new_suit(ctx: Ctx) -> tuple | None:
    """My takeout double, then my own suit: DOUBLER_SUIT_HCP+ and five cards.
    With four of partner's suit, the raise branches answer instead."""
    h = ctx.h
    if h.hcp < DOUBLER_SUIT_HCP:
        return None
    named = {strain_of(c) for _, c in ctx.calls}
    p_suits = {strain_of(c) for c in ctx.partners()} & set(SUITS)
    if any(h.len[s] >= 4 for s in p_suits):
        return None
    own = [s for s in SUITS if s not in named and h.len[s] >= 5]
    if not own:
        return None
    s = max(own, key=lambda s: (h.len[s], SUITS.index(s)))
    call = ctx.cheapest(s, 1)
    if call and level_of(call) <= DOUBLER_SUIT_LEVEL:
        return call, _doubler_alert(s)
    return None


def _raise_doubler_suit(ctx: Ctx, s: str) -> tuple | None:
    """Partner doubled, then bid a new suit: 18+ HCP, 5+ cards. Raise it on
    three, to game when DOUBLER_SUIT_JUDGE and my judgement points reach it.
    Without support the general branches answer."""
    h = ctx.h
    if h.len[s] < 3:
        return None
    game = f"{4 if s in MAJORS else 5}{s}"
    if h.judge + DOUBLER_SUIT_JUDGE >= (GAME_MAJOR if s in MAJORS else GAME) and ctx.ok(game):
        return game, f"3+ {SYM[s]}, game values. To play."
    if h.hcp >= DOUBLER_RAISE_HCP:
        call = ctx.cheapest(s, 1)
        if call and call != game and level_of(call) <= 4:
            return call, _raise_alert(s, f"3+ {SYM[s]}, {DOUBLER_RAISE_HCP}+ HCP.")
    return 'Pass', "Not enough to raise."


def doubler_guard(player: str, cards: list[Card], auction: AuctionState,
                  decision: tuple) -> tuple:
    """A takeout doubler's new suit always reads the 18+ alert, and a hand
    without 18+ and five cards passes instead, whichever branch chose it."""
    if not DOUBLE_THEN_SUIT:
        return decision
    ctx = Ctx(player, cards, auction)
    s = strain_of(decision[0])
    if (s not in SUITS or ctx.mine() != ['X'] or not _takeout_doubler(ctx, player)
            or any(strain_of(c) == s for _, c in ctx.calls)):
        return decision
    if ctx.h.hcp >= DOUBLER_SUIT_HCP and ctx.h.len[s] >= 5:
        return decision[0], _doubler_alert(s)
    return 'Pass', "Doubled: a new suit would show 18+."


def _defend_was_weak(ctx: Ctx, call: str) -> bool:
    """Was my first call a weak jump overcall? It has said everything."""
    first_their = next((c for w, c in ctx.calls if c != 'Pass'), None)
    if not first_their or strain_of(call) not in SUITS:
        return False
    s = strain_of(call)
    for lvl in range(1, 8):
        if rank_of(f"{lvl}{s}") > rank_of(first_their):
            return level_of(call) > lvl
    return False


def _opening_bid_only(ctx: Ctx) -> str | None:
    bids = [(w, c) for w, c in ctx.calls if c != 'Pass']
    if len(bids) != 1:
        return None
    return bids[0][1]


def _defend(ctx: Ctx) -> tuple | None:
    """Our first action after they opened."""
    h = ctx.h
    hcp = h.hcp
    theirs = _their_suits(ctx)
    lb = _last_their_bid(ctx)
    if lb is None:
        return None                       # they only doubled: ai.py decides
    opening = _opening_bid_only(ctx)
    lvl, their = parse_bid(lb)

    if opening == '1NT':                                      # Cappelletti
        if hcp >= 15 and ctx.ok('X'):
            return 'X', "15+ HCP. Penalty."
        if hcp >= 10:
            if h.len['H'] >= 4 and h.len['S'] >= 4 and h.len['H'] + h.len['S'] >= 9:
                return '2D', f"4+ {SYM['H']} and 4+ {SYM['S']}. Artificial."
            for m in MAJORS:
                if h.len[m] >= 5 and any(h.len[x] >= 4 for x in MINORS):
                    return f"2{m}", f"5+ {SYM[m]} and a 4+ minor."
            if h.len['C'] >= 5 and h.len['D'] >= 5:
                return '2NT', f"5+ {SYM['C']} and 5+ {SYM['D']}."
            if h.shape[0] >= 6:
                return '2C', "One long suit, 6+. Artificial."
        return 'Pass', "No action over 1NT."
    if opening == '2C' or their == 'NT':
        return 'Pass', "No action."

    # Two-suited overcalls over a one-level opening.
    if opening and level_of(opening) == 1 and hcp >= TWO_SUITED_MIN:
        fives = {s for s in SUITS if s != their and h.len[s] >= 5}
        if len(fives) >= 2:
            cue = f"2{their}"
            if their in MINORS and {'H', 'S'} <= fives and ctx.ok(cue):
                return cue, f"Michaels: 5+ {SYM['H']} and 5+ {SYM['S']}. Artificial."
            other = 'S' if their == 'H' else 'H'
            if their in MAJORS and other in fives and fives & set(MINORS) and ctx.ok(cue):
                return cue, f"Michaels: 5+ {SYM[other]} and a 5+ minor. Artificial."
            low = [s for s in SUITS if s != their][:2]
            if set(low) <= fives and ctx.ok('2NT'):
                return '2NT', (f"Unusual: 5+ {SYM[low[0]]} and 5+ {SYM[low[1]]}, "
                               f"8+ HCP.")
    # Over a weak two in a major: 4M = strong minors, 4NT = weaker minors.
    if opening in ('2H', '2S') and h.len['C'] >= 5 and h.len['D'] >= 5:
        if hcp >= 16 and ctx.ok(f"4{their}"):
            return f"4{their}", "Both minors, 5-5, 16+ HCP. Artificial."
        if 10 <= hcp <= 15 and ctx.ok('4NT'):
            return '4NT', f"5+ {SYM['C']} and 5+ {SYM['D']}, 10-15 HCP."
    # 1NT overcall.
    if lvl == 1 and h.balanced and NT_OVERCALL[0] <= hcp <= NT_OVERCALL[1] \
            and h.stopper(their) and ctx.ok('1NT'):
        return '1NT', f"15-18 HCP, balanced, {SYM[their]} stopper."
    # Weak jump overcall.
    if opening and level_of(opening) == 1 and WJO[0] <= hcp <= WJO[1]:
        long = [s for s in SUITS if s != their and h.len[s] >= 6]
        if long:
            s = max(long, key=lambda s: (h.len[s], SUITS.index(s)))
            cheap = ctx.cheapest(s, 1)
            if cheap:
                jump = f"{level_of(cheap) + 1}{s}"
                if level_of(jump) <= 3 and ctx.ok(jump):
                    return jump, f"6+ {SYM[s]}, 3-9 HCP. Weak jump overcall."
    # Simple overcall.
    own = [s for s in SUITS if s not in theirs and h.len[s] >= 5]
    if own and hcp <= 17:
        s = max(own, key=lambda s: (h.len[s], SUITS.index(s)))
        call = ctx.cheapest(s, 1)
        if call:
            need = OVERCALL_1 if level_of(call) == 1 else OVERCALL_2
            if level_of(call) <= 3 and need[0] <= hcp <= need[1] and \
                    (level_of(call) <= 2 or hcp >= 12):
                return call, f"5+ {SYM[s]}, {need[0]}-{need[1]} HCP. Overcall."
    # Takeout double, through 4H.
    if ctx.ok('X') and rank_of(lb) <= rank_of('4H') and their in SUITS:
        shape_ok = h.len[their] <= 2 and all(h.len[s] >= 3 for s in SUITS if s != their)
        need = TAKEOUT_MIN if lvl == 1 else 13
        if (shape_ok and hcp >= need) or hcp >= 18:
            return 'X', f"Takeout: {need}+ HCP."
    if lvl == 3 and h.balanced and hcp >= 16 and h.stopper(their) and ctx.ok('3NT'):
        return '3NT', f"16+ HCP, {SYM[their]} stopper."
    return 'Pass', "No action."


def _advance(ctx: Ctx) -> tuple | None:
    """Partner acted over their opening; this is my first call."""
    h = ctx.h
    hcp = h.hcp
    p = ctx.partners()[0]
    theirs = _their_suits(ctx)
    their = theirs[0] if theirs else None
    opening = next((c for w, c in ctx.calls if c != 'Pass'), None)
    if p == '1NT' and level_of(opening or '') == 1:
        # They have bid again over our 1NT overcall (systems on, when they
        # haven't, is `contested`'s): ai.py answers it.
        return None
    if p == 'X' and opening == '1NT':
        return 'Pass', "Penalty double: passing."
    if opening == '1NT':
        if p == '2C':
            return ('2D', "Relay. Artificial.") if ctx.ok('2D') else ('Pass', "No room.")
        if p == '2D':
            s = 'H' if h.len['H'] >= h.len['S'] else 'S'
            call = ctx.cheapest(s, 2)
            return (call, natural(s)) if call and level_of(call) <= 3 else ('Pass', "No room.")
        if p in ('2H', '2S'):
            s = strain_of(p)
            if h.len[s] >= 2:
                return 'Pass', "Happy in partner's major."
            if ctx.ok('2NT'):
                return '2NT', "Asks for partner's minor. Artificial."
        if p == '2NT':
            m = 'C' if h.len['C'] >= h.len['D'] else 'D'
            call = ctx.cheapest(m, 3)
            return (call, natural(m)) if call and level_of(call) <= 4 else ('Pass', "No room.")
        return None
    two = _two_suits_shown(ctx, p, opening)
    if two:
        a, b = two
        if b is None:
            choice = a if h.len[a] >= 2 else max(MINORS, key=lambda s: (h.len[s], SUITS.index(s)))
        else:
            choice = max((a, b), key=lambda s: (h.len[s], SUITS.index(s)))
        game = f"{4 if choice in MAJORS else 5}{choice}"
        if (TWO_SUITER_GAME and choice in (a, b) and h.len[choice] >= 3
                and h.judge + TWO_SUITED_MIN >= (GAME_MAJOR if choice in MAJORS else GAME)
                and ctx.ok(game)):
            return game, f"3+ {SYM[choice]}, game values. To play."
        call = ctx.cheapest(choice, 2)
        if call and level_of(call) <= 5:
            return call, "Choosing between partner's two suits."
        return 'Pass', "No room."
    if p == 'X':
        if parse_bid(ctx.calls[-1][1]) and ctx.calls[-1][1] != opening:
            unbid = [s for s in SUITS if s not in theirs]
            if hcp >= 8 and len(unbid) >= 2 and all(h.len[s] >= 4 for s in unbid[-2:]) \
                    and ctx.ok('X'):
                return 'X', "Responsive: 8+ HCP, two places to play."
        if parse_bid(ctx.calls[-1][1]) and ctx.calls[-1][0] not in (ctx.me, ctx.pd):
            # Their bid has answered for me: I am free to pass.
            for s in sorted(SUITS, key=lambda s: (h.len[s], SUITS.index(s)), reverse=True):
                if s not in theirs and h.len[s] >= 4 and hcp >= 6:
                    call = ctx.cheapest(s, 1)
                    if call and level_of(call) <= 3:
                        return call, f"4+ {SYM[s]}, 6+ HCP. Free advance."
            return 'Pass', "Not forced after their bid."
        return None                                           # ai.py answers it
    ps = strain_of(p)
    if ps in SUITS and level_of(p) <= 3:
        sup = h.len[ps]
        if sup >= 3 and hcp >= 10 and their in SUITS:
            call = ctx.cheapest(their, 2)
            if _cue_2nt_on(ctx, ps, their):
                if hcp >= CUE_ASK_HCP and not h.stopper(their):
                    return call, f"{CUE_ASK_HCP}+ HCP, no {SYM[their]} stopper. Asks for one, for 3NT."
                return '2NT', f"3+ {SYM[ps]}, 10+ HCP. Limit raise or better. Artificial."
            if call and level_of(call) <= 3:
                return call, f"Cuebid: 3+ {SYM[ps]}, 10+ HCP. Artificial."
        if sup >= 3 and 6 <= hcp <= 9:
            call = ctx.cheapest(ps, 2)
            if call and level_of(call) <= 3:
                return call, _raise_alert(ps, f"3+ {SYM[ps]}, 6-9 HCP.")
        if their in SUITS and h.stopper(their) and h.balanced:
            if 8 <= hcp <= 11 and ctx.ok('1NT'):
                return '1NT', f"8-11 HCP, {SYM[their]} stopper."
            if 12 <= hcp <= 14 and ctx.ok('2NT') and not _cue_2nt_on(ctx, ps, their):
                return '2NT', f"12-14 HCP, {SYM[their]} stopper."
        for s in SUITS:
            if s not in theirs and s != ps and h.len[s] >= 5 and hcp >= 8:
                call = ctx.cheapest(s, 1)
                if call and level_of(call) <= 2:
                    return call, f"5+ {SYM[s]}, 8+ HCP."
        return 'Pass', "Nothing to add."
    return None


def _two_suits_shown(ctx: Ctx, p: str, opening: str | None) -> tuple | None:
    if not opening or level_of(opening) != 1:
        return None
    their = strain_of(opening)
    if p == '2NT':
        low = [s for s in SUITS if s != their][:2]
        return (low[0], low[1])
    if p == f"2{their}" and their in SUITS:
        if their in MINORS:
            return ('H', 'S')
        return ('S' if their == 'H' else 'H', None)
    return None
