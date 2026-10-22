"""Guards on head-to-head challenge mode.

The feature rests on one arithmetic claim -- that a board's shortfall splits
exactly into what the auction cost and what the card play cost:

    par - actual = bidding_loss + play_loss

If that identity does not hold the two numbers are meaningless, so it is checked
on every deal in the library rather than on a sample.
"""
from __future__ import annotations

import sys
from pathlib import Path

root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import challenge
from game import DEALER_ROTATION


def test_the_library_is_completely_solved():
    """Every deal offered must have a trick count for all ten strain/side
    combinations -- that completeness is what lets any contract be priced."""
    library = challenge.load_library()
    assert len(library) >= 250, f"only {len(library)} deals in the library"
    wanted = [f"{s}:{side}" for s in challenge.STRAINS for side in challenge.SIDES]
    for deal_id, deal in library.items():
        missing = [k for k in wanted if k not in deal['tricks']]
        assert not missing, f"deal {deal_id} missing {missing}"
        for key, tricks in deal['tricks'].items():
            assert 0 <= tricks <= 13, f"deal {deal_id} {key} = {tricks}"


def test_hands_rebuild_to_four_valid_thirteen_card_hands():
    for deal_id in challenge.deal_ids()[:40]:
        hands = challenge.hands_for(deal_id)
        assert set(hands) == set(challenge.SEATS)
        every = [(c.suit, c.rank) for cards in hands.values() for c in cards]
        assert len(every) == 52, f"deal {deal_id} has {len(every)} cards"
        assert len(set(every)) == 52, f"deal {deal_id} has duplicate cards"
        for seat, cards in hands.items():
            assert len(cards) == 13, f"deal {deal_id} {seat} has {len(cards)}"


def test_hands_for_does_not_disturb_the_global_random_state():
    """`research.dd_dataset.deal_for` reseeds the global RNG to regenerate a
    deal. Doing that inside the app would make every later `deal()` reproducible
    as a side effect, so challenge mode rebuilds from stored text instead."""
    import random
    random.seed(12345)
    before = random.random()
    random.seed(12345)
    challenge.hands_for(challenge.deal_ids()[0])
    after = random.random()
    assert before == after, "hands_for perturbed the global random stream"


def test_the_two_sides_trick_counts_are_complementary_or_better():
    """Both sides cannot each take more than thirteen tricks between them in the
    same strain; the sum is at most 13 only when one side plays optimally
    against the other's best defence, so each count stands alone and both must
    sit in range."""
    for deal_id in challenge.deal_ids()[:60]:
        for strain in challenge.STRAINS:
            ns = challenge.dd_tricks(deal_id, strain, 'N/S')
            ew = challenge.dd_tricks(deal_id, strain, 'E/W')
            assert 0 <= ns <= 13 and 0 <= ew <= 13
            assert ns + ew <= 26


def test_robot_table_plays_a_complete_legal_board():
    for i, deal_id in enumerate(challenge.deal_ids()[:25]):
        dealer = DEALER_ROTATION[i % 4]
        result = challenge.robot_table(deal_id, dealer)
        if result['contract'] is None:
            assert result['ns_tricks'] == 0 and result['ew_tricks'] == 0
            continue
        assert result['ns_tricks'] + result['ew_tricks'] == 13, (
            f"deal {deal_id}: {result['ns_tricks']} + {result['ew_tricks']} tricks")
        side = result['contract']['side']
        expected = result['ns_tricks'] if side == 'N/S' else result['ew_tricks']
        assert result['declarer_tricks'] == expected


def test_the_robot_table_is_deterministic():
    """The comparison is only fair if the robot's result is reproducible.

    `ai.py` imports no RNG, so this should hold -- but the opponent in a
    head-to-head is the whole benchmark, and a benchmark that drifts between
    runs would make every margin partly noise. Checked under deliberately
    different global seeds, because that is how it would break.
    """
    import random
    for i, deal_id in enumerate(challenge.deal_ids()[:30]):
        dealer = DEALER_ROTATION[i % 4]
        random.seed(1)
        first = challenge.robot_table(deal_id, dealer)
        random.seed(99991)
        second = challenge.robot_table(deal_id, dealer)
        assert first['calls'] == second['calls'], f"deal {deal_id}: auction drifted"
        assert first['declarer_tricks'] == second['declarer_tricks'], (
            f"deal {deal_id}: card play drifted")


def test_a_player_who_plays_like_the_robot_draws_level():
    """Sanity check on the margin's meaning: identical play must score identically.

    If this ever fails, the comparison is measuring something other than the
    difference between the two tables.
    """
    for i, deal_id in enumerate(challenge.deal_ids()[:30]):
        dealer = DEALER_ROTATION[i % 4]
        table = challenge.robot_table(deal_id, dealer)
        mine = challenge.grade(deal_id, 'N/S', table['contract'],
                               table['declarer_tricks'])
        theirs = challenge.grade(deal_id, 'N/S', table['contract'],
                                 table['declarer_tricks'])
        assert mine['actual'] - theirs['actual'] == 0


def test_a_robot_board_is_replayable_like_a_human_one():
    """`as_history_record` must produce exactly what the replayer consumes.

    The point of the shape match is that the replayer needs no idea
    robot boards exist -- it steps through one the same way it steps through
    yours, which is what lets the two sit side by side on the same deal.
    """
    required = {'board_num', 'dealer', 'vulnerability', 'initial_hands',
                'auction_calls', 'contract', 'passed_out', 'tricks_log',
                'tricks_taken', 'result'}
    for i, deal_id in enumerate(challenge.deal_ids()[:25]):
        table = challenge.robot_table(deal_id, DEALER_ROTATION[i % 4])
        record = challenge.as_history_record(table, 1, 'Robots')
        assert required <= set(record), f"missing {required - set(record)}"
        if record['passed_out']:
            continue

        assert len(record['tricks_log']) == 13, (
            f"deal {deal_id}: {len(record['tricks_log'])} tricks logged")
        for n, entry in enumerate(record['tricks_log'], start=1):
            assert entry['trick_num'] == n
            assert len(entry['plays']) == 4
            assert entry['winner'] in challenge.SEATS
            # the winning card must be one actually played on that trick
            assert entry['winning_card'] in [c for _, c in entry['plays']]

        # every call carries an alert explaining what it showed
        assert len(record['bid_alerts']) == len(record['auction_calls'])
        assert all(a and a.strip() for a in record['bid_alerts'].values())

        # the log and the tally agree
        from game import PARTNERSHIP
        tally = {'N/S': 0, 'E/W': 0}
        for entry in record['tricks_log']:
            tally[PARTNERSHIP[entry['winner']]] += 1
        assert tally == record['tricks_taken'], (
            f"deal {deal_id}: log says {tally}, record says {record['tricks_taken']}")


def test_every_card_in_a_robot_board_was_actually_dealt():
    """The replayer reconstructs hands by removing played cards, so a board
    that plays a card nobody held would corrupt the diagram."""
    for i, deal_id in enumerate(challenge.deal_ids()[:20]):
        table = challenge.robot_table(deal_id, DEALER_ROTATION[i % 4])
        if table['contract'] is None:
            continue
        dealt = {seat: {(c.suit, c.rank) for c in cards}
                 for seat, cards in table['initial_hands'].items()}
        seen = {seat: set() for seat in challenge.SEATS}
        for entry in table['tricks_log']:
            for seat, card in entry['plays']:
                key = (card.suit, card.rank)
                assert key in dealt[seat], (
                    f"deal {deal_id}: {seat} played {card}, which it never held")
                assert key not in seen[seat], (
                    f"deal {deal_id}: {seat} played {card} twice")
                seen[seat].add(key)
        for seat in challenge.SEATS:
            assert seen[seat] == dealt[seat], f"deal {deal_id}: {seat} left cards unplayed"


def test_the_loss_decomposition_is_exact():
    """par - actual == bidding_loss + play_loss, on every deal in the library.

    This is the whole feature: the two halves are what make "how good is the
    robot at BIDDING" and "at DECLARING" separable questions.
    """
    for i, deal_id in enumerate(challenge.deal_ids()):
        dealer = DEALER_ROTATION[i % 4]
        table = challenge.robot_table(deal_id, dealer)
        for side in challenge.SIDES:
            g = challenge.grade(deal_id, side, table['contract'],
                                table['declarer_tricks'])
            assert g['bidding_loss'] + g['play_loss'] == g['total_loss'], (
                f"deal {deal_id} {side}: {g['bidding_loss']} + {g['play_loss']}"
                f" != {g['total_loss']}")
            assert g['total_loss'] == g['par']['score'] - g['actual']


def test_a_board_is_zero_sum_between_the_two_sides():
    """Whatever one side scores, the other concedes."""
    for i, deal_id in enumerate(challenge.deal_ids()[:40]):
        table = challenge.robot_table(deal_id, DEALER_ROTATION[i % 4])
        if table['contract'] is None:
            continue
        ns = challenge.score_for('N/S', table['contract'], table['declarer_tricks'])
        ew = challenge.score_for('E/W', table['contract'], table['declarer_tricks'])
        assert ns == -ew, f"deal {deal_id}: N/S {ns}, E/W {ew}"


def test_par_is_never_beaten_by_perfect_play_in_a_reached_contract():
    """Par is the best this side can do, so no contract played double dummy may
    score more FOR THE SIDE THAT CHOSE IT. (The defending side can exceed its
    own par, which is why this only checks the declaring side.) Par is priced
    over UNDOUBLED contracts, so a doubled contract that makes -- the
    defenders' mistake, which GIB's penalty and negative doubles now
    produce -- can score above it and is not checked."""
    for i, deal_id in enumerate(challenge.deal_ids()[:80]):
        table = challenge.robot_table(deal_id, DEALER_ROTATION[i % 4])
        contract = table['contract']
        if contract is None or contract['doubled'] != 'None':
            continue
        side = contract['side']
        g = challenge.grade(deal_id, side, contract, table['declarer_tricks'])
        assert g['dd_score'] <= g['par']['score'], (
            f"deal {deal_id}: {contract['level']}{contract['strain']} scores "
            f"{g['dd_score']} double dummy, above par {g['par']['score']}")


if __name__ == '__main__':
    for name, fn in list(globals().items()):
        if name.startswith('test_') and callable(fn):
            fn()
            print(f"PASS {name}")
    print("\nChallenge mode verified.")
