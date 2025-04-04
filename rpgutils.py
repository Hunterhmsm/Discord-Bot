from globals import DATA_FILE, RPG_INVENTORY_FILE, RPG_ITEMS_FILE, GRAVEYARD_FILE
import os
import json
from typing import Optional
import datetime


def rpg_load_data():
    if not os.path.exists(RPG_INVENTORY_FILE):
        return {}
    with open(RPG_INVENTORY_FILE, "r") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}


def rpg_save_data(data):
    with open(RPG_INVENTORY_FILE, "w") as f:
        json.dump(data, f, indent=4)


def load_rpg_items():
    """Load items data from rpgitems.json."""
    try:
        with open(RPG_ITEMS_FILE, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading items data: {e}")
        return {}


def load_rpg_party_data():
    """Load party data from rpgparties.json."""
    if not os.path.exists(RPG_PARTIES_FILE):
        return {}
    try:
        with open(RPG_PARTIES_FILE, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading party data: {e}")
        return {}


def calculate_equipment_bonuses(equipment: dict, items_data: dict) -> dict:
    """
    Calculates bonus values from equipped items.
    It searches for any keys ending with '_value_bonus' (e.g. "dexterity_value_bonus", "hp_value_bonus")
    and adds those to the corresponding bonus. In addition, it looks for dedicated bonus keys
    like "armor_class_bonus" and "speed_value_bonus". Finally, it calculates a derived Speed bonus
    as floor(Dexterity bonus / 2) plus any speed bonus from items.
    """
    bonus = {
        "Strength": 0,
        "Dexterity": 0,
        "Intelligence": 0,
        "Willpower": 0,
        "Fortitude": 0,
        "Charisma": 0,
        "Armor": 0,
        "Speed_item": 0,  # bonus coming from items specifically
        "HP": 0,
        "Mana": 0,
        "Stamina": 0,
    }

    for slot, item_name in equipment.items():
        if not item_name or item_name.lower() == "none":
            continue

        found_item = None
        # Search for the item by matching its 'name' field (case-insensitive)
        for category in items_data.values():
            for key, item in category.items():
                if item.get("name", "").lower() == item_name.lower():
                    found_item = item
                    break
            if found_item:
                break

        if found_item:
            # Check for keys that end with '_value_bonus'
            for key, value in found_item.items():
                if key.endswith("_value_bonus"):
                    prefix = key.split("_")[0]
                    # For hp, mana, and stamina, force uppercase letters
                    if prefix.lower() == "hp":
                        stat = "HP"
                    elif prefix.lower() == "mana":
                        stat = "Mana"
                    elif prefix.lower() == "stamina":
                        stat = "Stamina"
                    else:
                        stat = prefix.capitalize()
                    if stat in bonus:
                        bonus[stat] += value
            if "armor_class_bonus" in found_item:
                bonus["Armor"] += found_item["armor_class_bonus"]
            if "speed_value_bonus" in found_item:
                bonus["Speed_item"] += found_item["speed_value_bonus"]

    # Derived speed bonus: add half of Dexterity bonus (rounded down) plus any speed bonus from items.
    bonus["Speed"] = bonus["Dexterity"] // 2 + bonus["Speed_item"]

    return bonus


def update_equipment_bonuses_for_user(user_id: str) -> dict:
    data = rpg_load_data()  # Load all data
    if user_id not in data:
        return {
            key: 0
            for key in [
                "Strength",
                "Dexterity",
                "Intelligence",
                "Willpower",
                "Fortitude",
                "Charisma",
                "Armor",
                "Speed",
                "HP",
                "Mana",
                "Stamina",
            ]
        }

    character = data[user_id]
    equipment = character.get("equipment", {})
    items_data = load_rpg_items()  # Load item definitions
    # Calculate bonus from equipment
    equip_bonus = calculate_equipment_bonuses(equipment, items_data)

    # If no base stats have been stored, set them now.
    if "base_stats" not in character:
        # Copy the current stats as the unmodified base stats.
        character["base_stats"] = character.get("stats", {}).copy()

    base_stats = character["base_stats"]
    effective_stats = {}
    for stat in [
        "Strength",
        "Dexterity",
        "Intelligence",
        "Willpower",
        "Fortitude",
        "Charisma",
    ]:
        effective_stats[stat] = base_stats.get(stat, 0) + equip_bonus.get(stat, 0)

    # Set the effective stats on the character.
    character["stats"] = effective_stats
    character["equipment_bonus"] = equip_bonus

    # Update armor and speed as needed.
    character["armor"] = equip_bonus.get("Armor", 0)
    character["speed"] = equip_bonus.get("Speed", 0) + (
        effective_stats.get("Dexterity", 0) // 2
    )

    # Optionally update max_hp, max_mana, max_stamina similarly.
    base_hp = character.get("max_hp", 0)
    base_mana = character.get("max_mana", 0)
    base_stamina = character.get("max_stamina", 0)
    character["max_hp"] = base_hp + equip_bonus.get("HP", 0)
    character["max_mana"] = base_mana + equip_bonus.get("Mana", 0)
    character["max_stamina"] = base_stamina + equip_bonus.get("Stamina", 0)

    data[user_id] = character
    rpg_save_data(data)
    return equip_bonus


def calculate_starting_hp_mana_stamina(user_id: str) -> tuple:
    data = rpg_load_data()
    if user_id not in data:
        # if there's no character data just do whatever
        return 0, 0, 0

    character = data[user_id]
    stats = character.get("stats", {})
    fortitude = stats.get("Fortitude", 0)
    strength = stats.get("Strength", 0)
    intelligence = stats.get("Intelligence", 0)

    # calculate bonuses
    bonus = max(fortitude // 2, 1)
    stamina_bonus = max(strength // 2, 1)
    mana_bonus = max(intelligence // 2, 1)

    # get character class in lowercase to avoid case-sensitivity issues.
    char_class = character.get("class", "").strip().lower()

    if char_class == "warrior":
        max_hp = 10 + bonus
        max_stamina = 4 + bonus + stamina_bonus
        max_mana = mana_bonus
    elif char_class == "rogue":
        max_hp = 6 + bonus
        max_stamina = 4 + bonus + stamina_bonus
        max_mana = mana_bonus
    elif char_class == "mage":
        max_hp = 2 + bonus
        max_stamina = bonus + stamina_bonus
        max_mana = 8 + mana_bonus
    else:
        # fallback values
        max_hp = 10 + bonus
        max_stamina = 4 + bonus + stamina_bonus
        max_mana = mana_bonus

    # update character data with the calculated max values.
    character["max_hp"] = max_hp
    character["max_stamina"] = max_stamina
    character["max_mana"] = max_mana

    # if current values are not set initialize them to the max values.
    if "current_hp" not in character:
        character["current_hp"] = max_hp
    if "current_stamina" not in character:
        character["current_stamina"] = max_stamina
    if "current_mana" not in character:
        character["current_mana"] = max_mana

    data[user_id] = character
    rpg_save_data(data)

    return max_hp, max_mana, max_stamina


# function to full heal
def full_heal(user_id: str) -> tuple:
    data = rpg_load_data()
    if user_id not in data:
        # if there's no character data just do whatever
        return 0, 0, 0

    character = data[user_id]
    maxhp = character.get("max_hp")
    maxstamina = character.get("max_stamina")
    maxmana = character.get("max_mana")

    character["current_hp"] = maxhp
    character["current_stamina"] = maxstamina
    character["current_mana"] = maxmana

    data[user_id] = character
    rpg_save_data(data)

    return maxhp, maxmana, maxstamina



def check_user_in_party(user_id: str, check_is_leader: bool = False) -> bool:
    """Check if user is in part based on id, set if check_is_leader to True to check if user is the leader of a party."""
    party_data = load_rpg_party_data()
    for party in party_data.values():
        if user_id in party["members"] and not check_is_leader:
            return True
        if check_is_leader and party["leader"] == user_id:
            return True
    return False


def get_party_data(user_id: str) -> dict:
    """Get party data for a user."""
    party_data = load_rpg_party_data()
    for party in party_data.values():
        if user_id in party["members"]:
            return party
    return {}


def roll_d12():
    """Roll a d12 and return the result."""
    return random.randint(1, 12)

#defining backup here since i dont think its needed anywheres else
BACKUP_FILE = "rpgbackup.json"
def add_to_graveyard(user_id: str, enemy: Optional[str] = None):
    #open the graveyard file or default
    if os.path.exists(GRAVEYARD_FILE):
        with open(GRAVEYARD_FILE, "r") as f:
            try:
                graveyard = json.load(f)
            except json.JSONDecodeError:
                graveyard = []
    else:
        graveyard = []
    #load user data and get killer, default to unknown
    data = rpg_load_data()
    killer = enemy
    if enemy is None:
        killer = "Unknown"
    character = data[user_id]
    level = character["level"]
    name = character["name"]
    #setup the entry
    entry = f"Level [{level}], {name} was killed by {killer}."
    graveyard.append(entry)
    with open(GRAVEYARD_FILE, "w") as f:
        json.dump(graveyard, f, indent=4)

    #backup the entire character incase of bugs so we can restore :D
    backup_entry = {
        "user_id": user_id,
        "timestamp": datetime.datetime.utcnow().isoformat(),
        "character": character
    }
    
    if os.path.exists(BACKUP_FILE):
        with open(BACKUP_FILE, "r") as f:
            try:
                backup_data = json.load(f)
            except json.JSONDecodeError:
                backup_data = []
    else:
        backup_data = []
    backup_data.append(backup_entry)
    with open(BACKUP_FILE, "w") as f:
        json.dump(backup_data, f, indent=4)
    

