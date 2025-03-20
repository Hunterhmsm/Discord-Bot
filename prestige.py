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

        #get the current prestige level (default to 0 if not set) and calculate required balance.
        current_prestige = record.get("prestige", 0)
        required_money = 10 ** (current_prestige + 7)
        balance = record.get("balance", 0)

        #if upgrading from prestige 1 to 2, also require a miku factory and a nuclear reactor.
        if current_prestige == 1:
            facilities = record.get("facilities", {})
            if facilities.get("miku_factory", 0) < 1 or facilities.get("nuclear_power", 0) < 1:
                await interaction.response.send_message(
                    "To prestige to level 2, you must own at least one Miku Factory and one Nuclear Power facility.",
                    ephemeral=True
                )
                return

        if balance < required_money:
            await interaction.response.send_message(
                f"You need {required_money:,} Beaned Bucks to prestige to level {current_prestige + 1}. Your current balance is {balance:,}.",
                ephemeral=True
            )
            return

        #build new record preserving time accruals and incrementing prestige wipes everything else
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

        #create new record preserving time and prestige and incrementing prestige by 1.
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
            f"Congratulations! You have prestiged to level {current_prestige + 1}. Your economy data has been reset (except for your time accruals and prestige).",
            ephemeral=True
        )

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(
        name="prestigecheck", 
        description="Check your current prestige level and the amount required for the next prestige."
    )
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
        required = 10 ** (current_prestige + 7)
        balance = record.get("balance", 0)
        embed = discord.Embed(
            title=f"{target.display_name}'s Prestige Status",
            color=discord.Color.gold()
        )
        embed.add_field(name="Current Prestige Level", value=str(current_prestige), inline=False)
        embed.add_field(name="Current Balance", value=f"{balance:,}", inline=False)
        embed.add_field(name="Required for Next Prestige", value=f"{required:,}", inline=False)
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
        #bonus scales by 50% per prestige level
        factor = 1 + 0.5 * current_prestige
        base_reward = random.randint(10000, 30000)
        reward = int(base_reward * factor)
        balance = record.get("balance", 0)
        record["balance"] = balance + reward
        data[user_id] = record
        save_data(data)
        await interaction.response.send_message(
            f"You have received a prestige daily bonus of {reward:,} Beaned Bucks.",
            ephemeral=True
        )

async def setup(bot: commands.Bot):
    print("Loading PrestigeCog...")
    await bot.add_cog(PrestigeCog(bot))
