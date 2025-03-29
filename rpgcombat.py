import discord
from discord import app_commands
from discord.ext import commands
from globals import RPG_INVENTORY_FILE, GUILD_ID
from rpgutils import (
    rpg_load_data,
    rpg_save_data,
    update_equipment_bonuses_for_user,
    calculate_starting_hp_mana_stamina,
    full_heal,
)
import enum


class Tile(enum.Enum):
    EMPTY = "🔳"
    DEAD = "💀"


class State(enum.Enum):
    WAITING = "Waiting for player"
    ENEMY_TURN = "Enemy's turn"


class CombatScreen(discord.ui.View):
    def __init__(self, grid_width=2):
        super().__init__()
        # Create the grid first
        self.grid_width = grid_width
        self.grid = self.__create_grid()
        # Create the embedding second
        self.embed = self.__create_embed()
        # State machine
        self.sate = State.WAITING
        pass

    def __create_embed(self):
        embed = discord.Embed(
            title="Combat Encounter",
            description=f"You have encountered enemies!\n\n{self.__display_grid()}",
            color=discord.Color.red(),
        )
        return embed

    def __create_grid(self):
        grid = [[Tile.EMPTY.value for _ in range(self.grid_width)] for _ in range(2)]
        return grid

    def __display_grid(self) -> str:
        # Add padding, you better be thankful I didnt use numpy for this
        grid_with_spacing = [[""] + [str(i) for i in range(self.grid_width)]] + [
            [str(idx)] + row for idx, row in enumerate(self.grid)
        ]
        # Add column and row numbers to the grid because I know people wont be able to zero index
        for i in range(len(grid_with_spacing[0])):
            grid_with_spacing[0][i] = " " + str(i - 1) if i != 0 else ""
        for i in range(len(grid_with_spacing)):
            grid_with_spacing[i][0] = str(i - 1) if i != 0 else "-"
        grid_with_spacing = "\n\n\n".join(["\t".join(row) for row in grid_with_spacing])

        return f"```\n{grid_with_spacing}\n```"

    def get_embed(self):
        return self.embed

    def update_grid(self, row, col, value) -> None:
        self.grid[row][col] = value
        self.embed = self.__create_embed()

    def get_status(self) -> str:
        return self.sate.value


class CombatCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.combat_session = None

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="start_combat", description="Start a combat encounter.")
    async def start_combat(self, interaction: discord.Interaction):
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
