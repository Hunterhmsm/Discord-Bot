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
    @app_commands.command(name="balance", description="Show the Beaned Bucks balance of a user.")
    @app_commands.describe(user="The user to check balance for (defaults to yourself if not provided).")
    async def balance(self, interaction: discord.Interaction, user: Optional[discord.Member] = None):
        #default to the interaction user if no user is specified.
        target = user or interaction.user
        data = rpg_load_data()
        user_id = str(target.id)
        user_record = data.get(user_id, {"balance": 0})
        balance_value = user_record.get("balance", 0)
        
        await interaction.response.send_message(f"{target.display_name} has {balance_value} Beaned Bucks.")