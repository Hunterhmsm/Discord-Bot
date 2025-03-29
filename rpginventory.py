import discord
from discord import app_commands, Interaction
from discord.ext import commands
from typing import Optional
from globals import RPG_INVENTORY_FILE, GUILD_ID
from rpgutils import rpg_load_data, rpg_save_data, load_rpg_items, update_equipment_bonuses_for_user

#helper
def get_item_definition(item_name: str) -> dict:
    items_data = load_rpg_items()
    for category in items_data.values():
        for key, item in category.items():
            if item.get("name", "").lower() == item_name.lower():
                return item
    return {}

def add_to_inventory(inventory: dict, item_name: str):
    inventory[item_name] = inventory.get(item_name, 0) + 1

def swap_equip_item(user_id: str, new_item: dict, slot: str):
    data = rpg_load_data()
    user_data = data.get(user_id, {})
    equipment = user_data.get("equipment", {})
    inventory = user_data.get("inventory", {}) 
    #get the current item in the target slot.
    current_item = equipment.get(slot)
    if current_item and current_item != "None":
        #look up current item's definition.
        current_item_def = get_item_definition(current_item)
        #for either-hand items in mainhand/offhand, check if both hands have the same item.
        if slot in ("mainhand", "offhand") and current_item_def and current_item_def.get("slot") == "eitherhand":
            other_slot = "offhand" if slot == "mainhand" else "mainhand"
            other_item = equipment.get(other_slot)
            if other_item == current_item:
                add_to_inventory(inventory, current_item)
            else:
                add_to_inventory(inventory, current_item)
        else:
            add_to_inventory(inventory, current_item)
    
    #equip the new item in the designated slot.
    equipment[slot] = new_item["name"]

    #remove one occurrence of new_item from the inventory.
    if new_item["name"] in inventory:
        if inventory[new_item["name"]] > 1:
            inventory[new_item["name"]] -= 1
        else:
            del inventory[new_item["name"]]
    
    user_data["equipment"] = equipment
    user_data["inventory"] = inventory
    data[user_id] = user_data
    rpg_save_data(data)
    update_equipment_bonuses_for_user(user_id)


#helper function
def equip_two_handed(user_id: str, new_item: dict):
    data = rpg_load_data()
    user_data = data.get(user_id, {})
    equipment = user_data.get("equipment", {})
    inventory = user_data.get("inventory", {})

    #check for existing items in both hands.
    current_main = equipment.get("mainhand")
    current_off = equipment.get("offhand")

    if current_main and current_main != "None":
        main_def = get_item_definition(current_main)
        if main_def and main_def.get("slot") == "eitherhand":
            #always add a copy for an eitherhand weapon.
            add_to_inventory(inventory, current_main)
        else:
            add_to_inventory(inventory, current_main)
    if current_off and current_off != "None":
        off_def = get_item_definition(current_off)
        if off_def and off_def.get("slot") == "eitherhand":
            #always add a copy for an eitherhand weapon,
            #even if offhand equals mainhand.
            add_to_inventory(inventory, current_off)
        else:
            #for non-eitherhand items, only add if it differs from mainhand.
            if current_off != current_main:
                add_to_inventory(inventory, current_off)

    #equip the new two-handed weapon in both hands.
    equipment["mainhand"] = new_item["name"]
    equipment["offhand"] = new_item["name"]

    #remove one occurrence of the new item from the inventory.
    if new_item["name"] in inventory:
        if inventory[new_item["name"]] > 1:
            inventory[new_item["name"]] -= 1
        else:
            del inventory[new_item["name"]]

    user_data["equipment"] = equipment
    user_data["inventory"] = inventory
    data[user_id] = user_data
    rpg_save_data(data)
    update_equipment_bonuses_for_user(user_id)


class EquipEitherHandView(discord.ui.View):
    def __init__(self, item: dict, user_id: str):
        super().__init__(timeout=30)
        self.item = item
        self.user_id = user_id

    @discord.ui.button(label="Mainhand", style=discord.ButtonStyle.primary)
    async def mainhand(self, interaction: discord.Interaction, button: discord.ui.Button):
        swap_equip_item(self.user_id, self.item, "mainhand")
        await interaction.response.send_message(f"Equipped **{self.item['name']}** in mainhand.", ephemeral=True)
        # Refresh the main inventory view after equipping.
        data = rpg_load_data()
        record = data.get(self.user_id)
        equipment = record.get("equipment", {})
        inventory_items = record.get("inventory", {})
        gold = record.get("gold", 0)
        new_embed = discord.Embed(
            title=f"{interaction.user.display_name}'s Inventory",
            color=discord.Color.blue()
        )
        new_embed.add_field(
            name="Equipped Items",
            value="\n".join([f"{slot.title()}: {item}" for slot, item in equipment.items()]),
            inline=False
        )
        if inventory_items:
            inv_str = "\n".join([f"{name}: {qty}" for name, qty in inventory_items.items()])
        else:
            inv_str = "No items in inventory."
        new_embed.add_field(name="Other Inventory Items", value=inv_str, inline=False)
        new_embed.add_field(name="Gold", value=str(gold), inline=False)
        new_view = CombinedInventoryView(inventory_items, equipment, self.user_id)
        # Send a followup message with updated data.
        await interaction.followup.send(embed=new_embed, view=new_view, ephemeral=True)
        self.stop()

    @discord.ui.button(label="Offhand", style=discord.ButtonStyle.primary)
    async def offhand(self, interaction: discord.Interaction, button: discord.ui.Button):
        swap_equip_item(self.user_id, self.item, "offhand")
        await interaction.response.send_message(f"Equipped **{self.item['name']}** in offhand.", ephemeral=True)
        # Refresh the main inventory view after equipping.
        data = rpg_load_data()
        record = data.get(self.user_id)
        equipment = record.get("equipment", {})
        inventory_items = record.get("inventory", {})
        gold = record.get("gold", 0)
        new_embed = discord.Embed(
            title=f"{interaction.user.display_name}'s Inventory",
            color=discord.Color.blue()
        )
        new_embed.add_field(
            name="Equipped Items",
            value="\n".join([f"{slot.title()}: {item}" for slot, item in equipment.items()]),
            inline=False
        )
        if inventory_items:
            inv_str = "\n".join([f"{name}: {qty}" for name, qty in inventory_items.items()])
        else:
            inv_str = "No items in inventory."
        new_embed.add_field(name="Other Inventory Items", value=inv_str, inline=False)
        new_embed.add_field(name="Gold", value=str(gold), inline=False)
        new_view = CombinedInventoryView(inventory_items, equipment, self.user_id)
        await interaction.followup.send(embed=new_embed, view=new_view, ephemeral=True)
        self.stop()


class EquipSelect(discord.ui.Select):
    def __init__(self, options, user_id: str):
        super().__init__(placeholder="Select an item to equip", min_values=1, max_values=1, options=options)
        self.user_id = user_id

    async def callback(self, interaction: discord.Interaction):
        selected_item_name = self.values[0]
        item_def = get_item_definition(selected_item_name)
        if not item_def:
            await interaction.response.send_message("Item not found in database.", ephemeral=True)
            return
        slot_type = item_def.get("slot")
        if slot_type == "eitherhand":
            # Show the subview and return immediately.
            await interaction.response.send_message("Choose which hand to equip:", ephemeral=True,
                                                    view=EquipEitherHandView(item_def, self.user_id))
            return  # Do not continue to refresh the main view.
        elif slot_type == "twohanded":
            equip_two_handed(self.user_id, item_def)
            await interaction.response.send_message(f"Equipped **{item_def['name']}** in both hands.", ephemeral=True)
        else:
            swap_equip_item(self.user_id, item_def, slot_type)
            await interaction.response.send_message(f"Equipped **{item_def['name']}** in {slot_type}.", ephemeral=True)

        # Refresh the view only if not an eitherhand item.
        data = rpg_load_data()
        record = data.get(self.user_id)
        equipment = record.get("equipment", {})
        inventory_items = record.get("inventory", {})
        gold = record.get("gold", 0)

        new_embed = discord.Embed(
            title=f"{interaction.user.display_name}'s Inventory",
            color=discord.Color.blue()
        )
        new_embed.add_field(name="Equipped Items", value="\n".join([f"{slot.title()}: {item}" for slot, item in equipment.items()]), inline=False)
        if inventory_items:
            inv_str = "\n".join([f"{name}: {qty}" for name, qty in inventory_items.items()])
        else:
            inv_str = "No items in inventory."
        new_embed.add_field(name="Other Inventory Items", value=inv_str, inline=False)
        new_embed.add_field(name="Gold", value=str(gold), inline=False)

        # Create a new combined view.
        new_view = CombinedInventoryView(inventory_items, equipment, self.user_id)
        await interaction.edit_original_response(embed=new_embed, view=new_view)
        self.view.stop()



def unequip_item(user_id: str, slot: str) -> str:
    data = rpg_load_data()
    user_data = data.get(user_id, {})
    equipment = user_data.get("equipment", {})
    inventory = user_data.get("inventory", {})  

    current_item = equipment.get(slot)
    if not current_item or current_item == "None":
        return f"Nothing is equipped in {slot}."

    #for mainhand/offhand if both slots hold the same item remove from both.
    if slot in ("mainhand", "offhand"):
        other_slot = "offhand" if slot == "mainhand" else "mainhand"
        if equipment.get(other_slot) == current_item:
            equipment["mainhand"] = "None"
            equipment["offhand"] = "None"
            add_to_inventory(inventory, current_item)
            result = f"Unequipped {current_item} from both hands."
        else:
            equipment[slot] = "None"
            add_to_inventory(inventory, current_item)
            result = f"Unequipped {current_item} from {slot}."
    else:
        equipment[slot] = "None"
        add_to_inventory(inventory, current_item)
        result = f"Unequipped {current_item} from {slot}."
    
    user_data["equipment"] = equipment
    user_data["inventory"] = inventory
    data[user_id] = user_data
    rpg_save_data(data)
    update_equipment_bonuses_for_user(user_id)
    return result

#view for selecting an equipment slot to unequip.
class UnequipSelect(discord.ui.Select):
    def __init__(self, equipped: dict, user_id: str):
        options = []
        for slot, item in equipped.items():
            if item != "None":
                options.append(discord.SelectOption(
                    label=slot.title(),
                    description=item,
                    value=slot
                ))
        super().__init__(placeholder="Select an equipment slot to unequip", min_values=1, max_values=1, options=options)
        self.user_id = user_id

    async def callback(self, interaction: discord.Interaction):
        slot = self.values[0]
        result = unequip_item(self.user_id, slot)
        await interaction.response.send_message(result, ephemeral=True)
        
        #refresh the view:
        data = rpg_load_data()
        record = data.get(self.user_id)
        equipment = record.get("equipment", {})
        inventory_items = record.get("inventory", {})
        gold = record.get("gold", 0)

        new_embed = discord.Embed(
            title=f"{interaction.user.display_name}'s Inventory",
            color=discord.Color.blue()
        )
        new_embed.add_field(name="Equipped Items", value="\n".join([f"{slot.title()}: {item}" for slot, item in equipment.items()]), inline=False)
        if inventory_items:
            inv_str = "\n".join([f"{name}: {qty}" for name, qty in inventory_items.items()])
        else:
            inv_str = "No items in inventory."
        new_embed.add_field(name="Other Inventory Items", value=inv_str, inline=False)
        new_embed.add_field(name="Gold", value=str(gold), inline=False)

        new_view = CombinedInventoryView(inventory_items, equipment, self.user_id)
        await interaction.edit_original_response(embed=new_embed, view=new_view)
        self.view.stop()


#view for unequipping items.
class EquipmentUnequipView(discord.ui.View):
    def __init__(self, equipment: dict, user_id: str):
        super().__init__(timeout=60)
        if any(item != "None" for item in equipment.values()):
            self.add_item(UnequipSelect(equipment, user_id))
        else:
            self.add_item(discord.ui.Select(placeholder="No items are equipped", options=[], disabled=True))

#interactive View for the inventory.
class InventoryEquipView(discord.ui.View):
    def __init__(self, inventory_items: dict, user_id: str):
        super().__init__(timeout=60)
        self.inventory_items = inventory_items 
        self.user_id = user_id

        options = []
        for item_name, quantity in self.inventory_items.items():
            item_def = get_item_definition(item_name)
            if item_def and "slot" in item_def:
                slot = item_def["slot"]
                options.append(discord.SelectOption(
                    label=item_name,
                    description=f"Slot: {slot}, Qty: {quantity}",
                    value=item_name
                ))
        if options:
            self.add_item(EquipSelect(options, user_id))
        else:
            self.add_item(discord.ui.Select(placeholder="No equippable items", options=[], disabled=True))

class CombinedInventoryView(discord.ui.View):
    def __init__(self, inventory_items: dict, equipment: dict, user_id: str):
        super().__init__(timeout=60)
        self.owner_id = int(user_id)

        equip_view = InventoryEquipView(inventory_items, user_id)
        for child in equip_view.children:
            if isinstance(child, discord.ui.Select) and child.options:
                self.add_item(child)

        unequip_view = EquipmentUnequipView(equipment, user_id)
        for child in unequip_view.children:
            if isinstance(child, discord.ui.Select) and child.options:
                self.add_item(child)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("You can't interact with someone else's inventory.", ephemeral=True)
            return False
        return True



#the main Cog.
class RPGInventory(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="status", description="View your character's status (or another's).")
    @app_commands.describe(user="Optional: The user whose portfolio you want to see (defaults to yourself)")
    async def portfolio(self, interaction: discord.Interaction, user: discord.Member = None):
        target = user or interaction.user
        data = rpg_load_data()
        user_id = str(target.id)
        if user_id not in data:
            await interaction.response.send_message("User doesn't have a character.", ephemeral=True)
            return

        user_record = data.get(user_id, {"current_hp": 0, "stats": {}, "max_hp": 0, "gender": None, "class": None})
        stats = user_record.get("stats", {})
        character = data[user_id]
        charactername = character["name"]
        maxhp = character["max_hp"]
        hp = character["current_hp"]
        current_stamina = character["current_stamina"]
        max_stamina = character["max_stamina"]
        current_mana = character["current_mana"]
        max_mana = character["max_mana"]
        speed = character["speed"]
        armor = character["armor"]

        #extract individual stats with fallback values.
        strength = stats.get("Strength", 0)
        dexterity = stats.get("Dexterity", 0)
        intelligence = stats.get("Intelligence", 0)
        willpower = stats.get("Willpower", 0)
        fortitude = stats.get("Fortitude", 0)
        charisma = stats.get("Charisma", 0)

        strengthb = max(strength // 2, 1)
        dexterityb = max(dexterity // 2, 1)
        intelligenceb = max(intelligence // 2, 1)
        willpowerb = max(willpower // 2, 1)        
        fortitudeb = max(fortitude // 2, 1)
        charismab = max(charisma // 2, 1)

        embed = discord.Embed(
            title=f"{charactername}'s Status",
            color=discord.Color.green()
        )
        
        embed.add_field(
            name="Stats",
            value=(f"Strength: {strength}\nDexterity: {dexterity}\nIntelligence: {intelligence}\n"
                   f"Willpower: {willpower}\nFortitude: {fortitude}\nCharisma: {charisma}"),
            inline=True
        )
        embed.add_field(
            name="Stat Bonuses",
            value=(f"Strength: {strengthb}\nDexterity: {dexterityb}\nIntelligence: {intelligenceb}\n"
                   f"Willpower: {willpowerb}\nFortitude: {fortitudeb}\nCharisma: {charismab}"),
            inline=True
        )

        embed.add_field(name="\u200B", value="\u200B", inline=True)

        embed.add_field(
            name="Health",
            value=f"{hp}/{maxhp} HP",
            inline=True
        )
        embed.add_field(
            name="Stamina",
            value=f"{current_stamina}/{max_stamina} Stamina",
            inline=True
        )
        embed.add_field(name="\u200B", value="\u200B", inline=True)
        embed.add_field(
            name="Mana",
            value=f"{current_mana}/{max_mana} Mana",
            inline=True
        )
        embed.add_field(
            name="Speed",
            value=f"{speed} Speed",
            inline=True
        )
        embed.add_field(name="\u200B", value="\u200B", inline=True)
        embed.add_field(
            name="Armor",
            value=f"{armor} Armor",
            inline=True
        )
    
        await interaction.response.send_message(embed=embed)

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="inventory", description="View your equipped items, inventory, and gold.")
    @app_commands.describe(user="Optional: The user whose inventory you want to see (defaults to yourself)")
    async def inventory(self, interaction: discord.Interaction, user: discord.Member = None):
        target = user or interaction.user
        data = rpg_load_data()
        user_id = str(target.id)
        
        if user_id not in data:
            await interaction.response.send_message("User doesn't have a character.", ephemeral=True)
            return

        record = data[user_id]
        equipment = record.get("equipment", {
            "head": "None",
            "chest": "None",
            "hands": "None",
            "legs": "None",
            "feet": "None",
            "ring": "None",
            "bracelet": "None",
            "necklace": "None",
            "mainhand": "None",
            "offhand": "None"
        })
        inventory_items = record.get("inventory", {})  
        gold = record.get("gold", 0)

        equipment_str = "\n".join([f"{slot.title()}: {item}" for slot, item in equipment.items()])
        if inventory_items:
            inventory_str = "\n".join([f"{name}: {qty}" for name, qty in inventory_items.items()])
        else:
            inventory_str = "No items in inventory."

        embed = discord.Embed(
            title=f"{target.display_name}'s Inventory",
            color=discord.Color.blue()
        )
        embed.add_field(name="Equipped Items", value=equipment_str, inline=False)
        embed.add_field(name="Other Inventory Items", value=inventory_str, inline=False)
        embed.add_field(name="Gold", value=str(gold), inline=False)
        
        #only attach the interactive view if the user is viewing their own inventory
        if target.id == interaction.user.id:
            combined_view = CombinedInventoryView(inventory_items, equipment, str(target.id))
            await interaction.response.send_message(embed=embed, view=combined_view)
        else:
            await interaction.response.send_message(embed=embed)



async def setup(bot: commands.Bot):
    print("Loading RPGInventoryCog...")
    await bot.add_cog(RPGInventory(bot))
