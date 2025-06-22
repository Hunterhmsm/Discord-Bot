from random import randint
from rpgutils import rpg_load_data

def rend(scene, attacker_uid, target_uid):
    attacker_data = scene.enemies_data.get(attacker_uid) or rpg_load_data().get(attacker_uid)
    target_data = scene.enemies_data.get(target_uid) or rpg_load_data().get(target_uid)

    attacker_name = attacker_data.get('name', attacker_uid)
    target_name = target_data.get('name', target_uid)

    scene.conditions.setdefault(target_uid, {})["bleeding"] = 2  # 
    scene.cooldowns.setdefault(attacker_uid, {})["rend"] = 2  # 2-turn cooldown
    

    return f"{attacker_name} rends {target_name}, causing bleeding!"

def bleeding(scene, target_uid):
    damage = 1  
    scene.hp_map[target_uid] -= damage

    target_data = scene.enemies_data.get(target_uid) or rpg_load_data().get(target_uid)
    target_name = target_data.get('name', target_uid)

    return f"{target_name} takes {damage} bleeding damage!"