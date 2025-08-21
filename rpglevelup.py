import discord
from discord import app_commands
from discord.ext import commands, tasks
import json
import os
import datetime
import asyncio
from globals import RPG_PARTIES_FILE, GUILD_ID
from rpgutils import rpg_load_data, rpg_save_data, is_user_in_combat, SKILLS_BY_STAT

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
        
        # Proceed to skill improvement
        skill_view = SkillImprovementView(user_id=user_id)
        await interaction.followup.send(embed=skill_view.create_embed(), view=skill_view, ephemeral=True)
        view.stop()

# ------------------
# Skill Improvement System
# ------------------
class SkillImprovementView(discord.ui.View):
    def __init__(self, *, user_id: str):
        super().__init__(timeout=300)
        self.user_id = user_id
        self.choice_made = False
        
        # Add buttons for the two options
        self.add_item(LearnNewSkillButton())
        self.add_item(ImproveExistingSkillButton())

    def create_embed(self):
        data = rpg_load_data()
        user_data = data.get(self.user_id, {})
        character_name = user_data.get("name", "Unknown")
        trained_skills = user_data.get("trained_skills", [])
        
        embed = discord.Embed(
            title="Skill Improvement",
            description=f"**{character_name}** gained a level! Choose how to improve your skills:",
            color=discord.Color.gold()
        )
        
        embed.add_field(
            name="Option 1: Learn New Skill",
            value="Gain training in a new skill (+2 bonus)",
            inline=False
        )
        
        embed.add_field(
            name="Option 2: Improve Existing Skill", 
            value="Increase an existing skill bonus by +2 (up to +6 max)",
            inline=False
        )
        
        if trained_skills:
            current_skills = []
            skill_bonuses = user_data.get("skill_bonuses", {})
            for skill in trained_skills:
                bonus = skill_bonuses.get(skill, 0)
                current_skills.append(f"{skill} (+{bonus})")
            
            embed.add_field(
                name="Current Trained Skills",
                value="\n".join(current_skills),
                inline=False
            )
        
        embed.set_footer(text="Choose an option above to continue.")
        return embed

class LearnNewSkillButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Learn New Skill", style=discord.ButtonStyle.success, emoji="📚")

    async def callback(self, interaction: discord.Interaction):
        view: SkillImprovementView = self.view
        if view.choice_made:
            return
        
        view.choice_made = True
        new_skill_view = NewSkillSelectionView(user_id=view.user_id)
        await interaction.response.send_message(embed=new_skill_view.create_embed(), view=new_skill_view, ephemeral=True)
        view.stop()

class ImproveExistingSkillButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Improve Existing Skill", style=discord.ButtonStyle.primary, emoji="⬆️")

    async def callback(self, interaction: discord.Interaction):
        view: SkillImprovementView = self.view
        if view.choice_made:
            return
            
        view.choice_made = True
        data = rpg_load_data()
        user_data = data.get(view.user_id, {})
        trained_skills = user_data.get("trained_skills", [])
        
        if not trained_skills:
            await interaction.response.send_message("You don't have any trained skills to improve!", ephemeral=True)
            return
            
        improve_view = ImproveSkillSelectionView(user_id=view.user_id, trained_skills=trained_skills)
        await interaction.response.send_message(embed=improve_view.create_embed(), view=improve_view, ephemeral=True)
        view.stop()

# ------------------
# New Skill Selection
# ------------------
class NewSkillSelectionView(discord.ui.View):
    def __init__(self, *, user_id: str):
        super().__init__(timeout=300)
        self.user_id = user_id
        
        data = rpg_load_data()
        user_data = data.get(user_id, {})
        trained_skills = user_data.get("trained_skills", [])
        
        # Add dropdowns for each stat's skills
        for stat_name, skills in SKILLS_BY_STAT.items():
            # Only show skills the user doesn't already have
            available_skills = [skill for skill in skills if skill not in trained_skills]
            if available_skills:
                self.add_item(NewSkillSelect(stat_name, available_skills))

    def create_embed(self):
        embed = discord.Embed(
            title="Learn New Skill",
            description="Choose a new skill to learn. You'll gain +2 bonus to rolls with this skill.",
            color=discord.Color.green()
        )
        
        data = rpg_load_data()
        user_data = data.get(self.user_id, {})
        trained_skills = user_data.get("trained_skills", [])
        
        for stat_name, skills in SKILLS_BY_STAT.items():
            available_skills = [skill for skill in skills if skill not in trained_skills]
            if available_skills:
                skill_list = ", ".join(available_skills)
                embed.add_field(name=f"{stat_name} Skills", value=skill_list, inline=False)
        
        embed.set_footer(text="Select a skill from the dropdowns above.")
        return embed

class NewSkillSelect(discord.ui.Select):
    def __init__(self, stat_name: str, available_skills: list):
        options = []
        for skill in available_skills:
            options.append(discord.SelectOption(
                label=skill,
                description=f"{stat_name} skill - Gain +2 bonus",
                value=skill
            ))
        
        super().__init__(
            placeholder=f"Learn {stat_name} skill...",
            options=options,
            min_values=1,
            max_values=1
        )
        self.stat_name = stat_name

    async def callback(self, interaction: discord.Interaction):
        view: NewSkillSelectionView = self.view
        selected_skill = self.values[0]
        
        data = rpg_load_data()
        user_data = data.get(view.user_id, {})
        
        # Add the new skill
        trained_skills = user_data.get("trained_skills", [])
        skill_bonuses = user_data.get("skill_bonuses", {})
        
        trained_skills.append(selected_skill)
        skill_bonuses[selected_skill] = 2
        
        user_data["trained_skills"] = trained_skills
        user_data["skill_bonuses"] = skill_bonuses
        
        data[view.user_id] = user_data
        rpg_save_data(data)
        
        await interaction.response.send_message(
            f"🎉 **Level up complete!**\n"
            f"You learned **{selected_skill}** (+2 bonus)!\n"
            f"Your character has been updated.",
            ephemeral=True
        )
        view.stop()

# ------------------
# Improve Existing Skill
# ------------------
class ImproveSkillSelectionView(discord.ui.View):
    def __init__(self, *, user_id: str, trained_skills: list):
        super().__init__(timeout=300)
        self.user_id = user_id
        
        data = rpg_load_data()
        user_data = data.get(user_id, {})
        skill_bonuses = user_data.get("skill_bonuses", {})
        
        # Only show skills that can be improved (less than +6)
        improvable_skills = [skill for skill in trained_skills if skill_bonuses.get(skill, 0) < 6]
        
        if improvable_skills:
            self.add_item(ImproveSkillSelect(improvable_skills, skill_bonuses))

    def create_embed(self):
        data = rpg_load_data()
        user_data = data.get(self.user_id, {})
        skill_bonuses = user_data.get("skill_bonuses", {})
        trained_skills = user_data.get("trained_skills", [])
        
        embed = discord.Embed(
            title="Improve Existing Skill",
            description="Choose a skill to improve by +2 (maximum +6).",
            color=discord.Color.blue()
        )
        
        improvable_skills = []
        maxed_skills = []
        
        for skill in trained_skills:
            bonus = skill_bonuses.get(skill, 0)
            if bonus < 6:
                improvable_skills.append(f"{skill} (+{bonus} → +{bonus + 2})")
            else:
                maxed_skills.append(f"{skill} (+{bonus}) - MAX")
        
        if improvable_skills:
            embed.add_field(
                name="Can Improve",
                value="\n".join(improvable_skills),
                inline=False
            )
        
        if maxed_skills:
            embed.add_field(
                name="Already Maxed",
                value="\n".join(maxed_skills),
                inline=False
            )
        
        embed.set_footer(text="Select a skill to improve from the dropdown.")
        return embed

class ImproveSkillSelect(discord.ui.Select):
    def __init__(self, improvable_skills: list, skill_bonuses: dict):
        options = []
        for skill in improvable_skills:
            current_bonus = skill_bonuses.get(skill, 0)
            new_bonus = current_bonus + 2
            options.append(discord.SelectOption(
                label=skill,
                description=f"Improve from +{current_bonus} to +{new_bonus}",
                value=skill
            ))
        
        super().__init__(
            placeholder="Choose skill to improve...",
            options=options,
            min_values=1,
            max_values=1
        )

    async def callback(self, interaction: discord.Interaction):
        view: ImproveSkillSelectionView = self.view
        selected_skill = self.values[0]
        
        data = rpg_load_data()
        user_data = data.get(view.user_id, {})
        skill_bonuses = user_data.get("skill_bonuses", {})
        
        # Improve the skill
        old_bonus = skill_bonuses.get(selected_skill, 0)
        new_bonus = min(old_bonus + 2, 6)  # Cap at +6
        skill_bonuses[selected_skill] = new_bonus
        
        user_data["skill_bonuses"] = skill_bonuses
        data[view.user_id] = user_data
        rpg_save_data(data)
        
        await interaction.response.send_message(
            f"🎉 **Level up complete!**\n"
            f"**{selected_skill}** improved from +{old_bonus} to +{new_bonus}!\n"
            f"Your character has been updated.",
            ephemeral=True
        )
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
        if is_user_in_combat(str(user_id)):
            return await interaction.response.send_message("You cannot level up in combat.", ephemeral=True)
        if user_id not in data:
            await interaction.response.send_message("You don't have a character.", ephemeral=True)
            return
        character = data[user_id]

        
        #get current level and grab experience value.
        experience = character["experience"]
        current_level = character["level"]

        #see if they can level up
        if experience < levels[current_level]:
            nextlvl = levels[current_level] - experience
            await interaction.response.send_message(f"You need {nextlvl} XP to reach the next level.")
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