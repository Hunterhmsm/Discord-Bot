import discord
from discord import app_commands
from discord.ext import commands, tasks
import json
import os
import random
import datetime
import asyncio
from typing import Optional
import datetime
from zoneinfo import ZoneInfo
from globals import TOKEN, GUILD_ID, TARGET_MEMBER_ID, TARGET_USER_ID, DATA_FILE, ALLOWED_ROLES, STOCK_FILE, STOCK_HISTORY_FILE, UPDATE_INTERVAL_MINUTES, LOTTERY_FILE, AFK_CHANNEL_ID
from stocks import load_stocks
from utils import save_data, load_data

#keys are user IDs (as strings), values are dicts with session data. tracks active VCs
active_vc_sessions = {}

#sset up intents
intents = discord.Intents.default()
intents.members = True
intents.voice_states = True
with open("config.json", "r") as f:
    config = json.load(f)


bot = commands.Bot(command_prefix="!", intents=intents)


#onready event
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    commands = await bot.http.get_global_commands(bot.user.id)
    for cmd in commands:
        await bot.http.delete_global_command(bot.user.id, cmd['id'])
    await bot.load_extension("help")
    await bot.load_extension("rpgcharactercreation")
    await bot.load_extension("rpginventory")
    await bot.load_extension("rpgparties")
    await bot.load_extension("rpglevelup")
    try:
        synced = await bot.tree.sync(guild=discord.Object(id=GUILD_ID))
        print(f"Synced {len(synced)} command(s).")
    except Exception as e:
        print(f"Error syncing commands: {e}")

bot.run(TOKEN)
