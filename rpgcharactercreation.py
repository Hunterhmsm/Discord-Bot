import discord
from discord import app_commands
from discord.ext import commands
from globals import RPG_INVENTORY_FILE, GUILD_ID
from rpgutils import rpg_load_data, rpg_save_data, update_equipment_bonuses_for_user, calculate_starting_hp_mana_stamina, full_heal

# Defines starting stats and other constants.
INITIAL_STATS = {
    "Strength": 5,
    "Dexterity": 5,
    "Intelligence": 5,
    "Willpower": 5,
    "Fortitude": 5,
    "Charisma": 5
}
MAX_POINTS = 10

# ------------------
# Gender, Class, Race & Name Selection Components
# ------------------

class GenderSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Male", description="Choose Male", value="Male"),
            discord.SelectOption(label="Female", description="Choose Female", value="Female")
        ]
        super().__init__(placeholder="Select your gender...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        view: CharacterCreationView = self.view
        view.character["gender"] = self.values[0]
        self.disabled = True
        view.add_item(ClassSelect())
        await view.update_embed(interaction)

class ClassSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Warrior", description="Strong and brave", value="Warrior"),
            discord.SelectOption(label="Mage", description="Master of magic", value="Mage"),
            discord.SelectOption(label="Rogue", description="Stealthy and agile", value="Rogue")
        ]
        super().__init__(placeholder="Select your class...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        view: CharacterCreationView = self.view
        view.character["class"] = self.values[0]
        self.disabled = True
        view.add_item(RaceSelect())
        await view.update_embed(interaction)

class RaceSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Human", description="Versatile and resilient", value="Human"),
            discord.SelectOption(label="Elf", description="Agile and wise", value="Elf"),
            discord.SelectOption(label="Dwarf", description="Sturdy and brave", value="Dwarf")
        ]
        super().__init__(placeholder="Select your race...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        view: CharacterCreationView = self.view
        view.character["race"] = self.values[0]
        self.disabled = True
        # Once race is selected, open a modal to let the user enter a name.
        await interaction.response.send_modal(NameModal(root_view=view))

class NameModal(discord.ui.Modal, title="Enter Your Name"):
    name = discord.ui.TextInput(
        label="Character Name", 
        placeholder="Type your character's name here...",
        min_length=1, 
        max_length=32
    )
    
    def __init__(self, *, root_view: discord.ui.View):
        self.root_view = root_view  # Save a reference to the CharacterCreationView.
        super().__init__()

    async def on_submit(self, interaction: discord.Interaction):
        self.root_view.character["name"] = self.name.value
        #go to equipment selection;
        if self.root_view.character.get("class") in ("Warrior", "Rogue", "Mage"):
            equip_view = EquipmentSelectView(root_view=self.root_view)
            await interaction.response.send_message(embed=equip_view.create_embed(), view=equip_view, ephemeral=True)
        else:
            stat_view = StatDistributionView(root_view=self.root_view)
            await interaction.response.send_message(embed=stat_view.create_embed(), view=stat_view, ephemeral=True)



class EquipmentSelectView(discord.ui.View):
    def __init__(self, *, root_view: discord.ui.View):
        super().__init__(timeout=300)
        self.root_view = root_view
        self.selected_equipment = None 
        
        #get the character's class from the root view.
        char_class = self.root_view.character.get("class")
        
        #or Warrior
        if char_class == "Warrior":
            self.add_item(EquipmentButton("Option 1: Leather Armor & Longsword", {
                "head": "Leather Helmet",
                "chest": "Leather Armor",
                "hands": "None",
                "legs": "Leather Pants",
                "feet": "Leather Boots",
                "ring": "None",
                "bracelet": "None",
                "necklace": "None",
                "mainhand": "Iron Longsword",
                "offhand": "Iron Longsword"
            }))
            self.add_item(EquipmentButton("Option 2: Iron Armor, Mace, and Shield", {
                "head": "Iron Helmet",
                "chest": "Iron Breastplate",
                "hands": "None",
                "legs": "Leather Pants",
                "feet": "Iron Boots",
                "ring": "None",
                "bracelet": "None",
                "necklace": "None",
                "mainhand": "Mace",
                "offhand": "Wooden Shield"
            }))
        elif char_class == "Rogue":
            self.add_item(EquipmentButton("Option: Leather Armor & Dagger", {
                "head": "None",
                "chest": "Light Leather Armor",
                "hands": "Leather Gloves",
                "legs": "Leather Pants",
                "feet": "Leather Boots",
                "ring": "None",
                "bracelet": "None",
                "necklace": "None",
                "mainhand": "Iron Dagger",
                "offhand": "None"
            }))
        elif char_class == "Mage":
            self.add_item(EquipmentButton("Option: Robe & Staff", {
                "head": "None",
                "chest": "Cloth Robe",
                "hands": "None",
                "legs": "Cloth Pants",
                "feet": "Wooden Sandals",
                "ring": "None",
                "bracelet": "None",
                "necklace": "Lesser Amulet of Mana",
                "mainhand": "Wooden Staff",
                "offhand": "None"
            }))
        else:
            # Fallback: If for some reason the class isn't set or recognized,
            # add a generic default option.
            self.add_item(EquipmentButton("Default Equipment", {}))

    def create_embed(self):
        embed = discord.Embed(
            title="Equipment Selection",
            description="Select one of the following starting equipment packages:",
            color=discord.Color.gold()
        )
        # You could also list the options by reading from the items added.
        embed.add_field(name="Options", value="Choose one of the equipment packages above.", inline=False)
        return embed

class EquipmentButton(discord.ui.Button):
    def __init__(self, label: str, equipment: dict):
        super().__init__(label=label, style=discord.ButtonStyle.primary)
        self.equipment = equipment

    async def callback(self, interaction: discord.Interaction):
        view: EquipmentSelectView = self.view
        view.selected_equipment = self.equipment
        # Save the chosen equipment in the root character creation view.
        view.root_view.character["equipment"] = self.equipment
        await interaction.response.send_message("Equipment selected!", ephemeral=True)
        # Proceed to the stat distribution step.
        stat_view = StatDistributionView(root_view=view.root_view)
        await interaction.followup.send(embed=stat_view.create_embed(), view=stat_view, ephemeral=True)
        view.stop()

# ------------------
# Stat Distribution
# ------------------
class StatDistributionView(discord.ui.View):
    def __init__(self, *, root_view: discord.ui.View):
        super().__init__(timeout=300)
        self.stats = INITIAL_STATS.copy()  # copy initial stats for modifications
        self.available_points = 5
        self.root_view = root_view  # store reference to the root view
        self.add_item(StatAdjustButton("Strength", "+"))
        self.add_item(StatAdjustButton("Strength", "-"))
        self.add_item(StatAdjustButton("Dexterity", "+"))
        self.add_item(StatAdjustButton("Dexterity", "-"))
        self.add_item(StatAdjustButton("Intelligence", "+"))
        self.add_item(StatAdjustButton("Intelligence", "-"))
        self.add_item(StatAdjustButton("Willpower", "+"))
        self.add_item(StatAdjustButton("Willpower", "-"))
        self.add_item(StatAdjustButton("Fortitude", "+"))
        self.add_item(StatAdjustButton("Fortitude", "-"))
        self.add_item(StatAdjustButton("Charisma", "+"))
        self.add_item(StatAdjustButton("Charisma", "-"))
        self.add_item(ConfirmButton())

    def create_embed(self):
        embed = discord.Embed(
            title="Stat Distribution",
            description="Adjust your stats using the buttons below.",
            color=discord.Color.blurple()
        )
        total = sum(self.stats.values())
        embed.add_field(name="Total Points", value=str(total), inline=False)
        embed.add_field(name="Remaining Points", value=str(self.available_points), inline=False)
        for stat, value in self.stats.items():
            embed.add_field(name=stat, value=str(value), inline=True)
        embed.set_footer(text="Click Confirm when you are finished.")
        return embed

    async def update_message(self, interaction: discord.Interaction):
        new_embed = self.create_embed()
        try:
            await interaction.response.edit_message(embed=new_embed, view=self)
        except Exception:
            await interaction.message.edit(embed=new_embed, view=self)

class StatAdjustButton(discord.ui.Button):
    def __init__(self, stat: str, operation: str):
        label = f"{stat} {operation}"
        style = discord.ButtonStyle.green if operation == "+" else discord.ButtonStyle.red
        custom_id = f"{stat}_{operation}"
        super().__init__(label=label, style=style, custom_id=custom_id)
        self.stat = stat
        self.operation = operation

    async def callback(self, interaction: discord.Interaction):
        view: StatDistributionView = self.view
        if self.operation == "+":
            if view.available_points > 0 and view.stats[self.stat] < MAX_POINTS:
                view.stats[self.stat] += 1
                view.available_points -= 1
        elif self.operation == "-":
            if view.stats[self.stat] > 1:
                view.stats[self.stat] -= 1
                view.available_points += 1
        await view.update_message(interaction)
        await interaction.response.defer()

class ConfirmButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Confirm", style=discord.ButtonStyle.blurple, custom_id="confirm")

    async def callback(self, interaction: discord.Interaction):
        view: StatDistributionView = self.view
        for child in view.children:
            child.disabled = True
        await interaction.response.edit_message(embed=view.create_embed(), view=view)
        user_id = str(interaction.user.id)
        data = rpg_load_data()
        calculate_starting_hp_mana_stamina(user_id)
        character_data = {
            "stats": view.stats,
            "level": 1,
            "experience": 0,
            "experience_needed": 100,
            "armor": 0,
            "speed": 0,
            "gender": view.root_view.character.get("gender"),
            "class": view.root_view.character.get("class"),
            "race": view.root_view.character.get("race"),
            "name": view.root_view.character.get("name"),
            "equipment": view.root_view.character.get("equipment"),
            "inventory": {},
            "conditions:": {},
            "gold": 10
        }
        data[user_id] = character_data
        rpg_save_data(data)
        calculate_starting_hp_mana_stamina(user_id)
        update_equipment_bonuses_for_user(user_id)
        full_heal(user_id)
        await interaction.followup.send("Your character has been saved!", ephemeral=True)
        view.stop()

# ------------------
# Character Creation View
# ------------------
class CharacterCreationView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)
        self.character = {}  # Dictionary to store selections.
        self.embed = self.create_embed()
        self.add_item(GenderSelect())

    def create_embed(self):
        embed = discord.Embed(
            title="Character Creation",
            description="Please make your selections below:",
            color=discord.Color.purple()
        )
        gender = self.character.get("gender", "Not selected")
        char_class = self.character.get("class", "Not selected")
        race = self.character.get("race", "Not selected")
        name = self.character.get("name", "Not chosen")
        equipment = self.character.get("equipment", "Not chosen")
        stats = self.character.get("stats", "Not chosen")
        embed.add_field(name="Gender", value=gender, inline=True)
        embed.add_field(name="Class", value=char_class, inline=True)
        embed.add_field(name="Race", value=race, inline=True)
        embed.add_field(name="Name", value=name, inline=True)
        embed.add_field(name="Equipment", value=equipment, inline=True)
        embed.add_field(name="Stats", value=stats, inline=True)
        return embed

    async def update_embed(self, interaction: discord.Interaction, final: bool = False):
        self.embed = self.create_embed()
        if final:
            self.embed.set_footer(text="Character creation complete!")
        await interaction.response.edit_message(embed=self.embed, view=self)

class DeleteCharacter(discord.ui.Modal, title="Character Deletion"):
    answer = discord.ui.TextInput(
        label="Type YES to confirm", 
        placeholder="YES",
        min_length=1, 
        max_length=32
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        #check if the user typed "YES"
        if self.answer.value == "YES":
            data = rpg_load_data()
            user_id = str(interaction.user.id)
            #delete the data then save it
            if user_id in data:
                del data[user_id]
                rpg_save_data(data)
                await interaction.response.send_message("Your character has been deleted.", ephemeral=True)
        else:
            await interaction.response.send_message("You need to type YES to delete your character.", ephemeral=True)

# ------------------
# Slash Command Cog for Character Creation
# ------------------
class CharacterCreationCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="create_character", description="Create your character step-by-step.")
    async def create_character(self, interaction: discord.Interaction):
        data = rpg_load_data()
        user_id = str(interaction.user.id)
        if user_id in data:
            await interaction.response.send_message("You already have a character.", ephemeral=True)
        else:
            view = CharacterCreationView()
            await interaction.response.send_message(embed=view.embed, view=view, ephemeral=True)
            
    #command that deletes a users current character
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="delete_character", description="Deletes your current character")
    async def delete_character(self, interaction: discord.Interaction):
        data = rpg_load_data()
        user_id = str(interaction.user.id)
        if user_id not in data:
            await interaction.response.send_message("You don't have a character.", ephemeral=True)
        else:
            await interaction.response.send_modal(DeleteCharacter())

async def setup(bot: commands.Bot):
    print("Loading CharacterCreationCog...")
    await bot.add_cog(CharacterCreationCog(bot))
