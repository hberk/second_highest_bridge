"""Export the Python engine's behaviour as JSON, for the TypeScript port to match.

The Svelte front end (frontend/) runs a TypeScript port of card.py, bridge/,
ai.py and challenge.py. `ai.py` is tuned against measured results, so a port
that drifted by one tie-break would quietly invalidate every figure in
docs/BIDDING.md. Python stays the oracle: this script records what it does, and
frontend/src/lib/engine/engine.test.ts must reproduce every call, alert, card,
score and grade exactly.

Rerun whenever the Python engine changes:

    python tests/fixtures/export_ts_fixtures.py

Deals are generated here and stored as text, so the TypeScript side never needs
Python's RNG.

Needs Python 3.12+. From 3.12, sum() over floats is compensated (Neumaier), so
`eval_hand_sh` differs from 3.9-3.11 in the last bit. The port reproduces the
3.12 behaviour -- the deployed one -- and an older interpreter would write
fixtures it cannot match. No decision in the 1,200 fixture games moved, but a
hand landing exactly on a threshold could.
"""
from __future__ import annotations

import json
import os
import random
import re
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import challenge  # noqa: E402
from ai import ai_bid_explained, ai_play, eval_hand_sh, hcp, shown_lengths, visible_hands  # noqa: E402
from bridge import lin  # noqa: E402
from bridge.scoring import score_contract  # noqa: E402
from bridge.solver import replay  # noqa: E402
from card import Card, SUITS, RANKS, STRAINS  # noqa: E402
from game import (AuctionState, DEALER_ROTATION, VUL_ROTATION,  # noqa: E402
                  clockwise_from, legal_plays, resolve_trick)

OUT = ROOT / 'frontend' / 'src' / 'lib' / 'engine' / '__fixtures__'
SEATS = ['North', 'East', 'South', 'West']
VULS = ['None', 'N/S', 'E/W', 'Both']
GUARD = 60


def tok(c: Card) -> str:
    return f"{c.rank}{c.suit}"


def hand_text(hand: list[Card]) -> str:
    return ' '.join(tok(c) for c in hand)


def random_deal(rng: random.Random) -> dict[str, list[Card]]:
    """Same sort order as card.deal(), from a private RNG."""
    deck = [Card(s, r) for s in SUITS for r in RANKS]
    rng.shuffle(deck)
    return {p: sorted(deck[i * 13:(i + 1) * 13],
                      key=lambda c: (SUITS.index(c.suit), c.value()), reverse=True)
            for i, p in enumerate(SEATS)}


def play_game(hands, dealer, vul, rng: random.Random | None):
    """One board the way the web app runs it. With `rng`, South is a random human:
    that reaches auction and play states an all-robot table never produces
    (odd overcalls, doubles, ducked tricks), which is where a port goes wrong."""
    hands = {p: list(h) for p, h in hands.items()}
    auction = AuctionState(dealer=dealer, vulnerability=vul)
    calls = []
    while not auction.is_complete and len(calls) < GUARD:
        who = auction.current_player()
        if rng is not None and who == 'South':
            legal = auction.legal_calls()
            roll = rng.random()
            bids = [c for c in legal if c[0].isdigit() and int(c[0]) <= 4]
            if roll < 0.12 and 'X' in legal:
                call = 'X'
            elif roll < 0.35 and bids:
                call = rng.choice(bids[:8])
            else:
                call = 'Pass'
            why = None
        else:
            call, why = ai_bid_explained(who, hands[who], auction)
        calls.append([who, call, why, auction.legal_calls()])
        auction.apply_call(who, call)

    contract = auction.get_contract()
    record = {'dealer': dealer, 'vul': vul,
              'hands': {p: hand_text(h) for p, h in hands.items()},
              'calls': calls, 'contract': contract, 'plays': [],
              'tricks': None, 'result': None}
    if contract is None:
        return record

    trump, dummy = contract['trump'], contract['dummy']
    leader = contract['leader']
    # What the robots' bidding showed (a random South's calls have no alert).
    shown = shown_lengths([(w, c) for w, c, _, _ in calls],
                          {i: why for i, (_, _, why, _) in enumerate(calls) if why})
    played: list[Card] = []
    history: list = []
    taken = {'N/S': 0, 'E/W': 0}
    for _ in range(13):
        trick = []
        for seat in clockwise_from(leader):
            led = trick[0][1].suit if trick else None
            if rng is not None and seat == 'South':
                card = rng.choice(legal_plays(hands[seat], led))
            else:
                card = ai_play(seat, hands[seat], trick, trump, played,
                               visible=visible_hands(seat, contract, hands),
                               history=history, shown=shown)
            hands[seat].remove(card)
            trick.append((seat, card))
            record['plays'].append([seat, tok(card)])
        winner = resolve_trick(trick, trump)
        taken['N/S' if winner in ('North', 'South') else 'E/W'] += 1
        played.extend(c for _, c in trick)
        history.append(list(trick))
        leader = winner
    record['tricks'] = taken
    record['result'] = score_contract(contract, taken)
    return record


def _game(i: int, hands) -> dict:
    human = random.Random(i) if i % 2 else None
    return play_game(hands, DEALER_ROTATION[i % 4], VUL_ROTATION[i % 16], human)


def export_games(n: int) -> list[dict]:
    # Deals first, in order from the one RNG; then the boards, which share
    # nothing, on every core (the robots search from five cards a hand).
    rng = random.Random(20261003)
    deals = [random_deal(rng) for _ in range(n)]
    with ProcessPoolExecutor(os.cpu_count()) as pool:
        return list(pool.map(_game, range(n), deals, chunksize=8))


def export_evals(games: list[dict]) -> list[dict]:
    out = []
    for g in games[:400]:
        for text in g['hands'].values():
            hand = [Card(t[-1], t[:-1]) for t in text.split()]
            ev = eval_hand_sh(hand)
            out.append({'hand': text, 'hcp': hcp(hand),
                        'honour_pts': ev['honour_pts'],
                        'suit_pts': ev['suit_pts'],
                        'total_pts': ev['total_pts'],
                        'lengths': ev['lengths'],
                        'is_balanced': ev['is_balanced']})
    return out


def export_scoring() -> list[list]:
    """Every contract, doubling, vulnerability and trick count."""
    rows = []
    for level in range(1, 8):
        for strain in STRAINS:
            for doubled in ('None', 'X', 'XX'):
                for vul in VULS:
                    for side in ('N/S', 'E/W'):
                        contract = {'level': level, 'strain': strain, 'side': side,
                                    'tricks_needed': level + 6, 'doubled': doubled,
                                    'vulnerability': vul}
                        for won in range(14):
                            other = 'E/W' if side == 'N/S' else 'N/S'
                            r = score_contract(contract, {side: won, other: 13 - won})
                            rows.append([level, strain, doubled, vul, side, won,
                                         r['winner'], r['made'], r['points'],
                                         r['detail']])
    return rows


def export_challenge() -> list[dict]:
    with ProcessPoolExecutor(os.cpu_count()) as pool:
        return list(pool.map(_challenge_deal, challenge.deal_ids(), chunksize=4))


def _challenge_deal(deal_id: int) -> dict:
    i = deal_id
    dealer = DEALER_ROTATION[i % 4]
    vul = VUL_ROTATION[i % 16]
    table = challenge.robot_table(deal_id, dealer, vul)
    return {
        'deal_id': deal_id, 'dealer': dealer, 'vul': vul,
        'calls': table['calls'],
        'alerts': {str(k): v for k, v in table['alerts'].items()},
        'contract': table['contract'],
        'plays': [[p, tok(c)] for t in table['tricks_log'] for p, c in t['plays']],
        'tricks_taken': table['tricks_taken'],
        'result': table['result'],
        'grade': challenge.grade(deal_id, 'N/S', table['contract'],
                                 table['declarer_tricks'], vul),
        'par': {v: {s: challenge.par(deal_id, s, v) for s in ('N/S', 'E/W')}
                for v in VULS},
        'dd': {f"{st}:{who}": challenge.dd_tricks(deal_id, st, side, seat)
               for st in challenge.STRAINS
               for side, seats in challenge.PARTNERS.items()
               for who, seat in [(side, None), *[(x, x) for x in seats]]},
    }


def history_record(game: dict, board_num: int) -> dict:
    """A games.json record in the hand-history shape (`HistoryRecord` in
    frontend/src/lib/game.svelte.ts), so bridge.lin can write it."""
    hands = {p: [Card(t[-1], t[:-1]) for t in text.split()] for p, text in game['hands'].items()}
    contract = game['contract']
    tricks_log = []
    flat = [(p, Card(t[-1], t[:-1])) for p, t in game['plays']]
    for i in range(0, len(flat), 4):
        plays = flat[i:i + 4]
        winner = resolve_trick(plays, contract['trump'])
        tricks_log.append({'trick_num': i // 4 + 1, 'leader': plays[0][0], 'plays': plays,
                           'winner': winner, 'winning_card': dict(plays)[winner]})
    return {
        'board_num': board_num, 'dealer': game['dealer'], 'vulnerability': game['vul'],
        'initial_hands': hands,
        'auction_calls': [(c[0], c[1]) for c in game['calls']],
        'bid_alerts': {i: c[2] for i, c in enumerate(game['calls']) if c[2]},
        'contract': contract, 'passed_out': contract is None,
        'tricks_log': tricks_log, 'tricks_taken': game['tricks'] or {'N/S': 0, 'E/W': 0},
        'result': game['result'],
    }


def export_lin(games: list[dict]) -> list[dict]:
    """bridge.lin's output for the first 300 boards, which lin.ts must
    reproduce byte for byte: one hand-record format, two implementations."""
    out = []
    for i, g in enumerate(games[:300]):
        if g['contract'] is None and len(g['calls']) >= GUARD:
            continue  # an auction the guard cut off: not a real board
        record = history_record(g, i + 1)
        out.append({'lin': lin.to_lin(record), 'contract': record['contract'],
                    'tricks_taken': record['tricks_taken'], 'result': record['result']})
    return out


def export_hostile_lin(games: list[dict]) -> list[dict]:
    """Odd and hostile LIN, with bridge.lin's verdict on each: lin.ts must
    accept and refuse exactly the same texts, and read the same board number
    and alerts from the ones it accepts."""
    record = next(history_record(g, i + 1) for i, g in enumerate(games)
                  if g['contract'] and len(g['plays']) == 52)
    base = lin.to_lin(record)
    cut = [m.start() for m in re.finditer(r'pc\|', base)][8 * 4]
    claimed = base[:cut] + 'mc|{}|'
    first_call = base.index('mb|')
    end_of_call = base.index('|', first_call + 3) + 1
    if base.startswith('an|', end_of_call):              # after any alert it has: the last one counts
        end_of_call = base.index('|', end_of_call + 3) + 1
    alerted = base[:end_of_call] + 'an|{}|' + base[end_of_call:]

    texts = [
        base,
        '﻿' + base,                                         # byte-order mark
        base.replace(f"sv|{lin.LIN_VUL[record['vulnerability']]}|", 'sv|constructor|'),
        base.replace(f"sv|{lin.LIN_VUL[record['vulnerability']]}|", 'sv|toString|'),
        base.replace(f"sv|{lin.LIN_VUL[record['vulnerability']]}|", 'sv|__proto__|'),
        base.replace('ah|', 'ah|Board ٣ '),                 # an Arabic-Indic three
        re.sub(r'ah\|[^|]*\|', 'ah|Board 99999999999999999999|', base),
        re.sub(r'ah\|[^|]*\|', 'ah|Board 123456|', base),
        alerted.format('x' * 200),
        alerted.format('two\tlines\x07here  !s'),
    ]
    tricks = record['tricks_taken'][record['contract']['side']]
    for claim in (str(tricks), f' {tricks} ', '', '0x5', '1e1', '٥', '14', '-1', '7.0'):
        texts.append(claimed.format(claim))

    out = []
    for text in texts:
        try:
            r = lin.from_lin(text)
            out.append({'lin': text, 'ok': True, 'board_num': r['board_num'],
                        'bid_alerts': {str(k): v for k, v in r['bid_alerts'].items()}})
        except lin.LinError:
            out.append({'lin': text, 'ok': False})
    return out


def export_dd(games: list[dict]) -> list[dict]:
    """The Python solver's card values over the last five tricks of 16 boards.
    The History replayer runs research/solver-rs as WebAssembly; dd.test.ts
    checks it against these, an independent engine, value for value."""
    out = []
    for i, g in enumerate(games):
        if len(out) == 16:
            break
        if g['contract'] is None or len(g['plays']) != 52:
            continue
        record = history_record(g, i + 1)
        decisions = []
        for d in replay.decisions(record, max_cards=5, skip_forced=False):
            values = replay.analyse(d)['values']
            decisions.append({'index': (d.trick_num - 1) * 4 + len(d.trick_so_far),
                              'values': {tok(c): v for c, v in values.items()}})
        out.append({'hands': g['hands'], 'leader': g['contract']['leader'],
                    'strain': g['contract']['strain'], 'plays': g['plays'],
                    'decisions': decisions})
    return out


def write(name: str, data) -> None:
    path = OUT / name
    path.write_text(json.dumps(data, separators=(',', ':'), ensure_ascii=False),
                    encoding='utf-8')
    print(f"{path.relative_to(ROOT)}  {path.stat().st_size // 1024} KB")


def main() -> None:
    if sys.version_info < (3, 12):
        sys.exit("export_ts_fixtures.py needs Python 3.12+ (see the docstring); "
                 "on Windows: ./.venv/Scripts/python.exe")
    OUT.mkdir(parents=True, exist_ok=True)
    games = export_games(1200)
    write('games.json', games)
    write('evals.json', export_evals(games))
    write('scoring.json', export_scoring())
    write('challenge.json', export_challenge())
    write('lin.json', export_lin(games))
    write('lin_hostile.json', export_hostile_lin(games))
    write('dd.json', export_dd(games))


if __name__ == '__main__':
    main()
