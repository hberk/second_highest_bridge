"""LIN round trips (bridge/lin.py). Every board must survive to_lin -> from_lin
unchanged, because from_lin rebuilds contract, trick winners and score by
replaying the board: a mismatch means the writer dropped something or the
replay disagrees with the table. Byte-for-byte agreement with the front end's
lin.ts is checked there, against this module's exported output."""
from __future__ import annotations

import random
import re
import sys
from pathlib import Path

root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from bridge.lin import LinError, from_lin, from_lin_file, to_lin, to_lin_file  # noqa: E402
from game import DEALER_ROTATION, VUL_ROTATION  # noqa: E402
from tests.fixtures.export_ts_fixtures import history_record, play_game, random_deal  # noqa: E402

HUMAN_ALERTS = ['Forcing | one round', '5+ ♠, 10-12 HCP!', 'Natural']


def _boards(n: int = 30) -> list[dict]:
    """Seeded boards, half with a random human South whose calls are
    alerted with awkward text: a `|`, a suit symbol, a `!`."""
    rng = random.Random(7)
    out = []
    for i in range(n):
        human = random.Random(i) if i % 2 else None
        game = play_game(random_deal(rng), DEALER_ROTATION[i % 4], VUL_ROTATION[i % 16], human)
        if game['contract'] is None and len(game['calls']) >= 60:
            continue
        if human:
            for k, call in enumerate(game['calls']):
                if call[0] == 'South':
                    call[2] = HUMAN_ALERTS[k % 3]
        out.append(history_record(game, i + 1))
    return out


def _expected(r: dict) -> dict:
    """What a record looks like after LIN: `|` becomes `/` (LIN can't carry it)."""
    alerts = {i: re.sub(r'[|\r\n]+', '/', t).strip() for i, t in r['bid_alerts'].items()}
    return {**r, 'bid_alerts': alerts}


def _played(boards: list[dict]) -> list[dict]:
    return [b for b in boards if len(b['tricks_log']) == 13]


def test_every_board_round_trips_exactly():
    boards = _boards()
    human = [t for b in boards for i, t in b['bid_alerts'].items()
             if b['auction_calls'][i][0] == 'South']
    assert any('|' in t for t in human) and any('♠' in t for t in human)
    for r in boards:
        assert from_lin(to_lin(r)) == _expected(r), r['board_num']


def test_a_session_file_round_trips():
    boards = _boards(12)
    assert from_lin_file(to_lin_file(boards)) == [_expected(b) for b in boards]


def test_writes_bbo_conventions():
    r = _played(_boards())[0]
    lin = to_lin(r)
    assert re.match(r'^pn\|South,West,North,East\|st\|\|md\|[1-4]S', lin)
    assert not re.search(r'mb\|(Pass|X|XX|\dNT)!?\|', lin)
    assert '10' not in re.search(r'md\|([^|]*)\|', lin).group(1)
    assert '10' not in ' '.join(re.findall(r'pc\|([^|]*)\|', lin))


def test_reads_a_bbo_style_record_with_a_claim():
    r = _played(_boards())[0]
    lin = to_lin(r)
    lin = re.sub(r'(md\|[^|,]*,[^|,]*,[^|,]*),[^|]*\|', r'\1,|', lin)   # drop East
    cut = [m.start() for m in re.finditer(r'pc\|', lin)][8 * 4]
    lin = lin[:cut] + f"mc|{r['tricks_taken'][r['contract']['side']]}|"
    back = from_lin(lin.replace('mb|p|', 'mb|P|'))
    assert back['tricks_taken'] == r['tricks_taken']
    assert back['result'] == r['result']
    assert len(back['tricks_log']) == 8
    assert back['initial_hands'] == r['initial_hands']
    # ...and writes the claim back out, so the board round-trips. It used to
    # export as play that just stops, which import refuses.
    again = to_lin(back)
    assert re.search(r'mc\|\d+\|$', again), again[-40:]
    assert from_lin(again)['tricks_taken'] == r['tricks_taken']
    assert to_lin(r).count('mc|') == 0, "a fully played board has no claim"


def test_refuses_a_card_out_of_turn():
    lin = to_lin(_played(_boards())[0])
    a, b = re.findall(r'pc\|([^|]+)\|', lin)[:2]
    swapped = lin.replace(f"pc|{a}|pc|{b}|", f"pc|{b}|pc|{a}|")
    try:
        from_lin(swapped)
    except LinError:
        return
    raise AssertionError('a card played out of turn was accepted')


def test_refuses_a_board_that_stops_before_it_is_finished():
    lin = to_lin(_played(_boards())[0])
    cut = [m.start() for m in re.finditer(r'pc\|', lin)][5 * 4]
    second_call = lin.index('mb|', lin.index('mb|') + 3)
    for broken, why in ((lin[:cut], 'nothing was claimed'),
                        (lin[:second_call], 'auction never finished')):
        try:
            from_lin(broken)
        except LinError as e:
            assert why in str(e), str(e)
        else:
            raise AssertionError(f"an unfinished board was accepted ({why})")


def test_refuses_a_card_dealt_twice():
    try:
        from_lin('md|1SAKQJT98765432H,SA,,|')
    except LinError as e:
        assert 'twice' in str(e)
        return
    raise AssertionError('a duplicated card was accepted')


if __name__ == '__main__':
    for name, fn in list(globals().items()):
        if name.startswith('test_') and callable(fn):
            fn()
            print(f"PASS {name}")
