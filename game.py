from __future__ import annotations
from card import Card, SUITS, STRAINS, STRAIN_SYMBOLS, LEVELS, VULNERABILITIES, bid_index, parse_bid
from bridge.auction import PLAYERS, PARTNERS, PARTNERSHIP, clockwise_from, AuctionState
from bridge.trick import legal_plays, resolve_trick
from bridge.scoring import score_contract, score

# Duplicate Bridge Dealer & Vulnerability Rotations (Boards 1-16)
DEALER_ROTATION = ['North', 'East', 'South', 'West']
VUL_ROTATION = [
    'None', 'N/S', 'E/W', 'Both',
    'N/S', 'E/W', 'Both', 'None',
    'E/W', 'Both', 'None', 'N/S',
    'Both', 'None', 'N/S', 'E/W'
]

CONTRACT_LEVEL = 2          # default fallback
TRICKS_NEEDED  = 6 + CONTRACT_LEVEL   # 8

__all__ = [
    'PLAYERS', 'PARTNERS', 'PARTNERSHIP', 'DEALER_ROTATION', 'VUL_ROTATION',
    'CONTRACT_LEVEL', 'TRICKS_NEEDED', 'clockwise_from',
    'legal_plays', 'resolve_trick', 'AuctionState', 'score_contract', 'score'
]
