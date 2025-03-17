#stuff that pretty much everything needs
from globals import DATA_FILE, RPG_INVENTORY_FILE
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