import discord
from discord import app_commands
from discord.ext import commands, tasks
import json
import random
import datetime
from globals import STOCK_FILE, STOCK_HISTORY_FILE, UPDATE_INTERVAL_MINUTES, GUILD_ID
from utils import load_data, save_data
from typing import Optional
import pytz

#helper functions for stocks:
def load_stocks():
    try:
        with open(STOCK_FILE, "r") as f:
            data = json.load(f)
            if not isinstance(data, dict):
                raise ValueError("Stocks data is not a dictionary.")
            return data
    except (FileNotFoundError, json.JSONDecodeError, ValueError):
        default_data = {"INK": 300.0, "BEANEDCOIN": 10.0}
        save_stocks(default_data)
        return default_data

def save_stocks(data):
    with open(STOCK_FILE, "w") as f:
        json.dump(data, f, indent=4)

def load_stock_history():
    try:
        with open(STOCK_HISTORY_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_stock_history(history):
    with open(STOCK_HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=4)

def choose_new_market_event():
    events = [
        ("none", 0.96),
        ("rally", 0.02),
        ("crash", 0.02)
    ]
    total_weight = sum(weight for event, weight in events)
    r = random.random() * total_weight
    cumulative = 0
    for event, weight in events:
        cumulative += weight
        if r < cumulative:
            if event == "none":
                return None
            else:
                duration = random.randint(1, 3)
                return {"event": event, "duration": duration}
    return None
def update_stock_prices(current_market_event):
    data = load_stocks()
    history = load_stock_history()
    now_iso = datetime.datetime.now().isoformat()
    changes = {}

    if current_market_event is None:
        current_market_event = choose_new_market_event()
        if current_market_event:
            print(f"[Market Event] New event started: {current_market_event}")
        else:
            print("[Market Event] No event this update.")

    event_type = current_market_event["event"] if current_market_event else None

    for stock, price in data.items():
        old_price = price
        #check if the stock symbol contains "COIN"
        is_coin = "COIN" in stock.upper()

        #define the ranges based on whether it's a coin stock or not.
        if is_coin:
            #for coin stocks:
            if event_type == "rally":
                if random.random() < 0.70:
                    change_percent = random.uniform(0.10, 3.00)  #rally upward: 10% to %300
                    new_price = price * (1 + change_percent)
                else:
                    change_percent = random.uniform(0.005, 0.150)  #normal fluctuation: 0.5% to 150%
                    if random.random() < 0.5:
                        change_percent = random.uniform(0.005, 0.90)  #normal fluctuation: 0.5% to 90%
                        change_percent = -change_percent
                    new_price = price * (1 + change_percent)
            elif event_type == "crash":
                if random.random() < 0.70:
                    change_percent = random.uniform(0.10, 0.90)  #crash downward: 10% to 90%
                    new_price = price * (1 - change_percent)
                else:
                    change_percent = random.uniform(0.005, 0.90)
                    if random.random() < 0.5:
                        change_percent = -change_percent
                    new_price = price * (1 + change_percent)
            else:
                #normal update for coin stocks 0.5% to 50% fluctuation.
                change_percent = random.uniform(0.005, 0.50)
                if random.random() < 0.5:
                    change_percent = -change_percent
                new_price = price * (1 + change_percent)
        else:
            #for non-coin stocks, use the original percentages.
            if event_type == "rally":
                if random.random() < 0.70:
                    change_percent = random.uniform(0.10, 0.20)
                    new_price = price * (1 + change_percent)
                else:
                    change_percent = random.uniform(0.005, 0.05)
                    if random.random() < 0.5:
                        change_percent = -change_percent
                    new_price = price * (1 + change_percent)
            elif event_type == "crash":
                if random.random() < 0.70:
                    change_percent = random.uniform(0.10, 0.20)
                    new_price = price * (1 - change_percent)
                else:
                    change_percent = random.uniform(0.005, 0.05)
                    if random.random() < 0.5:
                        change_percent = -change_percent
                    new_price = price * (1 + change_percent)
            else:
                if random.random() < 0.01:
                    jump_factor = random.uniform(0.5, 0.95)
                    if random.random() < 0.5:
                        new_price = price * (1 + jump_factor)
                    else:
                        new_price = price * (1 - jump_factor)
                else:
                    change_percent = random.uniform(0.005, 0.05)
                    if random.random() < 0.5:
                        change_percent = -change_percent
                    new_price = price * (1 + change_percent)
                    
        data[stock] = new_price
        absolute_change = round(new_price - old_price, 2)
        percent_change = round(((new_price - old_price) / old_price) * 100, 2) if old_price != 0 else 0
        changes[stock] = {"old": old_price, "new": new_price, "abs": absolute_change, "perc": percent_change}
        if stock not in history:
            history[stock] = []
        history[stock].append({"timestamp": now_iso, "price": new_price})

    if current_market_event:
        current_market_event["duration"] -= 1
        if current_market_event["duration"] <= 0:
            print(f"[Market Event] Event ended: {current_market_event}")
            current_market_event = None

    save_stocks(data)
    save_stock_history(history)
    print("Stock prices updated:", data)
    return changes, current_market_event


class StocksCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.current_market_event = None
        self.market_task = tasks.loop(minutes=UPDATE_INTERVAL_MINUTES)(self.market_update_task)
        self.market_task.start()

    async def market_update_task(self):
        changes, self.current_market_event = update_stock_prices(self.current_market_event)
        channel = discord.utils.get(self.bot.get_all_channels(), name="bot-output")
        if channel:
            embed = discord.Embed(
                title="Stock Market Update",
                color=discord.Color.blue(),
                timestamp=datetime.datetime.now(pytz.timezone('America/New_York')) + datetime.timedelta(minutes=20)
            )
            embed.set_footer(text="Prices update every 20 minutes")
            for stock, change in changes.items():
                sign = "+" if change["abs"] >= 0 else ""
                embed.add_field(
                    name=stock,
                    value=f"**Old:** {change['old']}\n**New:** {change['new']}\n**Change:** {sign}{change['abs']} ({sign}{change['perc']}%)",
                    inline=True
                )
            try:
                await channel.send(embed=embed)
            except Exception as e:
                print(f"Failed to send stock update embed: {e}")

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="stockbuy", description="Buy stock using your Beaned Bucks.")
    @app_commands.describe(stock="Stock symbol (e.g. ACME)", amount="Amount to invest (or 'all')")
    async def stockbuy(self, interaction: discord.Interaction, stock: str, amount: str):
        stocks_data = load_stocks()
        stock = stock.upper()
        if stock not in stocks_data:
            await interaction.response.send_message("Invalid stock symbol.", ephemeral=True)
            return

        price = stocks_data[stock]
        data = load_data()
        user_id = str(interaction.user.id)
        user_record = data.get(user_id, {"balance": 0, "portfolio": {}, "total_spent": 0, "total_earned": 0})
        current_balance = float(user_record.get("balance", 0))

        #determine investment amount.
        if amount.lower() == "all":
            invest_amount = current_balance
        else:
            try:
                invest_amount = float(amount)
            except ValueError:
                await interaction.response.send_message("Invalid investment amount.", ephemeral=True)
                return

        if invest_amount <= 0:
            await interaction.response.send_message("Investment amount must be greater than 0.", ephemeral=True)
            return
        if invest_amount > current_balance:
            await interaction.response.send_message(f"You do not have enough Beaned Bucks to invest {invest_amount}.", ephemeral=True)
            return

        shares = invest_amount / price
        user_record["balance"] = current_balance - invest_amount
        portfolio = user_record.get("portfolio", {})
        portfolio[stock] = portfolio.get(stock, 0) + shares
        user_record["portfolio"] = portfolio
        user_record["total_spent"] = user_record.get("total_spent", 0) + invest_amount

        data[user_id] = user_record
        save_data(data)

        await interaction.response.send_message(
            f"Successfully invested {invest_amount} Beaned Bucks in {stock} at {price} per share.\n"
            f"You now own {portfolio[stock]} shares of {stock}.\n"
            f"Your new balance is {user_record['balance']} Beaned Bucks."
        )

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="portfolio", description="View your stock portfolio.")
    @app_commands.describe(user="Optional: The user whose portfolio you want to see (defaults to yourself)")
    async def portfolio(self, interaction: discord.Interaction, user: discord.Member = None):
        target = user or interaction.user
        data = load_data()
        user_id = str(target.id)
        user_record = data.get(user_id, {"balance": 0, "portfolio": {}, "total_spent": 0, "total_earned": 0})
        portfolio_holdings = user_record.get("portfolio", {})

        stock_prices = load_stocks()

        embed = discord.Embed(
            title=f"{target.display_name}'s Portfolio",
            color=discord.Color.green()
        )
        embed.set_footer(text=f"Balance: {user_record.get('balance', 0)} Beaned Bucks")
        
        if not portfolio_holdings:
            embed.description = "No stock holdings found."
        else:
            total_value = 0.0
            for symbol, shares in portfolio_holdings.items():
                price = stock_prices.get(symbol, 0)
                value = price * shares
                total_value += value
                embed.add_field(
                    name=symbol,
                    value=f"Shares: {shares}\nPrice: {price} Beaned Bucks\nValue: {round(value, 2)} Beaned Bucks",
                    inline=True
                )
            embed.add_field(
                name="Total Holdings Value",
                value=f"{round(total_value, 2)} Beaned Bucks",
                inline=False
            )
        
        #add profit tracking
        total_spent = user_record.get("total_spent", 0)
        total_earned = user_record.get("total_earned", 0)
        net_profit = total_earned - total_spent
        embed.add_field(name="Total Invested", value=f"{total_spent} Beaned Bucks", inline=True)
        embed.add_field(name="Total Earned", value=f"{total_earned} Beaned Bucks", inline=True)
        embed.add_field(name="Net Profit", value=f"{net_profit} Beaned Bucks", inline=True)
        
        await interaction.response.send_message(embed=embed)

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="stocksell", description="Sell a specific stock in shares.")
    @app_commands.describe(
    stock="The stock symbol you want to sell (e.g. MEN)",
    quantity="The number of shares you want to sell (can be fractional, e.g. 0.68, or type 'all' to sell everything)"
)
    async def sell(self, interaction: discord.Interaction, stock: str, quantity: str):
        stock = stock.upper()

        #load current stock data.
        stocks_data = load_stocks()
        if stock not in stocks_data:
            await interaction.response.send_message("Invalid stock symbol.", ephemeral=True)
            return

        price = stocks_data[stock]

        #load user data.
        data = load_data()
        user_id = str(interaction.user.id)
        user_record = data.get(user_id, {"balance": 0, "portfolio": {}, "total_spent": 0, "total_earned": 0})
        portfolio = user_record.get("portfolio", {})

        if stock not in portfolio:
            await interaction.response.send_message("You do not own any shares of that stock.", ephemeral=True)
            return

        #determine the quantity to sell.
        try:
            if quantity.lower() == "all":
                sell_quantity = portfolio[stock]
            else:
                sell_quantity = float(quantity)
        except Exception as e:
            await interaction.response.send_message("Invalid quantity format. Please provide a number or 'all'.", ephemeral=True)
            return

        if sell_quantity <= 0:
            await interaction.response.send_message("Quantity must be greater than zero.", ephemeral=True)
            return

        if portfolio[stock] < sell_quantity:
            await interaction.response.send_message("You do not own enough shares of that stock to sell.", ephemeral=True)
            return

        sale_value = round(price * sell_quantity, 2)

        #update portfolio.
        portfolio[stock] -= sell_quantity
        if portfolio[stock] <= 0:
            del portfolio[stock]
        user_record["portfolio"] = portfolio

        #update user's balance.
        user_record["balance"] += sale_value

        #update total earned.
        user_record["total_earned"] = user_record.get("total_earned", 0) + sale_value

        data[user_id] = user_record
        save_data(data)

        await interaction.response.send_message(
            f"Successfully sold {sell_quantity} shares of {stock} at {price} Beaned Bucks each for a total of {sale_value} Beaned Bucks.\n"
            f"Your new balance is {user_record['balance']} Beaned Bucks."
        )


    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="stocks", description="View current stock prices, or view a specific stock's price history.")
    @app_commands.describe(stock="Optional: The stock symbol to view history for")
    async def stocks(self, interaction: discord.Interaction, stock: Optional[str] = None):
        current_prices = load_stocks()
        

        if stock is None:
            embed = discord.Embed(title="Current Stock Prices", color=discord.Color.blue())
            for sym, price in current_prices.items():
                embed.add_field(name=sym, value=f"{price} Beaned Bucks", inline=False)
            await interaction.response.send_message(embed=embed)
        else:
            stock = stock.upper()

            if stock not in current_prices:
                await interaction.response.send_message(f"Stock symbol '{stock}' not found.", ephemeral=True)
                return


            price = current_prices[stock]
            embed = discord.Embed(title=f"{stock} Stock Information", color=discord.Color.green())
            embed.add_field(name="Current Price", value=f"{price} Beaned Bucks", inline=False)
            

            history = load_stock_history()
            if stock in history and history[stock]:
                history_text = "**Price History (last 10 updates):**\n"  
                for record in history[stock][-10:]:
                    timestamp = record["timestamp"]
                    hist_price = record["price"]
                    history_text += f"{timestamp}: {hist_price}\n"
                embed.add_field(name="History", value=history_text, inline=False)
            else:
                embed.add_field(name="History", value="No history available.", inline=False)
            
            await interaction.response.send_message(embed=embed)


    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="stockgive", description="Give a stock to another user.")
    @app_commands.describe(
    stock="The stock symbol you want to give (e.g. MEN)",
    quantity="The number of shares you want to give (can be fractional, e.g. 0.68, or type 'all' to give everything)",
    user="The user you want to  send the stocks to."
    )
    async def stockgive(self, interaction: discord.Interaction, stock: str, quantity: str,  user: discord.Member):
        stock = stock.upper()
        #load current stock data.
        stocks_data = load_stocks()
        if stock not in stocks_data:
            await interaction.response.send_message("Invalid stock symbol.", ephemeral=True)
            return
        
        #load user data
        data = load_data()
        user_id = str(interaction.user.id)
        user_record = data.get(user_id, {"balance": 0, "portfolio": {}, "total_spent": 0, "total_earned": 0})
        portfolio = user_record.get("portfolio", {})
        #load target data
        target_id = str(user.id)
        target_record = data.get(target_id, {"balance": 0, "portfolio": {}, "total_spent": 0, "total_earned": 0})
        target_portfolio = target_record.get("portfolio", {})

        if stock not in portfolio:
            await interaction.response.send_message("You do not own any shares of that stock.", ephemeral=True)
            return
        #determine the quantity to give.
        try:
            if quantity.lower() == "all":
                give_quantity = portfolio[stock]
            else:
                give_quantity = float(quantity)
        except Exception as e:
            await interaction.response.send_message("Invalid quantity format. Please provide a number or 'all'.", ephemeral=True)
            return

        if give_quantity <= 0:
            await interaction.response.send_message("Quantity must be greater than zero.", ephemeral=True)
            return

        if portfolio[stock] < give_quantity:
            await interaction.response.send_message("You do not own enough shares of that stock to sell.", ephemeral=True)
            return

        #update portfolio.
        portfolio[stock] -= give_quantity
        if portfolio[stock] <= 0:
            del portfolio[stock]
        user_record["portfolio"] = portfolio
        data[user_id] = user_record

        target_portfolio[stock] = target_portfolio.get(stock, 0) + give_quantity
        target_record["portfolio"] = target_portfolio
        data[target_id] = target_record


        save_data(data)

        await interaction.response.send_message(
            f"Successfully gave {user.mention} {give_quantity} shares of {stock}.")

async def setup(bot: commands.Bot):
    print("Loading StocksCog...")
    await bot.add_cog(StocksCog(bot))
