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
from globals import TOKEN, GUILD_ID, DATA_FILE, ALLOWED_ROLES, STOCK_FILE, STOCK_HISTORY_FILE, UPDATE_INTERVAL_MINUTES, LOTTERY_FILE, AFK_CHANNEL_ID
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

current_market_event = None

bot = commands.Bot(command_prefix="!", intents=intents)

def update_active_vc_sessions_on_startup():
    now = datetime.datetime.now()
    guild = bot.get_guild(GUILD_ID)
    if guild:
        for channel in guild.voice_channels:
            for member in channel.members:
                if not member.bot:
                    uid = str(member.id)
                    if uid not in active_vc_sessions:
                        non_bots = [m for m in channel.members if not m.bot]
                        active_vc_sessions[uid] = {
                            "join_time": now,
                            "channel_id": channel.id,
                            "last_alone_update": now if len(non_bots) == 1 else None,
                            "alone_accumulated": datetime.timedelta(0),
                            "afk": (channel.id == AFK_CHANNEL_ID or channel.name.lower() == "fuckin dead")
                        }
                        print(f"Added {member.display_name} (ID: {uid}) to active VC sessions.")


@tasks.loop(hours=4)
async def backup_data():
    backup_dir = "backups"
    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir)
    # Create a unique backup filename with timestamp
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = os.path.join(backup_dir, f"data_backup_{timestamp}.json")
    try:
        with open(DATA_FILE, "r") as f:
            data_content = f.read()
        with open(backup_file, "w") as f:
            f.write(data_content)
        print(f"Backup created at {backup_file}")
    except Exception as e:
        print(f"Failed to create backup: {e}")



# --- Voice State Update Event ---
@bot.event
async def on_voice_state_update(member, before, after):
    now = datetime.datetime.now()
    uid = str(member.id)

    def non_bot_members(channel):
        return [m for m in channel.members if not m.bot]

    #determine if the channel is the AFK channel.
    def is_afk(channel):
        return channel and (channel.id == AFK_CHANNEL_ID or channel.name.strip().lower() == "fuckin dead")
    
    #if a user joins a voice channel:
    if before.channel is None and after.channel is not None:
        channel = after.channel
        print(f"User {member.display_name} joined channel '{channel.name}' (ID: {channel.id}). is_afk: {is_afk(channel)}")
        members = non_bot_members(channel)
        alone = (len(members) == 1)
        #mark session as AFK if channel is the AFK channel.
        active_vc_sessions[uid] = {
            "join_time": now,
            "channel_id": channel.id,
            "last_alone_update": now if alone else None,
            "alone_accumulated": datetime.timedelta(0),
            "afk": is_afk(channel)
        }
    #if a user leaves a voice channel:
    elif before.channel is not None and after.channel is None:
        session = active_vc_sessions.pop(uid, None)
        if session:
            session_duration = now - session["join_time"]
            alone_time = session["alone_accumulated"]
            if session["last_alone_update"]:
                alone_time += now - session["last_alone_update"]
            data = load_data()
            #if session was AFK, update "vc_afk"; else update normal VC times.
            if session.get("afk"):
                record = data.get(uid, {"vc_afk": 0})
                record["vc_afk"] = record.get("vc_afk", 0) + session_duration.total_seconds()
            else:
                record = data.get(uid, {"vc_time": 0, "vc_timealone": 0})
                record["vc_time"] = record.get("vc_time", 0) + session_duration.total_seconds()
                record["vc_timealone"] = record.get("vc_timealone", 0) + alone_time.total_seconds()
            data[uid] = record
            save_data(data)
    #if a user switches voice channels:
    elif before.channel is not None and after.channel is not None:
        #end the old session.
        session = active_vc_sessions.pop(uid, None)
        if session:
            session_duration = now - session["join_time"]
            alone_time = session["alone_accumulated"]
            if session["last_alone_update"]:
                alone_time += now - session["last_alone_update"]
            data = load_data()
            #update the appropriate field based on whether it was AFK.
            if session.get("afk"):
                record = data.get(uid, {"vc_afk": 0})
                record["vc_afk"] = record.get("vc_afk", 0) + session_duration.total_seconds()
            else:
                record = data.get(uid, {"vc_time": 0, "vc_timealone": 0})
                record["vc_time"] = record.get("vc_time", 0) + session_duration.total_seconds()
                record["vc_timealone"] = record.get("vc_timealone", 0) + alone_time.total_seconds()
            data[uid] = record
            save_data(data)
        #start a new session for the new channel.
        channel = after.channel
        members = non_bot_members(channel)
        alone = (len(members) == 1)
        active_vc_sessions[uid] = {
            "join_time": now,
            "channel_id": channel.id,
            "last_alone_update": now if alone else None,
            "alone_accumulated": datetime.timedelta(0),
            "afk": is_afk(channel)
        }

    #additionally update alone status for users in both the before and after channels.
    for channel in [before.channel, after.channel]:
        if channel is None:
            continue
        members = non_bot_members(channel)
        for m in members:
            s = active_vc_sessions.get(str(m.id))
            if s and s["channel_id"] == channel.id:
                if len(members) == 1:
                    if s["last_alone_update"] is None:
                        s["last_alone_update"] = now
                else:
                    if s["last_alone_update"]:
                        delta = now - s["last_alone_update"]
                        s["alone_accumulated"] += delta
                        s["last_alone_update"] = None



# --- Custom Role Management ---
CREATED_ROLES_FILE = "created_roles.json"

def load_created_roles():
    """Load created roles from JSON file"""
    try:
        if os.path.exists(CREATED_ROLES_FILE):
            with open(CREATED_ROLES_FILE, "r") as f:
                return set(json.load(f))
        return set()
    except Exception as e:
        print(f"Error loading created roles: {e}")
        return set()

def save_created_roles(roles_set):
    """Save created roles to JSON file"""
    try:
        with open(CREATED_ROLES_FILE, "w") as f:
            json.dump(list(roles_set), f, indent=2)
    except Exception as e:
        print(f"Error saving created roles: {e}")

# Load created roles on startup
created_roles = load_created_roles()

@bot.tree.command(name="create_role", description="Create a new role that users can join (Requires 'huh' role)", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(rolename="The name of the role to create")
async def create_role(interaction: discord.Interaction, rolename: str):
    # Check if the invoking user has the "huh" role (case-insensitive)
    if not any(role.name.lower() == "huh" for role in interaction.user.roles):
        await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
        return
    
    # Check if role already exists
    existing_role = discord.utils.get(interaction.guild.roles, name=rolename)
    if existing_role:
        await interaction.response.send_message(f"Role '{rolename}' already exists.", ephemeral=True)
        return
    
    try:
        # Create the role
        new_role = await interaction.guild.create_role(name=rolename, mentionable=True)
        created_roles.add(rolename.lower())  # Store in lowercase for case-insensitive matching
        save_created_roles(created_roles)  # Save to file
        await interaction.response.send_message(f"Role '{rolename}' has been created successfully!", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"Error creating role: {e}", ephemeral=True)

@bot.tree.command(name="role_join", description="Join a role that was created with /create_role", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(role="The role to join")
async def role_join(interaction: discord.Interaction, role: str):
    # Check if this role was created with /create_role
    if role.lower() not in created_roles:
        await interaction.response.send_message("This role was not created with /create_role and cannot be joined.", ephemeral=True)
        return
    
    # Find the actual role object
    role_obj = discord.utils.get(interaction.guild.roles, name=role)
    if role_obj is None:
        # Role was deleted after creation, remove from our tracking
        created_roles.discard(role.lower())
        save_created_roles(created_roles)  # Save to file
        await interaction.response.send_message("This role no longer exists.", ephemeral=True)
        return
    
    member = interaction.user
    if role_obj in member.roles:
        await interaction.response.send_message(f"You already have the '{role}' role.", ephemeral=True)
    else:
        try:
            await member.add_roles(role_obj)
            await interaction.response.send_message(f"You have been given the '{role}' role.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"Error assigning the role: {e}", ephemeral=True)

#leaderboard command
@bot.tree.command(
    name="leaderboard",
    description="View the leaderboard. Categories: networth, prestige, time, timealone, or timeafk.",
    guild=discord.Object(id=GUILD_ID)
)
@app_commands.describe(category="Choose a category: networth, prestige, time, timealone, or timeafk")
async def leaderboard(interaction: discord.Interaction, category: str):
    category = category.lower()
    data = load_data()
    leaderboard_list = []

    if category == "networth":
        stock_prices = load_stocks()
        for user_id, record in data.items():
            balance = record.get("balance", 0)
            portfolio = record.get("portfolio", {})
            portfolio_value = sum(stock_prices.get(stock, 0) * shares for stock, shares in portfolio.items())
            networth = balance + portfolio_value + (record.get("graphics_cards", 0) * 10000)
            leaderboard_list.append((user_id, networth))
        title = "Net Worth Leaderboard"
    elif category == "time":
        #only include non-AFK voice channel time.
        for user_id, record in data.items():
            vc_time = record.get("vc_time", 0)
            leaderboard_list.append((user_id, vc_time))
        title = "Voice Channel Time Leaderboard (Non-AFK)"
    elif category == "timealone":
        #only include non-AFK alone time.
        for user_id, record in data.items():
            vc_timealone = record.get("vc_timealone", 0)
            leaderboard_list.append((user_id, vc_timealone))
        title = "Voice Channel Alone Time Leaderboard (Non-AFK)"
    elif category == "timeafk":
        #this one shows AFK time.
        for user_id, record in data.items():
            vc_afk = record.get("vc_afk", 0)
            leaderboard_list.append((user_id, vc_afk))
        title = "AFK Time Leaderboard"
    elif category == "prestige":
        for user_id, record in data.items():
            prestige = record.get("prestige", 0)
            leaderboard_list.append((user_id, prestige))
        title = "Prestige Leaderboard"
    else:
        await interaction.response.send_message("Invalid category. Please choose networth, time, timealone, or timeafk.", ephemeral=True)
        return

    leaderboard_list.sort(key=lambda x: x[1], reverse=True)
    embed = discord.Embed(title=title, color=discord.Color.gold())
    count = 0
    for user_id, value in leaderboard_list[:10]:
        count += 1
        member = interaction.guild.get_member(int(user_id))
        name = member.display_name if member else f"User {user_id}"
        if category == "networth":
            display_value = f"{value:.2f} Beaned Bucks"
        else:
            hrs = value // 3600
            mins = (value % 3600) // 60
            secs = value % 60
            display_value = f"{int(hrs)}h {int(mins)}m {int(secs)}s"
        embed.add_field(name=f"{count}. {name}", value=display_value, inline=False)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(
    name="exit",
    description="Shut down the bot and update VC trackers. (Restricted to users with the 'him' role.)",
    guild=discord.Object(id=GUILD_ID)
)
async def exit(interaction: discord.Interaction):
    #check if the invoking user has the "him" role (case-insensitive).
    if not any(role.name.lower() == "him" for role in interaction.user.roles):
        await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
        return

    now = datetime.datetime.now()
    data = load_data()
    #process all active VC sessions.
    for uid, session in list(active_vc_sessions.items()):
        session_duration = now - session["join_time"]
        alone_time = session["alone_accumulated"]
        if session["last_alone_update"]:
            alone_time += now - session["last_alone_update"]
        
        #check if this session is AFK
        if session.get("afk"):
            record = data.get(uid, {"vc_afk": 0})
            record["vc_afk"] = record.get("vc_afk", 0) + session_duration.total_seconds()
        else:
            record = data.get(uid, {"vc_time": 0, "vc_timealone": 0})
            record["vc_time"] = record.get("vc_time", 0) + session_duration.total_seconds()
            record["vc_timealone"] = record.get("vc_timealone", 0) + alone_time.total_seconds()
        
        data[uid] = record
        del active_vc_sessions[uid]

    save_data(data)
    await interaction.response.send_message("Shutting down the bot and updating VC trackers...", ephemeral=True)
    await bot.close()

#onready event
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    commands = await bot.http.get_global_commands(bot.user.id)
    for cmd in commands:
        await bot.http.delete_global_command(bot.user.id, cmd['id'])
    await bot.load_extension("general")
    await bot.load_extension("help")
    await bot.load_extension("stocks")
    await bot.load_extension("blackjack")
    await bot.load_extension("lottery")
    await bot.load_extension("roulette")
    await bot.load_extension("crypto")
    await bot.load_extension("options")
    await bot.load_extension("industry")
    await bot.load_extension("prestige")
    try:
        synced = await bot.tree.sync(guild=discord.Object(id=GUILD_ID))
        print(f"Synced {len(synced)} command(s).")
    except Exception as e:
        print(f"Error syncing commands: {e}")
    update_active_vc_sessions_on_startup()
    backup_data.start()

bot.run(TOKEN)