import discord
from discord import app_commands
from discord.ext import commands
import random
import datetime
import asyncio
from utils import load_data, save_data
from globals import GUILD_ID

#constants for cards:
HEARTS   = chr(9829)  # ♥
DIAMONDS = chr(9830)  # ♦
SPADES   = chr(9824)  # ♠
CLUBS    = chr(9827)  # ♣
BACKSIDE = "backside"

#helper functions for Blackjack
def get_deck():
    deck = []
    for suit in (HEARTS, DIAMONDS, SPADES, CLUBS):
        for rank in map(str, range(2, 11)):
            deck.append((rank, suit))
        for rank in ('J', 'Q', 'K', 'A'):
            deck.append((rank, suit))
    random.shuffle(deck)
    return deck

def get_hand_value(cards):
    value = 0
    number_of_aces = 0
    for card in cards:
        rank = card[0]
        if rank == 'A':
            number_of_aces += 1
        elif rank in ('K', 'Q', 'J'):
            value += 10
        else:
            value += int(rank)
    #count aces as 1, then add 10 if it doesn’t bust the hand
    value += number_of_aces
    for _ in range(number_of_aces):
        if value + 10 <= 21:
            value += 10
    return value

def card_to_str(card):
    if card == BACKSIDE:
        return "??"
    return f"{card[0]}{card[1]}"

def hand_to_str(hand):
    return ", ".join(card_to_str(card) for card in hand)

def render_game_state(game, final=False):
    """Return a string representing the current state of the game."""
    if final:
        dealer_display = hand_to_str(game.dealer_hand)
    else:
        #hide the dealer's first card
        dealer_display = "??"
        if len(game.dealer_hand) > 1:
            dealer_display += ", " + ", ".join(card_to_str(card) for card in game.dealer_hand[1:])
    player_display = hand_to_str(game.player_hand)
    text = (f"**Dealer's Hand:** {dealer_display}\n"
            f"**Your Hand:** {player_display} (Value: {get_hand_value(game.player_hand)})\n"
            f"**Bet:** {game.bet} Beaned Bucks")
    return text

def is_blackjack(hand):
    return len(hand) == 2 and get_hand_value(hand) == 21

#game state classes
class BlackjackGame:
    def __init__(self, player: discord.Member, bet: float):
        self.player = player
        self.bet = bet
        self.deck = get_deck()
        self.player_hand = [self.deck.pop(), self.deck.pop()]
        self.dealer_hand = [self.deck.pop(), self.deck.pop()]
        self.finished = False
        self.result = None

class BlackjackView(discord.ui.View):
    def __init__(self, game: BlackjackGame):
        super().__init__(timeout=60)
        self.game = game

    async def end_game(self, interaction: discord.Interaction):
        if self.game.finished:
            return
        self.game.finished = True

        #dealer draws until reaching a hand value of at least 17.
        while get_hand_value(self.game.dealer_hand) < 17:
            self.game.dealer_hand.append(self.game.deck.pop())
            await asyncio.sleep(1)

        player_val = get_hand_value(self.game.player_hand)
        dealer_val = get_hand_value(self.game.dealer_hand)
        if player_val > 21:
            self.game.result = "lose"
        elif dealer_val > 21 or player_val > dealer_val:
            self.game.result = "win"
        elif player_val < dealer_val:
            self.game.result = "lose"
        else:
            self.game.result = "tie"

        for child in self.children:
            child.disabled = True

        outcome_text = ""
        if self.game.result == "win":
            outcome_text = f"You win {self.game.bet} Beaned Bucks!"
        elif self.game.result == "lose":
            outcome_text = f"You lose {self.game.bet} Beaned Bucks!"
        elif self.game.result == "tie":
            outcome_text = "It's a tie! Your bet is returned."

        content = render_game_state(self.game, final=True) + "\n\n" + outcome_text
        try:
            if not interaction.response.is_done():
                await interaction.response.edit_message(content=content, view=self)
            else:
                await interaction.message.edit(content=content, view=self)
        except discord.NotFound:
            print("Message not found when trying to edit.")
        self.stop()

    @discord.ui.button(label="Hit", style=discord.ButtonStyle.primary)
    async def hit(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.game.player:
            await interaction.response.send_message("This is not your game!", ephemeral=True)
            return
        if self.game.finished:
            await interaction.response.defer()
            return

        self.game.player_hand.append(self.game.deck.pop())
        current_value = get_hand_value(self.game.player_hand)
        print(f"[Blackjack] Hit pressed. New hand: {self.game.player_hand} Value: {current_value}")

        if current_value > 21:
            await self.end_game(interaction)
        else:
            content = render_game_state(self.game)
            try:
                if not interaction.response.is_done():
                    await interaction.response.edit_message(content=content, view=self)
                else:
                    await interaction.message.edit(content=content, view=self)
            except discord.NotFound:
                print("Message not found when trying to edit on Hit.")

    @discord.ui.button(label="Stand", style=discord.ButtonStyle.secondary)
    async def stand(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.game.player:
            await interaction.response.send_message("This is not your game!", ephemeral=True)
            return
        await self.end_game(interaction)

    @discord.ui.button(label="Double Down", style=discord.ButtonStyle.success)
    async def double_down(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.game.player:
            await interaction.response.send_message("This is not your game!", ephemeral=True)
            return
        if self.game.finished:
            await interaction.response.defer()
            return
        if len(self.game.player_hand) != 2:
            await interaction.response.send_message("You can only double down on your first move (with exactly 2 cards).", ephemeral=True)
            return

        if not hasattr(self.game, 'remaining'):
            await interaction.response.send_message("Funds information missing.", ephemeral=True)
            return
        if self.game.remaining < self.game.bet:
            await interaction.response.send_message("You don't have enough funds to double down.", ephemeral=True)
            return

        self.game.remaining -= self.game.bet
        self.game.bet *= 2
        print(f"[Blackjack] Doubling down. New bet: {self.game.bet}. Remaining funds: {self.game.remaining}")
        self.game.player_hand.append(self.game.deck.pop())
        await self.end_game(interaction)

class BlackjackCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="blackjack", description="Play a round of Blackjack using your Beaned Bucks.")
    @app_commands.describe(bet="The amount of Beaned Bucks you want to bet (can be non-integer)")
    async def blackjack(self, interaction: discord.Interaction, bet: str):
        data = load_data()
        user_id = str(interaction.user.id)
        user_record = data.get(user_id, {"balance": 0})
        balance = float(user_record.get("balance", 0))

        if bet.lower() == "all":
            bet_val = balance
        else:
            try:
                bet_val = float(bet)
            except ValueError:
                await interaction.response.send_message("Invalid bet amount.", ephemeral=True)
                return

        if bet_val <= 0:
            await interaction.response.send_message("Bet must be greater than 0.", ephemeral=True)
            return
        if bet_val > balance:
            await interaction.response.send_message("You don't have enough Beaned Bucks to make that bet.", ephemeral=True)
            return

        #create the game and set up starting funds.
        game = BlackjackGame(interaction.user, bet_val)
        game.start_balance = balance
        game.remaining = balance - bet_val

        #check for immediate blackjack.
        if is_blackjack(game.player_hand):
            if is_blackjack(game.dealer_hand):
                game.result = "tie"
            else:
                game.result = "win"
                game.bet *= 1.5
            content = render_game_state(game, final=True)
            outcome_text = f"Blackjack! You win {game.bet} Beaned Bucks!" if game.result == "win" else "Both you and the dealer got blackjack. It's a tie!"
            content += "\n\n" + outcome_text
            await interaction.response.send_message(content=content, ephemeral=False)
            if game.result == "win":
                user_record["balance"] = balance + game.bet
            else:
                user_record["balance"] = balance
            data[user_id] = user_record
            save_data(data)
            try:
                await interaction.followup.send(f"Your new balance is {user_record['balance']} Beaned Bucks.", ephemeral=False)
            except Exception as e:
                print(f"Error sending followup message: {e}")
            return

        content = render_game_state(game)
        view = BlackjackView(game)
        await interaction.response.send_message(content=content, view=view, ephemeral=False)
        await view.wait()

        if game.result == "win":
            user_record["balance"] = balance + game.bet
        elif game.result == "lose":
            user_record["balance"] = balance - game.bet
        elif game.result == "tie":
            user_record["balance"] = balance
        else:
            print("Game result not set. No balance change.")
        data[user_id] = user_record
        save_data(data)
        try:
            await interaction.followup.send(f"Your new balance is {user_record['balance']} Beaned Bucks.", ephemeral=False)
        except Exception as e:
            print(f"Error sending followup message: {e}")

async def setup(bot: commands.Bot):
    print("Loading BlackjackCog...")
    await bot.add_cog(BlackjackCog(bot))
