import random
from rpgutils import rpg_load_data, apply_damage_modifiers, rpg_save_data, DAZED_PENALTY
from globals import RPG_ITEMS_FILE
import json

def template(scene, attacker_uid, target_uid):
    """
    Template skill with all modular blocks for easy copy/paste.
    Remove blocks you don't need, modify values as needed.
    """
    from rpgutils import rpg_load_data, rpg_save_data, apply_damage_modifiers, make_saving_throw, DAZED_PENALTY
    from globals import RPG_ITEMS_FILE
    import json
    import random

    # ---------------------------------------
    # BLOCK 1: BASIC DATA SETUP (ALWAYS NEEDED)
    # ---------------------------------------
    chars = rpg_load_data()
    is_player = attacker_uid in chars
    attacker_data = scene.enemies_data.get(attacker_uid) or chars.get(attacker_uid)
    target_data   = scene.enemies_data.get(target_uid) or chars.get(target_uid)

    attacker_name = attacker_data.get('name', attacker_uid)
    target_name   = target_data.get('name', target_uid)

    # ---------------------------------------
    # BLOCK 2: PLAYER-ONLY RESTRICTIONS
    # ---------------------------------------
    if is_player:
        
        # STAMINA COST CHECK 
        stamina = attacker_data.get("current_stamina", 0)
        stamina_cost = 3  # Modify this value
        if stamina < stamina_cost:
            return f"{attacker_name} doesn't have enough stamina to use [SKILL NAME]! ({stamina_cost} required)"
        
        # MANA COST CHECK 
        mana = attacker_data.get("current_mana", 0)
        mana_cost = 2  # Modify this value
        if mana < mana_cost:
            return f"{attacker_name} doesn't have enough mana to use [SKILL NAME]! ({mana_cost} required)"
        
        # EQUIPMENT REQUIREMENTS 
        eq = attacker_data.get("equipment", {})
        main = eq.get("mainhand", "").lower().replace(" ", "_")
        off  = eq.get("offhand", "").lower().replace(" ", "_")

        items = json.load(open(RPG_ITEMS_FILE))
        weapons = items.get("weapons", {})
        armor_items = items.get("armor", {})

        main_weapon = weapons.get(main, {})
        off_weapon  = weapons.get(off, {})
        main_armor  = armor_items.get(main, {})
        off_armor   = armor_items.get(off, {})

        # WEAPON TYPE REQUIREMENTS (pick one or combine) 
        
        # Melee weapon requirement
        has_melee = (main_weapon.get("range") == "melee" or 
                    off_weapon.get("range") == "melee")
        if not has_melee:
            return f"{attacker_name} needs a melee weapon to use [SKILL NAME]!"
        
        # Ranged weapon requirement
        has_ranged = (main_weapon.get("range") == "ranged" or 
                     off_weapon.get("range") == "ranged")
        if not has_ranged:
            return f"{attacker_name} needs a ranged weapon to use [SKILL NAME]!"
        
        # Specific damage type requirement
        required_type = "slashing"  # MODIFY: slashing, piercing, bludgeoning, etc.
        has_type = (main_weapon.get("type") == required_type or 
                   off_weapon.get("type") == required_type)
        if not has_type:
            return f"{attacker_name} needs a {required_type} weapon to use [SKILL NAME]!"
        
        # Shield requirement
        has_shield = ("shield" in main.lower() or "shield" in off.lower())
        if not has_shield:
            return f"{attacker_name} needs a shield to use [SKILL NAME]!"
        
        # Spellcasting focus requirement
        has_focus = (main_weapon.get("category") == "spellcasting" or 
                    off_weapon.get("category") == "spellcasting")
        if not has_focus:
            return f"{attacker_name} needs a spellcasting focus to use [SKILL NAME]!"

        #  DEDUCT RESOURCES 
        attacker_data["current_stamina"] = stamina - stamina_cost
        attacker_data["current_mana"] = mana - mana_cost
        chars[attacker_uid] = attacker_data
        rpg_save_data(chars)

    # ---------------------------------------
    # BLOCK 3: SAVING THROW (for effects that can be resisted)
    # ---------------------------------------
    save_dc = 12  # Modify this value
    save_type = "fortitude"  # MODIFY: fortitude, willpower, etc.
    
    save_success, save_msg = make_saving_throw(scene, target_uid, save_type, save_dc)
    if save_success:
        return f"{attacker_name} uses [SKILL NAME] on {target_name}! {save_msg} The effect is resisted!"

    # ---------------------------------------
    # BLOCK 4: ATTACK ROLL (for skills that require hitting)
    # ---------------------------------------
    
    # CALCULATE ATTACK BONUS 
    if is_player:
        # Get weapon stat or default to strength
        weapon_data = main_weapon if main_weapon else off_weapon
        raw_stat = weapon_data.get('stat', 'strength')
        stat_key = raw_stat.capitalize()
        stat_value = attacker_data.get('stats', {}).get(stat_key, 0)
        bonus = stat_value // 2
        
        # Apply dazed penalty if applicable
        if 'dazed' in scene.conditions.get(attacker_uid, {}):
            bonus -= DAZED_PENALTY
    else:
        # Enemy attack bonus
        bonus = attacker_data.get("attack_bonus", 0)
        if 'dazed' in scene.conditions.get(attacker_uid, {}):
            bonus -= DAZED_PENALTY

    # ROLL ATTACK 
    roll = random.randint(1, 10)
    total = roll + bonus
    armor = target_data.get('armor', 10)
    
    attack_msg = f"{attacker_name} attacks {target_name} with [SKILL NAME] ({roll}+{bonus}={total} vs AC {armor}). "

    if total < armor:
        return attack_msg + "Miss!"

    # ---------------------------------------
    # BLOCK 5: DAMAGE CALCULATION
    # ---------------------------------------
    
    if is_player:
        weapon_data = main_weapon if main_weapon else off_weapon
        
        # WEAPON DAMAGE 
        dmg_min = weapon_data.get('damage', {}).get('min', 1)
        dmg_max = weapon_data.get('damage', {}).get('max', 1)
        dmg_type = weapon_data.get('type', 'bludgeoning')
        
        # CUSTOM DAMAGE (instead of weapon) 
        dmg_min = 2  # MODIFY THESE VALUES
        dmg_max = 8
        dmg_type = "fire"  # MODIFY: fire, cold, lightning, etc.
        
        # DAMAGE MULTIPLIERS 
        damage_multiplier = 2  # MODIFY: 1.5 for 50% more, 2 for double, etc.
        dmg_min = int(dmg_min * damage_multiplier)
        dmg_max = int(dmg_max * damage_multiplier)
        
    else:
        # Enemy damage
        dmg_min = attacker_data.get("damage_min", 1)
        dmg_max = attacker_data.get("damage_max", 4)
        dmg_type = attacker_data.get("type", "bludgeoning")

    # ROLL AND APPLY DAMAGE 
    base_damage = random.randint(dmg_min, dmg_max)
    final_damage = apply_damage_modifiers(scene, target_uid, base_damage, dmg_type)
    
    scene.hp_map[target_uid] -= final_damage
    scene.hp_map[target_uid] = max(scene.hp_map[target_uid], 0)
    scene._last_attacker = attacker_name
    
    damage_msg = f"Hit! {final_damage} {dmg_type} damage."

    # ---------------------------------------
    # BLOCK 6: MULTI-TARGET DAMAGE (for AoE skills)
    # ---------------------------------------
    
    # Choose target group (enemies if player, friendlies if enemy)
    if is_player:
        frontline = scene.enemy_frontline
        backline  = scene.enemy_backline
    else:
        frontline = scene.friendly_frontline
        backline  = scene.friendly_backline
    
    # Target selection options:
    targets = frontline + backline  # All enemies/allies
    targets = frontline if frontline else backline  # Frontline first, then back
    targets = [target_uid]  # Just the original target
    
    if not targets:
        return f"{attacker_name} uses [SKILL NAME], but there are no valid targets!"

    results = []
    for tid in targets:
        # Repeat attack roll and damage for each target
        # (copy blocks 4 and 5 here with tid instead of target_uid)
        pass

    # ---------------------------------------
    # BLOCK 7: CONDITION EFFECTS
    # ---------------------------------------
    
    # APPLY CONDITIONS TO TARGET 
    condition_name = "dazed"  # MODIFY: bleeding, dazed, etc.
    condition_duration = 3    # MODIFY: number of turns
    
    scene.conditions.setdefault(target_uid, {})[condition_name] = condition_duration
    condition_msg = f" {target_name} is {condition_name} for {condition_duration} turns!"
    
    # APPLY CONDITIONS TO SELF 
    self_condition = "blessed"  # MODIFY: blessed, enraged, etc.
    self_duration = 2          # MODIFY: number of turns
    
    scene.conditions.setdefault(attacker_uid, {})[self_condition] = self_duration
    self_condition_msg = f" {attacker_name} becomes {self_condition}!"

    # ---------------------------------------
    # BLOCK 8: HEALING EFFECTS
    # ---------------------------------------
    
    # HEAL TARGET 
    heal_min = 5  # MODIFY THESE VALUES
    heal_max = 15
    heal_amount = random.randint(heal_min, heal_max)
    
    # Get max HP for healing cap
    if target_uid in chars:
        max_hp = chars[target_uid].get('max_hp', 100)
    else:
        max_hp = scene.hp_range_map.get(target_uid, (100, 100))[1]
    
    scene.hp_map[target_uid] = min(scene.hp_map[target_uid] + heal_amount, max_hp)
    heal_msg = f"{target_name} is healed for {heal_amount} HP!"
    
    # HEAL SELF 
    if attacker_uid in chars:
        max_hp = chars[attacker_uid].get('max_hp', 100)
    else:
        max_hp = scene.hp_range_map.get(attacker_uid, (100, 100))[1]
    
    scene.hp_map[attacker_uid] = min(scene.hp_map[attacker_uid] + heal_amount, max_hp)
    self_heal_msg = f"{attacker_name} is healed for {heal_amount} HP!"

    # ---------------------------------------
    # BLOCK 9: MOVEMENT EFFECTS
    # ---------------------------------------
    
    # FORCE TARGET MOVEMENT 
    if target_uid in scene.friendly_frontline:
        scene.friendly_frontline.remove(target_uid)
        scene.friendly_backline.append(target_uid)
        movement_msg = f"{target_name} is pushed to the backline!"
    elif target_uid in scene.friendly_backline:
        scene.friendly_backline.remove(target_uid)
        scene.friendly_frontline.append(target_uid)
        movement_msg = f"{target_name} is pulled to the frontline!"
    elif target_uid in scene.enemy_frontline:
        scene.enemy_frontline.remove(target_uid)
        scene.enemy_backline.append(target_uid)
        movement_msg = f"{target_name} is pushed to the backline!"
    elif target_uid in scene.enemy_backline:
        scene.enemy_backline.remove(target_uid)
        scene.enemy_frontline.append(target_uid)
        movement_msg = f"{target_name} is pulled to the frontline!"
    
    # SELF MOVEMENT 
    if attacker_uid in scene.friendly_frontline:
        scene.friendly_frontline.remove(attacker_uid)
        scene.friendly_backline.append(attacker_uid)
        self_movement_msg = f"{attacker_name} retreats to the backline!"
    elif attacker_uid in scene.friendly_backline:
        scene.friendly_backline.remove(attacker_uid)
        scene.friendly_frontline.append(attacker_uid)
        self_movement_msg = f"{attacker_name} charges to the frontline!"

    # ---------------------------------------
    # BLOCK 10: COOLDOWN (USUALLY NEEDED)
    # ---------------------------------------
    cooldown_turns = 4  # Modify this value
    scene.cooldowns.setdefault(attacker_uid, {})["template"] = cooldown_turns  # CHANGE "template" to skill name

    # ---------------------------------------
    # BLOCK 11: RETURN MESSAGE ASSEMBLY
    # ---------------------------------------
    
    # SIMPLE RETURN (pick one) 
    return f"{attacker_name} uses [SKILL NAME] on {target_name}!"
    
    # ATTACK + DAMAGE RETURN 
    return attack_msg + damage_msg
    
    # COMPLEX RETURN (combine multiple effects) 
    full_message = f"{attacker_name} uses [SKILL NAME]! "
    if 'damage_msg' in locals():
        full_message += damage_msg
    if 'condition_msg' in locals():
        full_message += condition_msg
    if 'heal_msg' in locals():
        full_message += f" {heal_msg}"
    if 'movement_msg' in locals():
        full_message += f" {movement_msg}"
    
    return full_message

# ABILITIES WARRIOR
#
# TIER 1
#

#rend that applies bleeding for two turns
def rend(scene, attacker_uid, target_uid):
    from rpgutils import rpg_load_data, rpg_save_data  # ensure these are imported

    chars = rpg_load_data()
    is_player = attacker_uid in chars
    attacker_data = scene.enemies_data.get(attacker_uid) or chars.get(attacker_uid)
    target_data   = scene.enemies_data.get(target_uid) or chars.get(target_uid)

    attacker_name = attacker_data.get('name', attacker_uid)
    target_name   = target_data.get('name', target_uid)

    # ——— Player-only restrictions ———
    if is_player:
        # Stamina cost
        stamina = attacker_data.get("stamina", 0)
        if stamina < 3:
            return f"{attacker_name} doesn't have enough stamina to use Rend! (3 required)"
        
        # Melee weapon requirement
        eq = attacker_data.get("equipment", {})
        main = eq.get("mainhand", "").lower().replace(" ", "_")
        off  = eq.get("offhand", "").lower().replace(" ", "_")

        items = json.load(open(RPG_ITEMS_FILE))
        weapons = items.get("weapons", {})

        main_data = weapons.get(main, {})
        off_data  = weapons.get(off, {})

        # Check for melee weapon
        has_melee = False
        if main_data.get("range") == "melee":
            has_melee = True
        elif off_data.get("range") == "melee":
            has_melee = True

        if not has_melee:
            return f"{attacker_name} needs a melee weapon to use Rend!"

        # Deduct stamina
        attacker_data["stamina"] = stamina - 3
        chars[attacker_uid] = attacker_data
        rpg_save_data(chars)

    # Apply bleeding condition (2 turns)
    scene.conditions.setdefault(target_uid, {})["bleeding"] = 2

    # Apply cooldown
    scene.cooldowns.setdefault(attacker_uid, {})["rend"] = 3  # 3-turn cooldown

    return f"{attacker_name} rends {target_name}, causing bleeding!"


def shield_bash(scene, attacker_uid, target_uid):
    from rpgutils import rpg_load_data, rpg_save_data  # ensure these are imported if not already

    chars = rpg_load_data()
    is_player = attacker_uid in chars
    attacker_data = scene.enemies_data.get(attacker_uid) or chars.get(attacker_uid)
    target_data   = scene.enemies_data.get(target_uid) or chars.get(target_uid)

    attacker_name = attacker_data.get('name', attacker_uid)
    target_name   = target_data.get('name', target_uid)

    # ——— Player-only restrictions ———
    if is_player:
        # Stamina cost
        stamina = attacker_data.get("stamina", 0)
        if stamina < 2:
            return f"{attacker_name} doesn't have enough stamina to use Shield Bash! (2 required)"
        
        # Shield requirement
        eq = attacker_data.get("equipment", {})
        main = eq.get("mainhand", "").lower().replace(" ", "_")
        off  = eq.get("offhand", "").lower().replace(" ", "_")

        items = json.load(open(RPG_ITEMS_FILE))
        armor_items = items.get("armor", {})

        main_data = armor_items.get(main, {})
        off_data  = armor_items.get(off, {})

        # Check for shield (shields are in armor category with offhand slot)
        has_shield = False
        if "shield" in main.lower():
            has_shield = True
        elif "shield" in off.lower():
            has_shield = True

        if not has_shield:
            return f"{attacker_name} needs a shield to use Shield Bash!"

        # Deduct stamina
        attacker_data["stamina"] = stamina - 2
        chars[attacker_uid] = attacker_data
        rpg_save_data(chars)

    # Apply dazed condition (2 turns)
    scene.conditions.setdefault(target_uid, {})["dazed"] = 2
    scene._last_attacker = attacker_name

    # Apply cooldown
    scene.cooldowns.setdefault(attacker_uid, {})["shield_bash"] = 3  # 3-turn cooldown

    return f"{attacker_name} bashes {target_name} with their shield, leaving them dazed!"

#attack that targets frontline first then backline
def cleave(scene, attacker_uid, target_uid=None):
    chars = rpg_load_data()
    is_player = attacker_uid in chars
    attacker_data = chars.get(attacker_uid) or scene.enemies_data.get(attacker_uid, {})
    attacker_name = attacker_data.get("name", attacker_uid)

    # Player-only restrictions
    if is_player:
        # Stamina cost
        stamina = attacker_data.get("stamina", 0)
        if stamina < 4:
            return f"{attacker_name} doesn't have enough stamina to cleave! (4 required)"

        # Weapon requirements: melee + slashing
        eq = attacker_data.get("equipment", {})
        main = eq.get("mainhand", "").lower().replace(" ", "_")
        off  = eq.get("offhand", "").lower().replace(" ", "_")

        items = json.load(open(RPG_ITEMS_FILE))
        weapons = items.get("weapons", {})

        main_data = weapons.get(main, {})
        off_data  = weapons.get(off, {})

        weapon_data = None
        if main_data.get("type") == "slashing" and main_data.get("range") == "melee":
            weapon_data = main_data
        elif off_data.get("type") == "slashing" and off_data.get("range") == "melee":
            weapon_data = off_data

        if not weapon_data:
            return f"{attacker_name} needs a melee slashing weapon to cleave!"

        # Deduct stamina
        attacker_data["stamina"] = stamina - 4
        chars[attacker_uid] = attacker_data
        rpg_save_data(chars)

    else:
        # Enemy path simplified check
        if attacker_data.get("type") == "slashing":
            weapon_data = {"type": "slashing"}
        else:
            weapon_data = None

    if not weapon_data:
        return f"{attacker_name} tries to cleave, but lacks the proper weapon!"

    # Choose target group
    frontline = scene.enemy_frontline if is_player else scene.friendly_frontline
    backline  = scene.enemy_backline if is_player else scene.friendly_backline
    targets = frontline if frontline else backline
    if not targets:
        return f"{attacker_name} swings wildly, but there are no targets!"

    results = []
    for tid in targets:
        target_data = scene.enemies_data.get(tid) or chars.get(tid, {})
        target_name = target_data.get("name", tid)
        armor = target_data.get("armor", 10)

        # Use player's stat for attack bonus
        if is_player:
            stat_key = weapons.get(main, {}).get("stat", "strength").capitalize()
            bonus = attacker_data.get("stats", {}).get(stat_key, 0) // 2
        else:
            bonus = attacker_data.get("attack_bonus", 0)
            
        if "dazed" in scene.conditions.get(attacker_uid, {}):
            bonus -= DAZED_PENALTY

        roll = random.randint(1, 10)
        total = roll + bonus
        msg = f"{attacker_name} cleaves at {target_name} ({roll}+{bonus}={total} vs AC {armor}). "

        if total >= armor:
            if is_player:
                dmg_min = weapons.get(main, {}).get("damage", {}).get("min", 1)
                dmg_max = weapons.get(main, {}).get("damage", {}).get("max", 4)
                dmg_type = weapons.get(main, {}).get("type", "slashing")
            else:
                dmg_min = attacker_data.get("damage_min", 1)
                dmg_max = attacker_data.get("damage_max", 4)
                dmg_type = attacker_data.get("type", "slashing")

            dmg = random.randint(dmg_min, dmg_max)
            final_dmg = apply_damage_modifiers(scene, tid, dmg, dmg_type)
            scene.hp_map[tid] -= final_dmg
            scene.hp_map[tid] = max(scene.hp_map[tid], 0)
            msg += f"Hit! {final_dmg} {dmg_type} damage."
            scene._last_attacker = attacker_name
        else:
            msg += "Miss!"

        results.append(msg)

    return "\n".join(results)


#rend that applies bleeding for two turns
def power_strike(scene, attacker_uid, target_uid):
    from rpgutils import rpg_load_data, rpg_save_data  # ensure these are imported

    chars = rpg_load_data()
    is_player = attacker_uid in chars
    attacker_data = scene.enemies_data.get(attacker_uid) or chars.get(attacker_uid)
    target_data   = scene.enemies_data.get(target_uid) or chars.get(target_uid)

    attacker_name = attacker_data.get('name', attacker_uid)
    target_name   = target_data.get('name', target_uid)

    # Player-only restrictions
    if is_player:
        # Stamina cost
        stamina = attacker_data.get("current_stamina", 0)
        if stamina < 4:
            return f"{attacker_name} doesn't have enough stamina to use Power Strike! (4 required)"
        
        # Melee weapon requirement
        eq = attacker_data.get("equipment", {})
        main = eq.get("mainhand", "").lower().replace(" ", "_")

        items = json.load(open(RPG_ITEMS_FILE))
        weapons = items.get("weapons", {})
        main_data = weapons.get(main, {})

        # Check for melee weapon
        if main_data.get("range") != "melee":
            return f"{attacker_name} needs a melee weapon to use Power Strike!"

        # Deduct stamina
        attacker_data["current_stamina"] = stamina - 4
        chars[attacker_uid] = attacker_data
        rpg_save_data(chars)

        # Calculate attack bonus
        raw_stat = main_data.get('stat', 'strength')
        stat_key = raw_stat.capitalize()
        stat_value = attacker_data.get('stats', {}).get(stat_key, 0)
        bonus = stat_value // 2
        if 'dazed' in scene.conditions.get(attacker_uid, {}):
            bonus -= DAZED_PENALTY

        # Roll attack
        roll = random.randint(1, 10)
        total = roll + bonus
        armor = target_data.get('armor', 10)
        
        result = f"{attacker_name} power strikes {target_name} ({roll}+{bonus}={total} vs AC {armor}). "

        # Check if attack hits
        if total >= armor:
            # Double weapon damage
            dmg_min = main_data.get('damage', {}).get('min', 1) * 2
            dmg_max = main_data.get('damage', {}).get('max', 1) * 2
            dmg = random.randint(dmg_min, dmg_max)
            dmg_type = main_data.get('type', 'bludgeoning')
            
            final_dmg = apply_damage_modifiers(scene, target_uid, dmg, dmg_type)
            scene.hp_map[target_uid] -= final_dmg
            scene.hp_map[target_uid] = max(scene.hp_map[target_uid], 0)
            
            # Apply dazed condition (3 turns)
            scene.conditions.setdefault(target_uid, {})["dazed"] = 3
            scene._last_attacker = attacker_name
            
            result += f"Hit! {final_dmg} {dmg_type} damage and dazed for 3 turns!"
        else:
            result += "Miss!"

    else:
        # Enemy version simplified
        bonus = attacker_data.get("attack_bonus", 0)
        if 'dazed' in scene.conditions.get(attacker_uid, {}):
            bonus -= DAZED_PENALTY

        roll = random.randint(1, 10)
        total = roll + bonus
        armor = target_data.get('armor', 10)
        
        result = f"{attacker_name} power strikes {target_name} ({roll}+{bonus}={total} vs AC {armor}). "

        if total >= armor:
            # Double enemy damage
            dmg_min = attacker_data.get("damage_min", 1) * 2
            dmg_max = attacker_data.get("damage_max", 4) * 2
            dmg = random.randint(dmg_min, dmg_max)
            dmg_type = attacker_data.get("type", "bludgeoning")
            
            final_dmg = apply_damage_modifiers(scene, target_uid, dmg, dmg_type)
            scene.hp_map[target_uid] -= final_dmg
            scene.hp_map[target_uid] = max(scene.hp_map[target_uid], 0)
            
            # Apply dazed condition (3 turns)
            scene.conditions.setdefault(target_uid, {})["dazed"] = 3
            scene._last_attacker = attacker_name
            
            result += f"Hit! {final_dmg} {dmg_type} damage and dazed for 3 turns!"
        else:
            result += "Miss!"

    # Apply cooldown
    scene.cooldowns.setdefault(attacker_uid, {})["power_strike"] = 5  # 5-turn cooldown

    return result

# CONDITION TICKERS
# #
# #
# #
# #
# # 
def bleeding(scene, target_uid):

    base_damage = random.randint(1, 3)
    damage_type = "bleeding"  
    final_damage = apply_damage_modifiers(scene, target_uid, base_damage, damage_type)

    scene.hp_map[target_uid] -= final_damage
    scene.hp_map[target_uid] = max(scene.hp_map[target_uid], 0)

    target_data = scene.enemies_data.get(target_uid) or rpg_load_data().get(target_uid)
    target_name = target_data.get('name', target_uid)

    return f"{target_name} takes {final_damage} bleeding damage!"

def dazed(scene, target_uid):
    """Dazed reduces to-hit chance. No message needed unless desired."""
    return None  
