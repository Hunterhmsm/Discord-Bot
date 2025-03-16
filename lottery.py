#lottery.py
import discord
from discord import app_commands
from discord.ext import commands, tasks
import json
import os
import random
import datetime
import asyncio
from zoneinfo import ZoneInfo
from globals import LOTTERY_FILE, GUILD_ID, ALLOWED_ROLES
from utils import load_data, save_data

def load_lottery():
    try:
        with open(LOTTERY_FILE, "r") as f:
            data = json.load(f)
            if "Jackpot" not in data:
                data["Jackpot"] = 100000
            if "Tickets" not in data:
                data["Tickets"] = []
            return data
    except (FileNotFoundError, json.JSONDecodeError):
        default_data = {"Jackpot": 100000, "Tickets": []}
        save_lottery(default_data)
        return default_data

def save_lottery(data):
    with open(LOTTERY_FILE, "w") as f:
        json.dump(data, f, indent=4)

def lottery_draw():
    lottery_data = load_lottery()
    jackpot = lottery_data.get("Jackpot", 100000)
    tickets = lottery_data.get("Tickets", [])
    drawn_numbers = random.sample(range(1, 61), 5)
    drawn_set = set(drawn_numbers)
    print(f"[Lottery] Drawn Numbers: {drawn_numbers}")

    winners = {1: [], 2: [], 3: [], 4: [], 5: []}
    for ticket in tickets:
        chosen = set(ticket.get("numbers", []))
        if len(chosen) != 5:
            continue
        matches = len(chosen.intersection(drawn_set))
        if matches >= 1:
            #only record tickets with at least one match.
            winners[matches].append(ticket["user_id"])

    total_payout = 0
    payouts = {}
    fixed_percentages = {1: 0.20, 2: 0.40, 3: 0.60, 4: 0.80, 5: 1.00}

    for matches, users in winners.items():
        if users:
            #the total group allocation is fixed percentage * jackpot.
            group_allocation = fixed_percentages[matches] * jackpot
            #each ticket in this group gets an equal share.
            share = group_allocation / len(users)
            for uid in users:
                payouts[uid] = payouts.get(uid, 0) + share
                total_payout += share

    #calculate the new jackpot 
    new_jackpot = jackpot - total_payout + 50000
    lottery_data["Jackpot"] = new_jackpot
    lottery_data["Tickets"] = []
    save_lottery(lottery_data)
    return drawn_numbers, payouts


class LotteryCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        #start the daily lottery draw task.
        self.daily_task = tasks.loop(hours=24)(self.daily_lottery_draw)
        self.daily_task.before_loop(self.before_daily_lottery_draw)
        self.daily_task.start()

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="lotteryticket", description="Buy a lottery ticket for 1,000 Beaned Bucks. Choose 5 unique numbers from 1 to 60.")
    async def lotteryticket(self, interaction: discord.Interaction, numbers: str):
        try:
            chosen_numbers = [int(n) for n in numbers.split()]
        except ValueError:
            await interaction.response.send_message("Invalid numbers. Please enter 5 numbers separated by spaces.", ephemeral=True)
            return

        if len(chosen_numbers) != 5 or len(set(chosen_numbers)) != 5 or any(n < 1 or n > 60 for n in chosen_numbers):
            await interaction.response.send_message("You must provide 5 unique numbers between 1 and 60.", ephemeral=True)
            return

        user_data = load_data()
        user_id = str(interaction.user.id)
        user_record = user_data.get(user_id, {"balance": 0})
        if user_record.get("balance", 0) < 1000:
            await interaction.response.send_message("You do not have enough Beaned Bucks to buy a lottery ticket.", ephemeral=True)
            return

        user_record["balance"] -= 1000
        user_data[user_id] = user_record
        save_data(user_data)

        lottery_data = load_lottery()
        lottery_data["Jackpot"] = lottery_data.get("Jackpot", 100000) + 1000
        ticket = {"user_id": user_id, "numbers": sorted(chosen_numbers)}
        lottery_data["Tickets"].append(ticket)
        save_lottery(lottery_data)

        await interaction.response.send_message(f"Ticket purchased with numbers: {sorted(chosen_numbers)}. 1000 Beaned Bucks deducted.", ephemeral=False)

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="lotterytotal", description="View the current lottery jackpot.")
    async def lotterytotal(self, interaction: discord.Interaction):
        lottery_data = load_lottery()
        jackpot = lottery_data.get("Jackpot", 100000)
        await interaction.response.send_message(f"The current lottery jackpot is {jackpot} Beaned Bucks.", ephemeral=False)

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="lotterydraw", description="Perform the lottery draw. (Restricted to lottery admins.)")
    async def lotterydraw(self, interaction: discord.Interaction):
        if not any(role.name.lower() == "him" for role in interaction.user.roles):
            await interaction.response.send_message("You do not have permission to run the lottery draw.", ephemeral=True)
            return
        drawn_numbers, payouts = lottery_draw()
        user_data = load_data()
        winners_msg = ""
        if payouts:
            for uid, amount in payouts.items():
                record = user_data.get(uid, {"balance": 0})
                record["balance"] = record.get("balance", 0) + amount
                user_data[uid] = record
                member = interaction.guild.get_member(int(uid))
                name = member.display_name if member else f"User {uid}"
                winners_msg += f"{name} wins {amount:.2f} Beaned Bucks.\n"
            save_data(user_data)
        else:
            winners_msg = "No winning tickets this draw."
        await interaction.response.send_message(f"Drawn Numbers: {drawn_numbers}\n{winners_msg}")
        
    async def daily_lottery_draw(self):
        drawn_numbers, payouts = lottery_draw()
        user_data = load_data()
        winners_msg = ""
        if payouts:
            for uid, amount in payouts.items():
                record = user_data.get(uid, {"balance": 0})
                record["balance"] = record.get("balance", 0) + amount
                user_data[uid] = record
                member = self.bot.get_guild(GUILD_ID).get_member(int(uid))
                name = member.display_name if member else f"User {uid}"
                winners_msg += f"{name} wins {amount:.2f} Beaned Bucks.\n"
            save_data(user_data)
        else:
            winners_msg = "No winning tickets this draw."
        channel = discord.utils.get(self.bot.get_all_channels(), name="bot-output")
        if channel:
            await channel.send(f"Daily Lottery Draw at 4pm ET:\nDrawn Numbers: {drawn_numbers}\n{winners_msg}")
        else:
            print("Channel not found for lottery.")

    async def before_daily_lottery_draw(self):
        now_et = datetime.datetime.now(ZoneInfo("America/New_York"))
        target_et = now_et.replace(hour=16, minute=0, second=0, microsecond=0)
        
        #if we're before 4pm, wait until 4pm.
        if now_et < target_et:
            delay = (target_et - now_et).total_seconds()
        #if we're between 4:00 and 4:05 pm, run immediately.
        elif now_et <= target_et + datetime.timedelta(minutes=5):
            delay = 0
        else:
            #if we're more than 5 minutes past 4pm, schedule for tomorrow at 4pm.
            target_et += datetime.timedelta(days=1)
            delay = (target_et - now_et).total_seconds()
        
        print(f"Waiting {delay} seconds until next lottery draw.")
        await asyncio.sleep(delay)


async def setup(bot: commands.Bot):
    print("Loading LotteryCog...")
    await bot.add_cog(LotteryCog(bot))
