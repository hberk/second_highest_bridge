"""Head-to-head mode: the same deal, played by you and by the robots.

This is duplicate bridge's own idea. A board means nothing in isolation — what
matters is what somebody else did with the identical cards. So a challenge board
is played twice: once by the human sitting South with a robot North, and once by
an all-robot table on the same deal. Comparing the two scores asks exactly the
question "is the robot better than me with these cards".

It runs on `data/solved_deals.json` -- the 400 deals solved in all five strains
for all four declarers -- which is what makes the interesting part affordable.
Because every trick count is already known, a contract can be scored as if it
had been played perfectly, and that splits a board's result in two:

    par  -  your actual  =  what the AUCTION cost  +  what the CARD PLAY cost

              bidding_loss = par - double-dummy value of the contract reached
                 play_loss = that value - what you actually scored

Those two numbers answer "how good is the robot at bidding" and "how good is it
at declaring" separately, which a single score cannot. The identity is exact and
`tests/test_challenge.py` asserts it.

No UI here: the web app runs frontend/src/lib/engine/challenge.ts, a port held
to this module by fixtures.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from ai import ai_bid_explained, ai_play, shown_lengths, visible_hands
from bridge.scoring import score_contract
from card import Card
from game import AuctionState, clockwise_from, resolve_trick

#: Written by research/export_challenge_deals.py.
LIBRARY_PATH = Path(__file__).resolve().parent / 'data' / 'solved_deals.json'

SIDES = ('N/S', 'E/W')
STRAINS = ('C', 'D', 'H', 'S', 'NT')
SEATS = ('North', 'East', 'South', 'West')
PARTNERS = {'N/S': ('North', 'South'), 'E/W': ('East', 'West')}

#: A board is abandoned if the auction will not terminate. Real auctions end in
#: a handful of calls; this only exists so a bug cannot hang the page.
_AUCTION_GUARD = 60

_library: Optional[dict] = None


def load_library() -> dict:
    """The solved deal library, read once. {id: {'hands': ..., 'tricks': ...}},
    `tricks` keyed "<strain>:<declarer>"."""
    global _library
    if _library is None:
        with LIBRARY_PATH.open(encoding='utf-8') as f:
            data = json.load(f)
        _library = {d['id']: d for d in data['deals']}
    return _library


def deal_ids() -> list[int]:
    return sorted(load_library())


def hands_for(deal_id: int) -> dict[str, list[Card]]:
    """The four hands, rebuilt from stored text.

    Deliberately NOT `research.dd_dataset.deal_for`, which reseeds the global
    RNG to regenerate a deal. Doing that inside the app would silently make
    every later `deal()` reproducible too.
    """
    raw = load_library()[deal_id]['hands']
    return {seat: [Card(tok[-1], tok[:-1]) for tok in raw[seat].split()]
            for seat in SEATS}


def dd_tricks(deal_id: int, strain: str, declaring_side: str,
              declarer: Optional[str] = None) -> int:
    """Tricks the declaring side takes in `strain`, with both sides perfect.

    The opening lead comes from declarer's left, so the two partners can take
    different numbers of tricks. With `declarer` named, that partner's count;
    without, the better partner's, since a side can choose who declares (par).
    """
    tricks = load_library()[deal_id]['tricks']
    if declarer is not None:
        return tricks[f"{strain}:{declarer}"]
    return max(tricks[f"{strain}:{seat}"] for seat in PARTNERS[declaring_side])


def other_side(side: str) -> str:
    return 'E/W' if side == 'N/S' else 'N/S'


def score_for(side: str, contract: dict, declarer_tricks: int) -> int:
    """The board's score FROM `side`: positive when they gain, negative when
    they concede, whichever side is declaring."""
    declaring = contract['side']
    taken = {declaring: declarer_tricks, other_side(declaring): 13 - declarer_tricks}
    result = score_contract(contract, taken)
    return result['points'] if result['winner'] == side else -result['points']


def _contract(level: int, strain: str, side: str, vulnerability: str) -> dict:
    """The minimum contract dict `score_contract` needs. Only used for pricing
    hypothetical contracts, never for play, so it carries no seats."""
    return {
        'level': level, 'strain': strain, 'side': side,
        'tricks_needed': level + 6,
        'doubled': 'None', 'vulnerability': vulnerability,
    }


#: Every contract in bidding order, 1♣ to 7NT: an auction can only climb this list.
CONTRACT_LADDER = tuple((level, strain) for level in range(1, 8) for strain in STRAINS)


def par_from_tricks(tricks, side: str, vulnerability: str = 'None') -> dict:
    """Duplicate par from a double dummy table: the score both sides reach when
    both bid perfectly, each knowing every card.

    `tricks(strain, declaring_side)` is the tricks that side takes declaring
    `strain` (its better partner). The auction is searched out in full: a side
    either passes the contract standing or bids a higher one of its own, a
    contract that fails is doubled, and one that makes is left undoubled. So the
    opponents' game counts, and so does a sacrifice that costs less than it.

    Returned from `side`: `score` (positive when `side` gains), and the par
    contract -- `level`, `strain`, the declaring `side`, `doubled` ('X' for a
    sacrifice) and the declaring side's `tricks`. A deal where neither side
    gains by bidding is passed out: level 0, strain None.

    N/S speak first. Who speaks first can only matter when both sides can make
    the same top contract, and on none of the 400 challenge deals, at any
    vulnerability, does it change the score.
    """
    other = {'N/S': 'E/W', 'E/W': 'N/S'}
    table = {(strain, s): tricks(strain, s) for strain in STRAINS for s in other}
    n = len(CONTRACT_LADDER)
    passed_out = {'score': 0, 'level': 0, 'strain': None, 'side': None,
                  'doubled': 'None', 'tricks': 0}

    def played(k: int, owner: str) -> dict:
        level, strain = CONTRACT_LADDER[k]
        taken = table[(strain, owner)]
        contract = _contract(level, strain, owner, vulnerability)
        if taken < level + 6:
            contract['doubled'] = 'X'
        return {'score': score_for('N/S', contract, taken), 'level': level,
                'strain': strain, 'side': owner, 'doubled': contract['doubled'],
                'tricks': taken}

    # best[k][owner]: the outcome once `owner` has bid contract k and the other
    # side is to speak, filled from the top of the ladder down. Scores from N/S;
    # each side keeps the first (lowest) of equal outcomes, passing before bidding.
    best = [dict() for _ in range(n)]
    for k in range(n - 1, -1, -1):
        for owner in other:
            mover = other[owner]
            sign = 1 if mover == 'N/S' else -1
            outcome = played(k, owner)
            for j in range(k + 1, n):
                reply = best[j][mover]
                if sign * reply['score'] > sign * outcome['score']:
                    outcome = reply
            best[k][owner] = outcome

    def opening(mover: str, after_pass: bool) -> dict:
        sign = 1 if mover == 'N/S' else -1
        outcome = passed_out if after_pass else opening(other[mover], True)
        for k in range(n):
            if sign * best[k][mover]['score'] > sign * outcome['score']:
                outcome = best[k][mover]
        return outcome

    result = dict(opening('N/S', False))
    if side == 'E/W':
        result['score'] = -result['score']
    return result


def ceiling(deal_id: int, side: str, vulnerability: str = 'None') -> dict:
    """The best score `side` could reach on its own, ignoring whether the
    opponents would have competed: what `par` was until 2026-11-06. The app
    no longer shows it; `research/challenge_losses.py` grades against it so
    the "lost in the auction" series in ROBOT_PROGRESS stays comparable."""
    best = None
    for strain in STRAINS:
        taken = dd_tricks(deal_id, strain, side)
        for level in range(1, 8):
            if level + 6 > taken:
                break
            points = score_for(side, _contract(level, strain, side, vulnerability),
                               taken)
            if best is None or points > best['score']:
                best = {'score': points, 'level': level, 'strain': strain,
                        'tricks': taken}
    if best is None:
        best = {'score': 0, 'level': 0, 'strain': None, 'tricks': 0}
    return best


def par(deal_id: int, side: str, vulnerability: str = 'None') -> dict:
    """Duplicate par on a library deal, from `side`: see `par_from_tricks`.

    Par counts both sides, so a board the opponents own has a negative par, and
    a side can score above par when the opponents miss their contract."""
    return par_from_tricks(lambda strain, s: dd_tricks(deal_id, strain, s),
                           side, vulnerability)


def robot_table(deal_id: int, dealer: str, vulnerability: str = 'None') -> dict:
    """Play the whole board with robots in all four seats.

    Cheap -- `ai_bid` and `ai_play` are pure evaluation, no solver -- so this can
    run inline when the human finishes their board.
    """
    hands = hands_for(deal_id)
    initial = {seat: list(cards) for seat, cards in hands.items()}
    auction = AuctionState(dealer=dealer, vulnerability=vulnerability)
    # Alerts are captured the same way the live table captures them, so
    # stepping through the robot auction explains each call instead of just
    # showing it. The robots read them too: partner's range, for a penalty
    # double.
    alerts: dict[int, str] = {}
    guard = 0
    while not auction.is_complete and guard < _AUCTION_GUARD:
        who = auction.current_player()
        call, why = ai_bid_explained(who, hands[who], auction, alerts)
        alerts[len(auction.calls)] = why
        auction.apply_call(who, call)
        guard += 1

    calls = [(who, call) for who, call in auction.calls]
    contract = auction.get_contract()
    base = {'contract': contract, 'calls': calls, 'alerts': alerts,
            'initial_hands': initial, 'dealer': dealer,
            'vulnerability': vulnerability}
    if contract is None:
        return {**base, 'declarer_tricks': 0, 'ns_tricks': 0, 'ew_tricks': 0,
                'tricks_log': [], 'tricks_taken': {'N/S': 0, 'E/W': 0},
                'result': None}

    remaining = {seat: list(cards) for seat, cards in hands.items()}
    shown = shown_lengths(calls, alerts)
    trump = contract['trump']
    leader = contract['leader']
    played: list[Card] = []
    taken = {'N/S': 0, 'E/W': 0}
    tricks_log = []

    for trick_num in range(1, 14):
        trick: list[tuple[str, Card]] = []
        trick_leader = leader
        for seat in clockwise_from(leader):
            card = ai_play(seat, remaining[seat], trick, trump, played,
                           visible=visible_hands(seat, contract, remaining),
                           history=[e['plays'] for e in tricks_log], shown=shown)
            remaining[seat].remove(card)
            trick.append((seat, card))
        winner = resolve_trick(trick, trump)
        taken['N/S' if winner in ('North', 'South') else 'E/W'] += 1
        # Same shape the live table logs, so the existing replayer can step
        # through a robot board with no changes of its own.
        tricks_log.append({
            'trick_num': trick_num,
            'leader': trick_leader,
            'plays': list(trick),
            'winner': winner,
            'winning_card': dict(trick)[winner],
        })
        played.extend(c for _, c in trick)
        leader = winner

    return {
        **base,
        'declarer_tricks': taken[contract['side']],
        'ns_tricks': taken['N/S'],
        'ew_tricks': taken['E/W'],
        'tricks_log': tricks_log,
        'tricks_taken': dict(taken),
        'result': score_contract(contract, taken),
    }


def as_history_record(table: dict, board_num, label: str) -> dict:
    """Shape a robot table's result like a hand-history entry.

    The replayer renders any record of this shape, so a robot board becomes
    steppable without the replayer knowing it exists. The web app's twin is
    `asHistoryRecord` in frontend/src/lib/game.svelte.ts.
    """
    return {
        'board_num': board_num,
        'label': label,
        'dealer': table['dealer'],
        'vulnerability': table['vulnerability'],
        'initial_hands': table['initial_hands'],
        'auction_calls': table['calls'],
        'bid_alerts': table['alerts'],
        'contract': table['contract'],
        'passed_out': table['contract'] is None,
        'tricks_log': table['tricks_log'],
        'tricks_taken': table['tricks_taken'],
        'result': table['result'],
    }


def grade(deal_id: int, side: str, contract: Optional[dict],
          declarer_tricks: int, vulnerability: str = 'None',
          against=None) -> dict:
    """Split a board's result into what the auction cost and what the play cost.

        par - actual = bidding_loss + play_loss

    A loss is reported POSITIVE as points given away, because "you lost 40 in
    the auction" reads more naturally than "-40". Either number can come out
    negative, which is meaningful rather than a bug: a negative bidding_loss
    means the contract reached beats par, which happens when the opponents miss
    their best contract or are pushed into something that fails.

    `against` replaces `par` as the target (`ceiling`, for research).
    """
    target = (against or par)(deal_id, side, vulnerability)
    if contract is None:
        return {'par': target, 'passed_out': True, 'dd_score': 0,
                'actual': 0, 'bidding_loss': target['score'], 'play_loss': 0,
                'total_loss': target['score']}

    perfect = dd_tricks(deal_id, contract['strain'], contract['side'],
                        contract.get('declarer'))
    dd_score = score_for(side, contract, perfect)
    actual = score_for(side, contract, declarer_tricks)
    return {
        'par': target,
        'passed_out': False,
        'dd_tricks': perfect,
        'dd_score': dd_score,
        'actual': actual,
        'bidding_loss': target['score'] - dd_score,
        'play_loss': dd_score - actual,
        'total_loss': target['score'] - actual,
    }
