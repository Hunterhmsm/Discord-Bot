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
                default_data[stock] = {"price": value, "expiration": {}}
                for i in range(4):
                    today = datetime.datetime.today()
                    next_date = (today + datetime.timedelta(days=i)).replace(hour=20, minute=0, second=0, microsecond=0)
                    date_string = next_date.strftime('%#m/%d/%Y %#I:%M%p')
                    default_data[stock]["expiration"][date_string] = {"call": {}, "put": {}}
            save_options(default_data)
        return default_data

def save_options(data):
    with open(OPTIONS_FILE, "w") as f:
        json.dump(data, f, indent=4)

def create_options(stock):
    options = load_options()
    stock_data = load_stocks()
    stock = stock.upper()
    
    if stock not in stock_data or stock.endswith("COIN"):
        return

    options[stock] = {"price": stock_data[stock], "expiration": {}}
    for i in range(4):
        today = datetime.datetime.today()
        next_date = (today + datetime.timedelta(days=i)).replace(hour=20, minute=0, second=0, microsecond=0)
        date_string = next_date.strftime('%#m/%d/%Y %#I:%M%p')
        options[stock]["expiration"][date_string] = {"call": {}, "put": {}}
    options[stock]["price"] = stock_data[stock]

    today = datetime.datetime.today()

    # Options variables
    S = options[stock].get("price")
    r = 0.04
    sigma = 0.2
    T = 0.5
    
    # Fill in expiration dates
    for i in range(4):
        next_date = (today + datetime.timedelta(days=i)).replace(hour=20, minute=0, second=0, microsecond=0)
        date_string = next_date.strftime('%#m/%d/%Y %#I:%M%p')

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
        
        T += 0.5

    save_options(options)

class OptionsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.options_task = tasks.loop(minutes=UPDATE_INTERVAL_MINUTES)(self.update_options)
        self.options_task.start()

    async def update_options(self):
        stock_data = load_stocks()
        options_data = load_options()
        right_now = datetime.datetime.today().strftime('%#m/%d/%Y %#I:%M%p')
        check_date = datetime.datetime.today().replace(hour=20, minute=0).strftime('%#m/%d/%Y %#I:%M%p')
        right_now_dt = datetime.datetime.strptime(right_now, '%m/%d/%Y %I:%M%p')
        check_date_dt = datetime.datetime.strptime(check_date, '%m/%d/%Y %I:%M%p')
        
        for stock in stock_data:
            if not stock.endswith("COIN"):
                # Check if the stock exists in the options_data and the structure matches the desired format
                if stock in options_data and isinstance(options_data[stock], dict):
                    if "price" in options_data[stock] and isinstance(options_data[stock]["expiration"], dict):
                        expiration_dates = options_data[stock]["expiration"]
                
                        # Check if expiration has valid dates with the required structure and empty "call" and "put" dictionaries
                        valid_expiration = all(
                            isinstance(expiration_dates[date], dict) and 
                            "call" in expiration_dates[date] and isinstance(expiration_dates[date]["call"], dict) and not expiration_dates[date]["call"] and 
                            "put" in expiration_dates[date] and isinstance(expiration_dates[date]["put"], dict) and not expiration_dates[date]["put"]
                            for date in expiration_dates
                        )

                        # If all conditions are met, execute create_options
                        if valid_expiration:
                            create_options(stock)
                            options_data = load_options()


        for stock in stock_data:
            if stock not in options_data and not stock.endswith("COIN"):
                create_options(stock)
                options_data = load_options()
            if not stock.endswith("COIN"):
                options_data[stock]["price"] = stock_data[stock]

        data = load_data()
        user_id_list = list(data.keys())

        if right_now_dt > check_date_dt:
            for stock in options_data:
                options_data[stock]["expiration"].pop(check_date, None)
                S = options_data[stock].get("price")
                r = 0.04
                sigma = 0.2
                T = 0.5
                next_date = (check_date_dt + datetime.timedelta(days=4)).replace(hour=20, minute=0)
                date_string = next_date.strftime('%#m/%d/%Y %#I:%M%p')
                if date_string not in options_data[stock]["expiration"]:
                    options_data[stock]["expiration"][date_string] = {"call": {}, "put": {}}

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
                    options_data[stock]["expiration"][date_string]["call"][strike_price] = {
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
                    options_data[stock]["expiration"][date_string]["put"][strike_price] = {
                        "put_price": float("{:.2f}".format(put_price)),
                        "put_delta": float("{:.2f}".format(put_delta)),
                        "put_gamma": float("{:.2f}".format(put_gamma)),
                        "put_theta": float("{:.2f}".format(put_theta))
                    }

                    K -= (K_original * 0.1)
                
                T += 0.5
            
            for i in range(len(user_id_list)):
                user_record = data.get(user_id_list[i], {"options": []})
                for entry in user_record.get("options", []):
                    if entry["expiration"] == check_date:
                        user_record["options"].remove(entry)
                        user = await self.bot.fetch_user(user_id_list[i])
                        await user.send(f"Your {entry['stock']} option(s) with expiration {check_date} has been removed.")
                        data[user_id_list[i]] = user_record

        else:
            for stock in options_data:
                dates = list(options_data[stock]["expiration"].keys())
                T = 0.5
                for i in range(len(dates)):
                    # Options variables
                    today = datetime.datetime.today()
                    S = float(options_data[stock].get("price"))
                    r = 0.04
                    sigma = 0.2

                    next_date = (today + datetime.timedelta(days=i)).replace(hour=20, minute=0)
                    date_string = next_date.strftime('%#m/%d/%Y %#I:%M%p')

                    # Update calls for this expiration date
                    strike_price = list(options_data[stock]["expiration"][date_string]["call"].keys())
                    for x in range(5):
                        K = float(strike_price[x])
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
                        if "{:.2f}".format(K) not in options_data[stock]["expiration"][date_string]["call"]:
                            options_data[stock]["expiration"][date_string]["call"]["{:.2f}".format(K)] = {}
                        options_data[stock]["expiration"][date_string]["call"]["{:.2f}".format(K)]["call_price"] = float("{:.2f}".format(call_price))
                        options_data[stock]["expiration"][date_string]["call"]["{:.2f}".format(K)]["call_delta"] = float("{:.2f}".format(call_delta))
                        options_data[stock]["expiration"][date_string]["call"]["{:.2f}".format(K)]["call_gamma"] = float("{:.2f}".format(call_gamma))
                        options_data[stock]["expiration"][date_string]["call"]["{:.2f}".format(K)]["call_theta"] = float("{:.2f}".format(call_theta))

                    # Update puts for this expiration date
                    strike_price = list(options_data[stock]["expiration"][date_string]["put"].keys())
                    for y in range(5):
                        K = float(strike_price[y])
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
                        if "{:.2f}".format(K) not in options_data[stock]["expiration"][date_string]["put"]:
                            options_data[stock]["expiration"][date_string]["put"]["{:.2f}".format(K)] = {}
                        options_data[stock]["expiration"][date_string]["put"]["{:.2f}".format(K)]["put_price"] = float("{:.2f}".format(put_price))
                        options_data[stock]["expiration"][date_string]["put"]["{:.2f}".format(K)]["put_delta"] = float("{:.2f}".format(put_delta))
                        options_data[stock]["expiration"][date_string]["put"]["{:.2f}".format(K)]["put_gamma"] = float("{:.2f}".format(put_gamma))
                        options_data[stock]["expiration"][date_string]["put"]["{:.2f}".format(K)]["put_theta"] = float("{:.2f}".format(put_theta))
                        
                    T += 0.5

        save_options(options_data)

        for i in range(len(user_id_list)):
            user_record = data.get(user_id_list[i], {"options": []})
            if not user_record.get("options"):
                continue
            for stock in options_data:
                for expiration_date in options_data[stock]["expiration"]:

                    call_data = options_data[stock]["expiration"][expiration_date]["call"]
                    for strike_price in call_data:
                        for entry in user_record.get("options", []):
                            if (entry["stock"] == stock and
                                entry["strategy"] == "call" and
                                entry["expiration"] == expiration_date and 
                                entry["strike_price"] == float(strike_price)):
                                entry["call_price"] = call_data[strike_price].get("call_price")

                    put_data = options_data[stock]["expiration"][expiration_date]["put"]
                    for strike_price in put_data:
                        for entry in user_record.get("options", []):
                            if (entry["stock"] == stock and
                                entry["strategy"] == "put" and
                                entry["expiration"] == expiration_date and 
                                entry["strike_price"] == float(strike_price)):
                                entry["put_price"] = put_data[strike_price].get("put_price")
            data[user_id_list[i]] = user_record    

        save_data(data)

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="options", description="Shows what options the user currently owns.")
    @app_commands.describe(user="The user to check options statistics for (defaults to yourself if not provided).")
    async def user_options(self, interaction: discord.Interaction, user: Optional[discord.Member] = None):
        target = user or interaction.user
        data = load_data()
        user_id = str(target.id)
        user_record = data.get(user_id, {"options": []})
        user_options = user_record.get("options", [])
        
        if not user_options:
            await interaction.response.send_message("That user does not own any options.", ephemeral=True)
            return
        else:
            embed = discord.Embed(
                title=f"{target}'s Options",
                color=discord.Color.purple()
            )
            for option in user_options:
                stock = option["stock"]
                strike = option["strike_price"]
                strategy = option["strategy"]
                strategy_price = option[f"{strategy}_price"]
                expiration = option["expiration"]
                quantity = option["quantity"]
                strategy_upper = strategy.upper()
                strategy_capital = strategy.capitalize()
                embed.add_field(
                    name=f"{stock} {strike} {strategy_upper}",
                    value=f"{strategy_capital} Price: {strategy_price}\n"
                          f"Expiration: {expiration}\n"
                          f"Quantity: {quantity}",
                    inline=False
                )
            await interaction.response.send_message(embed=embed)

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="optionview", description="Browse options for the Beaned stock market (cryptocoins not included).")
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
            await interaction.response.send_message("You may only view options from 0 to 3 DTE", ephemeral=True)
            return
        if not strategy in ('call', 'put'):
            await interaction.response.send_message(f"Please enter a valid strategy ('call or put').", ephemeral=True)
            return
        stocks = load_stocks()
        if stock not in stocks or stock.endswith("COIN"):
            await interaction.response.send_message(f"Please enter a valid stock symbol (check /stocks).", ephemeral=True)
            return
        
        options = load_options()

        if options[stock]["expiration"]:
            dates = list(options[stock]["expiration"].keys())
            target_date = dates[DTE]
        else:
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
            num_options = int(quantity)
        except ValueError:
            await interaction.response.send_message("Please enter an integer.", ephemeral=True)
            return
        try:
            strike_price = float(strike)
        except ValueError:
            await interaction.response.send_message("Please enter a valid strike price.", ephemeral=True)
            return
        if DTE > 3 or DTE < 0:
            await interaction.response.send_message("You may only buy options from 0 to 3 DTE", ephemeral=True)
            return
        if not strategy in ('call', 'put'):
            await interaction.response.send_message(f"Please enter a valid strategy ('call or put').", ephemeral=True)
            return
        if num_options < 1:
            await interaction.response.send_message(f"Enter a quantity greater than 0.", ephemeral=True)
            return
        stocks = load_stocks()
        if stock not in stocks or stock.endswith("COIN"):
            await interaction.response.send_message(f"Please enter a valid stock symbol (check /stocks).", ephemeral=True)
            return
        
        options = load_options()

        if options[stock]["expiration"]:
            dates = list(options[stock]["expiration"].keys())
            target_date = dates[DTE]
        else:
            create_options(stock)
            options = load_options()
            dates = list(options[stock]["expiration"].keys())
            target_date = dates[DTE]

        if strike not in options[stock]["expiration"][target_date][strategy]:
            await interaction.response.send_message("Please enter a valid strike price.", ephemeral=True)
            return
        
        data = load_data()
        user_id = str(interaction.user.id)
        user_record = data.get(user_id, {"balance": 0, "options": []})

        target_option = options[stock]["expiration"][target_date][strategy][strike]
        total_owed = target_option.get(f"{strategy}_price") * 100 * num_options

        if user_record.get("balance") < total_owed:
            await interaction.response.send_message(f"You can not afford {num_options} option(s) for {strike_price} x 100 (${total_owed:,} Beaned Bucks).", ephemeral=True)
            return
        
        user_record["balance"] -= total_owed
        
        if "options" not in user_record:
            user_record["options"] = []
        
        exists = False
        for entry in user_record["options"]:
            if (entry["stock"] == stock and 
                entry["strategy"] == strategy and 
                entry["expiration"] == target_date and 
                entry[f"{strategy}_price"] == target_option.get(f"{strategy}_price") and 
                entry["strike_price"] == strike_price):
                    entry["quantity"] += num_options
                    exists = True
                    break

        if not exists:
            user_record["options"].append({
                        "stock": stock,
                        "strategy": strategy,
                        "expiration": target_date,
                        f"{strategy}_price": target_option.get(f"{strategy}_price"),
                        "strike_price": strike_price,
                        "quantity": num_options
                    })

        data[user_id] = user_record
        save_data(data)

        await interaction.response.send_message(f"Successfully purchased {num_options} option(s) for ${total_owed:,} Beaned Bucks.", ephemeral=True)

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="optionsell", description="Sell options for the Beaned stock market (cryptocoins not included).")
    @app_commands.describe(stock="Stock symbol (e.g. ACME)", strategy="Enter the strategy you want to view ('call' or 'put')",
                           expiry="How many days to expiration (0-3)", strike="Enter the strike price of the option you'd like to buy",
                           quantity="Number of options you'd like to buy.")
    async def option_sell(self, interaction: discord.Interaction, stock: str, strategy: str, expiry: str, strike: str, quantity: str):
        stock = stock.upper()
        try:
            DTE = int(expiry)
            num_options = int(quantity)
        except ValueError:
            await interaction.response.send_message("Please enter an integer.", ephemeral=True)
            return
        try:
            strike_price = float(strike)
        except ValueError:
            await interaction.response.send_message("Please enter a valid strike price.", ephemeral=True)
            return
        if DTE > 3 or DTE < 0:
            await interaction.response.send_message("You may only sell options from 0 to 3 DTE", ephemeral=True)
            return
        if not strategy in ('call', 'put'):
            await interaction.response.send_message(f"Please enter a valid strategy ('call or put').", ephemeral=True)
            return
        if num_options < 1:
            await interaction.response.send_message(f"Enter a quantity greater than 0.", ephemeral=True)
            return
        stocks = load_stocks()
        if stock not in stocks or stock.endswith("COIN"):
            await interaction.response.send_message(f"Please enter a valid stock symbol (check /stocks).", ephemeral=True)
            return
        
        options = load_options()
        
        if options[stock]["expiration"]:
            dates = list(options[stock]["expiration"].keys())
            target_date = dates[DTE]
        else:
            create_options(stock)
            options = load_options()
            dates = list(options[stock]["expiration"].keys())
            target_date = dates[DTE]
        
        data = load_data()
        user_id = str(interaction.user.id)
        user_record = data.get(user_id, {"balance": 0, "options": []})
        user_options = user_record["options"]
        
        if not user_options:
            await interaction.response.send_message(f"You do not own any options to sell.", ephemeral=True)
            return
        exists = False
        for entry in user_options:
            if (entry["stock"] == stock and 
                entry["strategy"] == strategy and 
                entry["expiration"] == target_date and 
                entry["call_price"] == entry.get(f"{strategy}_price") and 
                entry["strike_price"] == strike_price and
                entry["quantity"] >= num_options):
                    target_option = entry
                    exists = True
                    break
        if not exists:
            await interaction.response.send_message(f"You do not own any of those options.", ephemeral=True)
            return
        
        total_owed = target_option.get(f"{strategy}_price") * 100 * num_options
        user_record["balance"] += total_owed

        target_option["quantity"] -= num_options
        if target_option.get("quantity", 0) <= 0:
            user_options.remove(target_option)

        data[user_id] = user_record
        save_data(data)

        await interaction.response.send_message(f"Successfully sold {num_options} option(s) for ${total_owed:,} Beaned Bucks.", ephemeral=True)
        
async def setup(bot: commands.Bot):
    print("Loading OptionsCog...")
    await bot.add_cog(OptionsCog(bot))