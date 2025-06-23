import random
from rpgutils import rpg_load_data, apply_damage_modifiers, rpg_save_data
from globals import RPG_ITEMS_FILE
import json




# ABILITIES WARRIOR
#
#
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

    # ——— Stamina cost for players ———
    if is_player:
        stamina = attacker_data.get("stamina", 0)
        if stamina < 3:
            return f"{attacker_name} doesn’t have enough stamina to use Rend! (3 required)"
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

    # ——— Stamina cost for players ———
    if is_player:
        stamina = attacker_data.get("stamina", 0)
        if stamina < 2:
            return f"{attacker_name} doesn’t have enough stamina to use Shield Bash! (2 required)"
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

    # ——— Stamina Check for players ———
    if is_player:
        stamina = attacker_data.get("stamina", 0)
        if stamina < 4:
            return f"{attacker_name} doesn't have enough stamina to cleave! (4 required)"
        attacker_data["stamina"] = stamina - 4
        chars[attacker_uid] = attacker_data
        rpg_save_data(chars)

    # Determine weapon types from equipment (for players)
    eq = attacker_data.get("equipment", {})
    main = eq.get("mainhand", "").lower().replace(" ", "_")
    off  = eq.get("offhand", "").lower().replace(" ", "_")

    items = json.load(open(RPG_ITEMS_FILE))
    weapons = items.get("weapons", {})

    main_data = weapons.get(main, {})
    off_data  = weapons.get(off, {})

    weapon_data = None
    if main_data.get("type") == "slashing":
        weapon_data = main_data
    elif off_data.get("type") == "slashing":
        weapon_data = off_data
    elif not is_player and attacker_data.get("type") == "slashing":
        weapon_data = {"type": "slashing"}  # fallback for NPCs

    if not weapon_data:
        return f"{attacker_name} tries to cleave, but is not wielding a slashing weapon!"

    # Choose target group
    frontline = scene.enemy_frontline
    backline  = scene.enemy_backline
    targets = frontline if frontline else backline
    if not targets:
        return f"{attacker_name} swings wildly, but there are no targets!"

    results = []
    for tid in targets:
        target_data = scene.enemies_data.get(tid) or chars.get(tid, {})
        target_name = target_data.get("name", tid)
        armor = target_data.get("armor", 10)

        # Use player's stat for attack bonus
        stat_key = weapons.get(main, {}).get("stat", "strength").capitalize()
        bonus = attacker_data.get("stats", {}).get(stat_key, 0) // 2 if is_player else attacker_data.get("attack_bonus", 0)
        if "dazed" in scene.conditions.get(attacker_uid, {}):
            bonus -= 2

        roll = random.randint(1, 10)
        total = roll + bonus
        msg = f"{attacker_name} cleaves at {target_name} ({roll}+{bonus}={total} vs AC {armor}). "

        if total >= armor:
            dmg_min = weapons.get(main, {}).get("damage", {}).get("min", 1)
            dmg_max = weapons.get(main, {}).get("damage", {}).get("max", 4)
            dmg_type = weapons.get(main, {}).get("type", "slashing")

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
    return None  # You could return a string if you want a log message