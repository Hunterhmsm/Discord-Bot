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

POWER_PER_CARD = 25  # Power consumed per graphics card per mining cycle

class CryptoCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.mine_loop = tasks.loop(minutes=UPDATE_INTERVAL_MINUTES)(self.execute_mine)
        self.mine_loop.start()

    async def execute_mine(self):
        data = load_data()
        stock_data = load_stocks()
        for user_id in data:
            user_record = data.get(user_id, {"balance": 0, "graphics_cards": 0, "mining": {}, "portfolio": {}, "inventory": {}})
            mining_config = user_record.get("mining", {})
            total_cards = user_record.get("graphics_cards", 0)
            
            if not mining_config or total_cards == 0:
                continue
                
            portfolio = user_record.get("portfolio", {})
            inventory = user_record.get("inventory", {})
            
            # Calculate total cards being used for mining
            total_mining_cards = sum(mining_config.values())
            if total_mining_cards == 0:
                continue
                
            # Calculate power needed
            power_needed = total_mining_cards * POWER_PER_CARD
            power_available = inventory.get("power", 0)
            
            # Calculate how many cards can actually mine based on available power
            cards_that_can_mine = min(total_mining_cards, power_available // POWER_PER_CARD)
            
            if cards_that_can_mine > 0:
                # Calculate total electricity cost across all coins
                total_electricity_cost = 0
                for coin, allocated_cards in mining_config.items():
                    if allocated_cards > 0 and coin in stock_data:
                        cost_per_card = stock_data[coin] * 0.50
                        total_electricity_cost += cost_per_card * allocated_cards
                
                # Scale electricity cost if not all cards can mine
                if cards_that_can_mine < total_mining_cards:
                    total_electricity_cost *= (cards_that_can_mine / total_mining_cards)
                
                # Check if user has enough money for electricity
                if user_record.get("balance", 0) >= total_electricity_cost:
                    # Consume power
                    power_consumed = cards_that_can_mine * POWER_PER_CARD
                    inventory["power"] = max(0, inventory.get("power", 0) - power_consumed)
                    
                    # Pay electricity cost
                    user_record["balance"] -= total_electricity_cost
                    
                    # Distribute mining rewards proportionally
                    for coin, allocated_cards in mining_config.items():
                        if allocated_cards > 0 and coin in stock_data:
                            # Calculate how many of this coin's cards can actually mine
                            proportion = allocated_cards / total_mining_cards
                            effective_cards = int(cards_that_can_mine * proportion)
                            
                            if effective_cards > 0:
                                portfolio[coin] = portfolio.get(coin, 0) + effective_cards
                    
                    user_record["portfolio"] = portfolio
                    user_record["inventory"] = inventory
                    data[user_id] = user_record
                    
                    print(f"User {user_id} mined with {cards_that_can_mine}/{total_mining_cards} cards using {power_consumed} power")
                else:
                    print(f"User {user_id} couldn't afford electricity for mining ({total_electricity_cost:.2f} needed)")
            else:
                print(f"User {user_id} has no power for mining (needs {power_needed}, has {power_available})")
        save_data(data)
    
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="crypto", description="Shows your mining rig status and current mining configuration.")
    @app_commands.describe(user="The user to check crypto statistics for (defaults to yourself if not provided).")
    async def crypto(self, interaction: discord.Interaction, user: Optional[discord.Member] = None):
        target = user or interaction.user
        data = load_data()
        user_id = str(target.id)
        user_record = data.get(user_id, {"graphics_cards": 0, "mining": {}, "inventory": {}})
        total_cards = user_record.get("graphics_cards", 0)
        mining_config = user_record.get("mining", {})
        power_available = user_record.get("inventory", {}).get("power", 0)
        
        # Calculate mining stats
        total_mining_cards = sum(mining_config.values())
        idle_cards = total_cards - total_mining_cards
        power_needed = total_mining_cards * POWER_PER_CARD
        cards_that_can_mine = min(total_mining_cards, power_available // POWER_PER_CARD) if power_available > 0 else 0

        embed = discord.Embed(
            title=f"{target.display_name}'s Crypto Mining Rig",
            color=discord.Color.green()
        )
        
        # Try to add image if it exists
        try:
            image = discord.File("RTX5090.jpg", filename="RTX5090.jpg")
            embed.set_image(url="attachment://RTX5090.jpg")
            has_image = True
        except:
            has_image = False
            
        embed.add_field(
            name="Graphics Cards",
            value=f"Total: {total_cards}\nMining: {total_mining_cards}\nIdle: {idle_cards}",
            inline=True
        )
        
        if mining_config:
            mining_status = ""
            for coin, allocated_cards in mining_config.items():
                if allocated_cards > 0:
                    mining_status += f"{coin}: {allocated_cards} cards\n"
            if not mining_status:
                mining_status = "No cards allocated"
        else:
            mining_status = "Not configured"
            
        embed.add_field(
            name="Mining Configuration",
            value=mining_status,
            inline=True
        )
        
        embed.add_field(
            name="Power Status",
            value=f"Available: {power_available}\nNeeded: {power_needed}\nEffective Cards: {cards_that_can_mine}/{total_mining_cards}",
            inline=False
        )
        
        embed.add_field(
            name="Power Usage",
            value=f"{POWER_PER_CARD} power per card per {UPDATE_INTERVAL_MINUTES} minutes",
            inline=False
        )
        
        if has_image:
            await interaction.response.send_message(embed=embed, file=image)
        else:
            await interaction.response.send_message(embed=embed)

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="mineconfig", description="Configure how many cards mine each cryptocurrency.")
    @app_commands.describe(
        coin="The cryptocurrency to mine (e.g., BEANEDCOIN)",
        cards="Number of cards to allocate to this coin (0 to stop mining this coin)"
    )
    async def mineconfig(self, interaction: discord.Interaction, coin: str, cards: int):
        data = load_data()
        user_id = str(interaction.user.id)
        user_record = data.get(user_id, {"graphics_cards": 0, "mining": {}})
        total_cards = user_record.get("graphics_cards", 0)
        mining_config = user_record.get("mining", {})
        
        coin = coin.upper()
        crypto_data = load_stocks()
        
        # Validation
        if not coin.endswith("COIN"):
            await interaction.response.send_message("Invalid crypto symbol. Must end with 'COIN'.", ephemeral=True)
            return
        if coin not in crypto_data:
            await interaction.response.send_message("Invalid crypto symbol.", ephemeral=True)
            return
        if total_cards == 0:
            await interaction.response.send_message("You do not own any RTX 5090s.", ephemeral=True)
            return
        if cards < 0:
            await interaction.response.send_message("Cannot allocate negative cards.", ephemeral=True)
            return
            
        # Calculate current allocation excluding this coin
        current_allocated = sum(count for c, count in mining_config.items() if c != coin)
        
        if current_allocated + cards > total_cards:
            available_cards = total_cards - current_allocated
            await interaction.response.send_message(
                f"Cannot allocate {cards} cards to {coin}. You only have {available_cards} cards available.\n"
                f"Current allocation: {current_allocated}/{total_cards} cards", 
                ephemeral=True
            )
            return
        
        # Update mining configuration
        if cards == 0:
            mining_config.pop(coin, None)  # Remove if setting to 0
            action = "stopped mining"
        else:
            mining_config[coin] = cards
            action = f"allocated {cards} cards to mine"
            
        user_record["mining"] = mining_config
        data[user_id] = user_record
        save_data(data)
        
        # Calculate new totals
        total_mining_cards = sum(mining_config.values())
        idle_cards = total_cards - total_mining_cards
        power_needed = total_mining_cards * POWER_PER_CARD
        
        response = f"Successfully {action} {coin}!\n\n"
        response += f"**Current Mining Setup:**\n"
        if mining_config:
            for c, count in mining_config.items():
                response += f"• {c}: {count} cards\n"
        else:
            response += "• No cards currently mining\n"
        response += f"\n**Summary:** {total_mining_cards}/{total_cards} cards mining, {idle_cards} idle"
        response += f"\n**Power needed:** {power_needed} per {UPDATE_INTERVAL_MINUTES} minutes"
        
        await interaction.response.send_message(response, ephemeral=True)

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="minestop", description="Stop all mining operations.")
    async def minestop(self, interaction: discord.Interaction):
        data = load_data()
        user_id = str(interaction.user.id)
        user_record = data.get(user_id, {"mining": {}})
        
        user_record["mining"] = {}
        data[user_id] = user_record
        save_data(data)
        
        await interaction.response.send_message("All mining operations have been stopped. All cards are now idle.", ephemeral=True)

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="minestart", description="Quickly start mining with all cards on one cryptocurrency.")
    @app_commands.describe(coin="The cryptocurrency to mine with all available cards")
    async def minestart(self, interaction: discord.Interaction, coin: str):
        data = load_data()
        user_id = str(interaction.user.id)
        user_record = data.get(user_id, {"graphics_cards": 0, "mining": {}})
        total_cards = user_record.get("graphics_cards", 0)
        
        coin = coin.upper()
        crypto_data = load_stocks()
        
        # Validation
        if not coin.endswith("COIN"):
            await interaction.response.send_message("Invalid crypto symbol. Must end with 'COIN'.", ephemeral=True)
            return
        if coin not in crypto_data:
            await interaction.response.send_message("Invalid crypto symbol.", ephemeral=True)
            return
        if total_cards == 0:
            await interaction.response.send_message("You do not own any RTX 5090s.", ephemeral=True)
            return
        
        # Set all cards to mine this coin
        user_record["mining"] = {coin: total_cards}
        data[user_id] = user_record
        save_data(data)
        
        power_needed = total_cards * POWER_PER_CARD
        power_available = user_record.get("inventory", {}).get("power", 0)
        cards_that_can_mine = min(total_cards, power_available // POWER_PER_CARD) if power_available > 0 else 0
        
        response = f"All {total_cards} cards are now mining {coin}!\n"
        response += f"Power needed: {power_needed} per {UPDATE_INTERVAL_MINUTES} minutes\n"
        response += f"Power available: {power_available}\n"
        response += f"Cards that can mine: {cards_that_can_mine}/{total_cards}"
        
        if cards_that_can_mine < total_cards:
            response += f"\n⚠️ You need more power to run all your cards!"
        
        await interaction.response.send_message(response, ephemeral=True)

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
        power_needed_all = total_cards * POWER_PER_CARD

        data[user_id] = user_record
        save_data(data)

        await interaction.response.send_message(
            f"Successfully purchased {num_cards} RTX 5090s.\n"
            f"You now own {total_cards} graphics cards.\n"
            f"Power needed if all mining: {power_needed_all} per {UPDATE_INTERVAL_MINUTES} minutes\n"
            f"Your new balance is {user_record['balance']} Beaned Bucks.\n"
            f"Use `/mineconfig` or `/minestart` to begin mining!"
        )

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="cryptosell", description="Sell your RTX 5090s for $5,000 Beaned Bucks. Don't complain, they've been used to mine crypto.")
    @app_commands.describe(quantity="The number of graphics cards you want to sell.")
    async def cryptosell(self, interaction: discord.Interaction, quantity: int):
        data = load_data()
        user_id = str(interaction.user.id)
        user_record = data.get(user_id, {"balance": 0, "graphics_cards": 0, "mining": {}})
        owned_cards = user_record.get("graphics_cards", 0)
        mining_config = user_record.get("mining", {})

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
        
        # Check if selling would create invalid mining configuration
        total_mining_cards = sum(mining_config.values())
        remaining_cards = owned_cards - num_sell
        
        if total_mining_cards > remaining_cards:
            await interaction.response.send_message(
                f"Cannot sell {num_sell} cards. You have {total_mining_cards} cards allocated for mining, "
                f"but would only have {remaining_cards} cards remaining. Use `/minestop` or `/mineconfig` first.",
                ephemeral=True
            )
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

    # Legacy command for backward compatibility
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="mine", description="Legacy command - use /minestart instead.")
    @app_commands.describe(crypto="Use /minestart [coin] instead, or /mineconfig for advanced setup")
    async def mine(self, interaction: discord.Interaction, crypto: str):
        await interaction.response.send_message(
            "⚠️ This command is deprecated. Please use:\n"
            "• `/minestart [coin]` - Start mining with all cards\n"
            "• `/mineconfig [coin] [cards]` - Configure specific cards per coin\n"
            "• `/minestop` - Stop all mining\n"
            "• `/crypto` - View your mining status",
            ephemeral=True
        )
                
async def setup(bot: commands.Bot):
    print("Loading CryptoCog...")
    await bot.add_cog(CryptoCog(bot))
