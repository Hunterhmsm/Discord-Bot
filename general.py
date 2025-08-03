# General commands with proper bank/cash separation
import discord
from discord import app_commands
from discord.ext import commands
import random
import datetime
from typing import Optional
from globals import GUILD_ID, DATA_FILE, ALLOWED_ROLES
from utils import load_data, save_data

class GeneralCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        
    def format_time_remaining(self, remaining_timedelta):
        """Format timedelta into readable string"""
        total_seconds = int(remaining_timedelta.total_seconds())
        days = total_seconds // 86400
        hours = (total_seconds % 86400) // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        
        if days > 0:
            return f"{days} days, {hours} hours, {minutes} minutes, {seconds} seconds"
        elif hours > 0:
            return f"{hours} hours, {minutes} minutes, {seconds} seconds"
        else:
            return f"{minutes} minutes, {seconds} seconds"

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="balance", description="Show your bank and cash balances.")
    @app_commands.describe(user="The user to check balance for (defaults to yourself)")
    async def balance(self, interaction: discord.Interaction, user: Optional[discord.Member] = None):
        target = user or interaction.user
        data = load_data()
        user_id = str(target.id)
        user_record = data.get(user_id, {"balance": 0, "cash": 0})
        
        # Backwards compatibility
        if "cash" not in user_record:
            user_record["cash"] = 0
        
        bank_balance = user_record.get("balance", 0)
        cash_balance = user_record.get("cash", 0)
        total = bank_balance + cash_balance
        
        embed = discord.Embed(
            title=f"{target.display_name}'s Wallet",
            color=discord.Color.green()
        )
        embed.add_field(name="🏦 Bank", value=f"{bank_balance:,} Beaned Bucks", inline=True)
        embed.add_field(name="💵 Cash", value=f"{cash_balance:,} Beaned Bucks", inline=True)
        embed.add_field(name="💰 Total", value=f"{total:,} Beaned Bucks", inline=False)
        
        await interaction.response.send_message(embed=embed)

    # === BANK INCOME SOURCES ===
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="daily", description="Claim your daily bank reward (1000-5000 Beaned Bucks, once every 24 hours).")
    async def daily(self, interaction: discord.Interaction):
        data = load_data()
        user_id = str(interaction.user.id)
        now = datetime.datetime.now()
        
        user_record = data.get(user_id, {"balance": 0, "cash": 0})
        user_record.setdefault("last_daily", None)
        
        # Check cooldown
        last_daily_str = user_record.get("last_daily")
        if last_daily_str:
            last_daily = datetime.datetime.fromisoformat(last_daily_str)
            if now - last_daily < datetime.timedelta(days=1):
                remaining = datetime.timedelta(days=1) - (now - last_daily)
                await interaction.response.send_message(
                    f"You have already claimed your daily reward. Try again in {self.format_time_remaining(remaining)}.",
                    ephemeral=True
                )
                return

        # Give bank money
        reward = random.randint(1000, 5000)
        user_record["balance"] = user_record.get("balance", 0) + reward
        user_record["last_daily"] = now.isoformat()
        data[user_id] = user_record
        save_data(data)
        
        await interaction.response.send_message(
            f"🏦 You received {reward:,} Beaned Bucks in your bank! Bank balance: {user_record['balance']:,}",
            ephemeral=True
        )

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="dailyboost", description="Claim your daily booster bank reward (5000-10000 Beaned Bucks) if you're a Server Booster.")
    async def dailyboost(self, interaction: discord.Interaction):
        if interaction.user.premium_since is None:
            await interaction.response.send_message("You must be a Server Booster to claim this reward.", ephemeral=True)
            return

        data = load_data()
        user_id = str(interaction.user.id)
        now = datetime.datetime.now()

        user_record = data.get(user_id, {"balance": 0, "cash": 0})
        user_record.setdefault("last_daily_boost", None)

        # Check cooldown
        last_boost_str = user_record.get("last_daily_boost")
        if last_boost_str:
            last_boost = datetime.datetime.fromisoformat(last_boost_str)
            if now - last_boost < datetime.timedelta(days=1):
                remaining = datetime.timedelta(days=1) - (now - last_boost)
                await interaction.response.send_message(
                    f"You have already claimed your booster reward. Try again in {self.format_time_remaining(remaining)}.",
                    ephemeral=True
                )
                return

        # Give bank money
        reward = random.randint(5000, 10000)
        user_record["balance"] = user_record.get("balance", 0) + reward
        user_record["last_daily_boost"] = now.isoformat()
        data[user_id] = user_record
        save_data(data)
        
        await interaction.response.send_message(
            f"🏦 Booster reward: {reward:,} Beaned Bucks added to your bank! Bank balance: {user_record['balance']:,}",
            ephemeral=True
        )

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="work", description="Work for bank money (1-500 Beaned Bucks, once every 10 minutes).")
    async def work(self, interaction: discord.Interaction):
        data = load_data()
        user_id = str(interaction.user.id)
        now = datetime.datetime.now()

        user_record = data.get(user_id, {"balance": 0, "cash": 0})
        user_record.setdefault("last_work", None)

        # Check cooldown
        last_work_str = user_record.get("last_work")
        if last_work_str:
            last_work = datetime.datetime.fromisoformat(last_work_str)
            if now - last_work < datetime.timedelta(minutes=10):
                remaining = datetime.timedelta(minutes=10) - (now - last_work)
                await interaction.response.send_message(
                    f"You can work again in {self.format_time_remaining(remaining)}.",
                    ephemeral=True
                )
                return

        # Give bank money
        reward = random.randint(1, 500)
        user_record["balance"] = user_record.get("balance", 0) + reward
        user_record["last_work"] = now.isoformat()
        data[user_id] = user_record
        save_data(data)
        
        await interaction.response.send_message(
            f"🏦 You worked and earned {reward} Beaned Bucks! Bank balance: {user_record['balance']:,}",
            ephemeral=True
        )

    # === MONEY MANAGEMENT ===
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="withdraw", description="Withdraw money from bank to cash.")
    @app_commands.describe(amount="Amount to withdraw (or 'all')")
    async def withdraw(self, interaction: discord.Interaction, amount: str):
        data = load_data()
        user_id = str(interaction.user.id)
        user_record = data.get(user_id, {"balance": 0, "cash": 0})
        
        bank_balance = user_record.get("balance", 0)
        
        if amount.lower() == "all":
            withdraw_amount = bank_balance
        else:
            try:
                withdraw_amount = int(amount)
            except ValueError:
                await interaction.response.send_message("Invalid amount. Use a number or 'all'.", ephemeral=True)
                return
        
        if withdraw_amount <= 0:
            await interaction.response.send_message("Amount must be greater than 0.", ephemeral=True)
            return
        if withdraw_amount > bank_balance:
            await interaction.response.send_message(f"Insufficient bank funds. You have {bank_balance:,}.", ephemeral=True)
            return
        
        user_record["balance"] = bank_balance - withdraw_amount
        user_record["cash"] = user_record.get("cash", 0) + withdraw_amount
        data[user_id] = user_record
        save_data(data)
        
        await interaction.response.send_message(
            f"💸 Withdrew {withdraw_amount:,} from bank to cash.\n"
            f"🏦 Bank: {user_record['balance']:,} | 💵 Cash: {user_record['cash']:,}",
            ephemeral=True
        )

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="deposit", description="Deposit cash into bank.")
    @app_commands.describe(amount="Amount to deposit (or 'all')")
    async def deposit(self, interaction: discord.Interaction, amount: str):
        data = load_data()
        user_id = str(interaction.user.id)
        user_record = data.get(user_id, {"balance": 0, "cash": 0})
        
        cash_balance = user_record.get("cash", 0)
        
        if amount.lower() == "all":
            deposit_amount = cash_balance
        else:
            try:
                deposit_amount = int(amount)
            except ValueError:
                await interaction.response.send_message("Invalid amount. Use a number or 'all'.", ephemeral=True)
                return
        
        if deposit_amount <= 0:
            await interaction.response.send_message("Amount must be greater than 0.", ephemeral=True)
            return
        if deposit_amount > cash_balance:
            await interaction.response.send_message(f"Insufficient cash. You have {cash_balance:,}.", ephemeral=True)
            return
        
        user_record["cash"] = cash_balance - deposit_amount
        user_record["balance"] = user_record.get("balance", 0) + deposit_amount
        data[user_id] = user_record
        save_data(data)
        
        await interaction.response.send_message(
            f"🏦 Deposited {deposit_amount:,} from cash to bank.\n"
            f"🏦 Bank: {user_record['balance']:,} | 💵 Cash: {user_record['cash']:,}",
            ephemeral=True
        )

    # === TRANSFERS ===
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="pay", description="Transfer cash to another user (instant, no fees).")
    @app_commands.describe(user="User to pay", amount="Amount of cash to transfer")
    async def pay(self, interaction: discord.Interaction, user: discord.Member, amount: int):
        if user.id == interaction.user.id:
            await interaction.response.send_message("You cannot pay yourself.", ephemeral=True)
            return
        if user.bot:
            await interaction.response.send_message("You cannot pay bots.", ephemeral=True)
            return
            
        payer_id = str(interaction.user.id)
        payee_id = str(user.id)
        data = load_data()

        # Ensure records exist
        if payer_id not in data:
            data[payer_id] = {"balance": 0, "cash": 0}
        if payee_id not in data:
            data[payee_id] = {"balance": 0, "cash": 0}
        if "cash" not in data[payer_id]:
            data[payer_id]["cash"] = 0
        if "cash" not in data[payee_id]:
            data[payee_id]["cash"] = 0

        if amount <= 0:
            await interaction.response.send_message("Amount must be greater than 0.", ephemeral=True)
            return

        payer_cash = data[payer_id].get("cash", 0)
        if payer_cash < amount:
            await interaction.response.send_message(f"Insufficient cash. You have {payer_cash:,}, need {amount:,}.", ephemeral=True)
            return

        # Transfer
        data[payer_id]["cash"] = payer_cash - amount
        data[payee_id]["cash"] = data[payee_id].get("cash", 0) + amount
        save_data(data)

        await interaction.response.send_message(f"💵 Transferred {amount:,} cash to {user.display_name}.", ephemeral=False)

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="pay_bank", description="Transfer bank money to another user (10% fee, but safe).")
    @app_commands.describe(user="User to pay", amount="Amount to transfer (before 10% fee)")
    async def pay_bank(self, interaction: discord.Interaction, user: discord.Member, amount: int):
        if user.id == interaction.user.id:
            await interaction.response.send_message("You cannot pay yourself.", ephemeral=True)
            return
        if user.bot:
            await interaction.response.send_message("You cannot pay bots.", ephemeral=True)
            return
            
        payer_id = str(interaction.user.id)
        payee_id = str(user.id)
        data = load_data()

        # Ensure records exist
        if payer_id not in data:
            data[payer_id] = {"balance": 0, "cash": 0}
        if payee_id not in data:
            data[payee_id] = {"balance": 0, "cash": 0}

        if amount <= 0:
            await interaction.response.send_message("Amount must be greater than 0.", ephemeral=True)
            return

        fee = int(amount * 0.10)
        total_cost = amount + fee
        
        payer_bank = data[payer_id].get("balance", 0)
        if payer_bank < total_cost:
            await interaction.response.send_message(
                f"Insufficient bank funds. Need {total_cost:,} (transfer: {amount:,} + fee: {fee:,}), have {payer_bank:,}.",
                ephemeral=True
            )
            return

        # Transfer
        data[payer_id]["balance"] = payer_bank - total_cost
        data[payee_id]["balance"] = data[payee_id].get("balance", 0) + amount
        save_data(data)

        await interaction.response.send_message(f"🏦 Transferred {amount:,} bank money to {user.display_name} (fee: {fee:,}).", ephemeral=False)

    # === ENTERTAINMENT ===
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="wheel", description="Timeout someone randomly (costs 10,000 bank money or requires allowed role + prestige 2+).")
    @app_commands.describe(target="User to timeout")
    async def wheel(self, interaction: discord.Interaction, target: discord.Member):
        if target.id == interaction.user.id:
            await interaction.response.send_message("You cannot wheel yourself.", ephemeral=True)
            return
        if target.bot:
            await interaction.response.send_message("You cannot wheel bots.", ephemeral=True)
            return
            
        invoker = interaction.user
        has_allowed_role = any(role.name.lower() in [r.lower() for r in ALLOWED_ROLES] for role in invoker.roles)
        data = load_data()
        user_id = str(invoker.id)
        user_record = data.get(user_id, {"balance": 0, "cash": 0, "prestige": 0})
        user_balance = user_record.get("balance", 0)
        user_prestige = user_record.get("prestige", 0)
        
        # Check prestige
        if user_prestige < 2:
            await interaction.response.send_message("You need prestige level 2+ to use this command.", ephemeral=True)
            return
            
        # Check payment
        wheel_cost = 10000
        if not has_allowed_role:
            if user_balance < wheel_cost:
                await interaction.response.send_message(
                    f"You need either an allowed role or {wheel_cost:,} bank money.",
                    ephemeral=True
                )
                return
            else:
                user_record["balance"] = user_balance - wheel_cost
                data[user_id] = user_record
                save_data(data)

        # Wheel
        options = [(60, "60 seconds"), (300, "5 minutes"), (600, "10 minutes"), (3600, "1 hour"), (86400, "1 day"), (604800, "1 week")]
        weights = [55, 20, 15, 5, 4, 1]
        duration_seconds, label = random.choices(options, weights=weights, k=1)[0]
        timeout_until = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=duration_seconds)
        
        try:
            await target.timeout(timeout_until)
            cost_msg = f" (Cost: {wheel_cost:,})" if not has_allowed_role else ""
            await interaction.response.send_message(f"🎰 {target.mention} timed out for {label}!{cost_msg}")
        except Exception as e:
            await interaction.response.send_message(f"Failed to timeout {target.display_name}. Check permissions.", ephemeral=True)
            # Refund
            if not has_allowed_role:
                user_record["balance"] = user_balance
                data[user_id] = user_record
                save_data(data)
            
async def setup(bot: commands.Bot):
    print("Loading GeneralCog...")
    await bot.add_cog(GeneralCog(bot))