from __future__ import annotations
from card import Card, SUITS, STRAINS, RANKS, RANK_VALUE, parse_bid, bid_index
from itertools import combinations
import re
from game import legal_plays, resolve_trick, AuctionState, PARTNERSHIP, PARTNERS, PLAYERS
import gib

_AI_TAG = '__ai__'

# All 13 card values, highest first
_ALL_VALUES = sorted(RANK_VALUE.values(), reverse=True)



# ── Second-Highest Hand Valuation & AI Bidding ────────────────────────────────

_HCP = {'A': 4, 'K': 3, 'Q': 2, 'J': 1}


def hcp(hand: list[Card]) -> int:
    """Standard Milton Work high-card points (A=4, K=3, Q=2, J=1).

    Not what the AI bids on — `eval_hand_sh` is, because honours are worth much
    less when the second-highest card wins. It is shown to the human purely as
    a familiar reference point, the way the other bridge clients do.
    """
    return sum(_HCP.get(c.rank, 0) for c in hand)


#: Tricks per card, fitted to double dummy results over 100 deals -- see
#: research/hand_value.py and "Hand evaluation and bidding research" in docs/BIDDING.md.
#: Out-of-sample R^2 0.740 (5-fold grouped by deal), mean error 1.05 tricks.
#:
#: The ace is NOT an honour in this variant. The highest card of the winning suit
#: always loses, so an ace can never win a contested trick; it is worth about a
#: ten. Kings and queens carry the hand. Low cards are an outright liability.
TRUMP_CARD = 1.025

#: Extra tricks credited for each trump past the fourth in ONE hand, on top of
#: TRUMP_CARD. This is the UMD card's own length-point rule ("add 1 point for
#: each additional card in a 4+ card suit") priced in tricks.
#:
#: IT IS NOT A PREDICTION FIX, and should not be described as one. Measured
#: over 2378 solved cases, per-hand length is already priced correctly: the
#: residual is +0.06 tricks at six cards (t = +0.59) and -0.04 at seven
#: (t = -0.23). The genuine bias is on COMBINED partnership length -- 7 trumps
#: too low by 0.33 (t = +5.56), 8 trumps by 0.45 (t = +6.33), 11 trumps too
#: HIGH by 1.06 (t = -2.69) -- which a bidder cannot see at the table.
#:
#: What this constant buys is a competitive edge: it wins contested boards by
#: outbidding. Head to head +5.8 per board (t = +2.40), stable across a
#: split-half check (+6.0 odd, +5.7 even). The cost is contract discipline,
#: so it is shipped at the CONSERVATIVE end of a plateau that ran to +14.3:
#:
#:                      3-level+   5-level+   made   self-play score
#:     0.00 (before)        63          1      67%        +57.1
#:     0.25 (shipped)       91          4      65%        +56.3
#:     0.50                117         10      63%        +55.9
#:     0.75  ...           +14.3 head to head, and worse on every line above
#:
#: Raising it further trades more accuracy for more aggression. Don't, without
#: new evidence -- and note that the self-play column falls the whole way, so
#: this is an edge against a timid opponent rather than a better evaluation.
LENGTH_BONUS = 0.25
LENGTH_BONUS_FROM = 4
HONOUR_VALUE = {
    'K': 0.281, 'Q': 0.281,
    'A': 0.117, '10': 0.117, '9': 0.117,
    'J': -0.094, '8': -0.094, '7': -0.094, '6': -0.094, '5': -0.094,
    '4': -0.199, '3': -0.199, '2': -0.199,
}


def eval_hand_sh(hand: list[Card]) -> dict:
    """Values a hand in EXPECTED TRICKS, fitted to solved double dummy results.

    Split in two, because a card's worth depends on whether its suit is trump:

    - `honour_pts` is suit-independent -- what the hand's ranks are worth wherever
      the contract lands.
    - `suit_pts[s]` is what this hand contributes with `s` as trump: `honour_pts`
      plus 1.025 per card held in `s`, plus `LENGTH_BONUS` for each card past the
      fourth. Trump length dominates everything else; one trump card is worth
      roughly three queens. See LENGTH_BONUS for why the extra term exists and
      why it is NOT a prediction correction.

    The fit is additive over cards, so a partnership's expected tricks in a suit is
    just `mine['suit_pts'][s] + partner['suit_pts'][s]`. The bidding thresholds
    below are expressed in that unit -- tricks, not invented points.

    `total_pts` is the hand's value in its own best trump suit, kept under the old
    name because the tests (and the TypeScript port) read it.

    This replaces a hand-written evaluation that ranked A-K-Q highest and measured
    r = -0.035 (R^2 = 0.001) against actual tricks -- no predictive power at all.
    """
    groups: dict[str, list[Card]] = {s: [] for s in SUITS}
    for c in hand:
        groups[c.suit].append(c)

    honour_pts = sum(HONOUR_VALUE.get(c.rank, 0.0) for c in hand)

    def _trump_value(count: int) -> float:
        return (TRUMP_CARD * count
                + LENGTH_BONUS * max(0, count - LENGTH_BONUS_FROM))

    suit_pts = {s: honour_pts + _trump_value(len(cards))
                for s, cards in groups.items()}

    lengths = sorted([len(cards) for cards in groups.values()], reverse=True)
    is_balanced = lengths in ([4, 3, 3, 3], [4, 4, 3, 2], [5, 3, 3, 2])

    return {
        'honour_pts': honour_pts,
        'suit_pts': suit_pts,
        'total_pts': max(suit_pts.values()),
        'groups': groups,
        'lengths': lengths,
        'is_balanced': is_balanced,
    }


# ── Bidding thresholds (fitted) ───────────────────────────────────────────────
# Every threshold is in EXPECTED TRICKS -- the unit eval_hand_sh returns -- so each
# can be compared directly against solved double dummy results. See
# research/hand_value.py and "Hand evaluation and bidding research" in docs/BIDDING.md.
#
#   * Notrump is never the right strain (it won 7 of 600 solved comparisons), so
#     this AI never bids it. A finding, not a simplification.
#   * Undoubled overtricks score exactly what contracted tricks score, so
#     underbidding is nearly free and overbidding costs 50-100 a trick.
#   * Game is rare and lives in the majors: 4M makeable 21%, 5m 12%, 3NT 10%.

# 9.5 was right while a trump card was worth a flat 1.025. `LENGTH_BONUS` adds
# up to ~1.5 tricks to a long-suit partnership's combined count, so the same
# threshold started firing on hands with no game values at all -- a 7-card suit
# with SIX points bid 4S and went three down. Moving it to 10.0 absorbs the
# inflation: head to head against 9.5 it is -0.0 (t = -0.04, 8 deals), while
# game contracts fall 27 -> 20, the make rate rises 65% -> 66%, and the
# declaring-side score recovers +56.3 -> +57.2 (above the +57.1 it had before
# the bonus). The older note that 9.5 beat 10.0 (+77.4 against +73.0) was
# measured WITHOUT the length bonus and no longer applies.
GAME_TRICKS = 10.0
PARTSCORE_LEVEL = 2
OPEN_TRICKS = 4.5
OPEN_SUIT_LENGTH = 5
SUPPORT_LENGTH = 3
OVERCALL_TRICKS = 4.5

#: Minimum points to overcall at all. The trick-count threshold alone is met by
#: a five-card suit holding nothing at all (length is worth ~1.15 tricks a card
#: here), which produced overcalls on 3 points -- something no bridge player
#: would make, and a good way to get doubled. The guide asks for more to come in
#: higher, so the enforced floors are OVERCALL_POINTS_1 / OVERCALL_POINTS_2
#: below; this is the lower of the two, kept as the "can I compete at all" gate.
OVERCALL_POINTS = 8
PREEMPT_LENGTH = 6
# The pre-empt gate used to be a trick ceiling (5.5). It is now the card's
# points band, PREEMPT_POINTS_LOW..PREEMPT_POINTS_HIGH below, which is both
# the guide's own test and what the alert quotes.

# ── A 2/1-shaped structure ────────────────────────────────────────────────────
# A new suit at the TWO level shows real values and asks partner to describe
# again; a jump raise shows support with extra; a simple raise is limited. That
# is the recognisable skeleton of a natural 2/1 system.
#
# TWO THINGS ARE DELIBERATELY NOT BORROWED FROM REAL 2/1, both measured:
#
# 1. It is forcing for ONE ROUND, not to game. Standard 2/1 is game-forcing
#    because in real bridge game is usually the right contract. Here 4M is
#    makeable 21% of the time and twelve tricks 1.3%, so committing to game
#    loses: driving to game measured -14 to -20 points per board.
#
# 2. The promises are DIFFERENTIATED BUT CONSERVATIVE. What partner actually
#    holds was measured -- opened 4.66, 2/1 5.66, simple raise 3.56, jump raise
#    4.67 at the 10th percentile -- and feeding those true values in scored -16.0
#    (t = -2.55) against a flat 4.5. Accurate promises bid WORSE, because the loss
#    function is asymmetric: with +/-1.14 tricks of estimate error, bidding at
#    true capability overshoots half the time, and overshooting is punished while
#    undershooting is nearly free. Shifting every promise down 1.5 keeps the
#    differentiation while restoring the conservatism, and costs only -0.5 points
#    (t = -0.09). Do not "correct" these upward to their measured values.
PROMISE_SHIFT = 1.5
PROMISE_OPENED = 4.66 - PROMISE_SHIFT
PROMISE_RESPONDED_1 = 4.39 - PROMISE_SHIFT
PROMISE_TWO_OVER_ONE = 5.66 - PROMISE_SHIFT
PROMISE_RAISED = 3.56 - PROMISE_SHIFT
PROMISE_JUMP_RAISED = 4.67 - PROMISE_SHIFT
#: A takeout double promises 3+ cards in every suit but theirs, which is the same
#: support a simple raise shows -- so it is valued the same. Advancing a double is
#: FORCED, so it promises less than a freely-chosen response: same value again.
PROMISE_DOUBLED = 3.56 - PROMISE_SHIFT
PROMISE_ADVANCED = 3.56 - PROMISE_SHIFT
#: A cuebid shows 11+ points with support -- more than a simple raise, so it is
#: valued like a jump raise. It says nothing whatever about the suit it names.
PROMISE_CUEBID = 4.67 - PROMISE_SHIFT

#: Own threshold to make a 2/1 (new suit at the two level) rather than a 1-level
#: response: it commits the partnership to another round, so it needs values.
TWO_OVER_ONE_TRICKS = 5.6

#: Minimum high-card points for a two-over-one. The trick threshold alone is met
#: by a six-card suit holding nothing (length is ~1.15 tricks a card here), which
#: produced "two-over-one" on 8 points -- not a hand any bridge player would call
#: game-forcing, and the bid says otherwise to partner.
TWO_OVER_ONE_POINTS = 12

#: A FREE BID: partner opened, an opponent overcalled, and this hand has a long
#: suit of its own. Not a two-over-one -- the overcall took away the one-level
#: response, so a two-level call here shows a SUIT, not game values. Without it
#: the suit had nowhere to go and the hand passed: board 2's North passed on
#: eight diamonds, and one hand in the dataset passed on nine and 16 points.
#: Measured head to head at 6+/8+: +3.6 per board, t = +2.36, 14 deals moved.
#: Swept: 5+/6+ gave +3.5 (t = +1.94), 6+/6+ +3.4 (t = +2.23), 7+/6+ only +0.3.
FREE_BID_LENGTH = 6
FREE_BID_POINTS = 8

#: Own threshold to jump-raise instead of raising simply.
JUMP_RAISE_TRICKS = 6.2

# Every decision below returns (call, explanation). The explanation is what the
# table sees when it alerts a robot's bid, so it is written for a player: what
# the bid shows, and the number behind it. `ai_bid` keeps returning a bare call
# so nothing that only wants the decision has to care.


def _bids_by(seat: str, auction: AuctionState) -> list:
    """(level, strain) for each real bid `seat` has made, in order."""
    return [parse_bid(call) for who, call in auction.calls
            if who == seat and parse_bid(call)]


def _doubled_by(seat: str, auction: AuctionState) -> bool:
    """Has `seat` made a takeout double? `_bids_by` cannot see one -- 'X' does not
    parse as a bid -- so every branch that cares has to ask separately."""
    return any(who == seat and call == 'X' for who, call in auction.calls)


def _their_suit(player: str, auction: AuctionState) -> str | None:
    """The strain the opponents most recently named."""
    partner = PARTNERS[player]
    for who, call in reversed(auction.calls):
        parsed = parse_bid(call)
        if parsed and who not in (player, partner):
            return parsed[1]
    return None


def _first_namer(auction: AuctionState, strain: str) -> str | None:
    """Who put `strain` on the table first. Raising is defined by order of the
    whole auction, not by each seat's own list: partner's FIRST bid can be a raise
    of a suit this hand opened, and reading that as a two-over-one both overstates
    what they hold and mislabels it in the alert."""
    for who, call in auction.calls:
        parsed = parse_bid(call)
        if parsed and parsed[1] == strain:
            return who
    return None


def _is_cuebid(player: str, auction: AuctionState, strain: str) -> bool:
    """Did our side name `strain` only after the opponents had already bid it?

    A bid in a suit the opponents introduced is not a suit bid. Reading it as one
    is the classic way a half-implemented cuebid goes wrong: partner "supports"
    the opponents' suit and the pair plays in it.
    """
    namer = _first_namer(auction, strain)
    return namer is not None and namer not in (player, PARTNERS[player])


def _partner_promise(player: str, partner: str, auction: AuctionState,
                     strain: str) -> float:
    """What partner has promised in `strain`, read off what they actually bid.

    A flat constant here is what made the old auction uninformative: nothing
    partner did changed what you assumed about them.
    """
    mine = _bids_by(player, auction)
    theirs = _bids_by(partner, auction)
    if not theirs:
        # A double is not a bid, but it is a promise: 3+ cards in every suit but
        # theirs. Without this the doubler's partner is read as having said
        # nothing at all.
        return PROMISE_DOUBLED if _doubled_by(partner, auction) else PROMISE_OPENED

    # Partner bidding over MY double is an advance -- forced, so weak. Reading it
    # as an opening (which the `opened` test below would) overstates it badly.
    if _doubled_by(player, auction) and not mine:
        return PROMISE_ADVANCED

    named_here = [b for b in theirs if b[1] == strain]
    if not named_here:
        return PROMISE_RESPONDED_1

    introduced_level = named_here[0][0]
    opened = (not mine) or theirs[0][0] <= mine[0][0]

    if _first_namer(auction, strain) == player:
        # partner is supporting a suit this hand named first
        return PROMISE_JUMP_RAISED if introduced_level >= 3 else PROMISE_RAISED
    if opened and theirs[0][1] == strain:
        return PROMISE_OPENED
    return PROMISE_TWO_OVER_ONE if introduced_level >= 2 else PROMISE_RESPONDED_1


def _is_two_over_one(responder_suit: str, opener_suit: str) -> bool:
    """Is a two-level bid of `responder_suit` over `opener_suit` a real 2/1?

    Only when responder's suit ranks BELOW opener's -- that is what forces it to
    the two level in the first place. A higher-ranking suit is available at the
    one level, so bidding it at the two is a jump shift: a different call, with a
    different meaning, costing a level of room. `SUITS` runs low to high.
    """
    if responder_suit not in SUITS or opener_suit not in SUITS:
        return False
    return SUITS.index(responder_suit) < SUITS.index(opener_suit)


def _game_call(strain: str, legal: list[str]) -> str | None:
    """The game worth bidding in `strain`, if one is still legal.

    Four of a major and nothing else. Five of a minor needs eleven tricks
    (makeable 12%); 3NT needs nine (10%) and notrump loses to the suit fit even
    where it makes. A minor fit plays a partscore.
    """
    if strain in ('H', 'S'):
        call = f"4{strain}"
        return call if call in legal else None
    return None


def _cheapest(strain: str, level: int, legal: list[str]) -> str | None:
    """The cheapest legal bid in `strain` at or above `level`."""
    for lvl in range(level, 8):
        call = f"{lvl}{strain}"
        if call in legal:
            return call
    return None


SUIT_WORD = {'S': 'spades', 'H': 'hearts', 'D': 'diamonds', 'C': 'clubs'}
SUIT_SYM = {'S': '\u2660', 'H': '\u2665', 'D': '\u2666', 'C': '\u2663'}

# Points are counted the UMD way: high cards plus LENGTH POINTS (one per card
# past the fourth in any suit), minus one for a flat 4-3-3-3. That method, not
# raw HCP, is the currency the system card's thresholds are written in -- and it
# is also much closer to what actually wins tricks here, where a trump card is
# worth about a trick (TRUMP_CARD). Counting the guide's way moved this AI's median
# opening from 11 raw HCP to exactly 12 guide points: the system was never as
# light as raw HCP made it look.
#
# The floors below ARE enforced, so an alert quoting them tells the truth, and
# they are the card's own numbers -- including the opening.
#
# THAT TOOK TWO MEASUREMENTS, and the first one was wrong. Scored from the
# DECLARING side (`harness.run`, the metric this project has used throughout),
# the card's 12+ opening looked catastrophic: -11.6 per board, t = -3.34. That
# metric grades whoever buys the contract, so a passed-out board scores 0 for
# it, and a tighter opening floor passes more boards out -- 35 against 10. It
# was counting caution as failure. Seated head to head instead (variant at N/S
# against the shipped AI at E/W, then the seats swapped, scored from the
# variant's own side) the card's floor costs -0.2, t = -0.14: nothing.
# So the opening is the card's 12+, not a house number.
OPEN_POINTS = 12
OVERCALL_POINTS_1 = 8          # guide: 1-level overcall, 8+ points, 5+ cards
OVERCALL_POINTS_2 = 10         # guide: 2-level overcall, 10+ points, 5+ cards
PREEMPT_POINTS_LOW = 6         # guide: weak two/three, 6-10 points
PREEMPT_POINTS_HIGH = 11
PREEMPT_LENGTH_3 = 7           # guide: 3-level preempt needs 7+ cards
# No pre-empt in FOURTH seat: after three passes there is nobody left to
# obstruct, and a weak hand can simply pass the board out. A two-level opening
# there shows a sound hand instead -- 11-15 points and a six-card suit -- as in
# standard bridge. A user caught North opening a weak 2S after three passes.
# Head to head over 289 deals x 4 dealers: +0.22 per board (t = +1.07, 13
# contracts moved) against the weak two; merely dropping the pre-empt was
# -0.06 (t = -0.95, 3 moved). Rare, so neither is detectable; it is the card.
FOURTH_TWO_POINTS_LOW = 11
FOURTH_TWO_POINTS_HIGH = 16

# Takeout doubles, from the guide's table. A double says "I have an opening hand
# but no suit long enough to name -- pick one". It is the only call that lets a
# strong flat hand compete, and without it this AI passed the whole class out.
TAKEOUT_POINTS_1 = 12          # guide: X over a 1-level opening
TAKEOUT_POINTS_2 = 14          # guide: X over a 2-level opening
TAKEOUT_MAX_THEIRS = 2         # guide: 2 or fewer cards in their suit
TAKEOUT_MIN_ELSEWHERE = 3      # guide: 3-4 cards in every other suit
ADVANCE_JUMP_POINTS = 8        # guide: 0-7 cheapest, 8-12 a level higher

# The guide's opener-rebid tiers. Partner passing has already denied a response,
# so these decide whether to speak again at all, not how high to go.
REBID_MINIMUM = 12             # guide: 12-15 is a minimum rebid
# The card's 16-17 'extra values' tier has no separate constant because the
# CALL cannot show it: the level is capped either way, so both tiers make the
# same bid and the alert quotes the 12+ floor rather than leaking strength.
REBID_LENGTH = 6               # extra length is its own reason to bid again

# The cuebid -- advancer bidding the OPPONENTS' suit to show a good raise of
# partner's overcall -- has no threshold constant because the AI does not make the
# call. The card's 11+ points with 3+ support was implemented and measured at
# -4.1 per board head to head (t = -2.66); see `_response`. `_is_cuebid` still
# READS one.

# The guide's raise tiers, which the alerts quote. JUMP_RAISE_POINTS is enforced
# as well as printed, and costs nothing: the trick threshold beside it already
# implied 10+ points, so adding it changed 0 of 299 deals. RAISE_POINTS is the
# floor a simple raise states; a simple raise is not upper-bounded here, so the
# alert says "6+" and not the card's "6-9", which would be false above nine.
RAISE_POINTS = 6
JUMP_RAISE_POINTS = 10
RESPONSE_POINTS_SHOWN = 6


def _points(groups: dict) -> int:
    """The guide's point count: high cards + length points, -1 if 4-3-3-3.

    Length points are one per card past the fourth in a suit, so a five-card suit
    is worth one and a six-card suit two. Every threshold in this module and
    every alert it writes is denominated in this count.
    """
    hcp = sum(_HCP.get(card.rank, 0)
              for cards in groups.values() for card in cards)
    length = sum(max(0, len(cards) - 4) for cards in groups.values())
    shape = sorted((len(cards) for cards in groups.values()), reverse=True)
    flat = -1 if shape == [4, 3, 3, 3] else 0
    return hcp + length + flat


def _dist_points(groups: dict, trump: str) -> int:
    """Shortness points, valid ONLY opposite a known fit -- the guide's rule.

    Void 5, singleton 3, doubleton 1, counted outside the trump suit.
    """
    bonus = {0: 5, 1: 3, 2: 1}
    return sum(bonus.get(len(cards), 0)
               for suit, cards in groups.items() if suit != trump)


def _place(strain: str, combined: float, legal: list[str], held: int) -> tuple:
    """Put the contract in `strain` no higher than the count supports.

    The floor is always PARTSCORE_LEVEL, never partner's level: letting the floor
    follow the auction upward is what made an earlier 2/1 attempt escalate, with
    2-level contracts collapsing from 211 to 125 and the score dropping 14 points.
    """
    if combined >= GAME_TRICKS:
        game = _game_call(strain, legal)
        if game:
            return game, f"{SUPPORT_LENGTH}+ {SUIT_SYM[strain]} support, game values."
    ceiling = max(1, int(combined) - 6)
    call = _cheapest(strain, PARTSCORE_LEVEL, legal)
    # A SIMPLE RAISE at the partscore level is never vetoed by the ceiling.
    # Showing three-card support is the most routine bid in bridge, and partner
    # cannot read a fit out of a pass. It was being suppressed because the
    # ceiling is computed from a deliberately conservative partner promise: on
    # board 146 South held four-card support and 10 points opposite an opening,
    # scored the partnership at 7.63 against a true 10.57, and passed.
    # Head to head this is +4.0 per board (t = +2.19, 42 of 300 deals moved).
    # It does NOT reopen the escalation that `_place`'s floor guards against:
    # `max(ceiling, PARTSCORE_LEVEL)` admits level 2 and nothing higher, so a
    # 3-level call still has to clear the ceiling on its own.
    if call and parse_bid(call)[0] <= max(ceiling, PARTSCORE_LEVEL):
        return call, (f"{SUPPORT_LENGTH}+ {SUIT_SYM[strain]} support, limited.")
    return 'Pass', "No extra values."


def _one_level_opening_alert(suit: str) -> str:
    """What a one-level opening SHOWS, which must not depend on the hand.

    A major promises five. A minor is opened on five cards or as the better
    minor on three or four, and the alert used to say which ("5+", "4+" or
    "3+ ... No five-card major") -- telling the table the hand's exact minor
    lengths. Every 1m opening shows the same thing: 3+.
    """
    shown = OPEN_SUIT_LENGTH if suit in ('H', 'S') else 3
    return f"{shown}+ {SUIT_SYM[suit]}, {OPEN_POINTS}+ points."


def _opening_bid(ev: dict, groups: dict, best_suit: str, best_len: int,
                 legal: list[str], fourth_seat: bool = False) -> tuple:
    """Open by showing length. Finding the fit is the whole job of the auction."""
    word = SUIT_WORD.get(best_suit, best_suit)
    pts = _points(groups)
    strong = ev['total_pts'] >= OPEN_TRICKS and pts >= OPEN_POINTS
    if (fourth_seat and FOURTH_TWO_POINTS_LOW <= pts < FOURTH_TWO_POINTS_HIGH
            and best_len >= PREEMPT_LENGTH and f"2{best_suit}" in legal):
        return f"2{best_suit}", (
            f"{PREEMPT_LENGTH}+ {SUIT_SYM[best_suit]}, "
            f"{FOURTH_TWO_POINTS_LOW}-{FOURTH_TWO_POINTS_HIGH - 1} points. "
            f"Fourth seat.")
    if strong and best_len >= OPEN_SUIT_LENGTH:
        if f"1{best_suit}" in legal:
            return f"1{best_suit}", _one_level_opening_alert(best_suit)

    # Pre-empts, at the card's lengths: six cards at the two level, seven at the
    # three. Too weak to open at the one level; bidding anyway steals their room.
    if PREEMPT_POINTS_LOW <= pts < PREEMPT_POINTS_HIGH and not fourth_seat:
        if best_len >= PREEMPT_LENGTH_3 and f"3{best_suit}" in legal:
            return f"3{best_suit}", (
                f"{PREEMPT_LENGTH_3}+ {SUIT_SYM[best_suit]}, "
                f"{PREEMPT_POINTS_LOW}-10 points. Pre-emptive.")
        if best_len >= PREEMPT_LENGTH and f"2{best_suit}" in legal:
            return f"2{best_suit}", (
                f"{PREEMPT_LENGTH}+ {SUIT_SYM[best_suit]}, "
                f"{PREEMPT_POINTS_LOW}-10 points. Pre-emptive.")

    # No five-card suit: open the better minor exactly as the card has it --
    # the longer minor, 1C when both are three, 1D when both are four.
    if strong:
        clubs, diamonds = len(groups['C']), len(groups['D'])
        if clubs >= 3 or diamonds >= 3:
            suit = 'C' if clubs > diamonds or (clubs == diamonds == 3) else 'D'
            if f"1{suit}" in legal:
                return f"1{suit}", _one_level_opening_alert(suit)
    if pts < OPEN_POINTS:
        return 'Pass', f"Fewer than {OPEN_POINTS} points."
    return 'Pass', "No suit worth opening."


def _takeout_double(player: str, auction: AuctionState, groups: dict,
                    pts: int, legal: list[str]) -> tuple | None:
    """The guide's takeout double, or None if this hand does not qualify.

    12+ points over a one-level opening and 14+ over a two-level one, at most two
    cards in their suit, and at least three in every other suit. The shape test
    is the point of the call: it says "no suit of my own, but I can play any of
    the others", which is exactly the hand that otherwise has nothing to bid.
    """
    if 'X' not in legal:
        return None
    theirs = _their_suit(player, auction)
    if theirs is None or theirs not in SUITS:
        return None
    if len(groups[theirs]) > TAKEOUT_MAX_THEIRS:
        return None
    if any(len(groups[s]) < TAKEOUT_MIN_ELSEWHERE for s in SUITS if s != theirs):
        return None
    their_level = max((parse_bid(c)[0] for who, c in auction.calls
                       if parse_bid(c) and who not in (player, PARTNERS[player])),
                      default=1)
    need = TAKEOUT_POINTS_1 if their_level <= 1 else TAKEOUT_POINTS_2
    if pts < need:
        return None
    return 'X', (f"{need}+ points, {TAKEOUT_MAX_THEIRS} or fewer "
                 f"{SUIT_SYM[theirs]}. Takeout: bid your best suit.")


def _advance_double(player: str, partner: str, auction: AuctionState, ev: dict,
                    groups: dict, legal: list[str]) -> tuple:
    """Partner doubled and it is my call: name my longest suit, not theirs.

    The double asked a question, so passing is not an answer -- it converts the
    double to a penalty double, which is never what it meant here. The level says
    how much I hold: cheapest on 0-7, one higher on 8+.
    """
    theirs = _their_suit(player, auction)
    pts = _points(groups)
    candidates = [s for s in SUITS if s != theirs]
    best = max(candidates, key=lambda s: (len(groups[s]), ev['suit_pts'][s],
                                          SUITS.index(s)))
    combined = ev['suit_pts'][best] + PROMISE_DOUBLED
    ceiling = max(1, int(combined) - 6)
    start = 1 + (1 if pts >= ADVANCE_JUMP_POINTS else 0)
    cheapest = _cheapest(best, 1, legal)

    def answer(call: str) -> str:
        # What the answer SHOWS: the longest suit other than theirs, and 8+ only
        # when it jumps. A non-jump is made on any strength (over 1S, 2H is the
        # cheapest heart bid for 3 points and for 12), and the suit may be
        # three cards long. This alert used to quote the hand's actual length
        # and point band, i.e. read the advancer's cards out to the table.
        sym = SUIT_SYM[parse_bid(call)[1]]
        if call != cheapest:
            return f"{ADVANCE_JUMP_POINTS}+ points, longest suit, {sym}. Answering the double."
        return f"Longest suit other than theirs, {sym}. Answering the double."

    call = _cheapest(best, start, legal)
    if call and parse_bid(call)[0] <= max(ceiling, PARTSCORE_LEVEL):
        return call, answer(call)

    # The cheapest answer may sit above the usual ceiling -- over a weak two, the
    # only reply is at the three level. Answer anyway: partner ASKED, and leaving
    # a takeout double in converts it to a penalty double, a different call
    # entirely. Only a hand with nothing at all passes it out.
    call = cheapest
    if call and pts >= ADVANCE_JUMP_POINTS:
        return call, answer(call)
    # Answer it whatever the level. Passing a takeout double converts it to a
    # PENALTY double, which is a different call and a disaster when partner
    # meant takeout: on deal 212 it handed the opponents 2S doubled and making,
    # worth 570. Head to head, always answering is worth +2.1 (t = +1.65). The
    # declaring-side metric scored it -3.3, because a board where the OPPONENTS
    # blunder into a made doubled contract counts as a win for that metric.
    if call:
        return call, answer(call)
    return 'Pass', "No legal suit to answer the double."


def _rebid_alone(player: str, auction: AuctionState, ev: dict, groups: dict,
                 best_suit: str, best_len: int, legal: list[str]) -> tuple:
    """I have bid, partner has not. Repeat a long suit, or pass -- honestly.

    Before this branch existed such a hand fell through to the overcall code and
    re-bid its own suit under the alert "Overcall", which is the one thing it
    demonstrably is not. Partner's pass has denied values, so the bar to speak
    again is extra LENGTH (a sixth card) or extra strength, never just a wish to
    compete.
    """
    mine = _bids_by(player, auction)
    my_first = mine[0][1]
    pts = _points(groups)
    held = len(groups[my_first])

    # Nothing has changed about this hand, so only real extra justifies a repeat.
    # The guide's minimum-rebid tier, and it measured best of the five bars
    # tried (+1.2 per board against never rebidding alone's -3.3).
    if held >= REBID_LENGTH or (pts >= REBID_MINIMUM and held >= OPEN_SUIT_LENGTH):
        combined = ev['suit_pts'][my_first] + PROMISE_RESPONDED_1
        ceiling = max(1, int(combined) - 6)
        call = _cheapest(my_first, PARTSCORE_LEVEL, legal)
        # The CEILING decides, not a hard clamp to the partscore. Clamping
        # here meant a lone rebid could never go above the two level, so once
        # the opponents competed to 2-something the hand was silenced whatever
        # it held: on board 106 North sat on eight clubs to the KQJ and a void,
        # its own estimate reading 11.37 tricks (ceiling 5), and passed -- while
        # 7C was available for +1440. Head to head +3.6, t = +2.92, 26 deals.
        # Capping at 3 as well measured identically (the ceiling never exceeds
        # 3 in practice), so the clamp buys nothing and is left out.
        if call and parse_bid(call)[0] <= ceiling:
            # ONE text for both reasons the rebid fires (six cards on any
            # strength, or five with 12+). Quoting whichever applied told the
            # table which it was -- "6+" or "12+ points" -- for the same call in
            # the same auction. Only the floor common to both may be quoted.
            return call, (f"{OPEN_SUIT_LENGTH}+ {SUIT_SYM[my_first]}. "
                          f"Rebidding my own suit.")
    return 'Pass', "Partner has passed; not enough to bid again alone."


def _response(player: str, partner: str, auction: AuctionState, ev: dict,
              groups: dict, best_suit: str, best_len: int, legal: list[str]) -> tuple:
    """Partner has bid. Raise with support, else show a suit -- at the two level
    with real values (the 2/1), at the one level without."""
    theirs = _bids_by(partner, auction)
    p_level, p_strain = theirs[-1]

    if p_strain not in SUITS:
        if best_len >= OPEN_SUIT_LENGTH:
            call = _cheapest(best_suit, p_level, legal)
            if call and parse_bid(call)[0] <= PARTSCORE_LEVEL + 1:
                return call, (
                    f"{OPEN_SUIT_LENGTH}+ {SUIT_SYM[best_suit]}. Taking it out of "
                    f"notrump.")
        return 'Pass', "Nothing to show over notrump."

    word = SUIT_WORD.get(p_strain, p_strain)
    held = len(groups[p_strain])

    # Partner's "suit" may be a cuebid of the opponents'. It shows support for
    # MY suit, not length in theirs, so fall through to the rebid logic.
    if _is_cuebid(player, auction, p_strain):
        mine_named = _bids_by(player, auction)
        agreed = mine_named[0][1] if mine_named else best_suit
        combined = ev['suit_pts'][agreed] + PROMISE_CUEBID
        call, why = _place(agreed, combined, legal, len(groups[agreed]))
        if call != 'Pass':
            why = (f"{SUIT_SYM[agreed]} again over the cuebid. "
                   f"Partner showed support, not their suit.")
        return call, why

    if held >= SUPPORT_LENGTH:
        # THE AI DOES NOT CUEBID, and this is where it would. Implemented and
        # measured: advancer bidding the opponents' suit on 11+ points with
        # support cost -4.1 points per board head to head (t = -2.66; -16.4 on
        # the declaring-side metric, which a competitive call can't use), and
        # pushed contracts at the 3-level or higher from 17 to 25. The cause is
        # the one already recorded for game-forcing 2/1: showing extra values
        # buys height, and height is where this variant loses money, because an
        # undoubled overtrick scores exactly what a contracted trick scores.
        # `_is_cuebid` is still live and the rebid branches still read a cuebid
        # correctly, so a HUMAN South who cuebids is understood by robot North.
        pass
        promise = _partner_promise(player, partner, auction, p_strain)
        combined = ev['suit_pts'][p_strain] + promise
        pts = _points(groups)
        if combined >= GAME_TRICKS:
            game = _game_call(p_strain, legal)
            if game:
                return game, (
                    f"{SUPPORT_LENGTH}+ {SUIT_SYM[p_strain]} support, game values.")
        ceiling = max(1, int(combined) - 6)
        if (ev['total_pts'] >= JUMP_RAISE_TRICKS and pts >= JUMP_RAISE_POINTS
                and ceiling >= PARTSCORE_LEVEL + 1):
            jump = _cheapest(p_strain, PARTSCORE_LEVEL + 1, legal)
            # Only a JUMP is a jump raise: where the cheapest raise is already
            # at the three level, the same call would carry two alerts.
            if (jump and parse_bid(jump)[0] <= ceiling
                    and jump != _cheapest(p_strain, PARTSCORE_LEVEL, legal)):
                return jump, (
                    f"{SUPPORT_LENGTH}+ {SUIT_SYM[p_strain]} support, "
                    f"{JUMP_RAISE_POINTS}+ points. Invitational.")
        # The guide's floor for a raise, enforced so the alert can quote it;
        # free on the solved set (0 of 299 deals changed). The alert states the
        # FLOOR, not the card's 6-9 band: a hand with 13 points that misses the
        # jump raise's trick test still raises simply, so "under 10" was false.
        if pts < RAISE_POINTS:
            return 'Pass', f"Fewer than {RAISE_POINTS} points."
        call, why = _place(p_strain, combined, legal, held)
        if call != 'Pass':
            why = (f"{SUPPORT_LENGTH}+ {SUIT_SYM[p_strain]} support, "
                   f"{RAISE_POINTS}+ points. Limited.")
        return call, why

    if best_len >= OPEN_SUIT_LENGTH:
        own = SUIT_WORD[best_suit]
        pts = _points(groups)
        # A suit that OUTRANKS partner's is shown at the one level. Bidding it
        # at the two instead is a jump shift, not a two-over-one, and it throws
        # away a level of room: over 1D, spades belong in 1S, never 2S.
        # SUITS runs low to high, so the 2/1 test is a rank comparison.
        one = _cheapest(best_suit, 1, legal)
        if one and parse_bid(one)[0] == 1 and pts >= RESPONSE_POINTS_SHOWN:
            return one, (
                f"{OPEN_SUIT_LENGTH}+ {SUIT_SYM[best_suit]}, "
                f"{RESPONSE_POINTS_SHOWN}+ points.")

        # Only a lower-ranking suit is a genuine two-over-one -- that is exactly
        # why it cannot be bid at the one level. Over 1C there is none, since
        # every other suit is available cheaper.
        # In competition a two-over-one and a free bid can be the SAME call in
        # the same auction, and an alert naming whichever fired would tell the
        # table "12+" or "6+ cards". There the alert quotes what both share.
        contested = any(who not in (player, partner) and parse_bid(call)
                        for who, call in auction.calls)
        ambiguous = contested and _is_two_over_one(best_suit, p_strain)
        either = (f"{OPEN_SUIT_LENGTH}+ {SUIT_SYM[best_suit]}, "
                  f"{FREE_BID_POINTS}+ points.")

        if (_is_two_over_one(best_suit, p_strain)
                and ev['total_pts'] >= TWO_OVER_ONE_TRICKS
                and pts >= TWO_OVER_ONE_POINTS):
            two = _cheapest(best_suit, 2, legal)
            if two and parse_bid(two)[0] == 2:
                return two, either if ambiguous else (
                    f"{OPEN_SUIT_LENGTH}+ {SUIT_SYM[best_suit]}, "
                    f"{TWO_OVER_ONE_POINTS}+ points. Forcing.")

        # A FREE BID. An overcall has taken the one-level response away, so a
        # long suit has no cheap home and the two-over-one's 12 points are the
        # wrong test -- this is not a game force, it is "I have a suit". Without
        # this branch the hand simply passed on six, eight, even nine cards.
        if contested and best_len >= FREE_BID_LENGTH and pts >= FREE_BID_POINTS:
            call, _ = _place(best_suit, ev['suit_pts'][best_suit] + PROMISE_OPENED,
                             legal, best_len)
            if call != 'Pass':
                return call, either if ambiguous else (
                    f"{FREE_BID_LENGTH}+ {SUIT_SYM[best_suit]}, "
                    f"{FREE_BID_POINTS}+ points. Free bid.")

    # Say which of the two reasons actually applies. Claiming "no five-card
    # suit" on a hand holding one was false 141 times across 300 deals.
    if best_len >= OPEN_SUIT_LENGTH:
        return 'Pass', "Not enough to introduce a new suit at this level."
    return 'Pass', (
        f"Fewer than {SUPPORT_LENGTH} {SUIT_SYM[p_strain]} and no five-card suit.")


def _rebid(player: str, partner: str, auction: AuctionState, ev: dict,
           groups: dict, best_suit: str, best_len: int, legal: list[str]) -> tuple:
    """Both have bid. Support partner's suit, settle in the agreed one, or pass.

    Everything goes through `_place`, so no describing call can push the contract
    past what the partnership's own count supports.
    """
    mine = _bids_by(player, auction)
    theirs = _bids_by(partner, auction)
    if not mine or not theirs:
        return 'Pass', "Pass."
    p_level, p_strain = theirs[-1]
    my_first = mine[0][1]

    if _is_cuebid(player, auction, p_strain):
        combined = ev['suit_pts'][my_first] + PROMISE_CUEBID
        call, why = _place(my_first, combined, legal, len(groups[my_first]))
        if call != 'Pass':
            why = (f"{SUIT_SYM[my_first]} again over the cuebid. "
                   f"Partner showed support, not their suit.")
        return call, why

    if p_strain in SUITS and len(groups[p_strain]) >= SUPPORT_LENGTH:
        held = len(groups[p_strain])
        promise = _partner_promise(player, partner, auction, p_strain)
        combined = ev['suit_pts'][p_strain] + promise
        call, why = _place(p_strain, combined, legal, held)
        if call != 'Pass':
            why = f"{SUPPORT_LENGTH}+ {SUIT_SYM[p_strain]} support, agreeing the suit."
        return call, why

    if p_strain == my_first:
        promise = _partner_promise(player, partner, auction, my_first)
        combined = ev['suit_pts'][my_first] + promise
        call, why = _place(my_first, combined, legal, len(groups[my_first]))
        if call != 'Pass':
            why = f"{SUIT_SYM[my_first]} agreed. No extra values shown."
        return call, why

    if best_len >= OPEN_SUIT_LENGTH + 1:
        combined = ev['suit_pts'][best_suit] + PROMISE_RESPONDED_1
        call, why = _place(best_suit, combined, legal, best_len)
        if call != 'Pass':
            why = f"6+ {SUIT_SYM[best_suit]}, rebidding the suit."
        return call, why
    return 'Pass', "No fit, nothing more to show."


#: GIB 2/1 is the default system (gib.py). False plays the previous system,
#: kept intact so the two can be measured head to head.
USE_GIB = True


def ai_bid_explained(player: str, hand: list[Card], auction: AuctionState) -> tuple:
    """The bid this hand would make, together with a plain-words alert saying what
    it shows. `ai_bid` returns only the call, for callers that do not want the
    explanation."""
    legal = auction.legal_calls()
    if not legal:
        return 'Pass', "Pass. No legal call available."

    # GIB 2/1 is the system. The logic below answers only the contested
    # situations GIB's notes leave to judgment. `USE_GIB = False` restores the
    # previous, measured system whole, for comparisons.
    if USE_GIB:
        decision = gib.gib_bid(player, hand, auction)
        if decision:
            return decision

    ev = eval_hand_sh(hand)
    groups = ev['groups']
    best_suit = max(SUITS, key=lambda s: (len(groups[s]), ev['suit_pts'][s],
                                          SUITS.index(s)))
    best_len = len(groups[best_suit])

    partner = PARTNERS[player]
    my_bids = _bids_by(player, auction)
    partner_bids = _bids_by(partner, auction)
    opponents_bid = any(who not in (player, partner)
                        and (parse_bid(call) or call in ('X', 'XX'))
                        for who, call in auction.calls)

    # Partner doubled and has said nothing else: the double asked a question and
    # this is the answer. It comes before every other branch, because passing a
    # takeout double turns it into a penalty double.
    if (_doubled_by(partner, auction) and not partner_bids and not my_bids
            and not _doubled_by(player, auction)):
        return _advance_double(player, partner, auction, ev, groups, legal)

    if partner_bids and my_bids:
        return _rebid(player, partner, auction, ev, groups, best_suit, best_len, legal)
    if partner_bids:
        return _response(player, partner, auction, ev, groups, best_suit, best_len, legal)
    if my_bids:
        # I have bid and partner has not. This branch used to be missing, which
        # sent the opener into the overcall code to bid its own suit again.
        return _rebid_alone(player, auction, ev, groups, best_suit, best_len, legal)
    if not opponents_bid:
        fourth_seat = (len(auction.calls) == 3
                       and all(call == 'Pass' for _, call in auction.calls))
        return _opening_bid(ev, groups, best_suit, best_len, legal, fourth_seat)

    pts = _points(groups)
    # Never overcall in a suit THEY have bid. It is not a bid any player makes --
    # they are the ones with length there -- and partner cannot tell it from a
    # cuebid. This fired for real: over 1H, a hand with five hearts and 18 points
    # "overcalled" 2H, and over 1D a seven-card diamond hand bid 2D.
    theirs_bid = {s for s in SUITS
                  if _first_namer(auction, s) not in (None, player, partner)}
    own = [s for s in SUITS if s not in theirs_bid]
    if own:
        best_suit = max(own, key=lambda s: (len(groups[s]), ev['suit_pts'][s],
                                            SUITS.index(s)))
        best_len = len(groups[best_suit])
    if own and ev['total_pts'] >= OVERCALL_TRICKS and best_len >= OPEN_SUIT_LENGTH:
        call = _cheapest(best_suit, 1, legal)
        if call:
            level = parse_bid(call)[0]
            # The card asks for more to come in higher: 8+ at the one level,
            # 10+ at the two. Starting higher costs more when it goes wrong.
            need = OVERCALL_POINTS_1 if level == 1 else OVERCALL_POINTS_2
            if level <= 2 and pts >= need:
                return call, (
                    f"{OPEN_SUIT_LENGTH}+ {SUIT_SYM[best_suit]}, "
                    f"{need}+ points. Overcall.")
    # Say which condition actually blocked the overcall. Reporting "not enough
    # points" on a 15-point hand whose real problem is shape is worse than saying
    # nothing -- it teaches the reader something false about the system.
    # Say which condition blocked the overcall, without naming the actual hand.
    # No suit worth naming -- but a strong flat hand still has a call.
    if not _doubled_by(player, auction):
        double = _takeout_double(player, auction, groups, pts, legal)
        if double:
            return double
    if best_len < OPEN_SUIT_LENGTH:
        # "outside theirs" matters: `best_suit` is chosen from suits the
        # opponents have NOT bid, so a hand whose only long suit is their suit
        # reaches here. Without the qualifier the alert denies a suit the hand
        # is holding, which is the same falsehood as the response pass had.
        return 'Pass', "No five-card suit outside theirs to overcall."
    if pts < OVERCALL_POINTS_1:
        return 'Pass', f"Fewer than {OVERCALL_POINTS_1} points."
    return 'Pass', "Not enough to come in at this level."


def ai_bid(player: str, hand: list[Card], auction: AuctionState) -> str:
    """A 2/1-shaped auction: limited raises, a forcing new suit at the two level.

    The auction is a search for trump length -- a trump card is worth about a
    trick (TRUMP_CARD), more than three queens -- and partners each showing their
    longest suit finds the true best fit 94% of the time. The 2/1 skeleton lets partner's bid
    mean different things, so the combined estimate is read off the auction rather
    than assumed; the ceiling keeps that information from being spent on height.
    """
    return ai_bid_explained(player, hand, auction)[0]


# ── Card memory helpers ───────────────────────────────────────────────────────

def _unplayed_values(suit: str, played: list[Card]) -> list[int]:
    """Descending list of card values still in circulation for a suit."""
    gone = {c.value() for c in played if c.suit == suit}
    return [v for v in _ALL_VALUES if v not in gone]


def _gap(suit: str, hand: list[Card], played: list[Card]) -> int:
    """
    Cards strictly between my two highest in this suit that opponents could hold.
    A gap of 0 means no card can insert between my top and 2nd — safest lead.
    """
    mine = sorted([c.value() for c in hand if c.suit == suit], reverse=True)
    if len(mine) < 2:
        return 99   # singleton — avoid leading if possible
    top, second = mine[0], mine[1]
    unplayed_not_mine = [
        v for v in _unplayed_values(suit, played)
        if v not in {c.value() for c in hand if c.suit == suit}
    ]
    return sum(1 for v in unplayed_not_mine if second < v < top)


_FULL_DECK = [Card(s, r) for s in SUITS for r in RANKS]


def _later_holdings(player: str, hand: list[Card], trick: list[tuple[str, Card]],
                    played: list[Card], visible: dict[str, list[Card]],
                    out: dict[str, set[str]] | None = None) -> set[Card]:
    """Cards the *opponents* still to act in this trick might hold.

    Partner is skipped: these cards are used to judge how a trick could be taken
    away, and partner taking it is not a loss. When partner's hand is unseen its
    cards still sit in the unseen pool — nothing can separate them — but a
    visible partner (the dummy) is no longer counted as a threat.
    """
    i = PLAYERS.index(player)
    later = [PLAYERS[(i + k) % 4] for k in range(1, 4 - len(trick))]
    opponents = [p for p in later if p != PARTNERS[player]]
    pool: set[Card] = set()
    if any(p not in visible for p in opponents):
        seen = set(played) | {c for _, c in trick} | set(hand)
        for h in visible.values():
            seen |= set(h)
        pool = {c for c in _FULL_DECK if c not in seen}
    # An opponent who has shown out of a suit holds none of it: drop those
    # cards from what they might play (there is at most one opponent still to
    # act after the second or third hand).
    if out:
        for p in opponents:
            if p not in visible and out.get(p):
                pool = {c for c in pool if c.suit not in out[p]}
    for p in opponents:
        if p in visible:
            pool |= set(visible[p])
    return pool


def _winning_suit(cards: list[Card], trump: str | None) -> str:
    """The suit that decides the trick: trump if any was played, else the led suit."""
    if trump in SUITS and any(c.suit == trump for c in cards):
        return trump
    return cards[0].suit


def _outlook(player: str, card: Card, trick: list[tuple[str, Card]],
             trump: str | None, later: set[Card]) -> tuple[str, int]:
    """Who takes the trick if `player` plays `card` now, and how many of the cards
    still to come would pull it away from this partnership.

    Both halves ask resolve_trick rather than reasoning about ranks directly, so
    the lone-card rule, the trump-promotion case and the second-highest rule
    itself cannot drift out of step with the engine.
    """
    plays = trick + [(player, card)]
    holder = resolve_trick(plays, trump)
    suit = _winning_suit([c for _, c in plays], trump)
    ours = (player, PARTNERS[player])
    # Only the deciding suit is counted. A ruff takes the trick whichever card we
    # play, so it is a constant across our candidates: counting it would swamp the
    # differences we are actually choosing between and duck every trick away.
    exposed = sum(1 for c in later
                  if c.suit == suit
                  and resolve_trick(plays + [(_AI_TAG, c)], trump) not in ours)
    return holder, exposed


# ── Main Play Entry Point ────────────────────────────────────────────────────

def visible_hands(seat: str, contract: dict, hands: dict[str, list[Card]]) -> dict:
    """What `seat` sees besides its own cards, once dummy is down: dummy, and
    for the declaring side declarer's hand as well -- declarer plays both.

    Passing only dummy made the robot declarer play dummy blind to its OWN
    hand: on a user's board dummy overtook declarer's winning jack of hearts
    with the king, fearing a queen that declarer was holding.
    """
    dummy, declarer = contract['dummy'], contract['declarer']
    view = {dummy: hands[dummy]}
    if seat in (dummy, declarer):
        view[declarer] = hands[declarer]
    return view



def ai_play(player: str, hand: list[Card], trick: list[tuple[str, Card]],
            trump: str | None, played: list[Card],
            visible: dict[str, list[Card]] | None = None,
            history: list[list[tuple[str, Card]]] | None = None,
            shown: dict[str, dict[str, int]] | None = None) -> Card:
    """
    played:  all cards from completed previous tricks (card memory).
    visible: hands every seat can see, keyed by seat (dummy, once exposed).
    history: the completed tricks with their seats, which is what shows who
             has run out of a suit. Given it, the last tricks are searched.
    shown:   the fewest cards each seat's bidding showed in each suit
             (`shown_lengths`), so the play can use the auction.
    """
    led_suit = trick[0][1].suit if trick else None
    legal    = legal_plays(hand, led_suit)
    if NO_PEEK_OPENING_LEAD and not trick and not played:
        visible = {}                  # dummy goes down after the opening lead
    if not AUCTION_IN_PLAY:
        shown = None

    if not trick and not played and shown:
        choice = _partner_suit_lead(player, hand, trump, shown)
        if choice is not None:
            return choice
    if not trick:
        choice = ((_draw_trump(player, hand, trump, played, visible, history, shown)
                   if DRAW_TRUMPS else None)
                  or (_ruff_lead(player, hand, trump, played, visible)
                      if RUFF_LEAD else None)
                  or (_run_long_suit(player, hand, trump, played, visible, history, shown)
                      if RUN_LONG_SUIT else None)
                  or (_run_long_suit(player, hand, trump, played, visible, history, shown,
                                     max_losers=float('inf'))
                      if NT_SET_UP_SUIT and trump not in SUITS else None)
                  or (_sure_lead(player, hand, trump, played, visible, history)
                      if SURE_LEAD else None)
                  or (_nt_long_lead(player, hand, trump, played, visible)
                      if NT_LONG_LEAD else None))
        if choice is None:
            choice = _lead(hand, trump, played)
            if SURE_LEAD_DECLARER:
                choice = _sure_lead_declarer(player, hand, trump, played, visible, history,
                                             choice.suit) or choice
            if FORCE_DUMMY and choice.suit == trump:
                choice = _force_dummy(player, hand, trump, visible, played) or choice
    elif len(trick) == 3:
        choice = _play_last(legal, trick, trump, hand, played)
    else:
        out = (_shown_out(history, trick)
               if SHOWOUT_MIDDLE and history is not None else None)
        later = _later_holdings(player, hand, trick, played, visible or {}, out)
        choice = _middle_play(player, legal, trick, trump, later)

    partner = PARTNERS[player]
    if len(trick) == 1 and visible and partner in visible and len(legal) > 1:
        choice = _cover_for_partner(player, hand, legal, trick, trump, played,
                                    visible, choice)

    if (history is not None and visible and len(legal) > 1
            and len(hand) <= (DEEP_ENDGAME_CARDS if DEEP_ENDGAME else ENDGAME_CARDS)):
        totals = _endgame_totals(player, hand, trick, trump, played, visible,
                                 history, legal, shown)
        if totals:
            best = max(totals.values())
            tied = [c for c in legal if totals[c] == best]
            if choice not in tied:
                choice = min(tied, key=lambda c: c.value())
    return choice


# ── Second hand, partner last and in view ────────────────────────────────────
#
# `_middle_play` judges a card as if nobody after the next opponent mattered.
# With partner fourth and partner's hand VISIBLE (declarer and dummy see each
# other), that misses the play this game turns on: covering high so that
# partner's middle card becomes second-highest. On a user's 3NT North led the
# 8C, East held K64 with dummy's 9C to come; the king makes the nine win, and
# low lets the eight hold. Scored over the layouts declarer could see, low
# cost 1.5 tricks. So each card is scored by how many of the third player's
# possible cards still leave partner a winning reply -- partner's cards are
# known, the third player's are only the ones declarer cannot see.

def _cover_for_partner(player: str, hand: list[Card], legal: list[Card],
                       trick: list[tuple[str, Card]], trump: str | None, played: list[Card],
                       visible: dict[str, list[Card]], choice: Card) -> Card:
    partner = PARTNERS[player]
    third = PLAYERS[(PLAYERS.index(player) + 1) % 4]
    led = trick[0][1].suit
    if third in visible:
        candidates = list(visible[third])
    else:
        # The whole hand, not just the legal cards: following suit, this hand's
        # other suits are still its own, never the third player's ruff or discard.
        seen = set(played) | {c for _, c in trick} | set(hand)
        for cards in visible.values():
            seen |= set(cards)
        candidates = [c for c in _FULL_DECK if c not in seen]
    follows = [c for c in candidates if c.suit == led]
    # A follow if they can; otherwise one ruff (if trump is live) and one discard.
    options = follows[:]
    if not follows or third not in visible:
        if trump in SUITS and trump != led:
            ruffs = [c for c in candidates if c.suit == trump]
            if ruffs:
                options.append(min(ruffs, key=lambda c: c.value()))
        discards = [c for c in candidates if c.suit not in (led, trump)]
        if discards:
            options.append(min(discards, key=_card_order))
    if not options:
        return choice
    ours = (player, partner)

    def score(card: Card) -> int:
        wins = 0
        for opp in options:
            plays = trick + [(player, card), (third, opp)]
            if any(resolve_trick(plays + [(partner, reply)], trump) in ours
                   for reply in legal_plays(visible[partner], led)):
                wins += 1
        return wins

    scores = {c: score(c) for c in legal}
    best = max(scores.values())
    if scores[choice] >= best:
        return choice
    return min((c for c in legal if scores[c] == best), key=lambda c: c.value())


# ── Endgame: single dummy search ─────────────────────────────────────────────
#
# One trick of look-ahead cannot plan an ending. On a user's board East ruffed
# with the J♦ because every ruff lost that trick, and kept A♦ K♦ -- where
# keeping J♦ A♦ wins the next trick, since a middle card under partner's or an
# opponent's high one is what wins in this game. So once every hand is this
# short, the robot searches instead: every layout of the unseen cards that fits
# what it has SEEN (its own hand, dummy, cards played, and who has shown out of
# which suit) is solved exactly, and the card with the most tricks summed over
# those layouts is played. It never looks at the real layout -- that would be
# double dummy, which no player at the table can do. Layouts are enumerated in
# a fixed order, never sampled, so play stays deterministic.

#: Search the play once every hand holds at most this many cards.
ENDGAME_CARDS = 3


def _card_order(c: Card) -> tuple:
    return (SUITS.index(c.suit), c.value())


# ── What the auction told the play ───────────────────────────────────────────
#
# The play used to know nothing of the bidding: a robot led its own best suit
# with partner's overcalled suit beside it, and counted every layout as equally
# likely when the bidding had placed a long suit. Every number an alert quotes
# is true of the hand (machine-checked), so "5+ ♠" is a floor on that seat's
# spades: `shown_lengths` reads those floors off the auction's alerts.

#: The opening leader never sees dummy, which goes down after the lead
#: (measurement switch). Before, the leader was handed dummy's cards.
NO_PEEK_OPENING_LEAD = True
#: Second and third hand drop the suits an opponent has shown out of from
#: the cards that opponent might play (measurement switch).
SHOWOUT_MIDDLE = True
#: The play uses the lengths the auction showed: the opening lead in
#: partner's bid suit, and layouts that fit the bidding (measurement switch).
AUCTION_IN_PLAY = True
#: The shortest suit partner's bidding must show for the opening lead in it.
PARTNER_LEAD_MIN = 5

_SUIT_OF_SYM = {'\u2660': 'S', '\u2665': 'H', '\u2666': 'D', '\u2663': 'C'}
_SHOWN_RE = re.compile(r'(\d+)\+ ([\u2660\u2665\u2666\u2663](?: [\u2660\u2665\u2666\u2663])*)')
_EXACT_RE = re.compile(r'exactly (\d+) ([\u2660\u2665\u2666\u2663])')


def shown_lengths(calls: list, alerts: dict) -> dict[str, dict[str, int]]:
    """The fewest cards each seat's alerts promise in each suit.

    `calls` is the auction as (seat, call); `alerts` maps a call's index to
    its alert. Only alerts that are true of the hand belong here -- the
    robots'. "4+ ♥ ♠" is four of each; "exactly 3 ♥" is three."""
    shown: dict[str, dict[str, int]] = {p: {} for p in PLAYERS}
    for i, (seat, _) in enumerate(calls):
        text = alerts.get(i) or ''
        for n, syms in _SHOWN_RE.findall(text):
            for sym in syms.split():
                s = _SUIT_OF_SYM[sym]
                shown[seat][s] = max(shown[seat].get(s, 0), int(n))
        for n, sym in _EXACT_RE.findall(text):
            s = _SUIT_OF_SYM[sym]
            shown[seat][s] = max(shown[seat].get(s, 0), int(n))
    return shown


def _played_in(seat: str, suit: str, history: list, trick: list) -> int:
    """Cards of `suit` that `seat` has already played."""
    return sum(1 for plays in list(history) + [trick] for p, c in plays
               if p == seat and c.suit == suit)


def _fits_auction(seat: str, cards: list, history: list, trick: list,
                  shown: dict[str, dict[str, int]]) -> bool:
    """Could `seat` hold `cards` now and still have bid what it bid?"""
    for suit, n in shown.get(seat, {}).items():
        if sum(1 for c in cards if c.suit == suit) + _played_in(seat, suit, history, trick) < n:
            return False
    return True


def _partner_suit_lead(player: str, hand: list[Card], trump: str | None,
                       shown: dict[str, dict[str, int]]) -> Card | None:
    """The opening lead in the suit partner's bidding showed, or None.

    Partner's longest shown suit of PARTNER_LEAD_MIN or more, not trumps, and
    one I hold; led like any other suit (`_lead`'s second-highest card)."""
    partner = PARTNERS[player]
    suits = [s for s, n in shown.get(partner, {}).items()
             if n >= PARTNER_LEAD_MIN and s != trump and any(c.suit == s for c in hand)]
    if not suits:
        return None
    s = max(suits, key=lambda t: (shown[partner][t], SUITS.index(t)))
    cards = sorted((c for c in hand if c.suit == s), key=lambda c: c.value(), reverse=True)
    return cards[min(1, len(cards) - 1)]


def _shown_out(history: list, trick: list) -> dict[str, set[str]]:
    """Suits each seat has failed to follow, so cannot hold."""
    out: dict[str, set[str]] = {p: set() for p in PLAYERS}
    for plays in list(history) + [trick]:
        if not plays:
            continue
        led = plays[0][1].suit
        for seat, card in plays[1:]:
            if card.suit != led:
                out[seat].add(led)
    return out


def _search(hands: dict[str, list[Card]], trick: list[tuple[str, Card]],
            leader: str, trump: str | None, side: str, memo: dict) -> int:
    """Tricks `side` takes from here on, both sides perfect on THIS layout."""
    if len(trick) == 4:
        winner = resolve_trick(trick, trump)
        won = 1 if PARTNERSHIP[winner] == side else 0
        if not hands[winner]:
            return won
        return won + _search(hands, [], winner, trump, side, memo)
    key = None
    if not trick:
        key = (leader,) + tuple(tuple(sorted(_card_order(c) for c in hands[p]))
                                for p in PLAYERS)
        if key in memo:
            return memo[key]
    seat = PLAYERS[(PLAYERS.index(leader) + len(trick)) % 4]
    led = trick[0][1].suit if trick else None
    ours = PARTNERSHIP[seat] == side
    best = -1 if ours else 99
    for card in legal_plays(hands[seat], led):
        at = hands[seat].index(card)
        hands[seat].pop(at)
        value = _search(hands, trick + [(seat, card)], leader, trump, side, memo)
        hands[seat].insert(at, card)
        best = max(best, value) if ours else min(best, value)
    if key is not None:
        memo[key] = best
    return best


# ── Mid-hand: the endgame search, two tricks earlier ────────────────────────
#
# One trick of look-ahead loses most where the hand is decided (tricks 5-9
# cost 2.3 tricks a deal each side against double dummy, research/robot_lines).
# The last three tricks were searched over every layout of the unseen cards;
# `_fast_search` makes every layout affordable from four cards a hand. A
# sample of eight layouts was tried first and dropped: on deal 0 it chose the
# K♦ third in hand where the 6♦ takes three more tricks -- whether the king
# wins depends on one card of East's, and eight layouts misjudge that often.

#: Search every layout from DEEP_ENDGAME_CARDS a hand, not ENDGAME_CARDS
#: (measurement switch). Five, not four: +0.204 tricks a board seated
#: (docs/CHALLENGE.md), the user's call, 2026-10-22.
DEEP_ENDGAME = True
DEEP_ENDGAME_CARDS = 5


# ── The same search on bit patterns ─────────────────────────────────────────
#
# `_fast_search` holds hands as lists of Card and builds a sorted tuple for
# every position it remembers; that bookkeeping, not the search, was most of
# its time. Here a hand is one 52-bit number (bit 13 * suit + rank, suits in
# SUITS order, rank 0 = the 2), as in bridge/solver: legal moves, rank
# equivalence and position keys are integer operations. Same answers --
# `tests/test_play_information.py` checks it against `_search` -- so the same
# cards are played, faster.

_SUIT_BITS = [((1 << 13) - 1) << (13 * i) for i in range(4)]

#: One memory of searched positions for every search, every robot, every
#: board: a position's value in N/S tricks is the same whoever is looking and
#: whichever layout led there (measurement switch). One table per trump suit,
#: bounded, so it can't grow without end.
SHARED_POSITIONS = True
_POSITION_MEMO: dict = {}
_POSITION_MEMO_MAX = 600_000


def _position_memo(trump: int | None) -> dict:
    table = _POSITION_MEMO.setdefault(trump, {})
    if len(table) > _POSITION_MEMO_MAX:
        table.clear()
    return table
_NS_SEATS = (0, 2)                         # North, South in PLAYERS order


def _bit(c: Card) -> int:
    return 13 * SUITS.index(c.suit) + c.value()


def _bit_winner(trick: tuple, trump: int | None) -> int:
    """The seat winning a full trick of (seat, bit) plays: resolve_trick's
    rule on bit numbers (second-highest of the winning suit, or a lone card)."""
    suit = trick[0][1] // 13
    if trump is not None:
        for _, b in trick:
            if b // 13 == trump:
                suit = trump
                break
    top = second = -1
    top_seat = second_seat = -1
    for seat, b in trick:
        if b // 13 == suit:
            if b > top:
                second, second_seat = top, top_seat
                top, top_seat = b, seat
            elif b > second:
                second, second_seat = b, seat
    return second_seat if second >= 0 else top_seat


def _relative(hands: list) -> tuple:
    """The four hands with each suit's unplayed cards renumbered 0, 1, 2, ...
    from the lowest: a position's value depends only on how the cards still
    out rank against each other, so ♠QJ against ♠K is ♠98 against ♠10 once
    the cards between have gone. The memory's key, so those positions are
    solved once."""
    out = [0, 0, 0, 0]
    for shift in (0, 13, 26, 39):
        m0, m1, m2, m3 = ((h >> shift) & 0x1FFF for h in hands)
        left = m0 | m1 | m2 | m3
        bit = 1 << shift
        while left:
            low = left & -left
            left ^= low
            if m0 & low:
                out[0] |= bit
            elif m1 & low:
                out[1] |= bit
            elif m2 & low:
                out[2] |= bit
            else:
                out[3] |= bit
            bit <<= 1
    return tuple(out)


def _bit_search(hands: list, trick: tuple, leader: int, trump: int | None,
                ns: bool, memo: dict, alpha: int = -1, beta: int = 14) -> int:
    """Tricks for N/S (`ns`) or E/W from here, both sides perfect: `_fast_search`
    on bit patterns. `hands` is four 52-bit numbers in PLAYERS order."""
    if len(trick) == 4:
        winner = _bit_winner(trick, trump)
        won = 1 if (winner in _NS_SEATS) == ns else 0
        if not hands[winner]:
            return won
        return won + _bit_search(hands, (), winner, trump, ns, memo,
                                 alpha - won, beta - won)
    key = None
    if not trick:
        key = (leader,) + _relative(hands)
        lo, hi = memo.get(key, (0, 13))
        if lo >= beta or lo == hi:
            return lo                 # known exactly: never search an empty window
        if hi <= alpha:
            return hi
        if lo > alpha:
            alpha = lo
        if hi < beta:
            beta = hi
    a0, b0 = alpha, beta
    seat = (leader + len(trick)) % 4
    hand = hands[seat]
    legal = hand
    if trick:
        follow = hand & _SUIT_BITS[trick[0][1] // 13]
        if follow:
            legal = follow
    others = 0
    for p in range(4):
        if p != seat:
            others |= hands[p]
    for _, b in trick:
        others |= 1 << b
    ours = (seat in _NS_SEATS) == ns
    best = -1 if ours else 99
    for suit in range(4):
        mine = legal & _SUIT_BITS[suit]
        if not mine:
            continue
        rest = others & _SUIT_BITS[suit]
        previous = -1
        while mine:
            low = mine & -mine
            mine ^= low
            b = low.bit_length() - 1
            # One card from each run with no other unplayed card between.
            if previous >= 0 and not rest & (((1 << b) - 1) ^ ((1 << (previous + 1)) - 1)):
                previous = b
                continue
            previous = b
            hands[seat] = hand ^ low
            value = _bit_search(hands, trick + ((seat, b),), leader, trump, ns,
                                memo, alpha, beta)
            hands[seat] = hand
            if ours:
                if value > best:
                    best = value
                    if best > alpha:
                        alpha = best
            else:
                if value < best:
                    best = value
                    if best < beta:
                        beta = best
            if alpha >= beta:
                break
        if alpha >= beta:
            break
    if key is not None:
        lo, hi = memo.get(key, (0, 13))
        if best <= a0:
            hi = min(hi, best)
        elif best >= b0:
            lo = max(lo, best)
        else:
            lo = hi = best
        memo[key] = (lo, hi)
    return best


def _fast_search(hands: dict[str, list[Card]], trick: list[tuple[str, Card]],
                 leader: str, trump: str | None, side: str, memo: dict,
                 alpha: int = -1, beta: int = 14) -> int:
    """`_search`'s answer -- tricks `side` takes from here, both sides perfect
    on THIS layout -- found far faster: alpha-beta, with bounds kept per
    position, and rank equivalence (cards in one hand with no outstanding
    card of the suit between them play alike, so one is tried). `_search`
    took 1 s at five cards a hand and 12+ s at six; this makes searching
    from mid-hand affordable."""
    if len(trick) == 4:
        winner = resolve_trick(trick, trump)
        won = 1 if PARTNERSHIP[winner] == side else 0
        if not hands[winner]:
            return won
        return won + _fast_search(hands, [], winner, trump, side, memo,
                                  alpha - won, beta - won)
    key = None
    if not trick:
        key = (leader,) + tuple(tuple(sorted(_card_order(c) for c in hands[p]))
                                for p in PLAYERS)
        lo, hi = memo.get(key, (0, 13))
        if lo >= beta or lo == hi:
            return lo                 # known exactly: never search an empty window
        if hi <= alpha:
            return hi
        alpha, beta = max(alpha, lo), min(beta, hi)
    a0, b0 = alpha, beta
    seat = PLAYERS[(PLAYERS.index(leader) + len(trick)) % 4]
    led = trick[0][1].suit if trick else None
    legal = legal_plays(hands[seat], led)
    tried = []
    for suit in SUITS:
        mine = [c for c in legal if c.suit == suit]
        if not mine:
            continue
        others = tuple(c.value() for p in PLAYERS if p != seat
                       for c in hands[p] if c.suit == suit) \
            + tuple(c.value() for _, c in trick if c.suit == suit)
        values = _distinct(tuple(c.value() for c in mine), others)
        tried += [c for c in mine if c.value() in values]
    ours = PARTNERSHIP[seat] == side
    best = -1 if ours else 99
    for card in tried:
        at = hands[seat].index(card)
        hands[seat].pop(at)
        value = _fast_search(hands, trick + [(seat, card)], leader, trump, side,
                             memo, alpha, beta)
        hands[seat].insert(at, card)
        if ours:
            best = max(best, value)
            alpha = max(alpha, best)
        else:
            best = min(best, value)
            beta = min(beta, best)
        if alpha >= beta:
            break
    if key is not None:
        lo, hi = memo.get(key, (0, 13))
        if best <= a0:
            hi = min(hi, best)
        elif best >= b0:
            lo = max(lo, best)
        else:
            lo = hi = best
        memo[key] = (lo, hi)
    return best


def _endgame_totals(player: str, hand: list[Card], trick: list[tuple[str, Card]],
                    trump: str | None, played: list[Card],
                    visible: dict[str, list[Card]], history: list,
                    legal: list[Card],
                    shown: dict[str, dict[str, int]] | None = None) -> dict | None:
    """Tricks for each legal card, summed over every layout that fits."""
    known = {player: list(hand)}
    seen = set(played) | {c for _, c in trick} | set(hand)
    for seat, cards in visible.items():
        if seat != player:
            known[seat] = list(cards)
            seen |= set(cards)
    hidden = [p for p in PLAYERS if p not in known]
    already = {seat for seat, _ in trick}
    size = {p: len(hand) - (1 if p in already else 0) for p in PLAYERS}
    unseen = sorted((c for c in _FULL_DECK if c not in seen), key=_card_order)
    if len(hidden) != 2 or len(unseen) != size[hidden[0]] + size[hidden[1]]:
        return None
    first, second = hidden
    out = _shown_out(history, trick)
    leader = trick[0][0] if trick else player
    side = PARTNERSHIP[player]
    totals = {c: 0 for c in legal}
    layouts = 0
    for picked in combinations(range(len(unseen)), size[first]):
        chosen = set(picked)
        a = [unseen[i] for i in range(len(unseen)) if i in chosen]
        b = [unseen[i] for i in range(len(unseen)) if i not in chosen]
        if any(c.suit in out[first] for c in a) or any(c.suit in out[second] for c in b):
            continue
        if shown and not (_fits_auction(first, a, history, trick, shown)
                          and _fits_auction(second, b, history, trick, shown)):
            continue
        layouts += 1
        held = {seat: list(cards) for seat, cards in known.items()}
        held[first], held[second] = a, b
        masks = [sum(1 << _bit(c) for c in held[p]) for p in PLAYERS]
        bits_trick = tuple((PLAYERS.index(p), _bit(c)) for p, c in trick)
        trump_bit = SUITS.index(trump) if trump in SUITS else None
        memo = _position_memo(trump_bit) if SHARED_POSITIONS else {}
        me = PLAYERS.index(player)
        left = (sum(bin(m).count('1') for m in masks) + len(trick)) // 4
        for card in legal:
            masks[me] ^= 1 << _bit(card)
            ns = _bit_search(masks, bits_trick + ((me, _bit(card)),),
                             PLAYERS.index(leader), trump_bit, True, memo)
            totals[card] += ns if side == 'N/S' else left - ns
            masks[me] ^= 1 << _bit(card)
    return totals if layouts else None


# ── Lead ──────────────────────────────────────────────────────────────────────

# ── Declarer draws trumps ────────────────────────────────────────────────────
#
# `_lead` is the same rule for every seat, and it ranks trumps last. So the
# declaring side kept leading side suits while the defence still held trumps
# for ruffing them: on deal 6, 4C by South with ten trumps (Q1075 opposite
# AJ9643), South led the K♠ at trick 4 where J♣ to the Q♣ draws trumps. Over
# the first 100 challenge deals, with the defence still holding trumps, the
# declaring side led one only 38% of the time, and a costly side-suit lead
# where a trump was best came up 66 times on 51 deals (double dummy, from
# research/robot_lines.jsonl).
#
# A trump lead's outcome depends only on where the trumps are: anyone out of
# trumps discards, and a discard never wins a trick in trumps. So declarer can
# play the trump suit out on its own, for every split of the trumps it can't
# see that fits who has shown out, and lead the trump that loses the fewest
# trump tricks on average (worst case, then the lower card, to break ties).
# Drawing trumps at a cost is still drawing them: the trumps it loses are
# trumps the defence can't ruff side-suit winners with.

#: Declaring side draws trumps when on lead (measurement switch).
DRAW_TRUMPS = True


def _distinct(cards: tuple, others: tuple) -> list:
    """One card from each run of `cards` with none of `others` in between.

    Such cards are interchangeable: every other card in the suit, including
    those already on the table this trick, ranks the same against each. So
    only one needs trying, as in the solver's rank equivalence.
    """
    keep = []
    previous = None
    for card in sorted(cards):
        if previous is None or any(previous < v < card for v in others):
            keep.append(card)
        previous = card
    return keep


def _options(cards: tuple, others: tuple) -> list:
    """A seat's distinct cards in the suit, or a discard when it has none."""
    return _distinct(cards, others) if cards else [None]


# `_trump_losers` keys a position by its cards' order alone, so an answer holds
# in every game: one memory serves every call instead of a fresh one each time
# (the same answers, far fewer searches). Bounded, so it can't grow without end.
_TRUMP_MEMO: dict = {}
_TRUMP_MEMO_MAX = 400_000


def _trump_memo() -> dict:
    if len(_TRUMP_MEMO) > _TRUMP_MEMO_MAX:
        _TRUMP_MEMO.clear()
    return _TRUMP_MEMO


def _trump_losers(ours: tuple, theirs: tuple, leader: int, memo: dict) -> int:
    """Trump tricks the defence wins before running out, trumps led throughout.

    `ours` is (leading hand, partner) and `theirs` is (left, right): each a
    sorted tuple of trump values, seats in play order leader, left, partner,
    right. The declaring side picks its cards and the defence picks its own,
    each knowing the layout; after the defence wins a trick, the declaring side
    leads trumps again from whichever of its hands does better.
    """
    if not theirs[0] and not theirs[1]:
        return 0
    if not ours[0] and not ours[1]:
        return len(theirs[0]) + len(theirs[1])
    # Only the cards' order matters, so positions are stored by order: the
    # same shape with different spot cards is one entry.
    order = {v: i for i, v in enumerate(sorted(ours[0] + ours[1] + theirs[0] + theirs[1]))}
    key = (tuple(order[v] for v in ours[0]), tuple(order[v] for v in ours[1]),
           tuple(order[v] for v in theirs[0]), tuple(order[v] for v in theirs[1]), leader)
    if key in memo:
        return memo[key]
    lead_hand, partner = (ours[0], ours[1]) if leader == 0 else (ours[1], ours[0])
    left, right = (theirs[0], theirs[1]) if leader == 0 else (theirs[1], theirs[0])
    if not lead_hand:
        result = _trump_losers(ours, theirs, 1 - leader, memo)
        memo[key] = result
        return result

    def drop(cards: tuple, card) -> tuple:
        return tuple(c for c in cards if c != card) if card is not None else cards

    best = None
    for a in _distinct(lead_hand, partner + left + right):
        worst = None
        for b in _options(left, lead_hand + partner + right):
            ours_best = None
            for c in _options(partner, lead_hand + left + right):
                defence_best = None
                for d in _options(right, lead_hand + partner + left):
                    played = [(0, a), (1, b), (2, c), (3, d)]
                    trumps = sorted((v, who) for who, v in played if v is not None)
                    winner = trumps[0][1] if len(trumps) == 1 else trumps[-2][1]
                    new_lead = drop(lead_hand, a)
                    new_partner = drop(partner, c)
                    new_left, new_right = drop(left, b), drop(right, d)
                    if leader == 0:
                        new_ours, new_theirs = (new_lead, new_partner), (new_left, new_right)
                    else:
                        new_ours, new_theirs = (new_partner, new_lead), (new_right, new_left)
                    if winner in (0, 2):
                        nxt = leader if winner == 0 else 1 - leader
                        value = _trump_losers(new_ours, new_theirs, nxt, memo)
                    else:
                        value = 1 + min(_trump_losers(new_ours, new_theirs, h, memo)
                                        for h in (0, 1) if new_ours[h]) \
                            if (new_ours[0] or new_ours[1]) else \
                            1 + len(new_theirs[0]) + len(new_theirs[1])
                    if defence_best is None or value > defence_best:
                        defence_best = value
                if ours_best is None or defence_best < ours_best:
                    ours_best = defence_best
            if worst is None or ours_best > worst:
                worst = ours_best
        if best is None or worst < best:
            best = worst
    memo[key] = best
    return best


def _draw_trump(player: str, hand: list[Card], trump: str | None,
                played: list[Card], visible: dict[str, list[Card]] | None,
                history: list | None,
                shown: dict[str, dict[str, int]] | None = None) -> Card | None:
    """The trump the declaring side should lead to draw trumps, or None.

    Only for a hand whose partner it can see (declarer and dummy see each
    other; a defender sees only dummy, an opponent). Leads a trump when the
    defence may still hold trumps and the declaring side holds more.
    """
    partner = PARTNERS[player]
    if trump not in SUITS or not visible or partner not in visible:
        return None
    mine = sorted(c.value() for c in hand if c.suit == trump)
    theirs_partner = sorted(c.value() for c in visible[partner] if c.suit == trump)
    if not mine:
        return None
    seen = set(played) | set(hand) | set(visible[partner])
    outstanding = [c.value() for c in _FULL_DECK if c.suit == trump and c not in seen]
    if not outstanding or len(mine) + len(theirs_partner) <= len(outstanding):
        return None

    ruff = _ruff_first(hand, visible[partner], trump, len(outstanding))
    if ruff is not None:
        return ruff if ruff is not _NO_DRAW else None

    layouts = _splits(player, hand, trump, outstanding, seen, history, shown)
    if not layouts:
        return None

    scored = []
    memo = _trump_memo()
    for card in sorted((c for c in hand if c.suit == trump), key=lambda c: c.value()):
        total = 0
        worst = 0
        weights = 0
        for left_trumps, right_trumps, weight in layouts:
            # This card is led; the rest of the trick is played by the search.
            losers = _after_lead(card.value(), tuple(v for v in mine if v != card.value()),
                                 tuple(theirs_partner), left_trumps, right_trumps, memo)
            total += losers * weight
            weights += weight
            worst = max(worst, losers)
        scored.append((total / weights, worst, card.value(), card))
    return min(scored, key=lambda t: t[:3])[3]


def _splits(player: str, hand: list[Card], suit: str, outstanding: list[int],
            seen: set, history: list | None,
            shown: dict[str, dict[str, int]] | None = None) -> list:
    """Every way the defence's cards in `suit` can lie, as (left, right, weight).

    Rules out a split that gives cards to a defender who has shown out, and
    weights each by how many ways the rest of the unseen cards fill the left
    hand, so a 2-2 split counts for more than 4-0, as in bridge odds.
    """
    left, right = PLAYERS[(PLAYERS.index(player) + 1) % 4], PLAYERS[(PLAYERS.index(player) + 3) % 4]
    out = _shown_out(history or [], [])
    gone = {p: _played_in(p, suit, history or [], []) for p in PLAYERS}
    unseen = sum(1 for c in _FULL_DECK if c not in seen)
    slots = len(hand)                     # every hand holds this many at a lead
    others = unseen - len(outstanding)
    layouts = []
    for n in range(len(outstanding) + 1):
        for picked in combinations(sorted(outstanding), n):
            left_cards = tuple(picked)
            right_cards = tuple(v for v in sorted(outstanding) if v not in picked)
            if (left_cards and suit in out[left]) or (right_cards and suit in out[right]):
                continue
            if len(left_cards) > slots or len(right_cards) > slots:
                continue
            if shown and (len(left_cards) + gone[left] < shown.get(left, {}).get(suit, 0)
                          or len(right_cards) + gone[right] < shown.get(right, {}).get(suit, 0)):
                continue                  # fewer than their bidding showed
            weight = _choose(others, slots - len(left_cards))
            if weight:
                layouts.append((left_cards, right_cards, weight))
    return layouts


# ── Declarer runs a long suit ────────────────────────────────────────────────
#
# The same blindness to partner's hand: on deal 96, 3NT by South, declarer
# won the opening heart and cashed the K♥ from AK9 opposite J74, setting up
# the defence's hearts (double dummy, six tricks became two), with clubs
# AJ1084 opposite KQ63 against 9752: five tricks off the top. `_gap` saw
# clubs as full of holes because the K and Q weren't in South's own hand.
#
# A suit led in notrump, or once the defence has no trumps, is a self-
# contained puzzle like the trump suit: the defence must follow, and a discard
# can't win. So for each suit where the partnership holds seven or more,
# declarer works out the expected losers of its best lead over every
# split of the defence's cards, weighted by how likely each split is, and runs
# the suit with the most expected tricks among those expected to lose less
# than half a trick. Not "no loss on any split": under these rules a defender
# holding all the outstanding cards behind dummy can almost always slip one
# between declarer's two, so even AKQJ10 8643 opposite 9752 loses to 4-0.

#: Declaring side runs a long suit that usually can't lose (measurement switch).
RUN_LONG_SUIT = True
#: In notrump, when no long suit runs that cheaply, the declaring side sets
#: one up anyway: the suit with the most tricks after its expected losers,
#: led with the card `_run_long_suit` scores best (measurement switch). Deal
#: 43, 3NT by West: dummy led the K♠ from AK9 where the Q♣ from Q65, opposite
#: K10982, keeps the contract to one down instead of two (double dummy).
NT_SET_UP_SUIT = False
#: The most expected losers a suit may have and still be run.
RUN_MAX_LOSERS = 0.5


def _run_long_suit(player: str, hand: list[Card], trump: str | None,
                   played: list[Card], visible: dict[str, list[Card]] | None,
                   history: list | None,
                   shown: dict[str, dict[str, int]] | None = None,
                   max_losers: float | None = None) -> Card | None:
    """A lead that runs the partnership's long suit without loss, or None.

    With `max_losers` raised, a suit that must lose tricks first: setting it up."""
    partner = PARTNERS[player]
    if not visible or partner not in visible:
        return None
    seen = set(played) | set(hand) | set(visible[partner])
    if trump in SUITS and any(c.suit == trump and c not in seen for c in _FULL_DECK):
        return None                       # the defence can still ruff
    best = None
    for suit in SUITS:
        if suit == trump:
            continue
        mine = sorted(c.value() for c in hand if c.suit == suit)
        theirs_partner = sorted(c.value() for c in visible[partner] if c.suit == suit)
        if not mine:
            continue
        outstanding = [c.value() for c in _FULL_DECK if c.suit == suit and c not in seen]
        # A long suit for the partnership (seven or more, so the defence holds
        # six at most and the search stays small), or one the defence is out
        # of, where every card left is a winner: keep running it.
        if outstanding and len(mine) + len(theirs_partner) < 7:
            continue
        tricks = max(len(mine), len(theirs_partner))
        cards = sorted((c for c in hand if c.suit == suit), key=lambda c: c.value())
        if outstanding:
            layouts = _splits(player, hand, suit, outstanding, seen, history, shown)
            if not layouts:
                continue
            memo = _trump_memo()
            scored = []
            for card in cards:
                total = weights = worst = 0
                for left_cards, right_cards, weight in layouts:
                    losers = _after_lead(card.value(), tuple(v for v in mine if v != card.value()),
                                         tuple(theirs_partner), left_cards, right_cards, memo)
                    total += losers * weight
                    weights += weight
                    worst = max(worst, losers)
                # Ties go to the HIGHEST card: cashing from the top needs the
                # least precision from partner's follow, which is played by
                # the ordinary rules, not by this search.
                scored.append((total / weights, worst, -card.value(), card))
            expected, _, _, lead = min(scored, key=lambda t: t[:3])
        else:
            expected, lead = 0.0, cards[-1]
        if expected > (RUN_MAX_LOSERS if max_losers is None else max_losers):
            continue
        rank = (tricks - expected, -SUITS.index(suit))
        if best is None or rank > best[0]:
            best = (rank, lead)
    return best[1] if best else None


# ── Defender cashes a sure trick ─────────────────────────────────────────────
#
# `_lead` never asks whether a card wins, and it never looks at dummy. On deal
# 92, 1NT by North, East won the J♦ at trick 2 holding K765 of clubs with dummy's
# J1032 in view and the 8♣ 9♣ 4♣ gone: the A♣ was the only club East couldn't
# see, so whoever held it had to play it under the K♣, which wins. East led the
# 7♣, dummy's J♣ took it, and the king never made a trick (double dummy, four
# tricks given away). `_gap` had counted dummy's J♣ 10♣ as cards an opponent
# might hold between the K and the 7.
#
# So a defender on lead tries each card against every split of the unseen cards
# of its suit between partner and declarer (ruling out a seat that has shown
# out), and every legal play from there: dummy's from its known cards, a hidden
# seat's from the cards the split gives it, or, void, any unseen trump or a
# discard. A card that wins the trick every time is a sure trick, and the lowest
# one is led. Partner's play is counted against us too: a trick that needs
# partner to find the right card isn't sure.

#: A defender on lead cashes a sure trick (measurement switch).
SURE_LEAD = True


def _sure_lead(player: str, hand: list[Card], trump: str | None,
               played: list[Card], visible: dict[str, list[Card]] | None,
               history: list | None) -> Card | None:
    """The lowest card that wins the trick on every layout, or None.

    Only for a defender: one that sees dummy but not partner.
    """
    partner = PARTNERS[player]
    if not visible or partner in visible or player in visible:
        return None
    dummy = next(iter(visible))
    seen = set(played) | set(hand) | set(visible[dummy])
    unseen = [c for c in _FULL_DECK if c not in seen]
    out = _shown_out(history or [], [])
    hidden = [p for p in PLAYERS if p not in (player, dummy)]
    order = [PLAYERS[(PLAYERS.index(player) + k) % 4] for k in (1, 2, 3)]
    ours = (player, partner)
    slots = len(hand)                     # every hand holds this many at a lead
    ruffing = trump if trump in SUITS else None

    for card in sorted(hand, key=lambda c: (c.value(), SUITS.index(c.suit))):
        led = card.suit
        follows = [c for c in unseen if c.suit == led]
        trumps = ([c for c in unseen if c.suit == ruffing]
                  if ruffing and ruffing != led else [])
        # A discard never wins: any card of a suit neither led nor trump.
        discard = Card(next(s for s in SUITS if s not in (led, ruffing)), '2')

        def loses(at: int, plays: list, options: dict, used: set) -> bool:
            if at == 3:
                return resolve_trick(plays, trump) not in ours
            seat = order[at]
            for c in options[seat]:
                if c in used:
                    continue
                # Both hidden seats may be void: they can't ruff with the same trump.
                if loses(at + 1, plays + [(seat, c)], options,
                         used | {c} if c in trumps else used):
                    return True
            return False

        sure = True
        for n in range(len(follows) + 1):
            for picked in combinations(range(len(follows)), n):
                held = {hidden[0]: [follows[i] for i in picked],
                        hidden[1]: [c for i, c in enumerate(follows) if i not in picked]}
                if any(held[p] and led in out[p] for p in hidden):
                    continue
                if any(len(held[p]) > slots for p in hidden):
                    continue
                options = {dummy: legal_plays(visible[dummy], led)}
                for p in hidden:
                    if held[p]:
                        options[p] = held[p]
                    else:
                        options[p] = [discard] + (trumps if ruffing not in out[p] else [])
                if loses(0, [(player, card)], options, set()):
                    sure = False
                    break
            if not sure:
                break
        if sure:
            return card
    return None


# ── Four rules from the user's review of deals 92, 156 and 174 ───────────────
#
# A card is DEAD when every higher card of its suit is played or in its own
# hand: it can then never be second-highest, so it wins a trick only as the
# one card of the winning suit. An ace is always dead.
#
# Deal 174, 4H by East, the defence out of trumps after trick 4: East led
# trumps three times (`_lead` ranks a suit by its gap, and 8-7-6-5 has none),
# each won with dummy's 9H, QH, KH, and the ruffs that make eleven tricks were
# gone. The declaring side never asked for a sure trick either: 9C to dummy's
# 10C wins whatever the defence does; East's 2C lost to North's 8C.
#
# Deal 92, 3C by North: East held 765 of trumps with dummy's J103 in view and
# dummy void in hearts. East led the 6C and dummy underplayed the 3C (of two
# trumps the lower wins). AH or 10H forces dummy to ruff (double dummy, down
# two instead of making).
#
# Deal 156, 1H by North: on 10C 3C 9C, North could not win the trick and
# dumped the 5C. Its AC and KC could never win a trick (the K needs a higher
# club from someone else, and the only one is North's own ace), while the 5C
# and 8C could still win under the defence's QC or JC.

#: The declaring side, in the side suit its lead rules chose, leads the lowest
#: card that wins the trick for sure, partner's card chosen by partner's own
#: rules (measurement switch).
SURE_LEAD_DECLARER = True
#: The declaring side, with the defence out of trumps, leads a suit its visible
#: partner is void in and can ruff (measurement switch).
RUFF_LEAD = False
#: A defender who would lead a trump forces dummy instead, in a suit dummy is
#: void in while it still has trumps (measurement switch).
FORCE_DUMMY = False
#: Fourth hand that can't keep the trick for its side follows with a dead card
#: (measurement switch).
DEAD_CARD_LAST = True


def _dead(card: Card, hand: list[Card], gone: set[Card]) -> bool:
    """No other seat can play a higher card of this suit: every one is gone or ours."""
    mine = set(hand)
    return all(c in gone or c in mine for c in _FULL_DECK
               if c.suit == card.suit and c.value() > card.value())


def _shed_first(cards: list[Card], hand: list[Card], played: list[Card]) -> Card:
    """The card of a suit to give up first: the lowest dead card, else the lowest."""
    gone = set(played)
    dead = [c for c in cards if _dead(c, hand, gone)]
    return min(dead or cards, key=lambda c: c.value())


def _ruff_lead(player: str, hand: list[Card], trump: str | None,
               played: list[Card], visible: dict[str, list[Card]] | None) -> Card | None:
    """A lead for partner to ruff, once the defence has no trumps, or None.

    Partner's lone trump in a trick wins it outright, so each ruff is a trick,
    where leading trumps makes our two hands' trumps fall together. The suit
    with a dead card goes first (that card wins nothing otherwise), then the
    longest.
    """
    partner = PARTNERS[player]
    if trump not in SUITS or not visible or partner not in visible:
        return None
    seen = set(played) | set(hand) | set(visible[partner])
    if any(c.suit == trump and c not in seen for c in _FULL_DECK):
        return None                       # the defence may still hold trumps
    if not any(c.suit == trump for c in visible[partner]):
        return None
    gone = set(played)
    best = None
    for suit in SUITS:
        if suit == trump or any(c.suit == suit for c in visible[partner]):
            continue
        cards = [c for c in hand if c.suit == suit]
        if not cards:
            continue
        has_dead = any(_dead(c, hand, gone) for c in cards)
        rank = (has_dead, len(cards), -SUITS.index(suit))
        if best is None or rank > best[0]:
            best = (rank, _shed_first(cards, hand, played))
    return best[1] if best else None


def _sure_lead_declarer(player: str, hand: list[Card], trump: str | None,
                        played: list[Card], visible: dict[str, list[Card]] | None,
                        history: list | None, suit: str) -> Card | None:
    """The lowest card of `suit` that wins the trick on every layout, or None.

    Card choice within a suit the other rules already chose, never the choice
    of suit: cashing a sure trick in a suit nobody chose cost timing (deal 0,
    1NT by North, the Q♥ cashed early, a trick lost later) and ruffed in the
    long trump hand (deal 4). Measured on ten deals, choosing the suit this way
    cost the declaring side 0.18 tricks a board.

    For the declaring side, which sees partner. `_sure_lead` treats partner's
    card as the enemy's because a defender can't see it; here partner's hand is
    in view, so partner's card is the one partner's own rules would play after
    the left-hand opponent's card, and each opponent's play is every card the
    split allows it (a void one ruffs with any unseen trump, or discards).
    """
    partner = PARTNERS[player]
    if not visible or partner not in visible:
        return None
    partner_hand = visible[partner]
    seen = set(played) | set(hand) | set(partner_hand)
    unseen = [c for c in _FULL_DECK if c not in seen]
    out = _shown_out(history or [], [])
    i = PLAYERS.index(player)
    left, right = PLAYERS[(i + 1) % 4], PLAYERS[(i + 3) % 4]
    ours = (player, partner)
    slots = len(hand)                     # every hand holds this many at a lead
    ruffing = trump if trump in SUITS else None

    for card in sorted((c for c in hand if c.suit == suit), key=lambda c: c.value()):
        led = card.suit
        # Trumps are `_draw_trump`'s. A "sure" trump trick with the defence
        # out of trumps spends two of ours on one trick: on deal 6, 4C by
        # South, the J♣ led to dummy's Q♣ cost four tricks over the hand.
        if led == ruffing:
            continue
        follows = [c for c in unseen if c.suit == led]
        trumps = ([c for c in unseen if c.suit == ruffing]
                  if ruffing and ruffing != led else [])
        # A discard never wins; any unseen card of another side suit stands for all.
        spare = [c for c in unseen if c.suit not in (led, ruffing)]
        discard = spare[:1]
        rest = [c for c in hand if c != card]
        partner_view = {player: rest, partner: partner_hand}
        replies: dict = {}

        def partner_card(b: Card) -> Card:
            if b not in replies:
                trick = [(player, card), (left, b)]
                legal = legal_plays(partner_hand, led)
                later = _later_holdings(partner, partner_hand, trick, played, partner_view)
                replies[b] = _middle_play(partner, legal, trick, trump, later)
            return replies[b]

        sure = True
        for n in range(len(follows) + 1):
            for picked in combinations(range(len(follows)), n):
                held = {left: [follows[k] for k in picked],
                        right: [c for k, c in enumerate(follows) if k not in picked]}
                if any(held[p] and led in out[p] for p in (left, right)):
                    continue
                if any(len(held[p]) > slots for p in (left, right)):
                    continue
                options = {}
                for p in (left, right):
                    options[p] = held[p] or (discard + (trumps if ruffing not in out[p] else []))
                for b in options[left]:
                    c = partner_card(b)
                    for d in options[right]:
                        if d == b and d in trumps:
                            continue      # both hidden seats can't ruff with the same trump
                        plays = [(player, card), (left, b), (partner, c), (right, d)]
                        if resolve_trick(plays, trump) not in ours:
                            sure = False
                            break
                    if not sure:
                        break
                if not sure:
                    break
            if not sure:
                break
        if sure:
            return card
    return None


def _force_dummy(player: str, hand: list[Card], trump: str | None,
                 visible: dict[str, list[Card]] | None, played: list[Card]) -> Card | None:
    """A defender's lead in a suit dummy is void in while dummy has trumps, or None.

    Only asked when the ordinary lead would be a trump: leading trumps into
    dummy's lets dummy underplay, while a forced ruff spends a dummy trump.
    """
    if trump not in SUITS or not visible or PARTNERS[player] in visible:
        return None
    dummy = next(iter(visible))
    if not any(c.suit == trump for c in visible[dummy]):
        return None
    best = None
    for suit in SUITS:
        if suit == trump or any(c.suit == suit for c in visible[dummy]):
            continue
        cards = [c for c in hand if c.suit == suit]
        if not cards:
            continue
        rank = (len(cards), -SUITS.index(suit))
        if best is None or rank > best[0]:
            best = (rank, _shed_first(cards, hand, played))
    return best[1] if best else None


def _after_lead(led: int, rest: tuple, partner: tuple, left: tuple, right: tuple,
                memo: dict) -> int:
    """Trump losers once `led` is on the table: the other three seats play,
    then the trump suit is played out by `_trump_losers`."""
    lead_hand = rest + (led,)
    worst = None
    for b in _options(left, lead_hand + partner + right):
        ours_best = None
        for c in _options(partner, lead_hand + left + right):
            defence_best = None
            for d in _options(right, lead_hand + partner + left):
                played = [(0, led), (1, b), (2, c), (3, d)]
                trumps = sorted((v, who) for who, v in played if v is not None)
                winner = trumps[0][1] if len(trumps) == 1 else trumps[-2][1]
                new_ours = (rest, tuple(x for x in partner if x != c))
                new_theirs = (tuple(x for x in left if x != b), tuple(x for x in right if x != d))
                if winner in (0, 2):
                    value = _trump_losers(new_ours, new_theirs, 0 if winner == 0 else 1, memo)
                elif new_ours[0] or new_ours[1]:
                    value = 1 + min(_trump_losers(new_ours, new_theirs, h, memo)
                                    for h in (0, 1) if new_ours[h])
                else:
                    value = 1 + len(new_theirs[0]) + len(new_theirs[1])
                if defence_best is None or value > defence_best:
                    defence_best = value
            if ours_best is None or defence_best < ours_best:
                ours_best = defence_best
        if worst is None or ours_best > worst:
            worst = ours_best
    return worst


#: `_ruff_first`'s answer when ruffs come first but this hand can't start one.
_NO_DRAW = object()


def _ruff_first(hand: list[Card], partner_hand: list[Card], trump: str,
                outstanding: int):
    """Ruffs in the short-trump hand that drawing trumps would throw away.

    The one reason to delay drawing trumps: the hand with fewer trumps (usually
    dummy) is needed to ruff the long hand's extra cards in a suit where it
    holds at most one. Each card the long hand holds past the short hand's
    length there is a ruff. Drawing takes at least half the outstanding trumps
    in rounds, each costing the short hand a trump; if what it would have left
    can't take the ruffs, ruff first.

    Returns None to draw trumps as usual; otherwise the card to lead (the long
    hand's lowest card in the suit the short hand lacks), or `_NO_DRAW` when
    this hand is the short one and can't start a ruff itself.
    """
    mine = [c for c in hand if c.suit == trump]
    theirs = [c for c in partner_hand if c.suit == trump]
    if len(mine) == len(theirs):
        return None
    long_hand, short_hand = (hand, partner_hand) if len(mine) > len(theirs) else (partner_hand, hand)
    short_trumps = min(len(mine), len(theirs))
    ruffs = 0
    target = None
    for suit in SUITS:
        if suit == trump:
            continue
        long_cards = [c for c in long_hand if c.suit == suit]
        short_count = sum(1 for c in short_hand if c.suit == suit)
        if short_count <= 1 and len(long_cards) > short_count:
            ruffs += len(long_cards) - short_count
            # The suit the short hand is shortest in, then the longest in the long hand.
            rank = (short_count, -len(long_cards), SUITS.index(suit))
            if target is None or rank < target[0]:
                target = (rank, min(long_cards, key=lambda c: c.value()))
    rounds = (outstanding + 1) // 2
    if not ruffs or short_trumps - rounds >= ruffs:
        return None
    return target[1] if long_hand is hand else _NO_DRAW


def _choose(n: int, k: int) -> int:
    if k < 0 or k > n:
        return 0
    result = 1
    for i in range(k):
        result = result * (n - i) // (i + 1)
    return result


# ── Defenders lead long suits in notrump ─────────────────────────────────────
#
# `_lead` picks the suit with the smallest gap between its top two cards, and
# length only breaks ties, so in notrump a defender with a five-card suit would
# lead a short, tidy one instead. The user's observation: in notrump the
# defence should set up its long suit, as in ordinary bridge -- but leading
# low gives the trick away in this game, so lead the second-highest card.

#: Defenders in notrump lead their longest suit of 4+ cards (measurement switch).
NT_LONG_LEAD = True
#: ...on the opening lead only, rather than every defender lead.
NT_LONG_LEAD_OPENING_ONLY = False


def _nt_long_lead(player: str, hand: list[Card], trump: str | None,
                  played: list[Card], visible: dict[str, list[Card]] | None) -> Card | None:
    """A defender's lead from its longest suit in notrump, or None."""
    if trump in SUITS or (visible and PARTNERS[player] in visible):
        return None
    if NT_LONG_LEAD_OPENING_ONLY and played:
        return None
    groups: dict[str, list[Card]] = {}
    for c in hand:
        groups.setdefault(c.suit, []).append(c)
    longest = max(len(cards) for cards in groups.values())
    if longest < 4:
        return None
    tied = [s for s in groups if len(groups[s]) == longest]
    best = max(tied, key=lambda s: (-_gap(s, hand, played), SUITS.index(s)))
    cards = sorted(groups[best], key=lambda c: c.value(), reverse=True)
    return cards[1]


#: `_lead` passes over a suit whose lead would be a dead card while another
#: suit's would be live (measurement switch). Deal 43, 3NT by West: West led
#: the K♥ from A-K-Q-3 and North's 9♥ won it. Every heart above the king was
#: West's own, so no one could play one and make the king second-highest;
#: `_gap` scored A-K the best holding of all, nothing between the top two.
LIVE_LEAD = False


def _lead(hand: list[Card], trump: str | None, played: list[Card]) -> Card:
    """
    Pick the best suit using gap analysis, then lead its 2nd-highest card.
    """
    groups: dict[str, list[Card]] = {}
    for c in hand:
        groups.setdefault(c.suit, []).append(c)
    gone = set(played)

    def lead_from(s: str) -> Card:
        cards = sorted(groups[s], key=lambda c: c.value(), reverse=True)
        # Lead 2nd-highest — the card positioned to be 2nd in the trick
        return cards[min(1, len(cards) - 1)]

    def suit_score(s: str) -> tuple:
        g = _gap(s, hand, played)
        is_trump_penalty = 1 if (trump in SUITS and s == trump) else 0
        dead = 1 if LIVE_LEAD and _dead(lead_from(s), hand, gone) else 0
        return (-dead, -g, -is_trump_penalty, len(groups[s]), SUITS.index(s))

    return lead_from(max(groups, key=suit_score))


# ── Giving up a trick ────────────────────────────────────────────────────────
#
# Both fallbacks below used to throw the lowest card by value in any suit, so a
# robot void in the led suit could throw the 2 of trumps on a trick it was
# losing anyway. The user's rule (roadmap 3.11): a trump is only ever played
# off-suit to ruff for a win, so a losing card comes from a side suit while
# there is one.

#: A void robot giving up a trick discards rather than throws a trump
#: (measurement switch).
KEEP_TRUMPS = True


def _shed(legal: list[Card], trump: str | None) -> Card:
    """The card to play on a trick this hand isn't trying to win."""
    if KEEP_TRUMPS:
        side = [c for c in legal if c.suit != trump]
        if side:
            return min(side, key=lambda c: c.value())
    return min(legal, key=lambda c: c.value())


# ── Middle positions (2nd / 3rd to play) ─────────────────────────────────────

def _middle_play(player: str, legal: list[Card], trick: list[tuple[str, Card]],
                 trump: str | None, later: set[Card]) -> Card:
    """Partnership-aware play when 2nd or 3rd to act.

    Every legal card is judged on the same two questions: does it leave the
    trick with us, and how many of the cards still to come would take it back.
    The cheapest card that keeps the trick and can be taken away at most once
    wins; if nothing qualifies, duck the lowest card.

    Who "currently" holds the trick is deliberately not consulted. With one or
    two cards down the second-highest of the winning suit is whoever played the
    lower card, so partner can hold a half-empty trick with a card that any
    later card displaces — and reading that as "partner is winning, play low"
    throws the trick away. Asking what survives collapses both cases into one
    rule, and it is also what finds the play this variant turns on: covering
    partner's high card to push it down into second place.
    """
    options = []
    for c in legal:
        holder, exposed = _outlook(player, c, trick, trump, later)
        if holder in (player, PARTNERS[player]) and exposed <= 1:
            options.append((exposed, c.value(), c))
    if options:
        return min(options, key=lambda t: (t[0], t[1]))[2]
    return _shed(legal, trump)


# ── Last to play ──────────────────────────────────────────────────────────────

#: Fourth hand counts partner's winning as its own (measurement switch).
LAST_HAND_FOR_PARTNER = True


def _play_last(legal: list[Card], trick: list[tuple[str, Card]], trump: str | None,
               hand: list[Card] | None = None, played: list[Card] | None = None) -> Card:
    """Simulate each legal card; pick the smallest that keeps the trick for the
    PARTNERSHIP, else dump the lowest.

    It used to ask only whether this hand itself won. Fourth hand's card often
    decides which of the others is second-highest: on a user's 3H, North led
    the 7H, East played the 8H, and dummy's 4H let the seven win, where the
    king pushes the eight into second place. Partner taking the trick is
    exactly as good as taking it.

    With nothing that keeps the trick, following suit, a dead card goes first
    (`DEAD_CARD_LAST`): on deal 156 North's AC and KC could never win a trick,
    while the 5C it dumped could."""
    partner = trick[1][0]                     # fourth hand's partner played second
    ours = (_AI_TAG, partner) if LAST_HAND_FOR_PARTNER else (_AI_TAG,)
    winning = [
        c for c in legal
        if resolve_trick(trick + [(_AI_TAG, c)], trump) in ours
    ]
    if winning:
        return min(winning, key=lambda c: c.value())
    if DEAD_CARD_LAST and hand is not None:
        led = trick[0][1].suit
        gone = set(played or []) | {c for _, c in trick}
        dead = [c for c in legal if c.suit == led and _dead(c, hand, gone)]
        if dead:
            return min(dead, key=lambda c: c.value())
    return _shed(legal, trump)

