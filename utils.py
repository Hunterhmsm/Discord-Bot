#stuff that pretty much everything needs
from globals import DATA_FILE, RPG_INVENTORY_FILE, RPG_ITEMS_FILE
import os
import json

def load_data():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

def rpg_load_data():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(RPG_INVENTORY_FILE, "r") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}
        
def rpg_save_data(data):
    with open(RPG_INVENTORY_FILE, "w") as f:
        json.dump(data, f, indent=4)      

import json
from utils import rpg_load_data, rpg_save_data  # your functions to load/save RPG data

ITEMS_FILE = "rpgitems.json"

def load_rpg_items():
    """Load items data from rpgitems.json."""
    try:
        with open(ITEMS_FILE, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading items data: {e}")
        return {}

def calculate_equipment_bonuses(equipment: dict, items_data: dict, stats: dict) -> dict:
    """
    Given a character's equipment (a dict mapping equipment slots to item names),
    the items data (loaded from your rpgitems.json), and the character's stats,
    calculates and returns a dictionary with bonuses.
    """
    armor_bonus = 0
    speed_bonus = 0

    # Loop over each equipped item.
    for slot, item_name in equipment.items():
        # Skip if the value is "None" or empty.
        if not item_name or item_name.lower() == "none":
            continue

        # Search for the item by matching the 'name' field (case-insensitive)
        found_item = None
        for category in items_data.values():
            for key, item in category.items():
                if item.get("name", "").lower() == item_name.lower():
                    found_item = item
                    break
            if found_item:
                break

        if found_item:
            # If the item provides an armor bonus, add it.
            if "armor_class_bonus" in found_item:
                armor_bonus += found_item["armor_class_bonus"]
            # If the item provides a speed bonus, add it.
            if "speed_value_bonus" in found_item:
                speed_bonus += found_item["speed_value_bonus"]
            # (You could also check for other bonuses as needed.)
    
    # For example, add half of the character's Dexterity to the speed bonus.
    dex = stats.get("Dexterity", 0)
    speed_bonus += dex / 2

    return {"armor_bonus": armor_bonus, "speed_bonus": speed_bonus}

def update_equipment_bonuses_for_user(user_id: str) -> dict:
    """
    Loads the character for the given user ID, calculates equipment bonuses using
    the character's equipment and stats (from the rpgitems.json file), updates the
    character's bonus fields ("armor" and "speed"), saves the updated data, and returns
    the bonuses.
    """
    data = rpg_load_data()  # your function that loads the RPG data (a dict)
    if user_id not in data:
        return {"armor_bonus": 0, "speed_bonus": 0}
    
    character = data[user_id]
    equipment = character.get("equipment", {})  # e.g., {"head": "Leather Helmet", ...}
    stats = character.get("stats", {})
    items_data = load_rpg_items()  # this function loads your items from rpgitems.json

    # Calculate bonuses based on equipment, items data, and character stats.
    bonuses = calculate_equipment_bonuses(equipment, items_data, stats)
    
    # Update the character's bonus fields.
    character["armor"] = bonuses.get("armor_bonus", 0)
    character["speed"] = bonuses.get("speed_bonus", 0)
    
    data[user_id] = character
    rpg_save_data(data)  # your function that saves the RPG data
    return bonuses


