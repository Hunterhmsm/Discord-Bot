import discord
from discord import app_commands
from discord.ext import commands
from globals import RPG_INVENTORY_FILE, GUILD_ID
from utils import rpg_load_data, rpg_save_data

#defines starting stats
INITIAL_STATS = {
    "Strength": 5,
    "Dexterity": 5,
    "Intelligence": 5,
    "Willpower": 5,
    "Fortitude": 5,
    "Charisma": 5
}

#defines maximum skillpoints
MAX_POINTS = 10

#gender selection
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
        #passes view to next in line
        view.add_item(ClassSelect())
        await view.update_embed(interaction)
#class select
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
#race select
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
        await interaction.response.send_modal(NameModal(root_view=view))
        view.stop()


#name input
class NameModal(discord.ui.Modal, title="Enter Your Name"):
    name = discord.ui.TextInput(
        label="Character Name", 
        placeholder="Type your character's name here...",
        min_length=1, 
        max_length=32
    )
    
    def __init__(self, *, root_view: discord.ui.View):
        self.root_view = root_view  #save the reference to the CharacterCreationView
        super().__init__()

    async def on_submit(self, interaction: discord.Interaction):
        #gets text input
        self.root_view.character["name"] = self.name.value
        #after the name is submitted send the stat distribution view.
        stat_view = StatDistributionView(root_view=self.root_view)
        await interaction.response.send_message(embed=stat_view.create_embed(), view=stat_view, ephemeral=True)

#stat distribution
class StatDistributionView(discord.ui.View):
    def __init__(self, *, root_view: discord.ui.View):
        super().__init__(timeout=300)
        self.stats = INITIAL_STATS.copy()  #copy initial stats so they can be modified
        self.available_points = 10
        self.root_view = root_view  #save the reference to the CharacterCreationView
        #add stat adjustment buttons.
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
    #creates the beautiful embed
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
    #updates the message everytime a button is pressed
    async def update_message(self, interaction: discord.Interaction):
        new_embed = self.create_embed()
        try:
            await interaction.response.edit_message(embed=new_embed, view=self)
        except Exception:
            await interaction.message.edit(embed=new_embed, view=self)
#does the actual adjustment
#logic is simple, if trying to increase and not over max/available increase
#if trying to decrease and higher than 1, decrease and add to available points
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

#confirm button that saves all creates options
class ConfirmButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Confirm", style=discord.ButtonStyle.blurple, custom_id="confirm")

    async def callback(self, interaction: discord.Interaction):
        view: StatDistributionView = self.view
        for child in view.children:
            child.disabled = True
        await interaction.response.edit_message(embed=view.create_embed(), view=view)
        # Save the final character data along with all selections.
        user_id = str(interaction.user.id)
        data = rpg_load_data()  # Assumes this returns a dictionary
        character_data = {
            "stats": view.stats,
            "gender": view.root_view.character.get("gender"),
            "class": view.root_view.character.get("class"),
            "race": view.root_view.character.get("race"),
            "name": view.root_view.character.get("name"),
            "level": 1,
            "experience": 0,
            "gold": 10
        }
        data[user_id] = character_data
        rpg_save_data(data)
        await interaction.followup.send("Your character has been saved!", ephemeral=True)
        view.stop()

#the view that starts it off
class CharacterCreationView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)
        self.character = {}  #dictionary to store all selections
        self.embed = self.create_embed()
        #start by adding the gender selection. (change to change start)
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
        stats = self.character.get("stats", "Not chosen")
        embed.add_field(name="Gender", value=gender, inline=True)   
        embed.add_field(name="Class", value=char_class, inline=True)
        embed.add_field(name="Race", value=race, inline=True)
        embed.add_field(name="Name", value=name, inline=True)
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
        
    
#commands
class CharacterCreationCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    #command that runs the user through character creation
    #users can only have one character at a time
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
    async def create_character(self, interaction: discord.Interaction):
        data = rpg_load_data()
        user_id = str(interaction.user.id)
        if user_id not in data:
            await interaction.response.send_message("You don't have a character.", ephemeral=True)
        else:
            await interaction.response.send_modal(DeleteCharacter())



async def setup(bot: commands.Bot):
    print("Loading CharacterCreationCog...")
    await bot.add_cog(CharacterCreationCog(bot))