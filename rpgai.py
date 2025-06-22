# rpgai.py

import random
from rpgutils import rpg_load_data

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

@register("melee")
def ai_melee(scene, enemy_uid):
    """
    Basic melee AI: attacks frontline first, then backline.
    Returns (result_str, target_uid).
    """
    cfg = scene.enemies_data[enemy_uid]
    name = cfg.get("name", enemy_uid)

    # choose a target
    if scene.friendly_frontline:
        pool = scene.friendly_frontline
    else:
        pool = scene.friendly_backline

    if not pool:
        return (f"{name} looks around but finds no one to attack.", None)

    targ = random.choice(pool)

    # to-hit
    roll  = random.randint(1, 10)
    bonus = cfg.get("attack_bonus", 0)
    total = roll + bonus
    pc    = rpg_load_data().get(targ, {})
    armor = pc.get("armor", 10)

    res = f"{name} attacks {pc.get('name', f'<@{targ}>')} " \
          f"({roll}+{bonus}={total} vs AC {armor}). "

    if total >= armor:
        dmg_min = cfg.get("damage_min", 1)
        dmg_max = cfg.get("damage_max", 4)
        dmg     = random.randint(dmg_min, dmg_max)
        scene.hp_map[targ] -= dmg
        # record killer for graveyard
        scene._last_attacker = name
        res += f"Hit! {dmg} damage."
    else:
        res += "Miss!"

    return (res, targ)
