import discord
from discord import app_commands
from discord.ext import commands, tasks
import json
import os
import datetime
from globals import UPDATE_INTERVAL_MINUTES, GUILD_ID, OPTIONS_FILE
from utils import load_data, save_data
from stocks import load_stocks
from typing import Optional
import numpy as np
from scipy.stats import norm

def black_scholes(S, K, T, r, sigma, option_type='call'):
    """
    Calculate the Black-Scholes option price and Greeks.
    """
    if S <= 0 or K <= 0 or T <= 0 or sigma <= 0:
        raise ValueError("S, K, T, and sigma must be positive values.")
    
    d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)

    if option_type == 'call':
        option_price = S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
        delta = norm.cdf(d1)
        theta = (-S * norm.pdf(d1) * sigma / (2 * np.sqrt(T))
                 - r * K * np.exp(-r * T) * norm.cdf(d2))
    elif option_type == 'put':
        option_price = K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)
        delta = norm.cdf(d1) - 1
        theta = (-S * norm.pdf(d1) * sigma / (2 * np.sqrt(T))
                 + r * K * np.exp(-r * T) * norm.cdf(-d2))

    gamma = norm.pdf(d1) / (S * sigma * np.sqrt(T))
    
    return option_price, delta, gamma, theta

def calculate_time_to_expiration(expiry_date_str):
    """Calculate time to expiration in years."""
    try:
        expiry_dt = datetime.datetime.strptime(expiry_date_str, '%Y-%m-%d %H:%M:%S')
        now = datetime.datetime.now()
        time_diff = expiry_dt - now
        return max(time_diff.total_seconds() / (365.25 * 24 * 3600), 0.001)  # Minimum 1 day
    except:
        return 0.001

def generate_strike_prices(stock_price, num_strikes=5):
    """Generate realistic strike prices around current stock price."""
    strikes = []
    # Generate strikes: 90%, 95%, 100%, 105%, 110% of current price
    percentages = [0.90, 0.95, 1.00, 1.05, 1.10]
    for pct in percentages:
        strike = round(stock_price * pct, 2)
        strikes.append(str(strike))
    return strikes

def load_options():
    try:
        with open(OPTIONS_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_options(data):
    with open(OPTIONS_FILE, "w") as f:
        json.dump(data, f, indent=4)

def create_options_for_stock(stock, stock_price):
    """Create option chain for a specific stock."""
    options = {}
    
    # Create 4 expiration dates (today + 1, 2, 3, 4 days at 8 PM)
    for i in range(1, 5):
        expiry_dt = datetime.datetime.now() + datetime.timedelta(days=i)
        expiry_dt = expiry_dt.replace(hour=20, minute=0, second=0, microsecond=0)
        expiry_str = expiry_dt.strftime('%Y-%m-%d %H:%M:%S')
        
        options[expiry_str] = {"call": {}, "put": {}}
        
        # Calculate time to expiration
        T = calculate_time_to_expiration(expiry_str)
        
        # Generate strike prices
        strikes = generate_strike_prices(stock_price)
        
        # Options parameters
        r = 0.04  # Risk-free rate
        sigma = 0.25  # Volatility
        
        for strike_str in strikes:
            K = float(strike_str)
            
            # Calculate call option
            try:
                call_price, call_delta, call_gamma, call_theta = black_scholes(
                    stock_price, K, T, r, sigma, 'call'
                )
                
                options[expiry_str]["call"][strike_str] = {
                    "price": max(round(call_price, 2), 0.01),
                    "delta": round(max(call_delta, 0.01), 3),
                    "gamma": round(max(call_gamma, 0.001), 3),
                    "theta": round(min(call_theta, -0.01), 3)
                }
                
                # Calculate put option
                put_price, put_delta, put_gamma, put_theta = black_scholes(
                    stock_price, K, T, r, sigma, 'put'
                )
                
                options[expiry_str]["put"][strike_str] = {
                    "price": max(round(put_price, 2), 0.01),
                    "delta": round(min(put_delta, -0.01), 3),
                    "gamma": round(max(put_gamma, 0.001), 3),
                    "theta": round(min(put_theta, -0.01), 3)
                }
                
            except Exception as e:
                print(f"Error calculating options for {stock} strike {K}: {e}")
                continue
    
    return options

class OptionsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.options_task = tasks.loop(minutes=UPDATE_INTERVAL_MINUTES)(self.update_options)
        self.options_task.start()

    async def update_options(self):
        """Update option prices and handle expirations."""
        stock_data = load_stocks()
        options_data = load_options()
        now = datetime.datetime.now()
        
        # Remove expired options and notify users
        data = load_data()
        for user_id, user_record in data.items():
            if "options" not in user_record:
                continue
                
            expired_options = []
            for option in user_record["options"][:]:  # Copy list to modify during iteration
                try:
                    expiry_dt = datetime.datetime.strptime(option["expiration"], '%Y-%m-%d %H:%M:%S')
                    if now >= expiry_dt:
                        expired_options.append(option)
                        user_record["options"].remove(option)
                except:
                    continue
            
            if expired_options:
                try:
                    user = await self.bot.fetch_user(int(user_id))
                    for option in expired_options:
                        await user.send(
                            f"Your {option['stock']} {option['strategy']} option "
                            f"(strike: {option['strike_price']}) has expired."
                        )
                except:
                    pass  # User not found or DMs disabled
        
        # Update options data for each stock
        for stock, price in stock_data.items():
            if stock.endswith("COIN"):
                continue  # Skip cryptocoins
                
            if stock not in options_data:
                options_data[stock] = {}
            
            # Update current stock price
            options_data[stock]["current_price"] = price
            
            # Create or update option chain
            new_options = create_options_for_stock(stock, price)
            options_data[stock]["expiration"] = new_options
            
            # Update user option prices
            for user_id, user_record in data.items():
                if "options" not in user_record:
                    continue
                    
                for option in user_record["options"]:
                    if option["stock"] != stock:
                        continue
                        
                    expiry = option["expiration"]
                    strategy = option["strategy"]
                    strike = str(option["strike_price"])
                    
                    if (expiry in new_options and 
                        strategy in new_options[expiry] and 
                        strike in new_options[expiry][strategy]):
                        option[f"{strategy}_price"] = new_options[expiry][strategy][strike]["price"]
        
        save_options(options_data)
        save_data(data)

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="options", description="Shows what options the user currently owns.")
    @app_commands.describe(user="The user to check options for (defaults to yourself)")
    async def user_options(self, interaction: discord.Interaction, user: Optional[discord.Member] = None):
        target = user or interaction.user
        data = load_data()
        user_id = str(target.id)
        user_record = data.get(user_id, {"options": []})
        user_options = user_record.get("options", [])
        
        if not user_options:
            await interaction.response.send_message("No options owned.", ephemeral=True)
            return
        
        embed = discord.Embed(
            title=f"{target.display_name}'s Options Portfolio",
            color=discord.Color.purple()
        )
        
        for option in user_options:
            strategy_price = option.get(f"{option['strategy']}_price", 0)
            embed.add_field(
                name=f"{option['stock']} ${option['strike_price']} {option['strategy'].upper()}",
                value=(f"Current Price: ${strategy_price}\n"
                      f"Quantity: {option['quantity']}\n"
                      f"Expires: {option['expiration'][:10]}"),
                inline=True
            )
        
        await interaction.response.send_message(embed=embed)

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="optionsview", description="Browse options for stocks (cryptocoins not included).")
    @app_commands.describe(
        stock="Stock symbol (e.g. INK)", 
        strategy="Option type ('call' or 'put')",
        expiry="Days to expiration (1-4)"
    )
    async def stock_options(self, interaction: discord.Interaction, stock: str, strategy: str, expiry: int):
        stock = stock.upper()
        
        if expiry < 1 or expiry > 4:
            await interaction.response.send_message("Expiry must be between 1 and 4 days.", ephemeral=True)
            return
            
        if strategy not in ('call', 'put'):
            await interaction.response.send_message("Strategy must be 'call' or 'put'.", ephemeral=True)
            return
        
        stocks = load_stocks()
        if stock not in stocks or stock.endswith("COIN"):
            await interaction.response.send_message("Invalid stock symbol.", ephemeral=True)
            return
        
        options_data = load_options()
        if stock not in options_data:
            # Create options for this stock
            new_options = create_options_for_stock(stock, stocks[stock])
            options_data[stock] = {
                "current_price": stocks[stock],
                "expiration": new_options
            }
            save_options(options_data)
        
        # Find the correct expiration date
        expiry_dates = sorted(options_data[stock]["expiration"].keys())
        if expiry > len(expiry_dates):
            await interaction.response.send_message("Not enough expiration dates available.", ephemeral=True)
            return
            
        target_expiry = expiry_dates[expiry - 1]
        option_chain = options_data[stock]["expiration"][target_expiry][strategy]
        
        embed = discord.Embed(
            title=f"{stock} {strategy.upper()} Options - Expires {target_expiry[:10]}",
            description=f"Current Stock Price: ${stocks[stock]}",
            color=discord.Color.blue()
        )
        
        for strike, data in option_chain.items():
            embed.add_field(
                name=f"Strike: ${strike}",
                value=(f"Price: ${data['price']}\n"
                      f"Delta: {data['delta']}\n"
                      f"Gamma: {data['gamma']}\n"
                      f"Theta: {data['theta']}"),
                inline=True
            )
        
        await interaction.response.send_message(embed=embed)

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="optionbuy", description="Buy options for stocks.")
    @app_commands.describe(
        stock="Stock symbol", strategy="'call' or 'put'", expiry="Days to expiration (1-4)",
        strike="Strike price", quantity="Number of contracts"
    )
    async def option_buy(self, interaction: discord.Interaction, stock: str, strategy: str, 
                        expiry: int, strike: float, quantity: int):
        stock = stock.upper()
        
        # Validation
        if expiry < 1 or expiry > 4:
            await interaction.response.send_message("Expiry must be between 1 and 4 days.", ephemeral=True)
            return
        if strategy not in ('call', 'put'):
            await interaction.response.send_message("Strategy must be 'call' or 'put'.", ephemeral=True)
            return
        if quantity < 1:
            await interaction.response.send_message("Quantity must be at least 1.", ephemeral=True)
            return
            
        stocks = load_stocks()
        if stock not in stocks or stock.endswith("COIN"):
            await interaction.response.send_message("Invalid stock symbol.", ephemeral=True)
            return
        
        options_data = load_options()
        if stock not in options_data:
            await interaction.response.send_message("Options not available for this stock.", ephemeral=True)
            return
            
        expiry_dates = sorted(options_data[stock]["expiration"].keys())
        if expiry > len(expiry_dates):
            await interaction.response.send_message("Invalid expiry date.", ephemeral=True)
            return
            
        target_expiry = expiry_dates[expiry - 1]
        strike_str = str(strike)
        
        if strike_str not in options_data[stock]["expiration"][target_expiry][strategy]:
            await interaction.response.send_message("Invalid strike price.", ephemeral=True)
            return
        
        option_data = options_data[stock]["expiration"][target_expiry][strategy][strike_str]
        total_cost = option_data["price"] * 100 * quantity  # Options are priced per share, sold in 100-share contracts
        
        data = load_data()
        user_id = str(interaction.user.id)
        user_record = data.get(user_id, {"balance": 0, "options": []})
        
        if user_record.get("balance", 0) < total_cost:
            await interaction.response.send_message(
                f"Insufficient funds. Need ${total_cost:,.2f}, have ${user_record.get('balance', 0):,.2f}.", 
                ephemeral=True
            )
            return
        
        # Deduct cost
        user_record["balance"] -= total_cost
        
        # Add option to portfolio
        if "options" not in user_record:
            user_record["options"] = []
            
        # Check if user already owns this exact option
        found = False
        for option in user_record["options"]:
            if (option["stock"] == stock and option["strategy"] == strategy and 
                option["expiration"] == target_expiry and option["strike_price"] == strike):
                option["quantity"] += quantity
                found = True
                break
        
        if not found:
            user_record["options"].append({
                "stock": stock,
                "strategy": strategy,
                "expiration": target_expiry,
                "strike_price": strike,
                "quantity": quantity,
                f"{strategy}_price": option_data["price"]
            })
        
        data[user_id] = user_record
        save_data(data)
        
        await interaction.response.send_message(
            f"Bought {quantity} {stock} ${strike} {strategy} contracts for ${total_cost:,.2f}.",
            ephemeral=True
        )

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="optionsell", description="Sell options.")
    @app_commands.describe(
        stock="Stock symbol", strategy="'call' or 'put'", expiry="Days to expiration (1-4)",
        strike="Strike price", quantity="Number of contracts to sell"
    )
    async def option_sell(self, interaction: discord.Interaction, stock: str, strategy: str,
                         expiry: int, strike: float, quantity: int):
        stock = stock.upper()
        
        data = load_data()
        user_id = str(interaction.user.id)
        user_record = data.get(user_id, {"balance": 0, "options": []})
        
        if not user_record.get("options"):
            await interaction.response.send_message("You don't own any options.", ephemeral=True)
            return
        
        # Find the option to sell
        target_option = None
        expiry_dates = sorted(load_options().get(stock, {}).get("expiration", {}).keys())
        if expiry <= len(expiry_dates):
            target_expiry = expiry_dates[expiry - 1]
            
            for option in user_record["options"]:
                if (option["stock"] == stock and option["strategy"] == strategy and
                    option["expiration"] == target_expiry and option["strike_price"] == strike):
                    target_option = option
                    break
        
        if not target_option or target_option["quantity"] < quantity:
            await interaction.response.send_message("You don't own enough of those options.", ephemeral=True)
            return
        
        # Calculate sale value using current option price
        current_price = target_option.get(f"{strategy}_price", 0)
        total_value = current_price * 100 * quantity
        
        # Update user data
        user_record["balance"] += total_value
        target_option["quantity"] -= quantity
        
        if target_option["quantity"] <= 0:
            user_record["options"].remove(target_option)
        
        data[user_id] = user_record
        save_data(data)
        
        await interaction.response.send_message(
            f"Sold {quantity} contracts for ${total_value:,.2f}.",
            ephemeral=True
        )

async def setup(bot: commands.Bot):
    print("Loading OptionsCog...")
    await bot.add_cog(OptionsCog(bot))