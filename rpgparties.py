import discord
from discord import app_commands
from discord.ext import commands, tasks
import json
import os
import datetime
import asyncio
from globals import RPG_PARTIES_FILE, GUILD_ID
from rpgutils import rpg_load_data, rpg_save_data, is_user_in_combat

def load_parties():
    if not os.path.exists(RPG_PARTIES_FILE):
        return {}
    with open(RPG_PARTIES_FILE, "r") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}

def save_parties(parties):
    with open(RPG_PARTIES_FILE, "w") as f:
        json.dump(parties, f, indent=4)

#modal for creating a party.
class PartyCreateModal(discord.ui.Modal, title="Create Party"):
    party_name = discord.ui.TextInput(
        label="Party Name", 
        placeholder="Enter your party's name",
        min_length=1,
        max_length=32
    )
    
    def __init__(self, user_id: str):
        self.user_id = user_id
        super().__init__()
    
    async def on_submit(self, interaction: discord.Interaction):
        parties = load_parties()
        #check if the user is already in a party.
        for party in parties.values():
            if self.user_id in party["members"]:
                await interaction.response.send_message("You are already in a party.", ephemeral=True)
                return
        party_id = self.party_name.value
        if party_id in parties:
            await interaction.response.send_message("A party with that name already exists.", ephemeral=True)
            return
        parties[party_id] = {
            "leader": self.user_id,
            "members": [self.user_id],
            "created_at": datetime.datetime.utcnow().isoformat()
        }
        save_parties(parties)
        await interaction.response.send_message(f"Party '{party_id}' created! You are the leader.", ephemeral=True)

#modal for responding to an invite.
class PartyInviteResponseView(discord.ui.View):
    def __init__(self, bot: commands.Bot, party_id: str, party_info: dict):
        super().__init__(timeout=60)
        self.bot = bot
        self.party_id = party_id
        self.party_info = party_info

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        parties = load_parties()
        party = parties.get(self.party_id)
        if party is None:
            await interaction.response.send_message("Party not found.", ephemeral=True)
            self.stop()
            return
        if len(party["members"]) >= 4:
            await interaction.response.send_message("The party is full.", ephemeral=True)
        else:
            user_id = str(interaction.user.id)
            if user_id not in party["members"]:
                party["members"].append(user_id)
                save_parties(parties)
                await interaction.response.send_message(f"You have joined party '{self.party_id}'.", ephemeral=True)
            else:
                await interaction.response.send_message("You are already in the party.", ephemeral=True)
        self.stop()

    @discord.ui.button(label="Decline", style=discord.ButtonStyle.danger)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("You declined the invitation.", ephemeral=True)
        self.stop()

#button for inviting a user.
class PartyInviteButton(discord.ui.Button):
    def __init__(self, bot: commands.Bot, user_id: str):
        super().__init__(label="Invite", style=discord.ButtonStyle.primary)
        self.bot = bot
        self.user_id = user_id

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_message("Please type a message in this channel mentioning the user to invite.", ephemeral=True)
        def check(m):
            return m.author.id == int(self.user_id) and m.channel == interaction.channel and len(m.mentions) > 0
        try:
            msg = await self.bot.wait_for("message", timeout=60.0, check=check)
        except asyncio.TimeoutError:
            await interaction.followup.send("You took too long to mention a user.", ephemeral=True)
            return
        invitee = msg.mentions[0]

        #check if the invited user has a character
        rpg_data = rpg_load_data()
        if str(invitee.id) not in rpg_data:
            await interaction.followup.send(f"{invitee.display_name} does not have a character.", ephemeral=True)
            return

        parties = load_parties()
        party_id = None
        for pid, party in parties.items():
            if self.user_id in party["members"]:
                party_id = pid
                break
        if party_id is None:
            await interaction.followup.send("You are not in a party.", ephemeral=True)
            return
        if len(parties[party_id]["members"]) >= 4:
            await interaction.followup.send("Your party is full.", ephemeral=True)
            return
        party_info = parties[party_id]
        #prepare a DM to the invitee including party name and current members (by character name)
        member_names = []
        for member_id in party_info["members"]:
            member_char = rpg_data.get(member_id, {})
            member_names.append(member_char.get("name", member_id))
        invite_view = PartyInviteResponseView(bot=self.bot, party_id=party_id, party_info=party_info)
        try:
            await invitee.send(
                f"You have been invited to join party '{party_id}' with members: {', '.join(member_names)}. Do you accept?",
                view=invite_view
            )
            await interaction.followup.send(f"Invitation sent to {invitee.display_name}.", ephemeral=True)
        except discord.Forbidden:
            await interaction.followup.send("Could not send a DM to that user.", ephemeral=True)


#button for leaving a party.
class PartyLeaveButton(discord.ui.Button):
    def __init__(self, user_id: str):
        super().__init__(label="Leave", style=discord.ButtonStyle.danger)
        self.user_id = user_id

    async def callback(self, interaction: discord.Interaction):
        parties = load_parties()
        party_id = None
        for pid, party in parties.items():
            if self.user_id in party["members"]:
                party_id = pid
                break
        if party_id is None:
            await interaction.response.send_message("You are not in a party.", ephemeral=True)
            return
        party = parties[party_id]
        if self.user_id in party["members"]:
            party["members"].remove(self.user_id)
        if party["leader"] == self.user_id:
            if party["members"]:
                party["leader"] = party["members"][0]
            else:
                del parties[party_id]
                save_parties(parties)
                await interaction.response.send_message("You left the party. Your party has been disbanded.", ephemeral=True)
                return
        save_parties(parties)
        await interaction.response.send_message(f"You have left the party '{party_id}'.", ephemeral=True)

#button for viewing all parties.
class PartyListButton(discord.ui.Button):
    def __init__(self, bot: commands.Bot):
        super().__init__(label="View All Parties", style=discord.ButtonStyle.secondary)
        self.bot = bot

    async def callback(self, interaction: discord.Interaction):
        parties = load_parties()
        embed = discord.Embed(title="All Parties", color=discord.Color.blue())
        rpg_data = rpg_load_data()
        if not parties:
            embed.description = "No parties exist."
        else:
            for pid, party in parties.items():
                member_names = []
                for member_id in party["members"]:
                    member_char = rpg_data.get(member_id, {})
                    member_names.append(member_char.get("name", member_id))
                embed.add_field(
                    name=f"Party: {pid}",
                    value=f"Leader: {party['leader']}\nMembers: {', '.join(member_names)}",
                    inline=False
                )
        await interaction.response.send_message(embed=embed, ephemeral=True)

#main Party Management View.
class PartyView(discord.ui.View):
    def __init__(self, bot: commands.Bot, user_id: str):
        super().__init__(timeout=300)
        self.bot = bot
        self.user_id = user_id
        self.add_item(PartyCreateButton(user_id))
        self.add_item(PartyInviteButton(bot, user_id))
        self.add_item(PartyLeaveButton(user_id))
        self.add_item(PartyListButton(bot))

class PartyCreateButton(discord.ui.Button):
    def __init__(self, user_id: str):
        super().__init__(label="Create", style=discord.ButtonStyle.primary)
        self.user_id = user_id

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(PartyCreateModal(user_id=self.user_id))

class PartyCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="party", description="Manage your party: Create, Invite, Leave, or view your current party.")
    async def party(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        if is_user_in_combat(str(user_id)):
            return await interaction.response.send_message("You cannot manage parties in combat.", ephemeral=True)
        parties = load_parties()
        user_party = None
        for pid, party in parties.items():
            if user_id in party["members"]:
                user_party = (pid, party)
                break

        #build an embed that displays the party details.
        embed = discord.Embed(title="Party Management", color=discord.Color.green())
        if user_party:
            pid, party = user_party
            rpg_data = rpg_load_data()
            member_names = []
            leader_id = party["leader"] 
            leader_name = rpg_data.get(leader_id, {}).get("name", leader_id)
            for member_id in party["members"]:
                member_char = rpg_data.get(member_id, {})
                member_names.append(member_char.get("name", member_id))
            embed.description = (
                f"You are in party **{pid}**.\n"
                f"Leader: {leader_name}\n"
                f"Members: {', '.join(member_names)}"
            )
        else:
            embed.description = "You are not in a party."

        #create the PartyView with interactive buttons.
        view = PartyView(bot=self.bot, user_id=user_id)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


async def setup(bot: commands.Bot):
    print("Loading PartyCog...")
    await bot.add_cog(PartyCog(bot))