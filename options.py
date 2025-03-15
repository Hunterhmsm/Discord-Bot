import discord
from discord import app_commands
from discord.ext import commands, tasks
import json
import random
import datetime
from globals import UPDATE_INTERVAL_MINUTES, GUILD_ID, OPTIONS_FILE
from utils import load_data, save_data
from stocks import load_stocks
from typing import Optional
import numpy as np
from scipy.stats import norm

import numpy as np
from scipy.stats import norm

def black_scholes(S, K, T, r, sigma, option_type='call'):
    """
    Calculate the Black-Scholes option price and Greeks.
    
    Parameters:
    - S: Current stock price
    - K: Strike price
    - T: Time to expiration (in years)
    - r: Risk-free rate (as a decimal)
    - sigma: Volatility of the underlying (as a decimal)
    - option_type: 'call' or 'put'
    
    Returns:
    - option_price: Price of the option
    - delta: First derivative of the option price w.r.t underlying price
    - gamma: Second derivative of the option price w.r.t underlying price
    - theta: Sensitivity of the option price w.r.t time decay
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


def load_options():
    try:
        with open(OPTIONS_FILE, "r") as f:
            data = json.load(f)
            if not isinstance(data, dict):
                raise ValueError("Stocks data is not a dictionary.")
            return data
    except (FileNotFoundError, json.JSONDecodeError, ValueError):
        default_data = {}
        stock_data = load_stocks()
        for stock, value in stock_data.items():
            if not stock.upper().endswith("COIN"):
                default_data[stock] = {"price": value}
        return default_data

def save_options(data):
    with open(OPTIONS_FILE, "w") as f:
        json.dump(data, f, indent=4)

def create_options(stock):
    options = load_options()
    stock = stock.upper()

    if "expiration" not in options[stock]:
        options[stock]["expiration"] = {}
        today = datetime.datetime.today()

        # Options variables
        S = options[stock].get("price")
        r = 0.04
        sigma = 0.2
        T = 0.5
        
        # Fill in expiration dates
        for i in range(4):
            next_date = (today + datetime.timedelta(days=i)).replace(hour=20, minute=0)
            date_string = next_date.strftime('%-m/%d/%Y %-I:%M%p')
            options[stock]["expiration"][date_string] = {"call": {}, "put": {}}

            K_original = S
            K = K_original * 0.8

            # Fill in calls for this expiration date
            for _ in range(5):
                call_price, call_delta, call_gamma, call_theta = black_scholes(S, K, T, r, sigma, 'call')
                if call_delta < 0.01:
                    call_delta = 0.01
                if call_gamma < 0.01:
                    call_gamma = 0.01
                if call_theta > 0:
                    call_theta = np.negative(call_theta)
                if call_theta == 0:
                    call_theta = -0.01
                if np.negative(call_theta) > call_price:
                    call_theta = np.negative(call_price)
                strike_price = "{:.2f}".format(K)
                options[stock]["expiration"][date_string]["call"][strike_price] = {
                    "call_price": float("{:.2f}".format(call_price)),
                    "call_delta": float("{:.2f}".format(call_delta)),
                    "call_gamma": float("{:.2f}".format(call_gamma)),
                    "call_theta": float("{:.2f}".format(call_theta))
                }

                K += (K_original * 0.1)

            K_original = S
            K = K_original * 1.2

            # Fill in puts for this expiration date
            for _ in range(5):
                put_price, put_delta, put_gamma, put_theta = black_scholes(S, K, T, r, sigma, 'put')
                if put_delta > -0.01:
                    put_delta = -0.01
                if put_gamma > -0.01:
                    put_gamma = -0.01
                if put_theta > 0:
                    put_theta = np.negative(put_theta)
                if put_theta == 0:
                    put_theta = -0.01
                if np.negative(put_theta) > put_price:
                    put_theta = np.negative(put_price)
                strike_price = "{:.2f}".format(K)
                options[stock]["expiration"][date_string]["put"][strike_price] = {
                    "put_price": float("{:.2f}".format(put_price)),
                    "put_delta": float("{:.2f}".format(put_delta)),
                    "put_gamma": float("{:.2f}".format(put_gamma)),
                    "put_theta": float("{:.2f}".format(put_theta))
                }

                K -= (K_original * 0.1)
            
            T += 0.25

        save_options(options)

class OptionsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        #self.options_task = tasks.loop(minutes=UPDATE_INTERVAL_MINUTES)(self.update_options)
        #self.options_task.start()

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="options", description="Browse options for the Beaned stock market (cryptocoins not included).")
    @app_commands.describe(stock="Stock symbol (e.g. ACME)", strategy="Enter the strategy you want to view ('call' or 'put')",
                           expiry="How many days to expiration (0-3)")
    async def stock_options(self, interaction: discord.Interaction, stock: str, strategy: str, expiry: str):
        stock = stock.upper()
        try:
            DTE = int(expiry)
        except ValueError:
            await interaction.response.send_message("Please enter an integer.", ephemeral=True)
            return
        if DTE > 3 or DTE < 0:
            await interaction.response.send_message("You may only view options from 0 to 4 DTE", ephemeral=True)
            return
        if not strategy in ('call', 'put'):
            await interaction.response.send_message(f"Please enter a valid strategy ('call or put').", ephemeral=True)
            return
        stocks = load_stocks()
        if stock not in stocks or stock.endswith("COIN"):
            await interaction.response.send_message(f"Please enter a valid stock symbol (check /stocks).", ephemeral=True)
            return
        
        options = load_options()
        if len(options[stock]) == 1:
            create_options(stock)
            options = load_options()

        dates = list(options[stock]["expiration"].keys())
        target_date = dates[DTE]

        if strategy == "call":
            strike_prices = list(options[stock]["expiration"][target_date]["call"].keys())
            
            embed = discord.Embed(
                title=f"{stock} Call Options Expiring {target_date}\n"
                    + f"Current Price: {stocks[stock]}",
                color=discord.Color.yellow()
            )
            for i in range(5):
                call_options = options[stock]["expiration"][target_date]["call"][strike_prices[i]]
                embed.add_field(
                    name=f"Strike Price: {strike_prices[i]}\n"
                        +f"Call Price: {call_options.get('call_price')}",
                    value=f"Delta: {call_options.get('call_delta')}\n"
                        + f"Gamma: {call_options.get('call_gamma')}\n"
                        + f"Theta: {call_options.get('call_theta')}",
                    inline=True
                )

        if strategy == "put":
            strike_prices = list(options[stock]["expiration"][target_date]["put"].keys())
            
            embed = discord.Embed(
                title=f"{stock} Put Options Expiring {target_date}\n"
                    + f"Current Price: {stocks[stock]}",
                color=discord.Color.yellow()
            )
            for i in range(5):
                put_options = options[stock]["expiration"][target_date]["put"][strike_prices[i]]
                embed.add_field(
                    name=f"Strike Price: {strike_prices[i]}\n"
                        +f"Put Price: {put_options.get('put_price')}",
                    value=f"Delta: {put_options.get('put_delta')}\n"
                        + f"Gamma: {put_options.get('put_gamma')}\n"
                        + f"Theta: {put_options.get('put_theta')}",
                    inline=True
                )

        await interaction.response.send_message(embed=embed)

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="optionbuy", description="Buy options for the Beaned stock market (cryptocoins not included).")
    @app_commands.describe(stock="Stock symbol (e.g. ACME)", strategy="Enter the strategy you want to view ('call' or 'put')",
                           expiry="How many days to expiration (0-3)", strike="Enter the strike price of the option you'd like to buy",
                           quantity="Number of options you'd like to buy.")
    async def option_buy(self, interaction: discord.Interaction, stock: str, strategy: str, expiry: str, strike: str, quantity: str):
        stock = stock.upper()
        try:
            DTE = int(expiry)
        except ValueError:
            await interaction.response.send_message("Please enter an integer.", ephemeral=True)
            return
        try:
            strike_price = float(strike)
        except ValueError:
            await interaction.response.send_message("Please enter a valid strike price.", ephemeral=True)
            return
        try:
            num_options = int(quantity)
        except ValueError:
            await interaction.response.send_message("Please enter an integer.", ephemeral=True)
            return
        if DTE > 3 or DTE < 0:
            await interaction.response.send_message("You may only view options from 0 to 4 DTE", ephemeral=True)
            return
        if not strategy in ('call', 'put'):
            await interaction.response.send_message(f"Please enter a valid strategy ('call or put').", ephemeral=True)
            return
        stocks = load_stocks()
        if stock not in stocks or stock.endswith("COIN"):
            await interaction.response.send_message(f"Please enter a valid stock symbol (check /stocks).", ephemeral=True)
            return
        
        options = load_options()
        if len(options[stock]) == 1:
            create_options(stock)
            options = load_options()
        
        data = load_data()
        user_id = str(interaction.user.id)
        user_record = data.get(user_id, {"balance": 0, "options": []})

        dates = list(options[stock]["expiration"].keys())
        target_date = dates[DTE]
        target_option = options[stock]["expiration"][target_date][strategy][strike]
        total_owed = target_option.get("call_price") * 100 * num_options

        if strike not in options[stock]["expiration"][target_date][strategy]:
            await interaction.response.send_message("Please enter a valid strike price.", ephemeral=True)
            return
        if user_record.get("balance") < total_owed:
            await interaction.response.send_message(f"You can not afford {num_options} for {strike_price} x 100 (${total_owed} Beaned Bucks).", ephemeral=True)
            return
        
        user_record["balance"] -= total_owed
        
        if "options" not in user_record:
            user_record["options"] = []
        
        user_record["options"].append({
            "stock": stock,
            "strategy": strategy,
            "expiration": target_date,
            "call_price": target_option.get("call_price"),
            "strike_price": strike_price,
            "quantity": num_options
        })

        data[user_id] = user_record
        save_data(data)

        await interaction.response.send_message(f"Successfully purchased {num_options} options for ${total_owed} Beaned Bucks.", ephemeral=True)
        
async def setup(bot: commands.Bot):
    print("Loading OptionsCog...")
    await bot.add_cog(OptionsCog(bot))