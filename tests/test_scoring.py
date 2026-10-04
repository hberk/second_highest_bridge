"""Duplicate scoring cases beyond test_bidding.py: minors, slams, doubled and redoubled."""
from __future__ import annotations
import sys
from pathlib import Path

root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from game import score_contract


def contract(level: int, strain: str, doubled: str = 'None', vul: str = 'None',
             side: str = 'N/S') -> dict:
    ns = side == 'N/S'
    return {
        'level': level, 'strain': strain,
        'declarer': 'South' if ns else 'East', 'dummy': 'North' if ns else 'West',
        'leader': 'West' if ns else 'South', 'tricks_needed': 6 + level,
        'trump': strain, 'doubled': doubled, 'vulnerability': vul, 'side': side,
    }


def result(c: dict, declarer_tricks: int) -> dict:
    other = 'E/W' if c['side'] == 'N/S' else 'N/S'
    return score_contract(c, {c['side']: declarer_tricks, other: 13 - declarer_tricks})


def points(c: dict, declarer_tricks: int) -> int:
    return result(c, declarer_tricks)['points']


def test_minor_suit_part_scores_and_game():
    assert points(contract(1, 'C'), 7) == 70        # 20 + 50 part-score
    assert points(contract(3, 'D'), 10) == 130      # 60 + 20 overtrick + 50
    assert points(contract(5, 'C'), 11) == 400      # 100 + 300 game


def test_slam_bonuses():
    assert points(contract(6, 'S'), 12) == 980                 # 180 + 300 + 500
    assert points(contract(6, 'S', vul='Both'), 12) == 1430    # 180 + 500 + 750
    assert points(contract(7, 'NT', vul='N/S'), 13) == 2220    # 220 + 500 + 1500


def test_doubled_contract_made():
    assert points(contract(2, 'H', 'X'), 8) == 470               # 120 + 300 game + 50 insult
    assert points(contract(2, 'H', 'X'), 9) == 570               # +100 overtrick, not vul
    assert points(contract(2, 'H', 'X', vul='Both'), 9) == 870   # 120 + 500 + 50 + 200


def test_redoubled_contract_made():
    assert points(contract(1, 'NT', 'XX'), 7) == 560               # 160 + 300 + 100 insult
    assert points(contract(1, 'NT', 'XX', vul='Both'), 8) == 1160  # 160 + 500 + 100 + 400


def test_doubled_undertricks_not_vulnerable():
    c = contract(4, 'S', 'X')
    assert [points(c, 10 - n) for n in (1, 2, 3, 4)] == [100, 300, 500, 800]


def test_doubled_undertricks_vulnerable():
    c = contract(4, 'S', 'X', vul='Both')
    assert [points(c, 10 - n) for n in (1, 2, 3)] == [200, 500, 800]


def test_redoubled_undertricks():
    assert [points(contract(4, 'S', 'XX'), 10 - n) for n in (1, 2, 3, 4)] == [200, 600, 1000, 1600]
    assert [points(contract(4, 'S', 'XX', vul='Both'), 10 - n) for n in (1, 2)] == [400, 1000]


def test_undoubled_undertricks_vulnerable():
    assert points(contract(4, 'S', vul='N/S'), 8) == 200


def test_vulnerability_is_per_side():
    # E/W being vulnerable doesn't make an N/S declarer vulnerable
    assert points(contract(4, 'S', vul='E/W'), 10) == 420
    assert points(contract(4, 'S', vul='E/W', side='E/W'), 10) == 620


def test_defenders_score_when_contract_fails():
    r = result(contract(3, 'NT', side='E/W'), 8)
    assert r['made'] is False
    assert r['winner'] == 'N/S'
    assert r['undertricks'] == 1
    assert r['points'] == 50


if __name__ == '__main__':
    for name, fn in list(globals().items()):
        if name.startswith('test_'):
            fn()
    print("All scoring tests passed.")
