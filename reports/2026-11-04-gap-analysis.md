# Contested passes with no meaning: gap analysis

2026-11-04, on main at 9c80080 (PR #62 merged). Research first; the two fixes it led to are under "What came of it".

## The short answer

Most contested passes are deliberate. A rule looked at the hand and decided to pass. About 70% come from an explicit GIB rule, 26% from the old fallback system, and 4% from GIB's generic catch-all. I costed every pass on a hand with values (10+ HCP or a six-card suit) against the natural alternatives. Very few groups gain when we bid instead, and the gains mostly shrink on fresh deals. That matches the October handoff study.

There is **one real "no meaning" gap that is worth fixing**: the robots read the opponents' **transfer suit as the opponents' own suit**. There are also two small ones: a pass of partner's responsive double, and the 1♠ (2NT) 3♣ case, which the other thread already owns. Everything else is about thresholds, not missing meanings, and the conservative rule argues against loosening those.

## Ranked gaps

The frequency column counts passes on hands with values, per 100 boards, from a survey of 6,800 fresh boards. The cost columns show the mean gain of the best natural alternative over the pass, from the passer's side. "800 solved" means the library plus training deals, 16 boards each, with t computed over deals. "Fresh" means one new deal per instance, solved double dummy with the Rust engine. "Experts" is the share of the 1996-2002 championship players who did something other than pass, with the same hand at the same point.

| # | Situation | Why the robot passes | Per 100 boards | 800 solved | Fresh | Experts act |
|---|---|---|---|---|---|---|
| 1 | **Their 1NT, then a transfer**: (1NT) P (2♦) P (2♥) P (P) ?, (1NT) P (2♥) ?, and similar | `_their_suits` counts the artificial transfer suit as theirs. A hand with 5-6 diamonds (or AKQxx in hearts over a heart transfer) has no suit it is allowed to bid, so it falls to "No action." (`gib:_defend:4540`) | ~0.9 affected (2.3 for the whole family) | balancing X **+210, t 2.5** (11 deals) | X +63 (t 1.0), own suit +52 (t 1.0), 37 deals | 20% in the balancing seat |
| 2 | **Partner's responsive double passed**: (1♣) X (2♣) X (P) ? | GIB has no rule here, and the fallback reads partner's X as penalty and passes (`ai:_previous_system:1426`) | 0.24 | not measurable (the menu had no "bid a suit" answer) | not enough cases (1) | n/a |
| 3 | **Partner's cuebid over Unusual 2NT**: 1♠ (2NT) 3♣ (P) ? | Being fixed in a separate fix ("Stop passing partner's cuebid over 2NT") (`ai:_place:526`) | 0.04 | n/a | n/a | n/a |
| 4 | Sacrifice over their game raise: (1x) P (4x) ?, (2x) P (4x) ? | Has a rule, but nothing over a game raise | 0.4 | own suit **+320, t 3.6** (9 deals) | own suit +332 (5 deals), +104 (13 deals) | 26-31% |
| 5 | Overcall at 2 after their response: (1x) P (2y) ? | Has a rule: a 2-level overcall needs the OVERCALL_2 range | 0.7 | own suit +222, t 0.9 | own suit +120, t 1.9 (20 deals); X and NT lose | 19% |
| 6 | Over their pre-empt: (3x) ? | Has a rule: needs 12+ HCP at the three level | 1.2 | own suit +111, t 2.4 | own suit +42, t 0.7 | 27% |
| 7 | Overcall at 1 after their response: (1x) P (1y) ? | Has a rule (overcall ranges); most hands hold length in their suits | 4.8 | own suit +98, t 1.7 | own suit +60, t 1.1; X **-75, t -1.8** | 20% |

### Checked and not gaps (the pass is right in this variant)

- **Responder over a 2-level overcall with values**, 1x (2y) ? passing with "Nothing to show." Experts act 52% of the time here. But on fresh deals every alternative loses: X -84 (t -2.0), new suit -115 (t -2.2), NT -139 (t -2.3), over 39 deals.
- **Balancing over their two-level rebid**, (1x) P (1y) P (2x) ?. X gained +96 (t 3.0) on the solved deals, but only +21 (t 0.5) on fresh ones, and experts act just 5%. This matches October, when BALANCE_RAISED lost.
- **Opener after partner's raise** ("No extra values.", `ai:_place:526`, 53 per 100 boards) and **the fallback's lone rebids** (`ai:_rebid_alone`). Neither gained on the solved deals.
- **Passes of partner's transfer completions and invitations** are sign-offs and declines, not gaps (see `partner_art_passes.txt`).

## What came of it

1. **The doubler answers a responsive double** (#2): `gib.RESPONSIVE_ANSWER`, +0.07 and +0.04 a board on seeds 14M and 15M (10,000 fresh deals each). On.
2. **Their transfer suit** (#1): read as the suit it shows, it lost -0.04 a board (t -1.3), because 3♦ straight over 1NT P 2♦ went for 1,470. Limited to the pass-out seat it changed 4 auctions and lost -0.02. Kept by the user's rule: the suit is ours only to 6+ cards and 12+ HCP (`gib.THEIR_SHOWN_SUITS`). That changed 3 auctions in 80,000 boards, +0.01.
3. #4 to #7 were left alone. They are thresholds, not missing meanings, and the robots stay conservative.

## Method and caveats

- `pass_trace.py` tags each robot Pass with the `file:function:line` that returned it, so "no rule fired" and "a rule decided to pass" can be told apart.
- The alternatives were fixed natural calls: X; my longest suit outside theirs with 5+ cards; a raise of partner's suit with 3+; and NT with no singleton. Each was bid at its cheapest legal level, and then the robots finished the auction. A real rule would choose its hands better, so these numbers are rough.
- The 800 solved deals repeat each hand across 16 boards, so they give only 8-22 independent deals per group, and they overstated every gain the fresh deals checked. The fresh check covered 306 deals and 608 solves. A larger fresh run would firm up #1 and #4 if you want them measured before a thread starts.
- In the championship comparison, the robot sits at the experts' table with the expert's hand. The experts' earlier calls carry no robot alerts, so they are read the way a human's would be.

## Files

The scripts are in `research/gap_analysis/` (`pass_trace.py` tags each pass with its source line; `survey.py`, `cost.py`, `analyse_cost.py`, `experts.py`, `compare.py`, `fresh.py`). Their outputs (the survey on seed 30M, the costs on the solved deals, the robots at the championship tables, the fresh double dummy check) were kept outside the repository, in the project's gap-analysis folder. The championship auctions come from github.com/ContractBridge/pbn-files.
