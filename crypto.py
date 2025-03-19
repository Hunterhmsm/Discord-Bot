import discord
from discord import app_commands
from discord.ext import commands, tasks
import json
import os
import random
import datetime
from zoneinfo import ZoneInfo
from globals import STOCK_FILE, GUILD_ID, UPDATE_INTERVAL_MINUTES
from stocks import load_stocks
from utils import load_data, save_data
from typing import Optional
import pytz

class CryptoCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.mine_loop = tasks.loop(minutes=UPDATE_INTERVAL_MINUTES)(self.execute_mine)
        self.mine_loop.start()

    async def execute_mine(self):
        data = load_data()
        stock_data = load_stocks()
        for user_id in data:
            user_record = data.get(user_id, {"balance": 0, "graphics_cards": 0, "mining": None, "portfolio": {}})
            if user_record.get("mining") and user_record.get("graphics_cards"):
                curr_mining = user_record.get("mining")
                num_cards = user_record.get("graphics_cards")
                portfolio = user_record.get("portfolio", {})
                use_cost = (stock_data[curr_mining] * 0.50) * num_cards
                
                if user_record.get("balance", 0) >= use_cost:
                    user_record["balance"] -= use_cost
                    portfolio[curr_mining] = portfolio.get(curr_mining, 0) + num_cards
                    user_record["portfolio"] = portfolio
                    data[user_id] = user_record
        save_data(data)
    
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="crypto", description="Shows how many RTX 5090s owned and what is currently being mined.")
    @app_commands.describe(user="The user to check crypto statistics for (defaults to yourself if not provided).")
    async def crypto(self, interaction: discord.Interaction, user: Optional[discord.Member] = None):
        target = user or interaction.user
        data = load_data()
        user_id = str(target.id)
        user_record = data.get(user_id, {"graphics_cards": 0, "mining": None})
        num_cards = user_record.get("graphics_cards", 0)
        curr_mining = user_record.get("mining", None)

        if not curr_mining:
            curr_mining = "Not mining..."
        
        embed = discord.Embed(
            title=f"{target}'s Crypto Mining Rig",
            color=discord.Color.green()
        )
        image = discord.File("RTX5090.jpg", filename="RTX5090.jpg")
        embed.set_image(url="attachment://RTX5090.jpg")
        embed.add_field(
            name="Graphics Cards Owned",
            value=f"{num_cards}",
            inline=True
        )
        embed.add_field(
            name="Currently Mining",
            value=f"{curr_mining}",
            inline=True
        )
        await interaction.response.send_message(embed=embed, file=image)

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="cryptobuy", description="Buy RTX 5090s using your Beaned Bucks. Each card is $10,000")
    @app_commands.describe(quantity="Number of cards to purchase")
    async def cryptobuy(self, interaction: discord.Interaction, quantity: int):
        data = load_data()
        user_id = str(interaction.user.id)
        user_record = data.get(user_id, {"balance": 0, "graphics_cards": 0})
        current_balance = float(user_record.get("balance", 0))

        try:
            num_cards = int(quantity)
        except ValueError:
            await interaction.response.send_message("You cannot buy fractional graphics cards!", ephemeral=True)
            return
        
        if num_cards <= 0:
            await interaction.response.send_message("Number of cards must be greater than 0.", ephemeral=True)
            return
        if (num_cards * 10000) > current_balance:
            await interaction.response.send_message(f"You do not have enough Beaned Bucks to buy {num_cards} cards.", ephemeral=True)
            return
        
        user_record["balance"] = current_balance - (num_cards * 10000)
        total_cards = user_record.get("graphics_cards", 0) + num_cards
        user_record["graphics_cards"] = total_cards

        data[user_id] = user_record
        save_data(data)

        await interaction.response.send_message(
            f"Successfully purchased {num_cards} RTX 5090s.\n"
            f"You now own {total_cards} graphics cards.\n"
            f"Your new balance is {user_record['balance']} Beaned Bucks."
        )

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="cryptosell", description="Sell your RTX 5090s for $5,000 Beaned Bucks. Don't complain, they've been used to mine crypto.")
    @app_commands.describe(quantity="The number of graphics cards you want to sell.")
    async def cryptosell(self, interaction: discord.Interaction, quantity: int):
        data = load_data()
        user_id = str(interaction.user.id)
        user_record = data.get(user_id, {"balance": 0, "graphics_cards": 0})
        owned_cards = user_record.get("graphics_cards", 0)

        if not owned_cards:
            await interaction.response.send_message("You do not own any RTX 5090s.", ephemeral=True)
            return
        
        try:
            num_sell = int(quantity)
        except Exception as e:
            await interaction.response.send_message("You cannot sell fractional graphics cards!", ephemeral=True)
            return
        
        if num_sell <= 0:
            await interaction.response.send_message("Quantity must be greater than zero.", ephemeral=True)
            return
        if owned_cards < num_sell:
            await interaction.response.send_message("You cannot sell more graphics cards than you own.", ephemeral=True)
            return
        
        sale_value = num_sell * 5000

        user_record["balance"] += float(sale_value)
        user_record["graphics_cards"] -= num_sell

        data[user_id] = user_record
        save_data(data)

        await interaction.response.send_message(
            f"Successfully sold {num_sell} RTX 5090s for $5,000 Beaned Bucks each for a total of {sale_value} Beaned Bucks.\n"
            f"Your new balance is {user_record['balance']} Beaned Bucks."
        )

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="mine", description="Decide what crypto you'd like to mine. You will gain 1 coin/card every 5 minutes.")
    @app_commands.describe(crypto="The cryptocoin that you'd like to mine ('stop' to stop mining).")
    async def mine(self, interaction: discord.Interaction, crypto: str):
        data = load_data()
        user_id = str(interaction.user.id)
        user_record = data.get(user_id, {"balance": 0, "graphics_cards": 0, "mining": None})
        owned_cards = user_record.get("graphics_cards")

        crypto_data = load_stocks()
        crypto = crypto.upper()

        if crypto == "STOP":
            user_record["mining"] = None
            data[user_id] = user_record
            save_data(data)
            await interaction.response.send_message(
            f"You are no longer mining\n", ephemeral=True)
            return

        if not crypto.endswith("COIN"):
            await interaction.response.send_message("Invalid crypto symbol.", ephemeral=True)
            return
        if crypto not in crypto_data:
            await interaction.response.send_message("Invalid crypto symbol.", ephemeral=True)
            return

        if not owned_cards:
            await interaction.response.send_message("You do not own any RTX 5090s.", ephemeral=True)
            return
        
        user_record["mining"] = crypto
        data[user_id] = user_record
        save_data(data)

        await interaction.response.send_message(
            f"You are now mining {crypto}\n", ephemeral=True)
                
async def setup(bot: commands.Bot):
    print("Loading CryptoCog...")
    await bot.add_cog(CryptoCog(bot))