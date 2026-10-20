"""What a call means in the robots' system: frontend/src/lib/meanings.ts, in
Python, for the Streamlit app.

A robot's alert depends only on the auction and the call, never on its cards
(tests/test_bidding_calibration.py checks it), so the meaning of any call is
found by asking the robots what they would bid, in this seat and auction,
with many sampled hands, and keeping the alert each call came with. The
robots' play reads a human's calls this way (`gib_alert`): as a robot
partner would take them, not from the human's free-text self-alert.

The sample is seeded from the auction, so the same auction always reads the
same way, and is skewed towards strong and long hands, as in meanings.ts. It
lives here, not in ai.py, because ai.py imports no randomness at all.
"""
from __future__ import annotations

from ai import ai_bid_explained
from card import Card, RANKS, SUITS
from game import AuctionState

#: Hands asked per call at most; sampling stops early once the call has been
#: seen often enough to read.
SAMPLE_HANDS = 4000
ENOUGH = 12

_DECK = [Card(s, r) for s in SUITS for r in RANKS]
_HONOURS = {'J', 'Q', 'K', 'A'}
_M32 = 0xFFFFFFFF


def _imul(a: int, b: int) -> int:
    return (a * b) & _M32


def prng(seed: int):
    """mulberry32, as meanings.ts: floats in [0, 1)."""
    state = [seed & _M32]

    def rnd() -> float:
        state[0] = (state[0] + 0x6D2B79F5) & _M32
        t = state[0]
        t = _imul(t ^ (t >> 15), t | 1)
        t ^= (t + _imul(t ^ (t >> 7), t | 61)) & _M32
        return ((t ^ (t >> 14)) & _M32) / 4294967296
    return rnd


def _seed_of(auction: AuctionState) -> int:
    """FNV-1a over the auction, as meanings.ts."""
    text = f"{auction.dealer}|{auction.vulnerability}|{' '.join(c for _, c in auction.calls)}"
    h = 0x811C9DC5
    for ch in text:
        h = _imul(h ^ ord(ch), 0x01000193)
    return h


def _weighted_hand(rnd, weight) -> list[Card]:
    keyed = [(rnd() ** (1 / weight(c)), c) for c in _DECK]
    keyed.sort(key=lambda kc: -kc[0])
    return [c for _, c in keyed[:13]]


def _sample_hand(rnd) -> list[Card]:
    """A hand from a mix of shapes and strengths, so rare calls get asked about."""
    pick = rnd()
    suit = SUITS[int(rnd() * 4)]
    other = SUITS[int(rnd() * 4)]
    honour, long, boost = 1.0, [], 1.0
    if pick < 0.4:
        pass
    elif pick < 0.55:
        honour = 2.5
    elif pick < 0.65:
        honour = 6.0
    elif pick < 0.8:
        long, boost = [suit], 4.0
    elif pick < 0.9:
        long, boost = [suit, other], 3.0
    else:
        long, boost, honour = [suit], 3.0, 2.5
    return _weighted_hand(rnd, lambda c: (honour if c.rank in _HONOURS else 1.0)
                          * (boost if c.suit in long else 1.0))


def gib_alert(auction: AuctionState, call: str) -> str | None:
    """The robots' alert for `call` if the player to act made it now, or None
    when no sampled hand made it (the system has no meaning for it here) or
    it is a pass."""
    if call == 'Pass':
        return None
    here = AuctionState(dealer=auction.dealer, vulnerability=auction.vulnerability)
    for who, c in auction.calls:
        here.apply_call(who, c)
    who = here.current_player()
    rnd = prng(_seed_of(here))
    whys: dict[str, int] = {}
    for _ in range(SAMPLE_HANDS):
        made, why = ai_bid_explained(who, _sample_hand(rnd), here)
        if made == call:
            whys[why] = whys.get(why, 0) + 1
            if sum(whys.values()) >= ENOUGH:
                break
    if not whys:
        return None
    # Each call should read one way; if an odd auction splits it, the commonest.
    return max(whys.items(), key=lambda kv: kv[1])[0]
