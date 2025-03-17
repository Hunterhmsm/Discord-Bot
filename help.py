#includes /help so i can better keep track of it

import discord
from discord import app_commands
from discord.ext import commands, tasks
from globals import TOKEN, GUILD_ID, TARGET_MEMBER_ID, TARGET_USER_ID, DATA_FILE, ALLOWED_ROLES, STOCK_FILE, STOCK_HISTORY_FILE, UPDATE_INTERVAL_MINUTES, LOTTERY_FILE, AFK_CHANNEL_ID

class HelpCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="help", description="Displays a list of available commands and their descriptions.")
    async def help_command(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="Beaned Bot Help",
            color=discord.Color.blue(),
            description="Below are the commands available, grouped by category."
        )
        
        general = (
            "**/balance [user]** - Check your Beaned Bucks balance (defaults to your own).\n"
            "**/leaderboard** - Check the networth, time, timealone, timeafk leaderboards.\n" 
            "**/daily** - Get your daily beaned bucks.\n"
            "**/dailyboost** - Get your daily beaned bucks. (boosters only)\n"
            "**/joinnotification** - Join the notif notifications channel.\n"
            "**/leavenotification** - Leave the notif notifications channel.\n"
            "**/work** - Work for Beaned Bucks every 10 minutes,\n"
            "**/crime** - Commit crime for Beaned Bucks ever 15 minutes."
        )
        
        gambling = (
            "**/blackjack [bet]** - Play a round of Blackjack using your Beaned Bucks.\n"
            "**/roulette [amount] [bet]** - Play a game of roulette with your bet.\n"
            "**/wheel [target]** - Timeout a user randomly if you have enough Beaned Bucks or the allowed role."
        )
        
        stocks = (
            "**/portfolio** - Check your stock portfolio and profit (invested vs. earned).\n"
            "**/stock [stock name]** - View current stock prices or a specific stock's history.\n"
            "**/buystock [stock] [price]** - Buy stock at your specified price.\n"
            "**/sellstock [stock] [price]** - Sell stock at your specified price."
        )
        
        lottery = (
            "**/lotteryticket [numbers]** - Buy a lottery ticket for 5,000 Beaned Bucks; choose 5 unique numbers (1-60).\n"
            "**/lotterydraw** - Force a lottery draw (restricted to lottery admins).\n"
            "**/lotterytotal** - View the current lottery jackpot."
        )

        crypto = (
            "**/crypto [user]** - Shows how many RTX 5090s owned and what is currently being mined.\n"
            "**/cryptobuy [quantity]** - Buy RTX 5090s using your Beaned Bucks. Each card is $10,000\n"
            "**/cryptosell [quantity]** - Sell your RTX 5090s for $5,000 Beaned Bucks. Don't complain, they've been used to mine crypto.\n"
            "**/mine [crypto]** - Decide what crypto you'd like to mine. You will gain 1 coin/card every 5 minutes.\n"
        )
        industry = (
            "**/industry tradecontract** - Set up a trading contract to send a fixed amount of a resource every hour for a specified duration to another user.\n"
            "**/industry contractstatus** - View your active trading contracts.\n"
            "**/industry buy** - Buy raw resources from the store.\n"
            "**/industry sell** - Sell raw resources to the store.\n"
            "**/industry build** - Build a facility from the industries list.\n"
            "**/industry status** - View your built facilities and resource inventory (optionally target another user).\n"
            "**/industry invtransfer** - Transfer a resource from your inventory to another user.\n"
            "**/industry industries** - List all available industries and their details.\n"
            "**/industry store** - Show the current store items and their details.\n"
            "**/industry sellindustry** - Sell one of your built industry facilities at half its base value."
        )
        options = (
            "**/options [user]** - Shows what options the user currently owns.\n"
            "**/optionsview [stock] [strategy] [expiry]** - Browse options for the Beaned stock market (cryptocoins not included).\n"
            "**/optionbuy [stock] [strategy] [expiry] [strike] [quantity]** - Buy options for the Beaned stock market.\n"
            "**/optionsell [stock] [strategy] [expiry] [strike] [quantity]** - Sell options for the Beaned stock market.\n"
        )

        embed.add_field(name="General", value=general, inline=False)
        embed.add_field(name="Gambling", value=gambling, inline=False)
        embed.add_field(name="Stocks", value=stocks, inline=False)
        embed.add_field(name="Lottery", value=lottery, inline=False)
        embed.add_field(name="Crypto", value=crypto, inline=False)
        embed.add_field(name="Industry", value=industry, inline=False)
        embed.add_field(name="Options", value=options, inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    print("Loading HelpCog...")
    await bot.add_cog(HelpCog(bot))