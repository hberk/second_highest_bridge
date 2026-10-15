"""LIN, BBO's hand-record format: a deal followed by every call and card, as
`key|value|` pairs.

A history record carries far more (contract, trick winners, score), but all of
that is derived. So `to_lin` writes only what LIN holds, and `from_lin`
rebuilds the rest by replaying the board under this game's rules.

That replay is also the validation: a card played out of turn, a revoke, or an
illegal call is refused rather than imported. A LIN from ordinary bridge is
usually refused for that reason: once a trick goes to a different hand under
the second-highest rule, the next lead comes from the "wrong" seat.

The reverse caveat: BBO's own hand viewer applies ordinary rules, so it would
credit our tricks to the wrong side and see leads out of turn.

`frontend/src/lib/lin.ts` is the TypeScript twin. Both must write byte-identical
LIN for the same board; `tests/fixtures/export_ts_fixtures.py` exports this
module's output and the front end's tests compare against it.

Everything `from_lin` returns is built from fixed vocabularies (seats, cards,
legal calls, vulnerabilities) or integers. The ONE free-text field is the
alert, which the app renders only through `call_badge`, which escapes it.
"""
from __future__ import annotations

import re

from card import Card, RANKS, SUITS
from bridge.auction import PLAYERS, PARTNERSHIP, AuctionState, clockwise_from
from bridge.scoring import score_contract
from bridge.trick import legal_plays, resolve_trick

#: LIN lists hands, and numbers the dealer, starting from South.
LIN_SEATS = ['South', 'West', 'North', 'East']
LIN_VUL = {'None': 'o', 'N/S': 'n', 'E/W': 'e', 'Both': 'b'}
VUL_FROM_LIN = {'o': 'None', '0': 'None', '-': 'None', 'n': 'N/S', 'e': 'E/W', 'b': 'Both'}
HAND_SUITS = ['S', 'H', 'D', 'C']
SYMBOL_TO_LIN = {'♠': '!S', '♥': '!H', '♦': '!D', '♣': '!C'}
LIN_TO_SYMBOL = {'S': '♠', 'H': '♥', 'D': '♦', 'C': '♣'}


class LinError(ValueError):
    """A LIN that cannot be read, or that was not played under these rules."""


def _lin_rank(r: str) -> str:
    return 'T' if r == '10' else r


def _rank_from_lin(r: str) -> str:
    return '10' if r == 'T' else r


def _card_key(c: Card) -> str:
    return f"{c.rank}{c.suit}"


def _sorted_hand(hand: list[Card]) -> list[Card]:
    """The order card.deal() uses: spades first, high to low in each suit."""
    return sorted(hand, key=lambda c: (SUITS.index(c.suit), c.value()), reverse=True)


def _lin_call(call: str) -> str:
    if call == 'Pass':
        return 'p'
    if call == 'X':
        return 'd'
    if call == 'XX':
        return 'r'
    return call.replace('NT', 'N')


def _call_from_lin(token: str) -> str:
    t = token.upper()
    if t in ('P', 'PASS'):
        return 'Pass'
    if t in ('D', 'X', 'DBL'):
        return 'X'
    if t in ('R', 'XX', 'RDBL'):
        return 'XX'
    if re.fullmatch(r'[1-7]N', t):
        return f"{t[0]}NT"
    return t


def _alert_to_lin(text: str) -> str:
    """LIN has no escaping: a `|` would end the field early. BBO writes suit
    symbols as !S/!H/!D/!C, so the symbols travel that way too."""
    text = re.sub(r'[|\r\n]+', '/', text)
    return re.sub('[♠♥♦♣]', lambda m: SYMBOL_TO_LIN[m.group(0)], text).strip()


def _alert_from_lin(text: str) -> str:
    return re.sub(r'!([SHDC])', lambda m: LIN_TO_SYMBOL[m.group(1).upper()],
                  text, flags=re.IGNORECASE).strip()


def _hand_to_lin(hand: list[Card]) -> str:
    ordered = _sorted_hand(hand)
    return ''.join(s + ''.join(_lin_rank(c.rank) for c in ordered if c.suit == s)
                   for s in HAND_SUITS)


def _hand_from_lin(text: str) -> list[Card]:
    out: list[Card] = []
    suit = None
    for ch in text.upper():
        if ch in HAND_SUITS:
            suit = ch
        elif suit and _rank_from_lin(ch) in RANKS:
            out.append(Card(suit, _rank_from_lin(ch)))
        else:
            raise LinError(f"Unreadable hand '{text}'")
    return out


def to_lin(record: dict, names: dict[str, str] | None = None) -> str:
    """One board as a single LIN line."""
    parts: list[str] = []

    def add(key: str, value: object = '') -> None:
        parts.append(f"{key}|{value}|")

    names = names or {}
    add('pn', ','.join(re.sub(r'[|,]', ' ', names.get(s, s)) for s in LIN_SEATS))
    add('st')
    dealer = LIN_SEATS.index(record['dealer']) + 1
    add('md', f"{dealer}" + ','.join(_hand_to_lin(record['initial_hands'][s]) for s in LIN_SEATS))
    add('rh')
    add('ah', f"Board {record['board_num']}")
    add('sv', LIN_VUL[record['vulnerability']])
    alerts = record.get('bid_alerts') or {}
    for i, (_, call) in enumerate(record['auction_calls']):
        alert = _alert_to_lin(alerts[i]) if alerts.get(i) else ''
        add('mb', _lin_call(call) + ('!' if alert else ''))
        if alert:
            add('an', alert)
    add('pg')
    for t in record['tricks_log']:
        for _, c in t['plays']:
            add('pc', f"{c.suit}{_lin_rank(c.rank)}")
        add('pg')
    # A board that ended in a claim: write the claim back, or the LIN reads as
    # play that just stops, which from_lin (rightly) refuses.
    contract = record.get('contract')
    if contract and len(record['tricks_log']) < 13:
        add('mc', record['tricks_taken'][contract['side']])
    return ''.join(parts)


def to_lin_file(records: list[dict]) -> str:
    """Several boards, one per line: what a .lin file of a session looks like."""
    return ''.join(to_lin(r) + '\n' for r in records)


def _tokens(text: str) -> list[tuple[str, str]]:
    fields = re.sub(r'\r?\n', '', text).split('|')
    return [(fields[i].strip().lower(), fields[i + 1]) for i in range(0, len(fields) - 1, 2)]


def from_lin_file(text: str) -> list[dict]:
    """Every board in a LIN text. A new board starts at each `md` (or a `qx`
    that follows one), so a whole session file reads in one call."""
    boards: list[list[tuple[str, str]]] = []
    current: list[tuple[str, str]] = []
    saw_deal = False
    for tok in _tokens(text):
        if tok[0] in ('md', 'qx') and saw_deal:
            boards.append(current)
            current = []
            saw_deal = False
        if tok[0] == 'md':
            saw_deal = True
        current.append(tok)
    if saw_deal:
        boards.append(current)
    if not boards:
        raise LinError('No deal (md) found')
    return [_build_record(b, i + 1) for i, b in enumerate(boards)]


def from_lin(text: str) -> dict:
    records = from_lin_file(text)
    if len(records) != 1:
        raise LinError(f"Expected one board, found {len(records)}")
    return records[0]


def _build_record(toks: list[tuple[str, str]], fallback_num: int) -> dict:
    dealer = None
    hands = None
    vulnerability = 'None'
    board_num = fallback_num
    calls: list[str] = []
    alerts: dict[int, str] = {}
    cards: list[Card] = []
    claim = None

    for key, value in toks:
        if key == 'md':
            d = value[:1]
            if d not in ('1', '2', '3', '4'):
                raise LinError(f"Bad dealer in md '{value}'")
            dealer = LIN_SEATS[int(d) - 1]
            hands = _parse_deal(value[1:])
        elif key == 'sv':
            v = VUL_FROM_LIN.get(value.strip().lower())
            if v is None:
                raise LinError(f"Bad vulnerability '{value}'")
            vulnerability = v
        elif key == 'ah':
            m = re.search(r'(\d+)', value)
            if m:
                board_num = int(m.group(1))
        elif key == 'mb':
            raw = value.strip()
            alerted = raw.endswith('!')
            calls.append(_call_from_lin(raw[:-1] if alerted else raw))
        elif key == 'an':
            if not calls:
                raise LinError('Alert (an) before any call')
            if _alert_from_lin(value):
                alerts[len(calls) - 1] = _alert_from_lin(value)
        elif key == 'pc':
            t = value.strip().upper()
            suit, rank = t[:1], _rank_from_lin(t[1:])
            if suit not in SUITS or rank not in RANKS:
                raise LinError(f"Bad card '{value}'")
            cards.append(Card(suit, rank))
        elif key == 'mc':
            try:
                claim = int(value)
            except ValueError:
                raise LinError(f"Bad claim '{value}'") from None
            if not 0 <= claim <= 13:
                raise LinError(f"Bad claim '{value}'")
        # pn, st, rh, pg, qx, nt, ...: presentation only.
    if dealer is None or hands is None:
        raise LinError('No deal (md) found')

    auction = AuctionState(dealer=dealer, vulnerability=vulnerability)
    for call in calls:
        who = auction.current_player()
        if auction.is_complete or call not in auction.legal_calls():
            raise LinError(f"Call {len(auction.calls) + 1} ({call} by {who}): illegal here")
        auction.apply_call(who, call)

    base = {
        'board_num': board_num,
        'dealer': dealer,
        'vulnerability': vulnerability,
        'initial_hands': {p: _sorted_hand(hands[p]) for p in PLAYERS},
        'auction_calls': list(auction.calls),
        'bid_alerts': alerts,
    }
    # A record has to be a finished board: there is nothing to score otherwise.
    if not auction.is_complete:
        raise LinError(f"Board {board_num}: the auction never finished")
    contract = auction.get_contract()
    if contract is None:
        if cards:
            raise LinError('Cards played on a passed-out board')
        return {**base, 'contract': None, 'passed_out': True,
                'tricks_log': [], 'tricks_taken': {'N/S': 0, 'E/W': 0}, 'result': None}

    left = {p: list(hands[p]) for p in PLAYERS}
    tricks_log: list[dict] = []
    taken = {'N/S': 0, 'E/W': 0}
    order = clockwise_from(contract['leader'])
    for i in range(0, len(cards), 4):
        plays: list[tuple[str, Card]] = []
        for k, c in enumerate(cards[i:i + 4]):
            who = order[k]
            if c not in left[who]:
                holder = next((p for p in PLAYERS if c in left[p]), None)
                raise LinError(
                    f"Trick {i // 4 + 1}: {_card_key(c)} is not {who}'s to play"
                    + (f" ({holder} holds it): not played under second-highest rules?"
                       if holder else ' (already played)'))
            led = plays[0][1].suit if plays else None
            if c not in legal_plays(left[who], led):
                raise LinError(f"Trick {i // 4 + 1}: {who} revokes with {_card_key(c)}")
            left[who].remove(c)
            plays.append((who, c))
        if len(plays) < 4:
            break  # a trick in progress at a claim
        winner = resolve_trick(plays, contract['trump'])
        taken[PARTNERSHIP[winner]] += 1
        tricks_log.append({
            'trick_num': len(tricks_log) + 1,
            'leader': plays[0][0],
            'plays': plays,
            'winner': winner,
            'winning_card': dict(plays)[winner],
        })
        order = clockwise_from(winner)

    if claim is not None:
        # `mc` is declarer's side's total for the whole board.
        remaining = 13 - len(tricks_log)
        side = contract['side']
        defence = 'E/W' if side == 'N/S' else 'N/S'
        if claim < taken[side] or claim - taken[side] > remaining:
            raise LinError(f"Claim of {claim} is impossible after {len(tricks_log)} tricks")
        taken[defence] += remaining - (claim - taken[side])
        taken[side] = claim
    elif len(tricks_log) != 13:
        raise LinError(f"Board {board_num}: play stops after {len(tricks_log)} tricks "
                       "and nothing was claimed")
    return {**base, 'contract': contract, 'passed_out': False, 'tricks_log': tricks_log,
            'tricks_taken': taken, 'result': score_contract(contract, taken)}


def _parse_deal(text: str) -> dict[str, list[Card]]:
    """`SAKQ..H..D..C..,<West>,<North>,<East>`: South first; the last hand is
    often left out, and is then whatever the other three don't hold."""
    parts = text.split(',')
    hands = {s: (_hand_from_lin(parts[i].strip()) if i < len(parts) and parts[i].strip() else [])
             for i, s in enumerate(LIN_SEATS)}
    seen: set[str] = set()
    for s in LIN_SEATS:
        for c in hands[s]:
            if _card_key(c) in seen:
                raise LinError(f"{_card_key(c)} dealt twice")
            seen.add(_card_key(c))
    empty = [s for s in LIN_SEATS if not hands[s]]
    if len(empty) == 1 and len(seen) == 39:
        hands[empty[0]] = [Card(s, r) for s in SUITS for r in RANKS
                           if f"{r}{s}" not in seen]
    for s in LIN_SEATS:
        if len(hands[s]) != 13:
            raise LinError(f"{s} holds {len(hands[s])} cards, not 13")
    return hands
