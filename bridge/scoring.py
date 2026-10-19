from __future__ import annotations


def score_contract(contract: dict, tricks_taken: dict[str, int]) -> dict:
    """Computes exact duplicate Bridge score for a completed hand."""
    declarer_side = contract['side']
    defender_side = 'E/W' if declarer_side == 'N/S' else 'N/S'
    
    vul_str = contract['vulnerability']
    is_vul = (vul_str == 'Both') or (vul_str == declarer_side)
    
    tricks_won = tricks_taken[declarer_side]
    tricks_needed = contract['tricks_needed']
    level = contract['level']
    strain = contract['strain']
    doubled = contract['doubled']
    
    made = (tricks_won >= tricks_needed)
    
    if made:
        overtricks = tricks_won - tricks_needed
        
        # 1. Base trick points
        if strain in ('C', 'D'):
            base_unit = 20
            base_pts = level * 20
        elif strain in ('H', 'S'):
            base_unit = 30
            base_pts = level * 30
        else:  # NT
            base_unit = 30
            base_pts = 40 + (level - 1) * 30
            
        mult = 1 if doubled == 'None' else (2 if doubled == 'X' else 4)
        contract_pts = base_pts * mult
        
        # 2. Game vs Part-score bonus
        is_game = (contract_pts >= 100)
        game_bonus = (500 if is_vul else 300) if is_game else 50
        
        # 3. Slam bonus
        slam_bonus = 0
        if level == 6:
            slam_bonus = 750 if is_vul else 500
        elif level == 7:
            slam_bonus = 1500 if is_vul else 1000
            
        # 4. Insult bonus (for making doubled/redoubled contract)
        insult_bonus = 0
        if doubled == 'X':
            insult_bonus = 50
        elif doubled == 'XX':
            insult_bonus = 100
            
        # 5. Overtrick points
        overtrick_pts = 0
        if overtricks > 0:
            if doubled == 'None':
                overtrick_pts = overtricks * base_unit
            elif doubled == 'X':
                overtrick_pts = overtricks * (200 if is_vul else 100)
            elif doubled == 'XX':
                overtrick_pts = overtricks * (400 if is_vul else 200)
                
        total_pts = contract_pts + game_bonus + slam_bonus + insult_bonus + overtrick_pts
        
        detail_parts = [f"{contract_pts} contract"]
        if overtrick_pts:
            detail_parts.append(f"{overtrick_pts} overtricks")
        detail_parts.append(f"{game_bonus} {'game' if is_game else 'part-score'} bonus")
        if slam_bonus:
            detail_parts.append(f"{slam_bonus} slam bonus")
        if insult_bonus:
            detail_parts.append(f"{insult_bonus} insult bonus")
            
        return {
            'winner': declarer_side,
            'made': True,
            'tricks_won': tricks_won,
            'tricks_needed': tricks_needed,
            'overtricks': overtricks,
            'undertricks': 0,
            'points': total_pts,
            'detail': " + ".join(detail_parts) + f" = {total_pts}",
        }
    else:
        undertricks = tricks_needed - tricks_won
        total_penalty = 0
        
        if not is_vul:
            if doubled == 'None':
                total_penalty = undertricks * 50
            elif doubled == 'X':
                # Non-vul doubled: 100 for 1st, 200 for 2nd and 3rd, 300 for 4th+
                p_table = [100, 200, 200] + [300] * 10
                total_penalty = sum(p_table[:undertricks])
            elif doubled == 'XX':
                # Non-vul redoubled: 2x doubled
                p_table = [200, 400, 400] + [600] * 10
                total_penalty = sum(p_table[:undertricks])
        else:
            if doubled == 'None':
                total_penalty = undertricks * 100
            elif doubled == 'X':
                # Vul doubled: 200 for 1st, 300 each subsequent
                p_table = [200] + [300] * 12
                total_penalty = sum(p_table[:undertricks])
            elif doubled == 'XX':
                # Vul redoubled: 2x doubled
                p_table = [400] + [600] * 12
                total_penalty = sum(p_table[:undertricks])
                
        return {
            'winner': defender_side,
            'made': False,
            'tricks_won': tricks_won,
            'tricks_needed': tricks_needed,
            'overtricks': 0,
            'undertricks': undertricks,
            'points': total_penalty,
            'detail': f"{undertricks} undertrick(s) = {total_penalty} pts to {defender_side}",
        }


def score(ns_tricks: int, trump: str) -> dict:
    """Legacy fallback for backward-compatibility with older tests."""
    fallback_contract = {
        'level': 2,
        'strain': trump,
        'declarer': 'South',
        'dummy': 'North',
        'leader': 'West',
        'tricks_needed': 8,
        'trump': trump,
        'doubled': 'None',
        'vulnerability': 'None',
        'side': 'N/S'
    }
    res = score_contract(fallback_contract, {'N/S': ns_tricks, 'E/W': 13 - ns_tricks})
    res['ns_tricks'] = ns_tricks
    return res

