import discord
from discord import app_commands
from discord.ext import commands
import datetime
import random
from globals import GUILD_ID
from utils import load_data, save_data

class PrestigeCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(
        name="prestigeup", 
        description="Prestige up if you meet the requirements. (Wipes your economy data except time accruals and prestige)"
    )
    async def prestigeup(self, interaction: discord.Interaction):
        data = load_data()
        user_id = str(interaction.user.id)
        record = data.get(user_id)
        if record is None:
            await interaction.response.send_message("You have no economy data to prestige.", ephemeral=True)
            return

        current_prestige = record.get("prestige", 0)
        #for prestige level 3 we require 100,000,000 instead of the default.
        if current_prestige == 2:
            required_money = 100_000_000
        else:
            required_money = 10 ** (current_prestige + 7)
        balance = record.get("balance", 0)

        #build a list of missing requirements.
        missing_requirements = []
        if current_prestige == 1:
            #to go from prestige 1 -> 2 require at least 1 miku_factory and 1 nuclear_power facility.
            facilities = record.get("facilities", {})
            if facilities.get("miku_factory", 0) < 1:
                missing_requirements.append(f"1 Miku Factory (owned: {facilities.get('miku_factory', 0)})")
            if facilities.get("nuclear_power", 0) < 1:
                missing_requirements.append(f"1 Nuclear Power (owned: {facilities.get('nuclear_power', 0)})")
        elif current_prestige == 2:
            # To go from prestige 2 -> 3 require at least 5 miku_factory and 100,000 miku_figure in inventory.
            facilities = record.get("facilities", {})
            inventory = record.get("inventory", {})
            if facilities.get("miku_factory", 0) < 5:
                missing_requirements.append(f"5 Miku Factories (owned: {facilities.get('miku_factory', 0)})")
            if inventory.get("miku_figure", 0) < 100000:
                missing_requirements.append(f"100,000 Miku Figures (owned: {inventory.get('miku_figure', 0)})")

        if missing_requirements:
            await interaction.response.send_message(
                "You are missing the following requirements for the next prestige: " +
                ", ".join(missing_requirements),
                ephemeral=True
            )
            return

        if balance < required_money:
            await interaction.response.send_message(
                f"You need {required_money:,} Beaned Bucks to prestige to level {current_prestige + 1}. Your current balance is {balance:,}.",
                ephemeral=True
            )
            return

        #build a new record preserving only time accruals and incrementing prestige.
        new_record = {
            "vc_time": record.get("vc_time", 0),
            "vc_timealone": record.get("vc_timealone", 0),
            "vc_afk": record.get("vc_afk", 0),
            "prestige": current_prestige + 1,
            "balance": 0
        }
        data[user_id] = new_record
        save_data(data)
        await interaction.response.send_message(
            f"Congratulations! You have prestiged to level {current_prestige + 1}. Your economy data has been reset (except your time accruals and prestige).",
            ephemeral=True
        )

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="prestigecheck", description="Check your current prestige level, balance, and the requirements for the next prestige.")
    @app_commands.describe(user="Optional: The user to check (defaults to yourself)")
    async def prestigecheck(self, interaction: discord.Interaction, user: discord.Member = None):
        target = user or interaction.user
        data = load_data()
        user_id = str(target.id)
        record = data.get(user_id)
        if record is None:
            await interaction.response.send_message("This user has no economy data.", ephemeral=True)
            return

        current_prestige = record.get("prestige", 0)
        #calculate the required money (default formula)
        required_money = 10 ** (current_prestige + 7)
        balance = record.get("balance", 0)

        #define additional requirements based on current prestige level.
        additional_requirements = ""
        if current_prestige == 0:
            additional_requirements = "None"
        elif current_prestige == 1:
            additional_requirements = "1 Miku Factory and 1 Nuclear Power facility"
        elif current_prestige == 2:
            additional_requirements = "5 Miku Factories and 100,000 Miku Figures in inventory"
        else:
            additional_requirements = "None"

        embed = discord.Embed(
            title=f"{target.display_name}'s Prestige Status",
            color=discord.Color.gold()
        )
        embed.add_field(name="Current Prestige Level", value=str(current_prestige), inline=False)
        embed.add_field(name="Current Balance", value=f"{balance:,}", inline=False)
        embed.add_field(name="Required for Next Prestige", value=f"{required_money:,}", inline=False)
        embed.add_field(name="Additional Requirements", value=additional_requirements, inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)


    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="prestigedaily", description="Claim your daily prestige bonus (requires at least 1 prestige).")
    async def prestigedaily(self, interaction: discord.Interaction):
        data = load_data()
        user_id = str(interaction.user.id)
        record = data.get(user_id)
        if record is None:
            await interaction.response.send_message("You have no economy data.", ephemeral=True)
            return

        current_prestige = record.get("prestige", 0)
        if current_prestige < 1:
            await interaction.response.send_message("You must have at least 1 prestige to claim a daily bonus.", ephemeral=True)
            return

        # Check for the daily cooldown.
        now = datetime.datetime.now(datetime.timezone.utc)
        last_claim_str = record.get("last_prestige_daily")
        if last_claim_str:
            last_claim = datetime.datetime.fromisoformat(last_claim_str)
            if now - last_claim < datetime.timedelta(days=1):
                remaining = datetime.timedelta(days=1) - (now - last_claim)
                # Format remaining time as H:M:S
                remaining_str = str(remaining).split('.')[0]
                await interaction.response.send_message(
                    f"You have already claimed your prestige daily bonus. Try again in {remaining_str}.",
                    ephemeral=True
                )
                return

        # Bonus scales by 50% per prestige level.
        factor = 1 + 0.5 * current_prestige
        base_reward = random.randint(10000, 30000)
        reward = int(base_reward * factor)
        balance = record.get("balance", 0)
        record["balance"] = balance + reward

        # Update the daily cooldown timestamp.
        record["last_prestige_daily"] = now.isoformat()

        data[user_id] = record
        save_data(data)
        await interaction.response.send_message(
            f"You have received a prestige daily bonus of {reward:,} Beaned Bucks.",
            ephemeral=True
        )

async def setup(bot: commands.Bot):
    print("Loading PrestigeCog...")
    await bot.add_cog(PrestigeCog(bot))
