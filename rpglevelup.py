import discord
from discord import app_commands
from discord.ext import commands, tasks
import json
import os
import datetime
import asyncio
from globals import RPG_PARTIES_FILE, GUILD_ID
from rpgutils import rpg_load_data, rpg_save_data

#levels dictionary for easy access
levels = {
    0: 0,
    1: 100,
    2: 200,
    3: 300,
    4: 400,
    5: 500,
    6: 600,
    7: 700,
    8: 800,
    9: 900,
    10: 1000,
    11: 1100,
    12: 1200,
}

MAX_POINTS = 12

class StatDistributionView(discord.ui.View):
    def __init__(self, *, user_id):
        super().__init__(timeout=300)
        data = rpg_load_data()
        self.user_id = user_id
        user_data = data.get(user_id)
        base_stats = user_data.get("stats")
        equipment_bonus = user_data.get("equipment_bonus")
        self.stats = { stat: base_stats.get(stat, 0) - equipment_bonus.get(stat, 0) for stat in base_stats }        
        self.available_points = 2
        self.add_item(StatAdjustButton("Strength", "+"))
        self.add_item(StatAdjustButton("Strength", "-"))
        self.add_item(StatAdjustButton("Dexterity", "+"))
        self.add_item(StatAdjustButton("Dexterity", "-"))
        self.add_item(StatAdjustButton("Intelligence", "+"))
        self.add_item(StatAdjustButton("Intelligence", "-"))
        self.add_item(StatAdjustButton("Willpower", "+"))
        self.add_item(StatAdjustButton("Willpower", "-"))
        self.add_item(StatAdjustButton("Fortitude", "+"))
        self.add_item(StatAdjustButton("Fortitude", "-"))
        self.add_item(StatAdjustButton("Charisma", "+"))
        self.add_item(StatAdjustButton("Charisma", "-"))
        self.add_item(ConfirmButton())

    def create_embed(self):
        embed = discord.Embed(
            title="Stat Distribution",
            description="Adjust your stats using the buttons below.",
            color=discord.Color.blurple()
        )
        total = sum(self.stats.values())
        embed.add_field(name="Total Points", value=str(total), inline=False)
        embed.add_field(name="Remaining Points", value=str(self.available_points), inline=False)
        for stat, value in self.stats.items():
            embed.add_field(name=stat, value=str(value), inline=True)
        embed.set_footer(text="Click Confirm when you are finished.")
        return embed

    async def update_message(self, interaction: discord.Interaction):
        new_embed = self.create_embed()
        try:
            await interaction.response.edit_message(embed=new_embed, view=self)
        except Exception:
            await interaction.message.edit(embed=new_embed, view=self)

class StatAdjustButton(discord.ui.Button):
    def __init__(self, stat: str, operation: str):
        label = f"{stat} {operation}"
        style = discord.ButtonStyle.green if operation == "+" else discord.ButtonStyle.red
        custom_id = f"{stat}_{operation}"
        super().__init__(label=label, style=style, custom_id=custom_id)
        self.stat = stat
        self.operation = operation

    async def callback(self, interaction: discord.Interaction):
        view: StatDistributionView = self.view
        if self.operation == "+":
            if view.available_points > 0 and view.stats[self.stat] < MAX_POINTS:
                view.stats[self.stat] += 1
                view.available_points -= 1
        elif self.operation == "-":
            if view.stats[self.stat] > 1:
                view.stats[self.stat] -= 1
                view.available_points += 1
        await view.update_message(interaction)
        await interaction.response.defer()

class ConfirmButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Confirm", style=discord.ButtonStyle.blurple, custom_id="confirm")

    async def callback(self, interaction: discord.Interaction):
        view: StatDistributionView = self.view

        for child in view.children:
            child.disabled = True

        await interaction.response.edit_message(embed=view.create_embed(), view=view)

        data = rpg_load_data()
        user_id = str(interaction.user.id)
        user_data = data.get(user_id)

        if not user_data:
            await interaction.followup.send("Character data not found.", ephemeral=True)
            view.stop()
            return

        equipment_bonus = user_data.get("equipment_bonus", {})


        base_stats = user_data.get("stats", {})
        for stat in base_stats:
            base_stats[stat] = view.stats.get(stat, base_stats.get(stat, 0)) + equipment_bonus.get(stat, 0)
        user_data["stats"] = base_stats

        rpg_save_data(data)
        await interaction.followup.send("Your character has been updated!", ephemeral=True)
        view.stop()


class LevelCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(
        name="levelup", 
        description="Level up if you have enough experience."
    )
    async def levelup(self, interaction: discord.Interaction):
        data = rpg_load_data()
        user_id = str(interaction.user.id)
        if user_id not in data:
            await interaction.response.send_message("You don't have a character.", ephemeral=True)
            return
        character = data[user_id]

        
        #get current level and grab experience value.
        experience = character["experience"]
        current_level = character["level"]

        #see if they can level up
        if experience < levels[current_level]:
            await interaction.response.send_message("You do not have enough experience to level up.")
            return
        else:

            experience -= levels[current_level]

            character["experience"] = experience
            current_level += 1
            character["level"] = current_level
            rpg_save_data(data)
            view = StatDistributionView(user_id=str(interaction.user.id))
            await interaction.response.send_message(embed=view.create_embed(), view=view)


async def setup(bot: commands.Bot):
    print("Loading RPGLevelCog...")
    await bot.add_cog(LevelCog(bot))
