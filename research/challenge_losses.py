"""The robots' challenge losses: what the auction and the card play give away.

Runs the all-robot table on every library deal at all 16 board positions
(dealer and vulnerability from the board number, as the app deals them) and
grades each board two ways:

    par - actual = bidding_loss + play_loss

- From N/S, the side the app grades, so this is what the "Robots" column of
  the match table averages to. When E/W declare, a trick their declarer drops
  is N/S's gain, so the card-play figure nets declarer and defence errors.
- From the declaring side: how much the declaring side's auction and play
  give away against its own par. This is the "declares well, bids badly"
  split docs/CHALLENGE.md describes.

Boards that pass out are left out, as they are of the figure the app quotes.
This is the one source for that figure (the web app's Challenge caption,
docs/CHALLENGE.md): rerun it after any robot change and quote what it prints.

    python research/challenge_losses.py
    python research/challenge_losses.py --deals 50
"""
from __future__ import annotations

import argparse
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import challenge
from game import DEALER_ROTATION, VUL_ROTATION


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--deals', type=int, default=None)
    args = parser.parse_args(argv)

    deal_ids = challenge.deal_ids()[:args.deals] if args.deals else challenge.deal_ids()
    views = {'N/S': ([], []), 'declaring side': ([], [])}
    passed_out = 0
    started = time.perf_counter()
    for deal_id in deal_ids:
        for board in range(1, 17):
            dealer = DEALER_ROTATION[(board - 1) % 4]
            vul = VUL_ROTATION[(board - 1) % 16]
            table = challenge.robot_table(deal_id, dealer, vul)
            if table['contract'] is None:
                passed_out += 1
                continue
            for view, side in (('N/S', 'N/S'), ('declaring side', table['contract']['side'])):
                graded = challenge.grade(deal_id, side, table['contract'],
                                         table['declarer_tricks'], vul)
                views[view][0].append(graded['bidding_loss'])
                views[view][1].append(graded['play_loss'])

    n = len(views['N/S'][0])
    print(f"{len(deal_ids)} deals x 16 boards: {n} boards with a contract, "
          f"{passed_out} passed out, {time.perf_counter() - started:.0f}s")
    for view, (bidding, play) in views.items():
        print(f"graded from {view}:")
        print(f"  lost in the auction:   mean {statistics.mean(bidding):6.1f}, median {statistics.median(bidding):6.1f}")
        print(f"  lost in the card play: mean {statistics.mean(play):6.1f}, median {statistics.median(play):6.1f}")
        print(f"  card play at or above double dummy on {sum(1 for x in play if x <= 0)} of {n} boards; "
              f"auction at or above par on {sum(1 for x in bidding if x <= 0)}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
