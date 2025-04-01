import discord
from discord import app_commands, Interaction
from discord.ext import commands
from typing import Optional
from globals import RPG_INVENTORY_FILE, GUILD_ID, GRAVEYARD_FILE
from rpgutils import rpg_load_data, rpg_save_data, full_heal
import json
import os

#the main Cog.
class RPGGeneral(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="rest", description="Rest at the Inn for 50 gold.")
    async def portfolio(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        data = rpg_load_data()
        if user_id not in data:
            await interaction.response.send_message("You don't have a character.", ephemeral=True)
            return
        character = data[user_id]
        gold = character["gold"]
        if gold < 50:
            await interaction.response.send_message("You don't have enough gold. You need 50 gold to rest.", ephemeral=True)
            return
        else:
            gold -= 50
            character["gold"] = gold
            rpg_save_data(data)
            full_heal(user_id)
            await interaction.response.send_message("You have rested. You have paid 50 gold.", ephemeral=True)
            return
        
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="graveyard", description="View all graveyard entries.")
    async def graveyard(self, interaction: discord.Interaction):
        #check if the graveyard file exists
        if not os.path.exists(GRAVEYARD_FILE):
            await interaction.response.send_message("No graveyard entries found.", ephemeral=True)
            return
        #load the graveyard data.
        try:
            with open(GRAVEYARD_FILE, "r") as f:
                entries = json.load(f)

        except json.JSONDecodeError:
            await interaction.response.send_message("Error reading graveyard entries.", ephemeral=True)
            return
        
        if not entries:
            await interaction.response.send_message("No graveyard entries found.", ephemeral=True)
            return
        #create an embed listing all entries.
        description = "\n".join(entries)
        embed = discord.Embed(
            title="Graveyard Tombs",
            description=description,
            color=discord.Color.dark_red()
        )
        await interaction.response.send_message(embed=embed)

async def setup(bot: commands.Bot):
    print("Loading RPGGeneralCog...")
    await bot.add_cog(RPGGeneral(bot))
