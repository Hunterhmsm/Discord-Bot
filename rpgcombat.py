import discord
from discord import app_commands
from discord.ext import commands
from globals import RPG_INVENTORY_FILE, GUILD_ID
from rpgutils import (
    check_user_in_party,
    get_party_data,
    rpg_load_data,
    roll_d12,
)
import enum
import random


class CombatTurnManager:
    def __init__(self, player_ids: list[str]):
        local_player_data = rpg_load_data()
        print(local_player_data)
        self.turn_order = [
            {
                "id": player_id,
                "name": local_player_data[player_id],
                "initiative": local_player_data[player_id]["speed"] + roll_d12(),
            }
            for player_id in player_ids
        ]
        self.turn_order = sorted(self.turn_order, key=lambda x: x["id"], reverse=True)
        self.current_player_id = self.turn_order[0]["id"]
        print(self.turn_order)

    def next_turn(self):
        """Set current player to next player in turn order, with circular looping"""
        current_player_index = self.turn_order.index(self.current_player_id)
        if current_player_index + 1 >= len(self.turn_order):
            self.current_player_id = self.turn_order[0]
        else:
            self.current_player_id = self.turn_order[current_player_index + 1]


class CombatView(discord.ui.View):
    def __init__(self, owner_id: str, members: list[str], is_party: bool):
        super().__init__()
        self.embed = self.__create_embed()
        # Get owner and current player from members lsit
        self.owner_id = owner_id
        self.combat_turn_manager = CombatTurnManager(members)

    def __create_embed(self):
        embed = discord.Embed(
            title="Combat Encounter",
            description=(
                "```"
                "Left Column         |         Right Column\n"
                "------------------------------------------\n"
                "Row 1: Left Text    |    Row 1: Right Text\n"
                "Row 2: Left Text    |    Row 2: Right Text\n"
                "```"
            ),
            color=discord.Color.red(),
        )
        return embed


class CombatCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.combat_sessions: dict[str, CombatView] = {}

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="start_combat", description="Start a combat encounter.")
    async def start_combat(self, interaction: discord.Interaction):
        local_party_data = get_party_data(str(interaction.user.id))
        # Check / get already existing combat session for user or party leader
        if str(interaction.user.id) in self.combat_sessions.keys():
            local_combat_session = self.combat_sessions[str(interaction.user.id)]
            await interaction.response.send_message(
                "Ongoing combat session detected!",
                embed=local_combat_session.embed,
                view=local_combat_session,
            )
            return
        elif local_party_data.get("leader", "") in self.combat_sessions.keys():
            local_combat_session = self.combat_sessions[str(interaction.user.id)]
            await interaction.response.send_message(
                "Ongoing combat session detected!",
                embed=local_combat_session.embed,
                view=local_combat_session,
            )
            return

        # No existing combat session, check if user is party leader or solo
        if check_user_in_party(str(interaction.user.id)) == False:
            local_combat_session = self.combat_sessions.get(
                str(interaction.user.id),
                CombatView(str(interaction.user.id), [str(interaction.user.id)], True),
            )
            self.combat_sessions[str(interaction.user.id)] = local_combat_session
            await interaction.response.send_message(
                "Solo combat started!!",
                embed=local_combat_session.embed,
                view=local_combat_session,
            )
        elif check_user_in_party(str(interaction.user.id), True) == True:
            local_combat_session = self.combat_sessions.get(
                str(interaction.user.id),
                CombatView(str(interaction.user.id), local_party_data["members"], True),
            )
            self.combat_sessions[str(interaction.user.id)] = local_combat_session
            await interaction.response.send_message(
                "Party combat started!!",
                embed=local_combat_session.embed,
                view=local_combat_session,
            )
        else:
            await interaction.response.send_message(
                "You must run solo or be the leader of a party to start a combat."
            )
        return

        if self.combat_session == None:
            combat_screen = CombatScreen(grid_width=3)
            # This is where you can populate the grid with enemies
            combat_screen.update_grid(0, 1, "🫃🏿")
            combat_screen.update_grid(1, 1, "🫃🏿")
            combat_screen.update_grid(0, 2, "🫃🏿")
            self.combat_session = combat_screen
            await interaction.response.send_message(
                "Combat started!!",
                embed=self.combat_session.get_embed(),
                view=self.combat_session,
            )
        else:
            await interaction.response.send_message(
                "Combat ongoing!!",
                embed=self.combat_session.get_embed(),
                view=self.combat_session,
            )

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="attack", description="Attack an enemy.")
    async def attack(self, interaction: discord.Interaction, row: int, col: int):
        if self.combat_session is None:
            await interaction.response.send_message("No active combat session.")
        elif (
            self.combat_session.grid[row][col] == Tile.EMPTY.value
            or self.combat_session.grid[row][col] == Tile.DEAD.value
        ):
            await interaction.response.send_message(
                "You can't attack a tile with no enemy in it."
            )
        else:
            self.combat_session.update_grid(row, col, Tile.DEAD.value)
            embed = self.combat_session.get_embed()
            await interaction.response.send_message(
                "You attacked an enemy!", embed=embed, view=self.combat_session
            )


async def setup(bot: commands.Bot):
    print("Loading CombatCog...")
    await bot.add_cog(CombatCog(bot))
