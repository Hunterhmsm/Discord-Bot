from globals import DATA_FILE, RPG_INVENTORY_FILE, RPG_ITEMS_FILE
import os
import json

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

ITEMS_FILE = "rpgitems.json"

def load_rpg_items():
    """Load items data from rpgitems.json."""
    try:
        with open(ITEMS_FILE, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading items data: {e}")
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
        "Stamina": 0
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
    """
    Loads the character for the given user ID, calculates equipment bonuses using
    the character's equipment and the items data (from rpgitems.json), then updates:
      - The effective base stats (for Strength, Dexterity, etc.) by adding the bonus.
      - The "armor" field with any armor bonus.
      - The "speed" field as the sum of the derived speed bonus (which already includes the bonus from Dexterity)
        and any base speed (if stored).
      - The max HP, Mana, and Stamina by adding the equipment bonus to the character’s current max values.
    Finally, it saves the updated character data and returns the equipment bonus dictionary.
    """
    data = rpg_load_data()  # This function loads your RPG data (a dict)
    if user_id not in data:
        return {key: 0 for key in ["Strength", "Dexterity", "Intelligence", "Willpower", "Fortitude", "Charisma", "Armor", "Speed", "HP", "Mana", "Stamina"]}
    
    character = data[user_id]
    equipment = character.get("equipment", {})  # e.g. {"head": "Leather Helmet", ...}
    items_data = load_rpg_items()  # This function should load your items from rpgitems.json
    # Calculate the bonuses based on equipped items.
    equip_bonus = calculate_equipment_bonuses(equipment, items_data)
    
    # Use the current stats as the base stats.
    base_stats = character.get("stats", {})
    
    effective_stats = {}
    for stat in ["Strength", "Dexterity", "Intelligence", "Willpower", "Fortitude", "Charisma"]:
        effective_stats[stat] = base_stats.get(stat, 0) + equip_bonus.get(stat, 0)
    
    character["stats"] = effective_stats
    character["equipment_bonus"] = equip_bonus  # For tracking purposes
    
    # Update armor and speed.
    character["armor"] = equip_bonus.get("Armor", 0)
    # Derived speed: effective speed = bonus derived from equipment + half of effective Dexterity.
    character["speed"] = equip_bonus.get("Speed", 0) + (effective_stats.get("Dexterity", 0) // 2)
    
    # Update max_hp, max_mana, and max_stamina.
    # If these already exist in the character, add the corresponding bonus.
    # (If they don't exist, you might want to initialize them elsewhere.)
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
        #if there's no character data just do whatever
        return 0, 0, 0

    character = data[user_id]
    stats = character.get("stats", {})
    fortitude = stats.get("Fortitude", 0)
    strength = stats.get("Strength", 0)
    intelligence = stats.get("Intelligence", 0)

    #calculate bonuses 
    bonus = fortitude // 2         
    stamina_bonus = strength // 2    
    mana_bonus = intelligence // 2   

    #get character class in lowercase to avoid case-sensitivity issues.
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
        #fallback values
        max_hp = 10 + bonus
        max_stamina = 4 + bonus + stamina_bonus
        max_mana = mana_bonus

    #update character data with the calculated max values.
    character["max_hp"] = max_hp
    character["max_stamina"] = max_stamina
    character["max_mana"] = max_mana

    #if current values are not set initialize them to the max values.
    if "current_hp" not in character:
        character["current_hp"] = max_hp
    if "current_stamina" not in character:
        character["current_stamina"] = max_stamina
    if "current_mana" not in character:
        character["current_mana"] = max_mana

    data[user_id] = character
    rpg_save_data(data)

    return max_hp, max_mana, max_stamina

#function to full heal
def full_heal(user_id: str) -> tuple:
    data = rpg_load_data()  #
    if user_id not in data:
        #if there's no character data just do whatever
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