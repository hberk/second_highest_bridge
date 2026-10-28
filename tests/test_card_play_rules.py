"""The card-play rules from the user's review of deals 10, 43, 92, 156, 174 and 356.

Each is a switch in ai.py (SURE_LEAD_DECLARER, RUFF_LEAD, FORCE_DUMMY,
DEAD_CARD_LAST, LIVE_LEAD, NT_SET_UP_SUIT, DEFENDER_SUIT_PLAN, DEAD_WINNER_FIRST). Every test sets the switches it needs and puts them back, so
the result doesn't depend on which rules are adopted.
"""
from __future__ import annotations

import sys
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import ai
import challenge
from card import Card

RULES = ('SURE_LEAD_DECLARER', 'RUFF_LEAD', 'FORCE_DUMMY', 'DEAD_CARD_LAST',
         'LIVE_LEAD', 'NT_SET_UP_SUIT', 'DEFENDER_SUIT_PLAN', 'RUFF_RETURN',
         'SHORT_LEAD_RETURN', 'DEAD_WINNER_FIRST')


@contextmanager
def rules(**on):
    """Every rule off except those named True."""
    saved = {name: getattr(ai, name) for name in RULES}
    try:
        for name in RULES:
            setattr(ai, name, on.get(name, False))
        yield
    finally:
        for name, value in saved.items():
            setattr(ai, name, value)


def C(text: str) -> Card:
    return Card(text[-1], text[:-1])


def replay(deal_id: int, tricks: list[str]):
    """The deal's hands after these tricks ("SEAT:card ..." each), the cards
    played and the history."""
    hands = challenge.hands_for(deal_id)
    played, history = [], []
    for line in tricks:
        trick = []
        for token in line.split():
            seat, card = token.split(':')
            seat = {'N': 'North', 'E': 'East', 'S': 'South', 'W': 'West'}[seat]
            hands[seat].remove(C(card))
            played.append(C(card))
            trick.append((seat, C(card)))
        history.append(trick)
    return hands, played, history


# Deal 174, 4H by East, dummy West. After trick 4 the defence has no trumps
# and dummy (KH QH 9H 10C, spades) is void in diamonds.
DEAL_174 = ['S:JC W:KC N:3C E:AC', 'W:JH N:2S E:3H S:10H',
            'S:7D W:8D N:5D E:KD', 'W:2H N:3S E:4H S:AH']


def _east_174(trick=()):
    hands, played, history = replay(174, DEAL_174)
    contract = {'declarer': 'East', 'dummy': 'West'}
    view = ai.visible_hands('East', contract, hands)
    return ai.ai_play('East', hands['East'], list(trick), 'H', played, view, history)


def test_deal_174_led_trumps_into_a_trumpless_defence():
    with rules():
        assert _east_174() == C('7H')


def test_deal_174_ruff_lead_leads_the_dead_ace_for_dummy_to_ruff():
    with rules(RUFF_LEAD=True):
        assert _east_174() == C('AD')


def test_deal_174_sure_lead_plays_the_nine_to_dummys_ten():
    """Trick 8, after East drew the trumps it didn't need to: East leads clubs
    from 9C 2C with dummy's 10C. The 2C (what East led) loses to North's 8C;
    the 9C wins whatever the defence plays."""
    hands, played, history = replay(174, DEAL_174 + [
        'E:7H S:3D W:9H N:4S', 'E:6H S:4D W:QH N:5C', 'E:5H S:4C W:KH N:6D'])
    contract = {'declarer': 'East', 'dummy': 'West'}
    view = ai.visible_hands('East', contract, hands)
    with rules():
        assert ai.ai_play('East', hands['East'], [], 'H', played, view, history) == C('2C')
    with rules(SURE_LEAD_DECLARER=True):
        assert ai.ai_play('East', hands['East'], [], 'H', played, view, history) == C('9C')


def test_sure_lead_leaves_the_trump_suit_alone():
    """At trick 5 the lead rules choose trumps; the sure-lead rule doesn't
    touch a trump lead (deal 6: a "sure" trump trick spent two trumps)."""
    with rules(SURE_LEAD_DECLARER=True):
        assert _east_174() == C('7H')


def test_nine_to_partners_ten_is_sure_and_the_two_is_not():
    """The user's point on deal 174: 9C to dummy's 10C wins whatever the
    opponents hold, while 2C to the 10C loses when they play the 8 and 7."""
    east = [C('9C'), C('2C')]
    west = [C('10C'), C('9S')]
    unseen = {C('QC'), C('7C'), C('8C'), C('6C')}
    kept = set(east) | set(west) | unseen
    played = [c for c in ai._FULL_DECK if c not in kept]
    got = ai._sure_lead_declarer('East', east, None, played, {'West': west, 'East': east}, [], 'C')
    assert got == C('9C'), got


# Deal 92, 3C by North, dummy South (J10 3 of trumps left, void in hearts).
DEAL_92 = ['E:QC S:8C W:4C N:9C', 'N:AC E:KC S:2C W:3H']


def _east_92():
    hands, played, history = replay(92, DEAL_92)
    contract = {'declarer': 'North', 'dummy': 'South'}
    view = ai.visible_hands('East', contract, hands)
    return ai.ai_play('East', hands['East'], [], 'C', played, view, history)


def test_deal_92_led_a_trump_into_dummy():
    with rules():
        assert _east_92() == C('6C')


def test_deal_92_force_dummy_leads_hearts():
    with rules(FORCE_DUMMY=True):
        assert _east_92() == C('AH')


def test_force_dummy_leaves_a_side_suit_lead_alone():
    """The rule only replaces a trump lead: in notrump nothing changes."""
    hands, played, history = replay(92, DEAL_92)
    contract = {'declarer': 'North', 'dummy': 'South'}
    view = ai.visible_hands('East', contract, hands)
    with rules():
        before = ai.ai_play('East', hands['East'], [], None, played, view, history)
    with rules(FORCE_DUMMY=True):
        after = ai.ai_play('East', hands['East'], [], None, played, view, history)
    assert before == after


# Deal 156, 1H by North, dummy South. Trick 4: 10C 3C 9C to North (AC KC 8C 5C).
DEAL_156 = ['E:KD S:2D W:9D N:QD', 'N:8H E:6H S:9H W:4H', 'N:2H E:7H S:5H W:JH']


def _north_156():
    hands, played, history = replay(156, DEAL_156)
    trick = [('East', C('10C')), ('South', C('3C')), ('West', C('9C'))]
    for seat, card in trick:
        hands[seat].remove(card)
    contract = {'declarer': 'North', 'dummy': 'South'}
    view = ai.visible_hands('North', contract, hands)
    return ai.ai_play('North', hands['North'], trick, 'H', played, view, history)


def test_deal_156_dumped_the_five():
    with rules():
        assert _north_156() == C('5C')


def test_deal_156_dead_card_last_plays_the_king():
    with rules(DEAD_CARD_LAST=True):
        assert _north_156() == C('KC')


def test_dead_card_last_still_takes_a_trick_it_can_win():
    """A card that keeps the trick for the side always comes before a dead one."""
    trick = [('East', C('7C')), ('South', C('3C')), ('West', C('9C'))]
    hand = [C('AC'), C('8C')]
    with rules(DEAD_CARD_LAST=True):
        # 8C under the 9C makes the 8 second-highest: North's own trick.
        assert ai._play_last(hand, trick, None, hand, []) == C('8C')


# Deal 43, 3NT by West, dummy East. North led the 10H, won by East's 7H.
DEAL_43 = ['N:10H E:7H S:4H W:3H']


def _lead_43(seat: str, tricks: list[str]):
    hands, played, history = replay(43, tricks)
    view = ai.visible_hands(seat, {'declarer': 'West', 'dummy': 'East'}, hands)
    return ai.ai_play(seat, hands[seat], [], None, played, view, history)


def test_deal_43_dummy_led_spades_from_ace_king():
    with rules():
        assert _lead_43('East', DEAL_43) == C('KS')


def test_deal_43_declarer_sets_up_the_club_suit():
    """The user's point: set up the long suit. Q65 opposite K10982; the QC is
    double dummy's best card (E/W keep 7 tricks; the KS left them 4)."""
    with rules(NT_SET_UP_SUIT=True):
        assert _lead_43('East', DEAL_43) == C('QC')


def test_deal_43_no_lead_from_ace_king_queen():
    """Trick 3: West led the KH from AKQ3 and North's 9H won. Every heart
    above the king is West's own, so it can never be second-highest."""
    tricks = DEAL_43 + ['E:KS S:JS W:QS N:3S']
    with rules():
        assert _lead_43('West', tricks) == C('KH')
    with rules(LIVE_LEAD=True):
        got = _lead_43('West', tricks)
        assert got.suit != 'H', got


def test_a_live_lead_still_leads_a_dead_card_when_every_suit_is_dead():
    """With nothing live to lead, the rule changes nothing."""
    hand = [C('AS'), C('KS'), C('AH'), C('KH')]
    with rules():
        before = ai._lead(hand, None, [])
    with rules(LIVE_LEAD=True):
        assert ai._lead(hand, None, []) == before


# Deal 356, 3S by East, dummy West. North won trick 2 with the 10C and leads
# from 10-9-6 of hearts: the A K Q J are gone and dummy's 8H is its last heart.
DEAL_356 = ['S:KH W:JH N:QH E:AH', 'S:JC W:5C N:10C E:3C']


def _lead_356():
    hands, played, history = replay(356, DEAL_356)
    view = ai.visible_hands('North', {'declarer': 'East', 'dummy': 'West'}, hands)
    return ai.ai_play('North', hands['North'], [], 'S', played, view, history)


def test_deal_356_led_the_nine_sure_to_be_highest():
    with rules():
        assert _lead_356() == C('9H')


def test_deal_356_suit_plan_leads_the_six():
    """The 9H can only be highest, so dummy's 8H wins and dummy can then ruff;
    the 6H lets South's 7H be second-highest (double dummy: 3S+1 after the
    nine, one down after the six)."""
    with rules(DEFENDER_SUIT_PLAN=True):
        assert _lead_356() == C('6H')


def test_suit_plan_on_deal_356s_real_layout():
    """With South's 7-3-2 and East's 5-4: after the 9H dummy wins and ruffs
    every heart after, so the defence takes none; after the 6H, South's 7H wins."""
    v = lambda *ranks: tuple(sorted(C(r + 'H').value() for r in ranks))
    # Seats from North: North, East (declarer), South, West (dummy, can ruff).
    hands = (v('10', '9', '6'), v('5', '4'), v('7', '3', '2'), v('8'))
    ruffs = (False, True, False, True)
    order = [0, 1, 2, 3]
    assert ai._plan_trick(hands, ruffs, [(0, C('9H').value())], order, {}) == 0
    assert ai._plan_trick(hands, ruffs, [(0, C('6H').value())], order, {}) == 1


# Deal 10, spades by East, dummy West. A line that reaches the user's trick 5:
# South leads the 8C, East is void in clubs and holds AS JS 6S, with the KS and
# QS gone. Any lone trump wins the trick.
DEAL_10 = ['S:JH W:6H N:4H E:AH', 'S:9H W:KH N:8H E:QH', 'E:KS S:AD W:QS N:2S',
           'W:5C N:3C E:7C S:6C']


def _ruff_10() -> Card:
    hands, played, history = replay(10, DEAL_10)
    trick = [('South', C('8C')), ('West', C('10C')), ('North', C('4C'))]
    for seat, card in trick:
        hands[seat].remove(card)
    visible = ai.visible_hands('East', {'declarer': 'East', 'dummy': 'West'}, hands)
    return ai.ai_play('East', hands['East'], trick, 'S', played, visible, history)


def test_deal_10_ruffed_with_the_six():
    with rules():
        assert _ruff_10() == C('6S')


def test_deal_10_dead_winner_first_ruffs_with_the_jack():
    """The JS and AS can't be beaten, so they win later only alone in spades;
    the 6S can still be second-highest (double dummy: the six goes one down,
    the jack or ace makes)."""
    with rules(DEAD_WINNER_FIRST=True):
        assert _ruff_10() == C('JS')


def test_dead_winner_first_only_chooses_among_winning_cards():
    """West leads the 10C, North plays the 4C, East the 8C. South's AC can't be
    beaten but would make West's 10C second-highest, so it isn't a winner; the
    9C wins and is still the card."""
    trick = [('West', C('10C')), ('North', C('4C')), ('East', C('8C'))]
    hand = [C('AC'), C('9C'), C('2C')]
    with rules(DEAD_WINNER_FIRST=True):
        assert ai._play_last(hand, trick, 'S', hand, []) == C('9C')

if __name__ == '__main__':
    failed = 0
    for name, fn in list(globals().items()):
        if name.startswith('test_') and callable(fn):
            try:
                fn()
                print(f"PASS {name}")
            except AssertionError as exc:
                failed += 1
                print(f"FAIL {name}: {exc}")
    sys.exit(1 if failed else 0)
