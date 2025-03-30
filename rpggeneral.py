import discord
from discord import app_commands, Interaction
from discord.ext import commands
from typing import Optional
from globals import RPG_INVENTORY_FILE, GUILD_ID
from rpgutils import rpg_load_data, rpg_save_data, full_heal

#the main Cog.
class RPGGeneral(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="rest", description="Rest at the Inn for 50 gold.")
    async def portfolio(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        data = rpg_load_data()
        character = data[user_id]
        gold = character["gold"]
        if gold < 50:
            await interaction.response.send_message("You don't have enough gold. You need 50 gold to rest.")
            return
        else:
            gold -= 50
            character["gold"] = gold
            rpg_save_data(data)
            full_heal(user_id)
            await interaction.response.send_message("You have rested. You have paid 50 gold.")
            return

async def setup(bot: commands.Bot):
    print("Loading RPGGeneralCog...")
    await bot.add_cog(RPGGeneral(bot))
