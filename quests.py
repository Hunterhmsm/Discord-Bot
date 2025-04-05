import discord
from discord import app_commands
from discord.ext import commands
from globals import RPG_INVENTORY_FILE, GUILD_ID, QUESTS
from rpgcharactercreation import ClassSelect, CharacterCreationView
from rpgutils import rpg_load_data, rpg_save_data, update_equipment_bonuses_for_user, \
    calculate_starting_hp_mana_stamina, full_heal, add_to_graveyard, add_daily_quests
import json


class DeleteQuest:
    pass

class QuestSelectView(discord.ui.View):
    def __init__(self, *, root_view: discord.ui.View):
        super().__init__(timeout=300)
        self.quest = None
        self.root_view = root_view
        self.selected_equipment = None

    async def update_embed(self, interaction):
        pass


class QuestSelect(discord.ui.Select):
    def __init__(self, options):
        super().__init__(placeholder="Choose a daily quest...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        selected_quest_id = self.values[0]
        await interaction.response.send_message(f"You chose quest ID {selected_quest_id}", ephemeral=True)


# ------------------
# Slash Command Cog for Quest Selection
# ------------------
class QuestSelectorCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="quest", description="Choose your daily quest.") # /quest is the command for this cog
    async def choose_quest(self, interaction: discord.Interaction):
        data = rpg_load_data() # loads rpg data
        user_id = str(interaction.user.id) # playerID will be converted a string

        if user_id in data: # if user ID is in the rpg.json data file
            add_daily_quests(user_id) # calls the 'add_daily_quests(user_id)' function in rpgutils.py

            await interaction.response.send_message("Finding your 3 daily quests...", ephemeral=True) # sends message
            try:
                daily_quests = data[user_id].get("daily_quests", []) # created a daily quest array
                # we go into data object from the user_id & we get the daily quests from the rpg.json & put it in array

                options = [] # instantiate options array
                used_values = set() # create a used_values array and store used quests in there
                for quest in daily_quests: # for every quest in daily quests
                    quest_id = str(quest["id"]) # convert quest_id from an integer to a string
                    # prevent duplicate select values
                    if quest_id in used_values: # if a quest ID exists continue
                        continue
                    # if the quest ID was in the used values add it to the used values array
                    used_values.add(quest_id)

                    options.append(discord.SelectOption(  # add each quest to the discord selectOption
                        label=quest["name"][:100], # 100 characters is discords max
                        description=quest["description"][:100], # grabs its description
                        value=quest_id # set the value to the quest ID from the rpg.json -> daily.quests
                    ))

                if not options: # if theres no quests for whatever reason, whether they are all being used etc.
                    await interaction.followup.send("No quests available.", ephemeral=True)
                    return

                select = discord.ui.Select( # lets you choose 1 daily quest
                    placeholder="Choose a daily quest...",
                    min_values=1,
                    max_values=1,
                    options=options
                )
                view = discord.ui.View()
                view.add_item(select)
                await interaction.followup.send("Choose one of your daily quests:", view=view, ephemeral=True)

            except Exception as e: # error handling
                print(f"Error loading quests: {e}")
                await interaction.followup.send("Failed to load quests.", ephemeral=True)

    # command that deletes a users current quest
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="remove_quest", description="Remove current quest")
    async def delete_quest(self, interaction: discord.Interaction):
        data = rpg_load_data()
        user_id = str(interaction.user.id)
        if user_id not in data:
            await interaction.response.send_message("You don't have a quest.", ephemeral=True)
        else:
            await interaction.response.send_modal(DeleteQuest())

async def setup(bot: commands.Bot):
    print("Loading QuestSelectorCog...")
    await bot.add_cog(QuestSelectorCog(bot))