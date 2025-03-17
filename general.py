#includes more general commands
#/crime /work /daily /dailyboost /pay /balance /wheel
import discord
from discord import app_commands
from discord.ext import commands
import random
import datetime
import json
import os
from typing import Optional
from globals import TOKEN, GUILD_ID, TARGET_MEMBER_ID, TARGET_USER_ID, DATA_FILE, ALLOWED_ROLES, STOCK_FILE, STOCK_HISTORY_FILE, UPDATE_INTERVAL_MINUTES, LOTTERY_FILE, AFK_CHANNEL_ID
from utils import load_data, save_data
class GeneralCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        #track the last time a user used /crime.
        self.crime_cooldowns = {}  
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="crime", description="Commit a crime for a chance to earn 500-1000 Beaned Bucks. (15-minute cooldown)")
    async def crime(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        now = datetime.datetime.now(datetime.timezone.utc)
        cooldown = datetime.timedelta(minutes=15)
        last_used = self.crime_cooldowns.get(user_id)
        
        if last_used and now - last_used < cooldown:
            remaining = cooldown - (now - last_used)
            minutes = remaining.seconds // 60
            seconds = remaining.seconds % 60
            await interaction.response.send_message(
                f"You must wait {minutes} minutes and {seconds} seconds before committing another crime.",
                ephemeral=True
            )
            return

        #set the new cooldown timestamp.
        self.crime_cooldowns[user_id] = now

        #roll the outcome.
        roll = random.random()
        if roll < 0.60:
            #success reward between 500 and 1000.
            reward = random.randint(500, 1000)
            data = load_data()
            user_record = data.get(user_id, {"balance": 0})
            user_record["balance"] = user_record.get("balance", 0) + reward
            data[user_id] = user_record
            save_data(data)
            await interaction.response.send_message(
                f"You successfully committed a crime and earned {reward} Beaned Bucks! Your new balance is {user_record['balance']}.",
                ephemeral=False
            )
        elif roll < 0.60 + 0.35:
            #failure timeout for 1 minute.
            timeout_duration = 60  
            try:
                until = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=timeout_duration)
                await interaction.user.timeout(until)
                await interaction.response.send_message(
                    "You were caught! You have been timed out for 1 minute.",
                    ephemeral=False
                )
            except Exception as e:
                await interaction.response.send_message(
                    f"You were caught, but I couldn't timeout you due to an error: {e}",
                    ephemeral=True
                )
        else:
            #failure timeout for 10 minutes.
            timeout_duration = 600 
            try:
                until = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=timeout_duration)
                await interaction.user.timeout(until)
                await interaction.response.send_message(
                    "You were caught in a big heist gone wrong! You have been timed out for 10 minutes.",
                    ephemeral=False
                )
            except Exception as e:
                await interaction.response.send_message(
                    f"You were caught, but I couldn't timeout you due to an error: {e}",
                    ephemeral=True
                )
    
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="daily", description="Claim your daily reward of 1000-3000 Beaned Bucks (once every 24 hours).")
    async def daily(self, interaction: discord.Interaction):
        data = load_data()
        user_id = str(interaction.user.id)
        now = datetime.datetime.now()
        
        #retrieve or initialize user record with a default balance of 0.
        user_record = data.get(user_id, {})
        user_record.setdefault("balance", 0)
        user_record.setdefault("last_daily", None)
        
        #check if the user has already claimed within the last 24 hours.
        last_daily_str = user_record.get("last_daily")
        if last_daily_str:
            last_daily = datetime.datetime.fromisoformat(last_daily_str)
            if now - last_daily < datetime.timedelta(days=1):
                remaining = datetime.timedelta(days=1) - (now - last_daily)
            
                # Calculate the remaining hours, minutes, and seconds
                remaining_hours = remaining.seconds // 3600  # Get the number of whole hours
                remaining_minutes = (remaining.seconds % 3600) // 60  # Get the remaining minutes after hours are accounted for
                remaining_seconds = remaining.seconds % 60  # Get the remaining seconds after minutes are accounted for
            
                # Send the response with the calculated time left
                await interaction.response.send_message(
                f"You have already claimed your daily reward. Try again in {remaining_hours} hours, {remaining_minutes} minutes, and {remaining_seconds} seconds.",
                ephemeral=True
                )
                return

        #award a random amount between 500 and 1000 Beaned Bucks.
        reward = random.randint(1000, 5000)
        user_record["balance"] += reward
        user_record["last_daily"] = now.isoformat()
        data[user_id] = user_record
        save_data(data)
        
        await interaction.response.send_message(
            f"You received {reward} Beaned Bucks! Your new balance is {user_record['balance']}.",
            ephemeral=True
        )
      
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="dailyboost", description="Claim your daily booster reward (5,000-15,000 Beaned Bucks) if you are a Server Booster.")
    async def dailyboost(self, interaction: discord.Interaction):
        #check if the user is a server booster.
        if interaction.user.premium_since is None:
            await interaction.response.send_message("You must be a Server Booster to claim this reward.", ephemeral=True)
            return

        data = load_data()
        user_id = str(interaction.user.id)
        now = datetime.datetime.now()

        #retrieve or initialize user record with default keys.
        user_record = data.get(user_id, {})
        user_record.setdefault("balance", 0)
        user_record.setdefault("last_daily_boost", None)

        last_boost_str = user_record.get("last_daily_boost")
        if last_boost_str:
            last_boost = datetime.datetime.fromisoformat(last_boost_str)
            if now - last_boost < datetime.timedelta(days=1):
                remaining = datetime.timedelta(days=1) - (now - last_boost)
                # Calculate the remaining hours, minutes, and seconds
                remaining_hours = remaining.seconds // 3600  # Get the number of whole hours
                remaining_minutes = (remaining.seconds % 3600) // 60  # Get the remaining minutes after hours are accounted for
                remaining_seconds = remaining.seconds % 60  # Get the remaining seconds after minutes are accounted for
                await interaction.response.send_message(
                    f"You have already claimed your daily booster reward. Try again in {remaining_hours} hours, {remaining_minutes} minutes and {remaining_seconds} seconds.",
                    ephemeral=True
                )
                return

        reward = random.randint(5000, 10000)
        user_record["balance"] += reward
        user_record["last_daily_boost"] = now.isoformat()
        data[user_id] = user_record
        save_data(data)
        
        await interaction.response.send_message(
            f"You worked as a booster and earned {reward} Beaned Bucks! Your new balance is {user_record['balance']}.",
            ephemeral=True
        )

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="pay", description="Transfer Beaned Bucks to another user.")
    @app_commands.describe(user="The user to transfer Beaned Bucks to", amount="The amount of Beaned Bucks to transfer")
    async def pay(self, interaction: discord.Interaction, user: discord.Member, amount: int):
        payer_id = str(interaction.user.id)
        payee_id = str(user.id)
        data = load_data()

        #ensure both payer and payee have an entry in the data.
        if payer_id not in data:
            data[payer_id] = {"balance": 0}
        if payee_id not in data:
            data[payee_id] = {"balance": 0}

        #check that the transfer amount is positive.
        if amount <= 0:
            await interaction.response.send_message("Transfer amount must be greater than 0.", ephemeral=True)
            return

        payer_balance = data[payer_id].get("balance", 0)
        if payer_balance < amount:
            await interaction.response.send_message("You do not have enough Beaned Bucks to complete this transfer.", ephemeral=True)
            return

        #subtract from payer and add to payee.
        data[payer_id]["balance"] = payer_balance - amount
        payee_balance = data[payee_id].get("balance", 0)
        data[payee_id]["balance"] = payee_balance + amount

        save_data(data)

        await interaction.response.send_message(
            f"You have transferred {amount} Beaned Bucks to {user.display_name}.",
            ephemeral=False
        )

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="balance", description="Show the Beaned Bucks balance of a user.")
    @app_commands.describe(user="The user to check balance for (defaults to yourself if not provided).")
    async def balance(self, interaction: discord.Interaction, user: Optional[discord.Member] = None):
        #default to the interaction user if no user is specified.
        target = user or interaction.user
        data = load_data()
        user_id = str(target.id)
        user_record = data.get(user_id, {"balance": 0})
        balance_value = user_record.get("balance", 0)
        
        await interaction.response.send_message(f"{target.display_name} has {balance_value} Beaned Bucks.")


    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="work", description="Work and earn between 1 and 500 Beaned Bucks (once every 10 minutes).")
    async def work(self, interaction: discord.Interaction):
        data = load_data()
        user_id = str(interaction.user.id)
        now = datetime.datetime.now()

        # Retrieve or initialize user record with default keys.
        user_record = data.get(user_id, {})
        user_record.setdefault("balance", 0)
        user_record.setdefault("last_work", None)

        last_work_str = user_record.get("last_work")
        if last_work_str:
            last_work = datetime.datetime.fromisoformat(last_work_str)
            if now - last_work < datetime.timedelta(minutes=10):
                remaining = datetime.timedelta(minutes=10) - (now - last_work)
                minutes = remaining.seconds // 60
                seconds = remaining.seconds % 60
                await interaction.response.send_message(
                    f"You can work again in {minutes} minutes and {seconds} seconds.",
                    ephemeral=True
                )
                return

        reward = random.randint(1, 500)
        user_record["balance"] += reward
        user_record["last_work"] = now.isoformat()
        data[user_id] = user_record
        save_data(data)
        
        await interaction.response.send_message(
            f"You worked and earned {reward} Beaned Bucks! Your new balance is {user_record['balance']}.",
            ephemeral=True
        )


    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="wheel", description="Timeout a user randomly with varying durations if you have at least 25,000 Beaned Bucks.")
    @app_commands.describe(target="The user to be timed out")
    async def wheel(self, interaction: discord.Interaction, target: discord.Member):
        invoker = interaction.user
        has_allowed_role = any(role.name.lower() in [r.lower() for r in ALLOWED_ROLES] for role in invoker.roles)
        data = load_data()
        user_id = str(invoker.id)
        user_balance = data.get(user_id, {}).get("balance", 0)
        if not has_allowed_role:
            if user_balance < 25000:
                await interaction.response.send_message("You do not have permission to use this command. You must either have one of the allowed roles or at least 10,000 Beaned Bucks.", ephemeral=True)
                return
            else:
                data[user_id]["balance"] = user_balance - 25000
                save_data(data)
        options = [
            (60, "60 seconds"),
            (300, "5 minutes"),
            (600, "10 minutes"),
            (3600, "1 hour"),
            (86400, "1 day"),
            (604800, "1 week"),
        ]
        weights = [55, 20, 15, 5, 4, 1]
        duration_seconds, label = random.choices(options, weights=weights, k=1)[0]
        timeout_until = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=duration_seconds)
        try:
            await target.timeout(timeout_until)
            await interaction.response.send_message(f"{target.mention} has been timed out for {label}!")
        except Exception as e:
            print(f"Error during timeout: {e}")

            await interaction.response.send_message("Failed to timeout the user. Check my permissions.", ephemeral=True)
            
async def setup(bot: commands.Bot):
    print("Loading GeneralCog...")
    await bot.add_cog(GeneralCog(bot))