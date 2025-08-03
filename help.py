#includes /help so i can better keep track of it

import discord
from discord import app_commands
from discord.ext import commands, tasks
from globals import TOKEN, GUILD_ID, TARGET_USER_ID, DATA_FILE, ALLOWED_ROLES, STOCK_FILE, STOCK_HISTORY_FILE, UPDATE_INTERVAL_MINUTES, LOTTERY_FILE, AFK_CHANNEL_ID

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
            "**/leaderboard [category]** - Check the networth, prestige, time, timealone, or timeafk leaderboards.\n" 
            "**/daily** - Get your daily beaned bucks.\n"
            "**/dailyboost** - Get your daily beaned bucks. (boosters only)\n"
            "**/work** - Work for Beaned Bucks every 10 minutes.\n"
            "**/crime** - Commit crime for Beaned Bucks every 15 minutes.\n"
            "**/exit** - Shut down the bot and update VC trackers. (Restricted to users with 'him' role.)"
        )
        
        roles = (
            "**/create_role [rolename]** - Create a new role that users can join (Restricted command).\n"
            "**/role_join [role]** - Join a role that was created with /create_role."
        )
        
        gambling = (
            "**/blackjack [bet]** - Play a round of Blackjack using your Beaned Bucks.\n"
            "**/roulette [amount] [bet]** - Play a game of roulette with your bet.\n"
            "**/wheel [target]** - Timeout a user randomly if you have enough Beaned Bucks or the allowed role."
        )
        
        stocks = (
            "**/portfolio [user]** - Check your stock portfolio and profit (invested vs. earned).\n"
            "**/stocks [stock]** - View current stock prices or a specific stock's history.\n"
            "**/stockbuy [stock] [amount]** - Buy stock using your Beaned Bucks.\n"
            "**/stocksell [stock] [quantity]** - Sell a specific stock in shares.\n"
            "**/stockgive [stock] [quantity] [user]** - Give a stock to another user."
        )
        
        lottery = (
            "**/lotteryticket [numbers]** - Buy a lottery ticket for 5,000 Beaned Bucks; choose 5 unique numbers (1-60).\n"
            "**/lotterydraw** - Force a lottery draw (restricted to lottery admins).\n"
            "**/lotterytotal** - View the current lottery jackpot."
        )

        crypto = (
            "**/crypto [user]** - Shows your mining rig status and current mining configuration.\n"
            "**/cryptobuy [quantity]** - Buy RTX 5090s using your Beaned Bucks. Each card is $10,000.\n"
            "**/cryptosell [quantity]** - Sell your RTX 5090s for $5,000 Beaned Bucks.\n"
            "**/mineconfig [coin] [cards]** - Configure how many cards mine each cryptocurrency.\n"
            "**/minestart [coin]** - Quickly start mining with all cards on one cryptocurrency.\n"
            "**/minestop** - Stop all mining operations.\n"
            "**/mine [crypto]** - Legacy command - use /minestart instead."
        )
        
        industry = (
            "**/industry_tradecontract [resource] [quantity] [hours] [target]** - Set up a trading contract with another user.\n"
            "**/industry_contractstatus** - View your active trading contracts.\n"
            "**/industry_buy [resource] [quantity]** - Buy raw resources from the store.\n"
            "**/industry_sell [resource] [quantity]** - Sell raw resources to the store.\n"
            "**/industry_build [facility]** - Build a facility from the industries list.\n"
            "**/industry_status [user]** - View built facilities and resource inventory.\n"
            "**/industry_invtransfer [resource] [quantity] [target]** - Transfer a resource to another user.\n"
            "**/industry_industries** - Show the list of facilities and their details.\n"
            "**/industry_store** - Show the current store items and their details.\n"
            "**/industry_sellindustry [industry] [quantity]** - Sell built industry facilities at half value."
        )
        
        options = (
            "**/options [user]** - Shows what options the user currently owns.\n"
            "**/optionsview [stock] [strategy] [expiry]** - Browse options for the Beaned stock market (cryptocoins not included).\n"
            "**/optionbuy [stock] [strategy] [expiry] [strike] [quantity]** - Buy options for the Beaned stock market.\n"
            "**/optionsell [stock] [strategy] [expiry] [strike] [quantity]** - Sell options for the Beaned stock market."
        )
        
        prestige = (
            "**/prestigeup** - Adds a level of prestige and wipes your account if you meet requirements.\n"
            "**/prestigecheck** - Checks the users prestige level and what they need for the next level.\n"
            "**/prestigedaily** - A daily locked to prestiged users." 
        )

        embed.add_field(name="General", value=general, inline=False)
        embed.add_field(name="Role Management", value=roles, inline=False)
        embed.add_field(name="Gambling", value=gambling, inline=False)
        embed.add_field(name="Stocks", value=stocks, inline=False)
        embed.add_field(name="Lottery", value=lottery, inline=False)
        embed.add_field(name="Crypto Mining", value=crypto, inline=False)
        embed.add_field(name="Industry", value=industry, inline=False)
        embed.add_field(name="Options", value=options, inline=False)
        embed.add_field(name="Prestige", value=prestige, inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    print("Loading HelpCog...")
    await bot.add_cog(HelpCog(bot))