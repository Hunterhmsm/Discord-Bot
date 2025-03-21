import discord
from discord import app_commands
from discord.ext import commands
import random
import datetime
import json
import os
from typing import Optional
from globals import RPG_INVENTORY_FILE, GUILD_ID
from utils import rpg_load_data, rpg_save_data

class RPGInventory(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        #track the last time a user used /crime.
        self.crime_cooldowns = {}  


    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="status", description="View your characters status. (or anothers)")
    @app_commands.describe(user="Optional: The user whose portfolio you want to see (defaults to yourself)")
    async def portfolio(self, interaction: discord.Interaction, user: discord.Member = None):
        target = user or interaction.user
        data = rpg_load_data()
        user_id = str(target.id)
        if user_id not in data:
            await interaction.response.send_message("User doesn't have a character.", ephemeral=True)
        user_record = data.get(user_id, {"currenthp": 0, "stats": {}, "maxhp": 0, "gender": None, "class": None})
        stats = user_record.get("stats", {})

        #extract individual stats with a fallback value if needed.
        strength = stats.get("Strength", 0)
        dexterity = stats.get("Dexterity", 0)
        intelligence = stats.get("Intelligence", 0)
        willpower = stats.get("Willpower", 0)
        fortitude = stats.get("Fortitude", 0)
        charisma = stats.get("Charisma", 0)
        embed = discord.Embed(
            title=f"{target.display_name}'s Status",
            color=discord.Color.green()
        )
        
        embed.add_field(
            name="Stats",
            value=f"Strength:{strength}\nDexterity:{dexterity}\nIntelligence:{intelligence}\nWillpower:{willpower}\nFortitude:{fortitude}\nCharisma:{charisma}",
            inline=True
        )
    
        await interaction.response.send_message(embed=embed)



async def setup(bot: commands.Bot):
    print("Loading RPGInventoryCog...")
    await bot.add_cog(RPGInventory(bot))
