"""The card-play rules from the user's review of deals 10, 43, 92, 114, 156, 174, 276 and 356.

Each is a switch in ai.py (SURE_LEAD_DECLARER, RUFF_LEAD, FORCE_DUMMY,
DEAD_CARD_LAST, LIVE_LEAD, NT_SET_UP_SUIT, DEFENDER_SUIT_PLAN, DEAD_WINNER_FIRST, RUFF_IF_FOLLOWS,
PARTNER_HONOUR_LEAD, COVER_SUIT_PLAN, COVER_PLAN_LOW, LAST_SUIT_PLAN). Every test sets the switches it needs and puts them back, so
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
         'SHORT_LEAD_RETURN', 'DEAD_WINNER_FIRST', 'RUFF_IF_FOLLOWS',
         'NT_DEFENCE_SUIT', 'IDLE_TRUMP_FOR_RUFF', 'PARTNER_HONOUR_LEAD',
         'COVER_SUIT_PLAN', 'COVER_PLAN_LOW', 'LAST_SUIT_PLAN')


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


# Deal 276, 4C by West, dummy East. Tricks 1-3 rebuilt to fit the user's
# board (the cards left in each hand, N/S 1 trick, E/W 2). At trick 4 dummy
# leads the JS, South plays the KS, and West is void in spades.
DEAL_276 = ['N:2D E:6D S:KD W:5D', 'E:3C S:7C W:5C N:JC', 'S:7D W:9D N:3D E:8D']


def _third_276() -> Card:
    hands, played, history = replay(276, DEAL_276)
    trick = [('East', C('JS')), ('South', C('KS'))]
    for seat, card in trick:
        hands[seat].remove(card)
    visible = ai.visible_hands('West', {'declarer': 'West', 'dummy': 'East'}, hands)
    return ai.ai_play('West', hands['West'], trick, 'C', played, visible, history)


def test_deal_276_threw_a_heart():
    """Both unseen clubs counted as overruffs, two threats to the discard's
    one (North's QS), so West threw the 3H under dummy's jack."""
    with rules():
        assert _third_276() == C('3H')


def test_deal_276_ruff_if_follows_ruffs():
    """North can only overruff when out of spades, with eight unseen: West
    ruffs (double dummy the 3H costs two tricks)."""
    with rules(RUFF_IF_FOLLOWS=True):
        assert _third_276() == C('8C')


def test_void_chance_counts_the_unseen_cards():
    """Eight spades unseen across North's ten cards and South's nine: North
    is void in C(9,8)/C(19,8) of the layouts."""
    hands, played, history = replay(276, DEAL_276)
    trick = [('East', C('JS')), ('South', C('KS'))]
    for seat, card in trick:
        hands[seat].remove(card)
    visible = ai.visible_hands('West', {'declarer': 'West', 'dummy': 'East'}, hands)
    chance = ai._void_chance('West', hands['West'], trick, played, visible, history,
                             ai._shown_out(history, trick))
    assert chance == 9 / 75582


# The user's board, 2026-10-29: 4S by North, dummy South. Two rounds drew the
# defence's trumps; at trick 6 South led the 9S, North had to follow with
# the K, and two trumps took one trick that a heart, ruffed in North, takes
# with one.
BOARD_4S = {'North': 'AS KS QS 7S 6S AD JD 10D 5D 3D AC 6C 2C',
            'South': 'JS 9S 8S 4S JH 5H 2H KD 7D 4D 2D 10C 7C',
            'West': '3S 2S 9H 8H 7H 6H 4H QD 8D 6D KC 8C 5C',
            'East': '10S 5S AH KH QH 10H 3H 9D QC JC 9C 4C 3C'}
BOARD_4S_TRICKS = ['E:KH S:2H W:4H N:QS', 'N:6S E:5S S:8S W:2S', 'N:7S E:10S S:4S W:3S',
                   'N:AD E:9D S:KD W:QD', 'S:7D W:6D N:10D E:3C']


def _south_4s() -> Card:
    hands = {seat: [C(t) for t in text.split()] for seat, text in BOARD_4S.items()}
    played, history = [], []
    for line in BOARD_4S_TRICKS:
        trick = []
        for token in line.split():
            seat, card = token.split(':')
            seat = {'N': 'North', 'E': 'East', 'S': 'South', 'W': 'West'}[seat]
            hands[seat].remove(C(card))
            played.append(C(card))
            trick.append((seat, C(card)))
        history.append(trick)
    contract = {'declarer': 'North', 'dummy': 'South'}
    return ai.ai_play('South', hands['South'], [], 'S', played,
                      visible=ai.visible_hands('South', contract, hands), history=history)


def test_4s_board_led_an_idle_trump():
    with rules():
        assert _south_4s().suit == 'S'


def test_4s_board_idle_trump_for_ruff_leads_a_heart():
    with rules(IDLE_TRUMP_FOR_RUFF=True):
        assert _south_4s().suit == 'H'


def test_idle_trump_for_ruff_waits_while_the_defence_has_trumps():
    """Before trick 2 the defence holds four trumps: no swap."""
    hands = {seat: [C(t) for t in text.split()] for seat, text in BOARD_4S.items()}
    visible = ai.visible_hands('South', {'declarer': 'North', 'dummy': 'South'}, hands)
    assert ai._ruff_for_idle_trump('South', hands['South'], 'S', [], visible) is None


def test_nt_defence_suit_returns_partners_opening_lead():
    """3NT by South: West led a heart; East, on lead later, returns one."""
    hand = [C(t) for t in 'AS QS 9S 4S 2S 8H 3H KD 5D'.split()]
    history = [[('West', C('JH')), ('North', C('2H')), ('East', C('QH')), ('South', C('AH'))],
               [('South', C('3C')), ('West', C('4C')), ('North', C('KC')), ('East', C('AC'))]]
    with rules(NT_DEFENCE_SUIT=True):
        assert ai._nt_defence_suit('East', hand, 'NT', history, {'North': []}) == C('3H')
    out = history + [[('North', C('5H')), ('East', C('7H')), ('South', C('6H')), ('West', C('2C'))]]
    assert ai._nt_defence_suit('East', hand, 'NT', out, {'North': []}) is None   # West is out
    assert ai._nt_defence_suit('East', hand, 'S', history, {'North': []}) is None


# Board 26 (challenge deal 114), 2S by East after 1NT P 2H(transfer) X P...:
# North's double is lead-directing, "5+ ♥, 4+ judgement points there", with
# ♥A K J 8 3. South holds ♥Q 2.
AUCTION_114 = [('East', '1NT'), ('South', 'Pass'), ('West', '2H'), ('North', 'X'),
               ('East', '2S'), ('South', 'Pass'), ('West', 'Pass'), ('North', 'Pass')]
ALERTS_114 = {2: "Transfer: 5+ \u2660. Artificial.",
              3: "Lead-directing: 5+ \u2665, 4+ judgement points there."}


def test_shown_lengths_reads_judgement_points():
    shown = ai.shown_lengths(AUCTION_114, ALERTS_114)
    assert shown['North']['H'] == 5 and shown['West']['S'] == 5
    assert shown['judge']['North'] == {'H': 4} and shown['judge']['West'] == {}


def test_deal_114_leads_the_queen_of_partners_suit():
    """South led the 2 from Q-2; the queen, under North's jack, makes a trick."""
    hands = challenge.hands_for(114)
    shown = ai.shown_lengths(AUCTION_114, ALERTS_114)
    with rules():
        assert ai.ai_play('South', hands['South'], [], 'S', [], shown=shown) == C('2H')
    with rules(PARTNER_HONOUR_LEAD=True):
        assert ai.ai_play('South', hands['South'], [], 'S', [], shown=shown) == C('QH')
        # Without the judgement points (an ordinary 5-card overcall), the old lead.
        bare = {**shown, 'judge': {p: {} for p in ai.PLAYERS}}
        assert ai.ai_play('South', hands['South'], [], 'S', [], shown=bare) == C('2H')
        # No honour to lead: the second-highest card as before.
        low = [c for c in hands['South'] if c != C('QH')] + [C('3H')]
        low.remove(C('7D'))
        assert ai.ai_play('South', low, [], 'S', [], shown=shown) == C('2H')


def _east_114() -> tuple:
    """Trick 2: North leads the KH (A 8 3 left); East holds T 6, dummy 9 7.
    North's double showed five, so South has one heart at most."""
    hands, played, history = replay(114, ['S:QH W:5H N:JH E:4H'])
    trick = [('North', C('KH'))]
    hands['North'].remove(C('KH'))
    visible = ai.visible_hands('East', {'declarer': 'East', 'dummy': 'West'}, hands)
    shown = ai.shown_lengths(AUCTION_114, ALERTS_114)
    return hands, trick, played, visible, history, shown


def test_deal_114_east_played_the_ten():
    hands, trick, played, visible, history, shown = _east_114()
    with rules():
        assert ai.ai_play('East', hands['East'], trick, 'S', played, visible,
                          history, shown) == C('10H')


def test_deal_114_east_plays_the_six_and_keeps_the_ten():
    """The 6 and dummy's 7 win the trick, and the T and 9 win another heart."""
    hands, trick, played, visible, history, shown = _east_114()
    with rules(COVER_SUIT_PLAN=True, COVER_PLAN_LOW=True):
        assert ai.ai_play('East', hands['East'], trick, 'S', played, visible,
                          history, shown) == C('6H')
        planned = ai._cover_suit_plan('East', hands['East'], [C('10H'), C('6H')], trick, 'S',
                                      played, visible, history, shown)
        assert planned[C('10H')] == planned[C('6H')]      # both win twice, played right


def test_deal_114_dummy_keeps_the_seven_after_the_ten():
    """After K T 2, dummy's 9 and 7 both keep the trick; only the 9 leaves
    dummy's 7 beside East's 6 to win a later heart."""
    hands, trick, played, visible, history, shown = _east_114()
    trick = trick + [('East', C('10H')), ('South', C('2H'))]
    for seat, card in trick[1:]:
        hands[seat].remove(card)
    visible = ai.visible_hands('West', {'declarer': 'East', 'dummy': 'West'}, hands)
    with rules():
        assert ai.ai_play('West', hands['West'], trick, 'S', played, visible,
                          history, shown) == C('7H')
    with rules(LAST_SUIT_PLAN=True):
        assert ai.ai_play('West', hands['West'], trick, 'S', played, visible,
                          history, shown) == C('9H')


def test_deal_114_robot_table_wins_two_hearts_for_east_west():
    """The whole board as shipped: E/W win trick 2 and a later heart."""
    table = challenge.robot_table(114, 'East', 'Both')
    log = table['tricks_log']
    assert log[0]['plays'][0] == ('South', C('QH'))
    assert dict(log[1]['plays'])['East'] == C('6H')
    hearts_ew = [t for t in log if t['plays'][0][1].suit == 'H'
                 and t['winner'] in ('East', 'West')]
    assert len(hearts_ew) == 2


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
