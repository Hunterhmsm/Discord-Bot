# Crime commands module - all criminal activities
import discord
from discord import app_commands
from discord.ext import commands
import random
import datetime
from globals import GUILD_ID
from utils import load_data, save_data

class CrimeCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Track cooldowns for different criminal activities
        self.crime_cooldowns = {}
        self.mug_cooldowns = {}
        self.storerobbery_cooldowns = {}
        self.bankheist_cooldowns = {}
        self.drugrobbery_cooldowns = {}
        
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
    @app_commands.command(name="crime", description="Commit petty crime for cash (500-1000, 15-minute cooldown, risk of timeout).")
    async def crime(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        now = datetime.datetime.now(datetime.timezone.utc)
        cooldown = datetime.timedelta(minutes=15)
        last_used = self.crime_cooldowns.get(user_id)
        
        # Check cooldown
        if last_used and now - last_used < cooldown:
            remaining = cooldown - (now - last_used)
            await interaction.response.send_message(
                f"You must wait {self.format_time_remaining(remaining)} before committing another petty crime.",
                ephemeral=True
            )
            return

        self.crime_cooldowns[user_id] = now

        # Roll outcome
        roll = random.random()
        if roll < 0.60:  # 60% success
            reward = random.randint(500, 1000)
            data = load_data()
            user_record = data.get(user_id, {"balance": 0, "cash": 0})
            user_record["cash"] = user_record.get("cash", 0) + reward
            data[user_id] = user_record
            save_data(data)
            
            await interaction.response.send_message(
                f"💵 Petty crime successful! You earned {reward} cash! Cash balance: {user_record['cash']:,}",
                ephemeral=False
            )
        elif roll < 0.95:  # 35% minor failure
            try:
                until = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=60)
                await interaction.user.timeout(until)
                await interaction.response.send_message("🚨 You were caught! Timed out for 1 minute.", ephemeral=False)
            except:
                await interaction.response.send_message("🚨 You were caught but couldn't be timed out!", ephemeral=True)
        else:  # 5% major failure
            try:
                until = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=600)
                await interaction.user.timeout(until)
                await interaction.response.send_message("🚨 Major crime gone wrong! Timed out for 10 minutes.", ephemeral=False)
            except:
                await interaction.response.send_message("🚨 Major crime failed but couldn't be timed out!", ephemeral=True)

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="mug", description="Steal 5-30% of someone's cash (15-minute cooldown, heavy fines if caught).")
    @app_commands.describe(target="The player to attempt to mug")
    async def mug(self, interaction: discord.Interaction, target: discord.Member):
        if target.id == interaction.user.id:
            await interaction.response.send_message("You cannot mug yourself.", ephemeral=True)
            return
        if target.bot:
            await interaction.response.send_message("You cannot mug bots.", ephemeral=True)
            return

        mugger_id = str(interaction.user.id)
        target_id = str(target.id)
        now = datetime.datetime.now(datetime.timezone.utc)
        cooldown = datetime.timedelta(minutes=15)
        last_used = self.mug_cooldowns.get(mugger_id)
        
        # Check cooldown
        if last_used and now - last_used < cooldown:
            remaining = cooldown - (now - last_used)
            await interaction.response.send_message(
                f"You must wait {self.format_time_remaining(remaining)} before attempting another mugging.",
                ephemeral=True
            )
            return

        self.mug_cooldowns[mugger_id] = now
        data = load_data()
        
        mugger_record = data.get(mugger_id, {"balance": 0, "cash": 0})
        target_record = data.get(target_id, {"balance": 0, "cash": 0})
        
        # Ensure cash exists
        if "cash" not in mugger_record:
            mugger_record["cash"] = 0
        if "cash" not in target_record:
            target_record["cash"] = 0

        target_cash = target_record.get("cash", 0)

        # Check minimum cash
        if target_cash < 100:
            await interaction.response.send_message(
                f"{target.display_name} doesn't have enough cash to mug (minimum: 100 cash).",
                ephemeral=True
            )
            return

        # Roll for success
        if random.random() < 0.50:  # 50% success
            steal_percentage = random.uniform(0.05, 0.30)
            stolen_amount = int(target_cash * steal_percentage)
            
            target_record["cash"] = target_cash - stolen_amount
            mugger_record["cash"] = mugger_record.get("cash", 0) + stolen_amount
            
            data[mugger_id] = mugger_record
            data[target_id] = target_record
            save_data(data)
            
            await interaction.response.send_message(
                f"💰 Mugging successful! You stole {stolen_amount:,} cash from {target.display_name} ({steal_percentage*100:.1f}%)!\n"
                f"Your cash: {mugger_record['cash']:,}",
                ephemeral=False
            )
            
            await interaction.followup.send(
                f"💸 {target.mention} You were mugged and lost {stolen_amount:,} cash! Your cash: {target_record['cash']:,}",
                ephemeral=False
            )
        else:  # 50% failure
            fine_amount = random.randint(100, 10000)
            mugger_cash = mugger_record.get("cash", 0)
            mugger_bank = mugger_record.get("balance", 0)
            
            # Take from cash first, then bank
            if fine_amount <= mugger_cash:
                mugger_record["cash"] = mugger_cash - fine_amount
                fine_msg = f"Fine: {fine_amount:,} cash"
            else:
                remaining_fine = fine_amount - mugger_cash
                if remaining_fine <= mugger_bank:
                    mugger_record["cash"] = 0
                    mugger_record["balance"] = mugger_bank - remaining_fine
                    fine_msg = f"Fine: {mugger_cash:,} cash + {remaining_fine:,} bank"
                else:
                    total = mugger_cash + mugger_bank
                    mugger_record["cash"] = 0
                    mugger_record["balance"] = 0
                    fine_msg = f"Fine: All your money ({total:,} total)"
            
            data[mugger_id] = mugger_record
            save_data(data)
            
            # Timeout
            timeout_duration = random.randint(120, 300)
            try:
                until = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=timeout_duration)
                await interaction.user.timeout(until)
                timeout_msg = f" and timed out for {timeout_duration//60} minutes"
            except:
                timeout_msg = ""
                
            await interaction.response.send_message(
                f"🚨 Caught mugging {target.display_name}! {fine_msg}{timeout_msg}.\n"
                f"Cash: {mugger_record['cash']:,} | Bank: {mugger_record['balance']:,}",
                ephemeral=False
            )

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="storerobbery", description="Rob a store for big cash (5000-20000, 40% success, but 1-hour timeout and 5000-10000 fine if caught).")
    async def storerobbery(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        now = datetime.datetime.now(datetime.timezone.utc)
        cooldown = datetime.timedelta(hours=2)  # 2-hour cooldown for store robbery
        last_used = self.storerobbery_cooldowns.get(user_id)
        
        # Check cooldown
        if last_used and now - last_used < cooldown:
            remaining = cooldown - (now - last_used)
            await interaction.response.send_message(
                f"You must wait {self.format_time_remaining(remaining)} before attempting another store robbery.",
                ephemeral=True
            )
            return

        self.storerobbery_cooldowns[user_id] = now

        # Roll outcome - 40% success rate
        roll = random.random()
        data = load_data()
        user_record = data.get(user_id, {"balance": 0, "cash": 0})
        
        if roll < 0.40:  # 40% success
            reward = random.randint(5000, 20000)
            user_record["cash"] = user_record.get("cash", 0) + reward
            data[user_id] = user_record
            save_data(data)
            
            await interaction.response.send_message(
                f"💰💰 STORE ROBBERY SUCCESSFUL! You escaped with {reward:,} cash!\n"
                f"Your cash balance: {user_record['cash']:,}",
                ephemeral=False
            )
        else:  # 60% failure
            # Heavy fine
            fine_amount = random.randint(5000, 10000)
            mugger_cash = user_record.get("cash", 0)
            mugger_bank = user_record.get("balance", 0)
            
            # Take from cash first, then bank
            if fine_amount <= mugger_cash:
                user_record["cash"] = mugger_cash - fine_amount
                fine_msg = f"Fine: {fine_amount:,} cash"
            else:
                remaining_fine = fine_amount - mugger_cash
                if remaining_fine <= mugger_bank:
                    user_record["cash"] = 0
                    user_record["balance"] = mugger_bank - remaining_fine
                    fine_msg = f"Fine: {mugger_cash:,} cash + {remaining_fine:,} bank"
                else:
                    total = mugger_cash + mugger_bank
                    user_record["cash"] = 0
                    user_record["balance"] = 0
                    fine_msg = f"Fine: All your money ({total:,} total)"
            
            data[user_id] = user_record
            save_data(data)
            
            # 1-hour timeout
            try:
                until = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)
                await interaction.user.timeout(until)
                timeout_msg = " and timed out for 1 HOUR"
            except:
                timeout_msg = " but couldn't be timed out"
                
            await interaction.response.send_message(
                f"🚨🚨 STORE ROBBERY FAILED! You were caught by security!\n"
                f"{fine_msg}{timeout_msg}.\n"
                f"Cash: {user_record['cash']:,} | Bank: {user_record['balance']:,}",
                ephemeral=False
            )

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="bankheist", description="Rob someone's bank account (Prestige 1+ only, 100k supplies, 10-20% steal, 20% success, massive fines).")
    @app_commands.describe(target="The player whose bank account you want to rob")
    async def bankheist(self, interaction: discord.Interaction, target: discord.Member):
        if target.id == interaction.user.id:
            await interaction.response.send_message("You cannot rob your own bank account.", ephemeral=True)
            return
        if target.bot:
            await interaction.response.send_message("You cannot rob bot bank accounts.", ephemeral=True)
            return

        heister_id = str(interaction.user.id)
        target_id = str(target.id)
        now = datetime.datetime.now(datetime.timezone.utc)
        cooldown = datetime.timedelta(hours=6)  # 6-hour cooldown for bank heists
        last_used = self.bankheist_cooldowns.get(heister_id)
        
        # Check cooldown
        if last_used and now - last_used < cooldown:
            remaining = cooldown - (now - last_used)
            await interaction.response.send_message(
                f"You must wait {self.format_time_remaining(remaining)} before attempting another bank heist.",
                ephemeral=True
            )
            return

        data = load_data()
        heister_record = data.get(heister_id, {"balance": 0, "cash": 0, "prestige": 0})
        target_record = data.get(target_id, {"balance": 0, "cash": 0})
        
        # Check prestige requirement
        heister_prestige = heister_record.get("prestige", 0)
        if heister_prestige < 1:
            await interaction.response.send_message(
                "You need at least prestige level 1 to attempt bank heists.", 
                ephemeral=True
            )
            return

        # Check upfront cost for supplies
        supplies_cost = 100000
        heister_bank = heister_record.get("balance", 0)
        heister_cash = heister_record.get("cash", 0)
        total_money = heister_bank + heister_cash

        if total_money < supplies_cost:
            await interaction.response.send_message(
                f"You need {supplies_cost:,} total money (bank + cash) to buy supplies for a bank heist. "
                f"You have {total_money:,} total.",
                ephemeral=True
            )
            return

        # Check if target has enough bank money to make it worthwhile
        target_bank = target_record.get("balance", 0)
        if target_bank < 10000:
            await interaction.response.send_message(
                f"{target.display_name} doesn't have enough bank money to make a heist worthwhile (minimum: 10,000).",
                ephemeral=True
            )
            return

        # Pay for supplies (take from bank first, then cash)
        if supplies_cost <= heister_bank:
            heister_record["balance"] = heister_bank - supplies_cost
        else:
            remaining_cost = supplies_cost - heister_bank
            heister_record["balance"] = 0
            heister_record["cash"] = heister_cash - remaining_cost

        # Set cooldown
        self.bankheist_cooldowns[heister_id] = now
        
        # Roll for success - 20% success rate
        roll = random.random()
        
        if roll < 0.20:  # 20% success
            # Steal 10-20% of target's bank account
            steal_percentage = random.uniform(0.10, 0.20)
            stolen_amount = int(target_bank * steal_percentage)
            
            # Transfer the money to heister's bank
            target_record["balance"] = target_bank - stolen_amount
            heister_record["balance"] = heister_record.get("balance", 0) + stolen_amount
            
            data[heister_id] = heister_record
            data[target_id] = target_record
            save_data(data)
            
            await interaction.response.send_message(
                f"🏦💰 BANK HEIST SUCCESSFUL! You robbed {target.display_name}'s bank and stole {stolen_amount:,} Beaned Bucks ({steal_percentage*100:.1f}%)!\n"
                f"Your bank balance: {heister_record['balance']:,}",
                ephemeral=False
            )
            
            await interaction.followup.send(
                f"🚨🏦 {target.mention} Your bank account was robbed! You lost {stolen_amount:,} Beaned Bucks!\n"
                f"Your remaining bank balance: {target_record['balance']:,}",
                ephemeral=False
            )
        else:  # 80% failure
            # Massive fine
            fine_amount = random.randint(50000, 100000)
            heister_cash_after = heister_record.get("cash", 0)
            heister_bank_after = heister_record.get("balance", 0)
            
            # Take fine from remaining money (cash first, then bank)
            if fine_amount <= heister_cash_after:
                heister_record["cash"] = heister_cash_after - fine_amount
                fine_msg = f"Fine: {fine_amount:,} cash"
            else:
                remaining_fine = fine_amount - heister_cash_after
                if remaining_fine <= heister_bank_after:
                    heister_record["cash"] = 0
                    heister_record["balance"] = heister_bank_after - remaining_fine
                    fine_msg = f"Fine: {heister_cash_after:,} cash + {remaining_fine:,} bank"
                else:
                    total_remaining = heister_cash_after + heister_bank_after
                    heister_record["cash"] = 0
                    heister_record["balance"] = 0
                    fine_msg = f"Fine: All remaining money ({total_remaining:,} total)"
            
            data[heister_id] = heister_record
            save_data(data)
            
            # 2-hour timeout for failed bank heist
            try:
                until = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=2)
                await interaction.user.timeout(until)
                timeout_msg = " and timed out for 2 HOURS"
            except:
                timeout_msg = " but couldn't be timed out"
                
            await interaction.response.send_message(
                f"🚨🏦 BANK HEIST FAILED! The security was too tight!\n"
                f"Supplies cost: {supplies_cost:,} | {fine_msg}{timeout_msg}.\n"
                f"Cash: {heister_record['cash']:,} | Bank: {heister_record['balance']:,}",
                ephemeral=False
            )

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="drugrobbery", description="Rob drugs from someone or steal from dealers (5-30% of player drugs, risky but rewarding).")
    @app_commands.describe(target="Optional player to rob drugs from (leave blank to rob dealers)")
    async def drugrobbery(self, interaction: discord.Interaction, target: discord.Member = None):
        robber_id = str(interaction.user.id)
        now = datetime.datetime.now(datetime.timezone.utc)
        
        last_used = self.drugrobbery_cooldowns.get(robber_id)
        
        # Check if user is on cooldown
        if last_used:
            time_since = now - last_used
            required_cooldown = datetime.timedelta(hours=1)  # Default to 1 hour, will be updated based on outcome
            
            if time_since < required_cooldown:
                remaining = required_cooldown - time_since
                await interaction.response.send_message(
                    f"You must wait {self.format_time_remaining(remaining)} before attempting another drug robbery.",
                    ephemeral=True
                )
                return

        data = load_data()
        robber_record = data.get(robber_id, {"balance": 0, "cash": 0, "inventory": {}})
        
        if target is None:
            # Rob random dealers (no target)
            await interaction.response.send_message("💊 Attempting to rob drug dealers...", ephemeral=False)
            
            # 50-50 odds
            if random.random() < 0.50:  # Success
                # Get 1-10 random drugs
                drug_types = ["marijuana", "coca_leaves", "cannabis_products", "cocaine"]
                stolen_drugs = {}
                
                for _ in range(random.randint(1, 10)):
                    drug = random.choice(drug_types)
                    # Higher chance for common drugs, lower for rare ones
                    if drug == "cocaine":
                        amount = random.randint(1, 3)
                    elif drug == "cannabis_products":
                        amount = random.randint(1, 5)
                    else:
                        amount = random.randint(2, 8)
                    
                    stolen_drugs[drug] = stolen_drugs.get(drug, 0) + amount
                
                # Add to robber's inventory
                if "inventory" not in robber_record:
                    robber_record["inventory"] = {}
                
                for drug, amount in stolen_drugs.items():
                    robber_record["inventory"][drug] = robber_record["inventory"].get(drug, 0) + amount
                
                # 15-minute cooldown for success
                self.drugrobbery_cooldowns[robber_id] = now - datetime.timedelta(minutes=45)  # Set to allow retry in 15 min
                
                data[robber_id] = robber_record
                save_data(data)
                
                # Format stolen drugs message
                stolen_msg = "\n".join([f"- {amount} {drug.replace('_', ' ')}" for drug, amount in stolen_drugs.items()])
                
                await interaction.edit_original_response(
                    content=f"💰 Drug dealer robbery successful! You stole:\n{stolen_msg}\n"
                           f"Next robbery available in 15 minutes."
                )
            else:  # Failure
                # 1-hour cooldown for failure
                self.drugrobbery_cooldowns[robber_id] = now
                
                await interaction.edit_original_response(
                    content="🚨 Drug dealer robbery failed! The dealers were ready for you.\n"
                           "Next attempt available in 1 hour."
                )
        else:
            # Rob specific player
            if target.id == interaction.user.id:
                await interaction.response.send_message("You cannot rob yourself.", ephemeral=True)
                return
            if target.bot:
                await interaction.response.send_message("You cannot rob bots.", ephemeral=True)
                return
            
            target_id = str(target.id)
            target_record = data.get(target_id, {"balance": 0, "cash": 0, "inventory": {}})
            target_inventory = target_record.get("inventory", {})
            
            # Filter only drug items
            drug_items = {k: v for k, v in target_inventory.items() if k in ["marijuana", "coca_leaves", "cannabis_products", "cocaine"]}
            
            if not drug_items or sum(drug_items.values()) == 0:
                await interaction.response.send_message(
                    f"{target.display_name} doesn't have any drugs to steal.",
                    ephemeral=True
                )
                return
            
            await interaction.response.send_message(
                f"💊 Attempting to rob drugs from {target.display_name}...", 
                ephemeral=False
            )
            
            # 40% success rate
            if random.random() < 0.40:  # Success
                stolen_drugs = {}
                
                # Steal 5-30% of each drug type
                steal_percentage = random.uniform(0.05, 0.30)
                
                for drug, amount in drug_items.items():
                    stolen_amount = max(1, int(amount * steal_percentage))
                    stolen_amount = min(stolen_amount, amount)  # Don't steal more than they have
                    
                    if stolen_amount > 0:
                        stolen_drugs[drug] = stolen_amount
                        target_record["inventory"][drug] = amount - stolen_amount
                        
                        # Remove from inventory if 0
                        if target_record["inventory"][drug] == 0:
                            del target_record["inventory"][drug]
                
                # Add to robber's inventory
                if "inventory" not in robber_record:
                    robber_record["inventory"] = {}
                
                for drug, amount in stolen_drugs.items():
                    robber_record["inventory"][drug] = robber_record["inventory"].get(drug, 0) + amount
                
                # 1-day cooldown for successful player robbery
                self.drugrobbery_cooldowns[robber_id] = now - datetime.timedelta(hours=23)  # Allow retry in 1 hour
                
                data[robber_id] = robber_record
                data[target_id] = target_record
                save_data(data)
                
                # Format stolen drugs message
                stolen_msg = "\n".join([f"- {amount} {drug.replace('_', ' ')}" for drug, amount in stolen_drugs.items()])
                
                await interaction.edit_original_response(
                    content=f"💰 Successfully robbed {target.display_name}! You stole:\n{stolen_msg}\n"
                           f"({steal_percentage*100:.1f}% of their drugs)\n"
                           f"Next robbery available in 1 day."
                )
                
                await interaction.followup.send(
                    f"💸 {target.mention} You were robbed and lost drugs:\n{stolen_msg}",
                    ephemeral=False
                )
            else:  # Failure
                # 3-day cooldown for failed player robbery
                self.drugrobbery_cooldowns[robber_id] = now - datetime.timedelta(hours=21)  # 3 days = 72 hours, so set to now - 21 hours = 51 hours remaining
                
                # 5-minute timeout
                try:
                    until = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=5)
                    await interaction.user.timeout(until)
                    timeout_msg = " and timed out for 5 minutes"
                except:
                    timeout_msg = " but couldn't be timed out"
                
                await interaction.edit_original_response(
                    content=f"🚨 Drug robbery failed! {target.display_name} caught you in the act{timeout_msg}.\n"
                           f"Next attempt available in 3 days."
                )

async def setup(bot: commands.Bot):
    print("Loading CrimeCog...")
    await bot.add_cog(CrimeCog(bot))