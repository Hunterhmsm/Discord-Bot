# rpgai.py

import random
from rpgutils import rpg_load_data, apply_damage_modifiers
import rpgskills

# registry of AI handlers by key
AI_HANDLERS: dict[str, callable] = {}

def register(ai_name: str):
    """Decorator to register an AI handler under a given name."""
    def deco(fn):
        AI_HANDLERS[ai_name] = fn
        return fn
    return deco

def resolve_ai(scene, enemy_uid):
    """Look up the AI type in scene.enemies_data and run its handler."""
    cfg   = scene.enemies_data[enemy_uid]
    ai    = cfg.get("AI", "melee")
    handler = AI_HANDLERS.get(ai)
    if handler:
        return handler(scene, enemy_uid)
    else:
        # fallback to no-op
        return None
    
def enemy_attack(scene, attacker_uid, target_uid):
    """Handles enemy basic attack with damage modifiers and conditions like dazed."""
    cfg = scene.enemies_data.get(attacker_uid, {})
    name = cfg.get("name", attacker_uid)

    roll = random.randint(1, 10)
    bonus = cfg.get("attack_bonus", 0)

    # Apply condition penalties
    if 'dazed' in scene.conditions.get(attacker_uid, {}):
        bonus -= 2

    total = roll + bonus
    pc = rpg_load_data().get(target_uid, {})
    armor = pc.get("armor", 10)

    msg = f"{name} attacks {pc.get('name', f'<@{target_uid}>')} ({roll}+{bonus}={total} vs AC {armor}). "

    if total >= armor:
        dmg_min = cfg.get("damage_min", 1)
        dmg_max = cfg.get("damage_max", 4)
        dmg = random.randint(dmg_min, dmg_max)
        dmg_type = cfg.get("type", "slashing")

        final_dmg = apply_damage_modifiers(scene, target_uid, dmg, dmg_type)
        scene.hp_map[target_uid] -= final_dmg
        scene.hp_map[target_uid] = max(scene.hp_map[target_uid], 0)
        scene._last_attacker = name

        msg += f"Hit! {final_dmg} {dmg_type} damage."
    else:
        msg += "Miss!"

    return msg

@register("melee")
def ai_melee(scene, enemy_uid):
    cfg = scene.enemies_data[enemy_uid]
    name = cfg.get("name", enemy_uid)

    targets = scene.friendly_frontline or scene.friendly_backline
    if not targets:
        return (f"{name} looks around but finds no one to attack.", None)

    target_uid = random.choice(targets)
    results = []

    cds = scene.cooldowns.get(enemy_uid, {})
    side_skills = cfg.get("sideaction_skills", [])
    abilities = cfg.get("action_skills", [])
    print(f"[AI DEBUG] Enemy: {enemy_uid}, action_skills: {abilities}, side_skills: {side_skills}, cds: {cds}")

    # --- ACTION ABILITIES ---
    available = [a for a in abilities if a.lower().replace(" ", "_") not in cds]
    if available:
        chosen = random.choice(available)
        func_name = chosen.lower().replace(" ", "_")
        func = getattr(rpgskills, func_name, None)
        if callable(func):
            result = func(scene, enemy_uid, target_uid)
            if result:
                results.append(result)
            scene.cooldowns.setdefault(enemy_uid, {})[func_name] = 2
            scene.actions_used.setdefault(enemy_uid, {})['action'] = True

    else:
        result = enemy_attack(scene, enemy_uid, target_uid)
        results.append(result)

        scene.actions_used.setdefault(enemy_uid, {})['action'] = True

    # --- SIDE ACTION ABILITIES ---
    side_available = [s for s in side_skills if s.lower().replace(" ", "_") not in cds]
    if side_available:
        side = random.choice(side_available)
        func_name = side.lower().replace(" ", "_")
        func = getattr(rpgskills, func_name, None)
        if callable(func):
            result = func(scene, enemy_uid, target_uid)
            if result:
                results.append(result)
            scene.cooldowns.setdefault(enemy_uid, {})[func_name] = 2
            scene.actions_used.setdefault(enemy_uid, {})['side_action'] = True

    return ("\n".join(results), target_uid)