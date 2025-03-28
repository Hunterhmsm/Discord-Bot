import discord
from discord import app_commands
from discord.ext import commands
import random
import datetime
import json
import os
from typing import Optional
from globals import RPG_INVENTORY_FILE, GUILD_ID
from rpgutils import rpg_load_data, rpg_save_data

class RPGInventory(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        #track the last time a user used /crime.
        self.crime_cooldowns = {}  


    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="status", description="View your characters status. (or anothers)")
    @app_commands.describe(user="Optional: The user whose portfolio you want to see (defaults to yourself)")
    async def portfolio(self, interaction: discord.Interaction, user: discord.Member = None):
        target = user or interaction.user
        data = rpg_load_data()
        user_id = str(target.id)
        if user_id not in data:
            await interaction.response.send_message("User doesn't have a character.", ephemeral=True)
        user_record = data.get(user_id, {"currenthp": 0, "stats": {}, "maxhp": 0, "gender": None, "class": None})
        stats = user_record.get("stats", {})
        character = data[user_id]
        charactername = character["name"]
        maxhp = character["max_hp"]
        hp = character["current_hp"]
        current_stamina = character["current_stamina"]
        max_stamina = character["max_stamina"]
        current_mana = character["current_mana"]
        max_mana = character["max_mana"]
        speed = character["speed"]
        armor = character["armor"]

        #extract individual stats with a fallback value if needed.
        strength = stats.get("Strength", 0)
        dexterity = stats.get("Dexterity", 0)
        intelligence = stats.get("Intelligence", 0)
        willpower = stats.get("Willpower", 0)
        fortitude = stats.get("Fortitude", 0)
        charisma = stats.get("Charisma", 0)

        strengthb = strength // 2
        dexterityb = dexterity // 2
        intelligenceb = intelligence //2
        willpowerb = willpower // 2
        fortitudeb = fortitude // 2
        charismab = charisma // 2

        embed = discord.Embed(
            title=f"{charactername}'s Status",
            color=discord.Color.green()
        )
        
        embed.add_field(
            name="Stats",
            value=f"Strength:{strength}\nDexterity:{dexterity}\nIntelligence:{intelligence}\nWillpower:{willpower}\nFortitude:{fortitude}\nCharisma:{charisma}",
            inline=True
        )
        embed.add_field(
            name="Stat Bonuses",
            value=f"Strength:{strengthb}\nDexterity:{dexterityb}\nIntelligence:{intelligenceb}\nWillpower:{willpowerb}\nFortitude:{fortitudeb}\nCharisma:{charismab}",
            inline=True
        )

        embed.add_field(name="\u200B", value="\u200B", inline=True)

        embed.add_field(
            name="Health",
            value=f"{hp}/{maxhp} HP",
            inline=True
        )
        embed.add_field(
            name="Stamina",
            value=f"{current_stamina}/{max_stamina} Stamina",
            inline=True
        )
        embed.add_field(name="\u200B", value="\u200B", inline=True)
        embed.add_field(
            name="Mana",
            value=f"{current_mana}/{max_mana} Mana",
            inline=True
        )
        embed.add_field(
            name="Speed",
            value=f"{speed} Speed",
            inline=True
        )
        embed.add_field(name="\u200B", value="\u200B", inline=True)
        embed.add_field(
            name="Armor",
            value=f"{armor} Armor",
            inline=True
        )
    
        await interaction.response.send_message(embed=embed)



async def setup(bot: commands.Bot):
    print("Loading RPGInventoryCog...")
    await bot.add_cog(RPGInventory(bot))
