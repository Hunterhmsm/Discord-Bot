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




# --- Voice State Update Event ---
@bot.event
async def on_voice_state_update(member, before, after):
    now = datetime.datetime.now()
    uid = str(member.id)

    def non_bot_members(channel):
        return [m for m in channel.members if not m.bot]

    # -- Notification for target user --
    if member.id == TARGET_USER_ID:
        if before.channel is None and after.channel is not None:
            notif_channel = discord.utils.get(member.guild.text_channels, name="notif")
            if notif_channel is None:
                print("Channel #notif not found.")
            else:
                role = discord.utils.get(member.guild.roles, name="notif")
                if role is None:
                    print("Role 'notif' not found.")
                else:
                    await notif_channel.send(f"{role.mention} Alert: {member.mention} has joined a voice channel!")

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

# --- Join/Leave Notification Commands ---
@bot.tree.command(name="joinnotification", description="Join the notif notifications", guild=discord.Object(id=GUILD_ID))
async def joinnotification(interaction: discord.Interaction):
    role = discord.utils.get(interaction.guild.roles, name="notif")
    if role is None:
        await interaction.response.send_message("The role 'notif' does not exist.", ephemeral=True)
        return
    member = interaction.user
    if role in member.roles:
        await interaction.response.send_message("You already have the 'notif' role.", ephemeral=True)
    else:
        try:
            await member.add_roles(role)
            await interaction.response.send_message("You have been given the 'notif' role.", ephemeral=True)
        except Exception:
            await interaction.response.send_message("Error assigning the role.", ephemeral=True)

@bot.tree.command(name="leavenotification", description="Leave the notif notifications", guild=discord.Object(id=GUILD_ID))
async def leavenotification(interaction: discord.Interaction):
    role = discord.utils.get(interaction.guild.roles, name="notif")
    if role is None:
        await interaction.response.send_message("The role 'notif' does not exist.", ephemeral=True)
        return
    member = interaction.user
    if role not in member.roles:
        await interaction.response.send_message("You don't have the 'notif' role.", ephemeral=True)
    else:
        try:
            await member.remove_roles(role)
            await interaction.response.send_message("The 'notif' role has been removed.", ephemeral=True)
        except Exception:
            await interaction.response.send_message("Error removing the role.", ephemeral=True)

#leaderboard command
@bot.tree.command(
    name="leaderboard",
    description="View the leaderboard. Categories: networth, time, timealone, or timeafk.",
    guild=discord.Object(id=GUILD_ID)
)
@app_commands.describe(category="Choose a category: networth, time, timealone, or timeafk")
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
    await bot.load_extension("industry")
    try:
        synced = await bot.tree.sync(guild=discord.Object(id=GUILD_ID))
        print(f"Synced {len(synced)} command(s).")
    except Exception as e:
        print(f"Error syncing commands: {e}")
    update_active_vc_sessions_on_startup()

bot.run(TOKEN)
