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

    def get_prestige_requirements(self, current_prestige):
        """Get money and additional requirements for the next prestige level."""
        # Money requirements
        if current_prestige == 2:
            required_money = 100_000_000  # Special case for prestige 2→3
        else:
            required_money = 10 ** (current_prestige + 7)
            
        # Additional requirements
        additional_reqs = {
            0: "None",
            1: "1 Miku Factory and 1 Nuclear Power facility", 
            2: "5 Miku Factories and 100,000 Miku Figures in inventory",
        }
        
        additional_requirements = additional_reqs.get(current_prestige, "No higher prestige levels available")
        
        return required_money, additional_requirements

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(
        name="prestigeup", 
        description="Prestige up if you meet the requirements. (Wipes your economy data)"
    )
    async def prestigeup(self, interaction: discord.Interaction):
        data = load_data()
        user_id = str(interaction.user.id)
        record = data.get(user_id)
        if record is None:
            await interaction.response.send_message("You have no economy data to prestige.", ephemeral=True)
            return

        current_prestige = record.get("prestige", 0)
        
        # Check if max prestige reached
        if current_prestige >= 3:
            await interaction.response.send_message("You have reached the maximum prestige level!", ephemeral=True)
            return
            
        required_money, _ = self.get_prestige_requirements(current_prestige)
        balance = record.get("balance", 0)

        # Build a list of missing requirements
        missing_requirements = []
        
        # Check money requirement
        if balance < required_money:
            missing_requirements.append(f"{required_money:,} Beaned Bucks (have: {balance:,})")
            
        # Check additional requirements
        if current_prestige == 1:
            facilities = record.get("facilities", {})
            if facilities.get("miku_factory", 0) < 1:
                missing_requirements.append(f"1 Miku Factory (owned: {facilities.get('miku_factory', 0)})")
            if facilities.get("nuclear_power", 0) < 1:
                missing_requirements.append(f"1 Nuclear Power (owned: {facilities.get('nuclear_power', 0)})")
        elif current_prestige == 2:
            facilities = record.get("facilities", {})
            inventory = record.get("inventory", {})
            if facilities.get("miku_factory", 0) < 5:
                missing_requirements.append(f"5 Miku Factories (owned: {facilities.get('miku_factory', 0)})")
            if inventory.get("miku_figure", 0) < 100000:
                missing_requirements.append(f"100,000 Miku Figures (owned: {inventory.get('miku_figure', 0):,})")

        if missing_requirements:
            await interaction.response.send_message(
                "You are missing the following requirements for the next prestige:\n• " +
                "\n• ".join(missing_requirements),
                ephemeral=True
            )
            return

        # Build a new record preserving only time accruals and incrementing prestige
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
            f"🎉 Congratulations! You have prestiged to level {current_prestige + 1}! 🎉\n"
            f"Your economy data has been reset (except your time accruals and prestige).",
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
        balance = record.get("balance", 0)
        
        embed = discord.Embed(
            title=f"{target.display_name}'s Prestige Status",
            color=discord.Color.gold()
        )
        embed.add_field(name="Current Prestige Level", value=str(current_prestige), inline=False)
        embed.add_field(name="Current Balance", value=f"{balance:,}", inline=False)
        
        # Check if max prestige reached
        if current_prestige >= 3:
            embed.add_field(name="Status", value="🏆 Maximum prestige level reached!", inline=False)
        else:
            required_money, additional_requirements = self.get_prestige_requirements(current_prestige)
            embed.add_field(name="Required Money for Next Prestige", value=f"{required_money:,}", inline=False)
            embed.add_field(name="Additional Requirements", value=additional_requirements, inline=False)
            
            # Show current progress on additional requirements
            if current_prestige == 1:
                facilities = record.get("facilities", {})
                progress = (f"Miku Factories: {facilities.get('miku_factory', 0)}/1\n"
                           f"Nuclear Power: {facilities.get('nuclear_power', 0)}/1")
                embed.add_field(name="Current Progress", value=progress, inline=False)
            elif current_prestige == 2:
                facilities = record.get("facilities", {})
                inventory = record.get("inventory", {})
                progress = (f"Miku Factories: {facilities.get('miku_factory', 0)}/5\n"
                           f"Miku Figures: {inventory.get('miku_figure', 0):,}/100,000")
                embed.add_field(name="Current Progress", value=progress, inline=False)
                
            # Check if ready to prestige
            missing_requirements = []
            if balance < required_money:
                missing_requirements.append("money")
            if current_prestige == 1:
                facilities = record.get("facilities", {})
                if facilities.get("miku_factory", 0) < 1:
                    missing_requirements.append("miku factory")
                if facilities.get("nuclear_power", 0) < 1:
                    missing_requirements.append("nuclear power")
            elif current_prestige == 2:
                facilities = record.get("facilities", {})
                inventory = record.get("inventory", {})
                if facilities.get("miku_factory", 0) < 5:
                    missing_requirements.append("miku factories")
                if inventory.get("miku_figure", 0) < 100000:
                    missing_requirements.append("miku figures")
                    
            if not missing_requirements:
                embed.add_field(name="✅ Status", value="Ready to prestige! Use `/prestigeup`", inline=False)
            else:
                embed.add_field(name="❌ Missing", value=", ".join(missing_requirements).title(), inline=False)

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

        # Check for the daily cooldown
        now = datetime.datetime.now(datetime.timezone.utc)
        last_claim_str = record.get("last_prestige_daily")
        if last_claim_str:
            last_claim = datetime.datetime.fromisoformat(last_claim_str)
            if now - last_claim < datetime.timedelta(days=1):
                remaining = datetime.timedelta(days=1) - (now - last_claim)
                # Format remaining time as H:M:S
                hours, remainder = divmod(remaining.total_seconds(), 3600)
                minutes, seconds = divmod(remainder, 60)
                remaining_str = f"{int(hours)}h {int(minutes)}m {int(seconds)}s"
                await interaction.response.send_message(
                    f"You have already claimed your prestige daily bonus. Try again in {remaining_str}.",
                    ephemeral=True
                )
                return

        # Bonus scales by 50% per prestige level
        factor = 1 + 0.5 * current_prestige
        base_reward = random.randint(10000, 30000)
        reward = int(base_reward * factor)
        balance = record.get("balance", 0)
        record["balance"] = balance + reward

        # Update the daily cooldown timestamp
        record["last_prestige_daily"] = now.isoformat()

        data[user_id] = record
        save_data(data)
        await interaction.response.send_message(
            f"💎 You have received a prestige daily bonus of {reward:,} Beaned Bucks! 💎\n"
            f"(Base: {base_reward:,} × {factor:.1f} prestige multiplier)",
            ephemeral=True
        )

async def setup(bot: commands.Bot):
    print("Loading PrestigeCog...")
    await bot.add_cog(PrestigeCog(bot))