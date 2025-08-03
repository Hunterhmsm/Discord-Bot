import discord
from discord import app_commands
from discord.ext import commands, tasks
import json
import os
import random
import datetime
import asyncio
from zoneinfo import ZoneInfo
from typing import Optional
from globals import GUILD_ID
from utils import load_data, save_data

# --- Helper functions to load our JSON configurations ---
STORE_FILE = "industriesstore.json"  
INDUSTRIES_FILE = "industries.json"  
CONTRACTS_FILE = "contracts.json"  

def load_industry_store():
    if not os.path.exists(STORE_FILE):
        raise FileNotFoundError(f"{STORE_FILE} not found.")
    with open(STORE_FILE, "r") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            raise ValueError("Store JSON file is invalid.")

def load_industries():
    if not os.path.exists(INDUSTRIES_FILE):
        raise FileNotFoundError(f"{INDUSTRIES_FILE} not found.")
    with open(INDUSTRIES_FILE, "r") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            raise ValueError("Industries JSON file is invalid.")

def load_contracts():
    if not os.path.exists(CONTRACTS_FILE):
        return []
    with open(CONTRACTS_FILE, "r") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []

def save_contracts(contracts):
    with open(CONTRACTS_FILE, "w") as f:
        json.dump(contracts, f, indent=4)


# --- Industry Cog (as a regular Cog, not a group cog) ---
class IndustryGroup(commands.Cog):
    """All industry and trading commands are grouped under /industry."""
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.store = load_industry_store()
        self.industries = load_industries()  
        self.production_task = tasks.loop(hours=1)(self.hourly_production)
        self.production_task.start()
        self.contract_task = tasks.loop(hours=1)(self.process_contracts)
        self.contract_task.start()
        super().__init__()

    async def hourly_production(self):
        data = load_data()
        for user_id, record in data.items():
            facilities = record.get("facilities", {})
            inventory = record.get("inventory", {})
            
            for facility_name, facility_value in facilities.items():
                # Get facility definition from the facilities dict
                facility_def = self.industries.get("facilities", {}).get(facility_name)
                if facility_def is None:
                    continue
                    
                category = facility_def.get("category", "raw")
                
                if category == "oil":
                    # Oil drilling logic (unchanged)
                    new_wells = []
                    total_extracted = 0
                    for well in facility_value:
                        remaining = well["capacity"] - well["extracted"]
                        if remaining <= 0:
                            continue
                        extract = min(50, remaining)
                        well["extracted"] += extract
                        total_extracted += extract
                        if well["extracted"] < well["capacity"]:
                            new_wells.append(well)
                    record["facilities"][facility_name] = new_wells
                    inventory["oil"] = inventory.get("oil", 0) + total_extracted
                    
                elif category == "raw":
                    # Raw resource production (mines, farms, etc.)
                    count = facility_value
                    
                    # Check if we have enough power for powered production
                    power_available = inventory.get("power", 0)
                    power_needed = facility_def.get("power_required", 0) * count
                    
                    if power_available >= power_needed and power_needed > 0:
                        # Use powered production and consume power
                        prod_range = facility_def.get("powered_prod", facility_def.get("base_prod", [0, 0]))
                        inventory["power"] = power_available - power_needed
                    else:
                        # Use base production
                        prod_range = facility_def.get("base_prod", [0, 0])
                    
                    # Calculate production per facility
                    prod_per_facility = random.uniform(prod_range[0], prod_range[1])
                    total_production = prod_per_facility * count
                    
                    # Add to inventory
                    resource = facility_def.get("resource")
                    if resource:
                        inventory[resource] = inventory.get(resource, 0) + total_production
                        
                elif category in ["power", "industry"]:
                    # Power plants and industry facilities
                    count = facility_value
                    
                    # Check consumption requirements
                    consumption = facility_def.get("consumption", {})
                    can_produce = True
                    
                    # Check if we have enough of each required resource
                    for resource, needed_per_facility in consumption.items():
                        total_needed = needed_per_facility * count
                        available = inventory.get(resource, 0)
                        if available < total_needed:
                            can_produce = False
                            break
                    
                    if can_produce:
                        # Consume required resources
                        for resource, needed_per_facility in consumption.items():
                            total_needed = needed_per_facility * count
                            inventory[resource] = inventory.get(resource, 0) - total_needed
                            if inventory[resource] <= 0:
                                del inventory[resource]
                        
                        # Produce outputs
                        production = facility_def.get("production", {})
                        if isinstance(production, dict):
                            # Multiple outputs (like estrogen_lab)
                            for output_resource, amount_per_facility in production.items():
                                total_output = amount_per_facility * count
                                inventory[output_resource] = inventory.get(output_resource, 0) + total_output
                        else:
                            # Single output (like coal_power producing just power)
                            resource = facility_def.get("resource")
                            if resource:
                                total_output = production * count
                                inventory[resource] = inventory.get(resource, 0) + total_output

            record["inventory"] = inventory
            data[user_id] = record
        save_data(data)
        print("Hourly production completed.")

    async def process_contracts(self):
        contracts = load_contracts()
        data = load_data()
        updated = False
        for contract in contracts:
            if contract.get("status") != "active":
                continue
            offering_id = contract["offering_user"]
            receiving_id = contract["receiving_user"]
            resource = contract["resource"]
            qty = contract["quantity_per_hour"]
            offering_record = data.get(offering_id, {"inventory": {}})
            offering_inventory = offering_record.get("inventory", {})
            if offering_inventory.get(resource, 0) >= qty:
                offering_inventory[resource] -= qty
                if offering_inventory[resource] <= 0:
                    del offering_inventory[resource]
                offering_record["inventory"] = offering_inventory
                data[offering_id] = offering_record

                receiving_record = data.get(receiving_id, {"inventory": {}})
                receiving_inventory = receiving_record.get("inventory", {})
                receiving_inventory[resource] = receiving_inventory.get(resource, 0) + qty
                receiving_record["inventory"] = receiving_inventory
                data[receiving_id] = receiving_record

                contract["remaining_hours"] -= 1
                updated = True
                if contract["remaining_hours"] <= 0:
                    contract["status"] = "completed"
            else:
                contract["status"] = "cancelled"
                updated = True
        if updated:
            save_data(data)
            save_contracts(contracts)
        print("Contract processing completed.")

    # --- Trading Contract Commands ---
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="industry_tradecontract", description="Set up a trading contract with another user.")
    @app_commands.describe(
         resource="The resource to trade (e.g., coal, soy, etc.)",
         quantity="Quantity to trade per hour",
         hours="Number of hours for the contract",
         target="The user to receive the resource"
    )
    async def tradecontract(self, interaction: discord.Interaction, resource: str, quantity: float, hours: int, target: discord.Member):
        resource = resource.lower()
        if quantity <= 0 or hours <= 0:
            await interaction.response.send_message("Quantity and hours must be positive numbers.", ephemeral=True)
            return
        contract = {
            "contract_id": str(random.randint(100000, 999999)),
            "offering_user": str(interaction.user.id),
            "receiving_user": str(target.id),
            "resource": resource,
            "quantity_per_hour": quantity,
            "remaining_hours": hours,
            "created_at": datetime.datetime.now().isoformat(),
            "status": "active"
        }
        contracts = load_contracts()
        contracts.append(contract)
        save_contracts(contracts)
        await interaction.response.send_message(f"Trade contract created: {quantity} {resource} per hour for {hours} hours to {target.mention}.", ephemeral=True)

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="industry_contractstatus", description="View your active trading contracts.")
    async def contractstatus(self, interaction: discord.Interaction):
        contracts = load_contracts()
        user_id = str(interaction.user.id)
        user_contracts = [c for c in contracts if c["offering_user"] == user_id and c["status"] == "active"]
        if not user_contracts:
            await interaction.response.send_message("You have no active trading contracts.", ephemeral=True)
            return
        embed = discord.Embed(title="Your Active Trading Contracts", color=discord.Color.blue())
        for contract in user_contracts:
            embed.add_field(
                name=f"Contract {contract['contract_id']}",
                value=(f"Resource: {contract['resource']}\nQuantity/hr: {contract['quantity_per_hour']}\n"
                       f"Remaining hours: {contract['remaining_hours']}\nStatus: {contract['status']}"),
                inline=False
            )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # --- Store and Resource Trading Commands ---
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="industry_buy", description="Buy raw resources from the store.")
    @app_commands.describe(
        resource="The raw resource to buy (e.g., coal, raw_iron, uranium, soy, oil, power)",
        quantity="Quantity to buy"
    )
    async def buyraw(self, interaction: discord.Interaction, resource: str, quantity: float):
        resource = resource.lower()
        store_resources = self.store.get("raw_resources", {})
        if resource not in store_resources:
            await interaction.response.send_message("Invalid resource.", ephemeral=True)
            return
        buy_price = store_resources[resource]["buy_price"]
        cost = buy_price * quantity

        data = load_data()
        user_id = str(interaction.user.id)
        record = data.get(user_id, {"balance": 0, "inventory": {}})
        balance = record.get("balance", 0)
        if cost > balance:
            await interaction.response.send_message("You do not have enough funds to buy that quantity.", ephemeral=True)
            return

        record["balance"] = balance - cost
        inventory = record.get("inventory", {})
        inventory[resource] = inventory.get(resource, 0) + quantity
        record["inventory"] = inventory
        data[user_id] = record
        save_data(data)
        await interaction.response.send_message(f"Purchased {quantity} {resource} for {cost} Beaned Bucks. New balance: {record['balance']}.", ephemeral=False)

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="industry_sell", description="Sell raw resources to the store.")
    @app_commands.describe(
        resource="The resource to sell (e.g., coal, raw_iron, uranium, soy, oil, power)",
        quantity="Quantity to sell (or 'all' to sell everything)"
    )
    async def sellraw(self, interaction: discord.Interaction, resource: str, quantity: str):
        resource = resource.lower()
        store_resources = self.store.get("raw_resources", {})
        if resource not in store_resources:
            await interaction.response.send_message("Invalid resource.", ephemeral=True)
            return
        sell_price = store_resources[resource]["sell_price"]
        
        data = load_data()
        user_id = str(interaction.user.id)
        record = data.get(user_id, {"balance": 0, "inventory": {}})
        inventory = record.get("inventory", {})
        available = inventory.get(resource, 0)
        
        if quantity.lower() == "all":
            sell_quantity = available
        else:
            try:
                sell_quantity = float(quantity)
            except ValueError:
                await interaction.response.send_message("Invalid quantity format. Please provide a number or 'all'.", ephemeral=True)
                return

        if sell_quantity <= 0:
            await interaction.response.send_message("Quantity must be greater than zero.", ephemeral=True)
            return

        if available < sell_quantity:
            await interaction.response.send_message(f"You do not have enough of that resource to sell. You only have {available}.", ephemeral=True)
            return

        earnings = sell_price * sell_quantity
        inventory[resource] -= sell_quantity
        if inventory[resource] <= 0:
            del inventory[resource]
        record["inventory"] = inventory
        record["balance"] = record.get("balance", 0) + earnings
        data[user_id] = record
        save_data(data)
        await interaction.response.send_message(
            f"Sold {sell_quantity} {resource} for {earnings} Beaned Bucks. New balance: {record['balance']}.", ephemeral=False
        )


    # --- Building and Status Commands ---
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="industry_build", description="Build a facility from the industries list.")
    @app_commands.describe(facility="The facility you want to build (e.g., soy_farm, coal_mine, sparse_drill, coal_power, estrogen_lab, steelmaker)")
    async def build(self, interaction: discord.Interaction, facility: str):
        facility = facility.lower()
        # Get facilities from the JSON structure
        facilities_data = self.industries.get("facilities", {})
        
        if facility not in facilities_data:
            await interaction.response.send_message("Invalid facility.", ephemeral=True)
            return

        facility_info = facilities_data[facility]
        build_price = facility_info.get("cost")
        if build_price is None:
            await interaction.response.send_message("This facility cannot be built.", ephemeral=True)
            return

        data = load_data()
        user_id = str(interaction.user.id)
        record = data.get(user_id, {"balance": 0, "facilities": {}})
        balance = record.get("balance", 0)
        if balance < build_price:
            await interaction.response.send_message("You do not have enough funds to build this facility.", ephemeral=True)
            return

        record["balance"] = balance - build_price

        # Check if the facility is an oil facility.
        if facility_info.get("category", "") == "oil":
            # Roll on outcomes to determine the well's total capacity.
            outcomes = facility_info.get("outcomes", [])
            r = random.random()
            cumulative = 0
            capacity = None
            for outcome in outcomes:
                chance = outcome.get("chance", 0)
                cumulative += chance
                if r <= cumulative:
                    low, high = outcome.get("range", [0, 0])
                    capacity = random.randint(low, high)
                    break
            if capacity is None:
                capacity = 0  # fallback if no outcome matched
            # Create a well object with capacity and extracted set to 0.
            well = {"capacity": capacity, "extracted": 0}
            # Store oil facilities as a list of wells.
            facilities_owned = record.get("facilities", {})
            if facility in facilities_owned:
                facilities_owned[facility].append(well)
            else:
                facilities_owned[facility] = [well]
        else:
            # For non-oil facilities, just increment count.
            facilities_owned = record.get("facilities", {})
            facilities_owned[facility] = facilities_owned.get(facility, 0) + 1

        record["facilities"] = facilities_owned
        data[user_id] = record
        save_data(data)
        await interaction.response.send_message(
            f"Successfully built {facility} for {build_price} Beaned Bucks. New balance: {record['balance']}.", 
            ephemeral=False
        )

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="industry_industries", description="Show the list of facilities and their details.")
    async def industries(self, interaction: discord.Interaction):
        try:
            industries_json = load_industries()
        except Exception as e:
            await interaction.response.send_message(f"Error loading industries: {e}", ephemeral=True)
            return

        facilities = industries_json.get("facilities", {})
        if not facilities:
            await interaction.response.send_message("No facilities defined.", ephemeral=True)
            return

        embed = discord.Embed(title="Available Facilities", color=discord.Color.green())
        for facility_key, details in facilities.items():
            nice_name = facility_key.replace("_", " ").title()
            field_value = ""
            for key, value in details.items():
                if isinstance(value, list):
                    value = " - ".join(map(str, value))
                elif isinstance(value, dict):
                    value = ", ".join([f"{k}: {v}" for k, v in value.items()])
                field_value += f"**{key.capitalize()}**: {value}\n"
            embed.add_field(name=nice_name, value=field_value, inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(
        name="industry_status", 
        description="View built facilities and your resource inventory."
    )
    @app_commands.describe(user="Optional: The user whose industry status you want to view (defaults to yourself)")
    async def industrystatus(self, interaction: discord.Interaction, user: discord.Member = None):
        target = user or interaction.user
        data = load_data()
        user_id = str(target.id)
        record = data.get(user_id, {"facilities": {}, "inventory": {}})
        facilities_owned = record.get("facilities", {})
        inventory = record.get("inventory", {})

        embed = discord.Embed(
            title=f"{target.display_name}'s Industry Status",
            color=discord.Color.green()
        )

        if facilities_owned:
            facility_lines = []
            for facility, value in facilities_owned.items():
                facility_info = self.industries.get("facilities", {}).get(facility, {})
                category = facility_info.get("category", "raw")
                
                if category == "oil":
                    well_details = []
                    for idx, well in enumerate(value, start=1):
                        capacity = well.get("capacity", 0)
                        extracted = well.get("extracted", 0)
                        remaining = capacity - extracted
                        well_details.append(f"Well {idx}: {remaining}/{capacity} remaining")
                    facility_line = (
                        f"**{facility.replace('_', ' ').title()}**\n"
                        f"Extracts 50 oil/hr per well\n"
                        f"{chr(10).join(well_details)}"
                    )
                else:
                    count = value
                    # Production info
                    prod_info = facility_info.get("production", {})
                    if isinstance(prod_info, dict):
                        prod_str = ", ".join([f"{k}: {v}/hr" for k, v in prod_info.items()])
                    elif prod_info:
                        resource = facility_info.get("resource", "power")
                        prod_str = f"{resource}: {prod_info}/hr"
                    else:
                        base_prod = facility_info.get("base_prod", [0, 0])
                        resource = facility_info.get("resource", "unknown")
                        prod_str = f"{resource}: {base_prod[0]}-{base_prod[1]}/hr"
                    
                    # Consumption info
                    cons = facility_info.get("consumption", {})
                    cons_str = ", ".join([f"{k}: {v}/hr" for k, v in cons.items()]) if cons else "None"
                    
                    facility_line = (
                        f"**{facility.replace('_', ' ').title()}** (x{count})\n"
                        f"Production: {prod_str}\n"
                        f"Consumption: {cons_str}"
                    )
                facility_lines.append(facility_line)
            embed.add_field(name="Facilities", value="\n\n".join(facility_lines), inline=False)
        else:
            embed.add_field(name="Facilities", value="None", inline=False)

        if inventory:
            inv_lines = [f"**{res.capitalize()}**: {qty:.1f}" for res, qty in inventory.items()]
            embed.add_field(name="Resource Inventory", value="\n".join(inv_lines), inline=False)
        else:
            embed.add_field(name="Resource Inventory", value="None", inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="industry_invtransfer", description="Transfer a resource from your inventory to another user.")
    @app_commands.describe(
        resource="The resource to transfer (e.g. coal, soy)",
        quantity="The quantity to transfer (or type 'all' to transfer everything)",
        target="The user to send the resource to"
    )
    async def invtransfer(self, interaction: discord.Interaction, resource: str, quantity: str, target: discord.Member):
        resource = resource.lower()
        data = load_data()
        sender_id = str(interaction.user.id)
        receiver_id = str(target.id)
        sender_record = data.get(sender_id, {"inventory": {}})
        receiver_record = data.get(receiver_id, {"inventory": {}})
        sender_inventory = sender_record.get("inventory", {})
        receiver_inventory = receiver_record.get("inventory", {})

        if resource not in sender_inventory:
            await interaction.response.send_message(f"You do not have any **{resource}** in your inventory.", ephemeral=True)
            return

        available_qty = sender_inventory.get(resource, 0)
        if quantity.lower() == "all":
            transfer_qty = available_qty
        else:
            try:
                transfer_qty = float(quantity)
            except ValueError:
                await interaction.response.send_message("Invalid quantity provided. Please provide a number or 'all'.", ephemeral=True)
                return

        if transfer_qty <= 0:
            await interaction.response.send_message("You must transfer a positive quantity.", ephemeral=True)
            return

        if transfer_qty > available_qty:
            await interaction.response.send_message(f"You do not have enough **{resource}**. You only have {available_qty}.", ephemeral=True)
            return

        sender_inventory[resource] = available_qty - transfer_qty
        if sender_inventory[resource] == 0:
            del sender_inventory[resource]
        sender_record["inventory"] = sender_inventory

        receiver_inventory[resource] = receiver_inventory.get(resource, 0) + transfer_qty
        receiver_record["inventory"] = receiver_inventory

        data[sender_id] = sender_record
        data[receiver_id] = receiver_record
        save_data(data)

        await interaction.response.send_message(f"Successfully transferred {transfer_qty} of **{resource}** to {target.display_name}.", ephemeral=False)

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="industry_store", description="Show the current store items and their details.")
    async def store(self, interaction: discord.Interaction):
        try:
            store_items = load_industry_store()
        except Exception as e:
            await interaction.response.send_message(f"Error loading store: {e}", ephemeral=True)
            return

        embed = discord.Embed(title="Industry Store", color=discord.Color.blue())
        for item_name, details in store_items.items():
            item_text = f"**{item_name.replace('_', ' ').title()}**\n"
            for key, value in details.items():
                if isinstance(value, list):
                    value = " - ".join(map(str, value))
                item_text += f"• **{key.capitalize()}**: {value}\n"
            embed.add_field(name=item_name.replace('_', ' ').title(), value=item_text, inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="industry_sellindustry", description="Sell one of your built industry facilities at half its base value.")
    @app_commands.describe(
        industry="The name of the industry to sell (e.g. steelmaker)",
        quantity="The number of facilities to sell (or 'all' to sell everything)"
    )
    async def sellindustry(self, interaction: discord.Interaction, industry: str, quantity: str):
        industry_key = industry.lower()
        data = load_data()
        user_id = str(interaction.user.id)
        user_record = data.get(user_id, {"balance": 0, "facilities": {}})
        user_facilities = user_record.get("facilities", {})

        if industry_key not in user_facilities or user_facilities[industry_key] <= 0:
            await interaction.response.send_message(f"You do not own any {industry} facilities.", ephemeral=True)
            return

        if quantity.lower() == "all":
            sell_quantity = user_facilities[industry_key]
        else:
            try:
                sell_quantity = float(quantity)
            except ValueError:
                await interaction.response.send_message("Invalid quantity format. Please provide a number or 'all'.", ephemeral=True)
                return

        if sell_quantity <= 0 or sell_quantity > user_facilities[industry_key]:
            await interaction.response.send_message("You do not own enough facilities to sell that many.", ephemeral=True)
            return

        try:
            industries_def = load_industries()
        except Exception as e:
            await interaction.response.send_message(f"Error loading industries definitions: {e}", ephemeral=True)
            return

        facilities_def = industries_def.get("facilities", {})
        if industry_key not in facilities_def:
            await interaction.response.send_message(f"Industry '{industry}' not found in definitions.", ephemeral=True)
            return

        base_price = facilities_def[industry_key].get("cost")
        if base_price is None:
            await interaction.response.send_message(f"No price defined for {industry}.", ephemeral=True)
            return

        sale_value = 0.5 * base_price * sell_quantity

        user_facilities[industry_key] -= sell_quantity
        if user_facilities[industry_key] <= 0:
            del user_facilities[industry_key]
        user_record["facilities"] = user_facilities
        user_record["balance"] += sale_value
        data[user_id] = user_record
        save_data(data)

        await interaction.response.send_message(f"Successfully sold {sell_quantity} {industry} facility(ies) for {sale_value} Beaned Bucks (half price).", ephemeral=False)
class DrugMarket:
    def __init__(self):
        # Load base prices from drugprice.json
        self.base_prices = self.load_drug_prices()
        
    def load_drug_prices(self):
        """Load base drug prices from drugprice.json"""
        try:
            with open('drugprice.json', 'r') as f:
                data = json.load(f)
                # Convert format from {buy_price, sell_price} to {buy, sell}
                converted = {}
                for drug, prices in data.items():
                    converted[drug] = {
                        "buy": prices["buy_price"],
                        "sell": prices["sell_price"]
                    }
                return converted
        except:
            # Fallback to default prices if file doesn't exist
            return {
                "marijuana": {"buy": 80, "sell": 40},
                "coca_leaves": {"buy": 120, "sell": 60},
                "cannabis_products": {"buy": 800, "sell": 400},
                "cocaine": {"buy": 1500, "sell": 750}
            }
        
    def get_market_data(self):
        """Load or create market data"""
        try:
            with open('drug_market.json', 'r') as f:
                return json.load(f)
        except:
            # Default market data
            default_data = {}
            for drug in self.base_prices:
                default_data[drug] = {
                    "sales_3days": [],  # List of [date, quantity] for last 3 days
                    "price_multiplier": 1.0,
                    "last_update": datetime.date.today().isoformat()
                }
            self.save_market_data(default_data)
            return default_data
    
    def save_market_data(self, data):
        """Save market data"""
        with open('drug_market.json', 'w') as f:
            json.dump(data, f)
    
    def clean_old_sales(self, market_data):
        """Remove sales older than 3 days and update prices"""
        today = datetime.date.today()
        three_days_ago = (today - datetime.timedelta(days=3)).isoformat()
        
        for drug in market_data:
            # Clean old sales (keep only last 3 days)
            market_data[drug]["sales_3days"] = [
                sale for sale in market_data[drug]["sales_3days"] 
                if sale[0] > three_days_ago
            ]
            
            # Calculate total sales in last 3 days
            total_sales = sum(sale[1] for sale in market_data[drug]["sales_3days"])
            
            # Get current multiplier
            current_multiplier = market_data[drug]["price_multiplier"]
            target_multiplier = 1.0  # Default target
            
            # Determine target multiplier based on 3-day sales
            if total_sales < 50:
                target_multiplier = 1.5  # +50%
            elif total_sales < 100:
                target_multiplier = 1.25  # +25%
            elif total_sales < 200:
                target_multiplier = 1.2   # +20%
            elif total_sales > 800:
                target_multiplier = 0.5   # -50%
            elif total_sales > 600:
                target_multiplier = 0.75  # -25%
            elif total_sales > 400:
                target_multiplier = 0.9   # -10%
            else:
                target_multiplier = 1.0   # Normal price
            
            # Slowly move towards target (adjust by 15% per day max)
            if current_multiplier < target_multiplier:
                new_multiplier = min(target_multiplier, current_multiplier + 0.15)
            elif current_multiplier > target_multiplier:
                new_multiplier = max(target_multiplier, current_multiplier - 0.15)
            else:
                new_multiplier = current_multiplier
            
            market_data[drug]["price_multiplier"] = round(new_multiplier, 3)
            market_data[drug]["last_update"] = today.isoformat()
        
        self.save_market_data(market_data)
        return market_data
    
    def record_sale(self, drug, quantity):
        """Record a drug sale"""
        if drug not in self.base_prices:
            return
            
        market_data = self.get_market_data()
        market_data = self.clean_old_sales(market_data)
        
        # Add new sale [date, quantity]
        today = datetime.date.today().isoformat()
        market_data[drug]["sales_3days"].append([today, quantity])
        self.save_market_data(market_data)
    
    def get_current_prices(self):
        """Get current drug prices with market adjustments"""
        market_data = self.get_market_data()
        market_data = self.clean_old_sales(market_data)
        
        current_prices = {}
        for drug, base in self.base_prices.items():
            multiplier = market_data[drug]["price_multiplier"]
            
            # Calculate total sales in last 3 days
            total_sales_3days = sum(sale[1] for sale in market_data[drug]["sales_3days"])
            
            current_prices[drug] = {
                "buy_price": int(base["buy"] * multiplier),
                "sell_price": int(base["sell"] * multiplier),
                "multiplier": multiplier,
                "sales_3days": total_sales_3days
            }
        
        return current_prices

# Usage in your sell command:
drug_market = DrugMarket()

def sell_drugs(user_id, drug, quantity):
    """Example sell function with market tracking"""
    if drug in ["marijuana", "coca_leaves", "cannabis_products", "cocaine"]:
        # Record the sale
        drug_market.record_sale(drug, quantity)
        
        # Get current price
        current_prices = drug_market.get_current_prices()
        sell_price = current_prices[drug]["sell_price"]
        
        # Calculate earnings
        earnings = sell_price * quantity
        
        # Update user money
        data = load_data()
        user_record = data.get(user_id, {"balance": 0, "cash": 0})
        user_record["cash"] = user_record.get("cash", 0) + earnings
        data[user_id] = user_record
        save_data(data)
        
        return earnings, sell_price
    
    return 0, 0

# Command to buy drugs
@app_commands.command(name="buydrug", description="Buy drugs from the market")
@app_commands.describe(drug="Type of drug to buy", quantity="Amount to buy")
async def buydrug(interaction: discord.Interaction, drug: str, quantity: int):
    if quantity <= 0:
        await interaction.response.send_message("Quantity must be positive.", ephemeral=True)
        return
    
    drug = drug.lower().replace(" ", "_")
    current_prices = drug_market.get_current_prices()
    
    if drug not in current_prices:
        available = ", ".join(current_prices.keys()).replace("_", " ")
        await interaction.response.send_message(f"Invalid drug. Available: {available}", ephemeral=True)
        return
    
    user_id = str(interaction.user.id)
    buy_price = current_prices[drug]["buy_price"]
    total_cost = buy_price * quantity
    
    # Load user data
    data = load_data()
    user_record = data.get(user_id, {"balance": 0, "cash": 0, "inventory": {}})
    user_cash = user_record.get("cash", 0)
    
    if user_cash < total_cost:
        await interaction.response.send_message(
            f"Not enough cash! Need {total_cost:,}, you have {user_cash:,}",
            ephemeral=True
        )
        return
    
    # Process purchase
    user_record["cash"] = user_cash - total_cost
    if "inventory" not in user_record:
        user_record["inventory"] = {}
    user_record["inventory"][drug] = user_record["inventory"].get(drug, 0) + quantity
    
    data[user_id] = user_record
    save_data(data)
    
    await interaction.response.send_message(
        f"💰 Bought {quantity} {drug.replace('_', ' ')} for {total_cost:,} cash!\n"
        f"Cash remaining: {user_record['cash']:,}"
    )

# Command to sell drugs
@app_commands.command(name="selldrug", description="Sell drugs to the market")
@app_commands.describe(drug="Type of drug to sell", quantity="Amount to sell")
async def selldrug(interaction: discord.Interaction, drug: str, quantity: int):
    if quantity <= 0:
        await interaction.response.send_message("Quantity must be positive.", ephemeral=True)
        return
    
    drug = drug.lower().replace(" ", "_")
    current_prices = drug_market.get_current_prices()
    
    if drug not in current_prices:
        available = ", ".join(current_prices.keys()).replace("_", " ")
        await interaction.response.send_message(f"Invalid drug. Available: {available}", ephemeral=True)
        return
    
    user_id = str(interaction.user.id)
    
    # Load user data
    data = load_data()
    user_record = data.get(user_id, {"balance": 0, "cash": 0, "inventory": {}})
    user_inventory = user_record.get("inventory", {})
    current_amount = user_inventory.get(drug, 0)
    
    if current_amount < quantity:
        await interaction.response.send_message(
            f"Not enough {drug.replace('_', ' ')}! You have {current_amount}, trying to sell {quantity}",
            ephemeral=True
        )
        return
    
    # Process sale
    sell_price = current_prices[drug]["sell_price"]
    total_earnings = sell_price * quantity
    
    user_record["cash"] = user_record.get("cash", 0) + total_earnings
    user_record["inventory"][drug] = current_amount - quantity
    
    # Remove from inventory if quantity reaches 0
    if user_record["inventory"][drug] == 0:
        del user_record["inventory"][drug]
    
    data[user_id] = user_record
    save_data(data)
    
    # Record the sale for market tracking
    drug_market.record_sale(drug, quantity)
    
    await interaction.response.send_message(
        f"💵 Sold {quantity} {drug.replace('_', ' ')} for {total_earnings:,} cash!\n"
        f"Cash balance: {user_record['cash']:,}"
    )

# Command to check drug inventory
@app_commands.command(name="drugs", description="Check your drug inventory")
async def drugs(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    data = load_data()
    user_record = data.get(user_id, {"inventory": {}})
    inventory = user_record.get("inventory", {})
    
    # Filter only drug items
    drug_items = {k: v for k, v in inventory.items() if k in drug_market.base_prices}
    
    if not drug_items:
        await interaction.response.send_message("🚫 No drugs in inventory.", ephemeral=True)
        return
    
    current_prices = drug_market.get_current_prices()
    embed = discord.Embed(title="💊 Your Drug Inventory", color=0x9932cc)
    
    total_value = 0
    for drug, amount in drug_items.items():
        sell_price = current_prices[drug]["sell_price"]
        value = sell_price * amount
        total_value += value
        
        embed.add_field(
            name=f"{drug.replace('_', ' ').title()}",
            value=f"Amount: {amount:,}\nValue: {value:,} cash",
            inline=True
        )
    
    embed.set_footer(text=f"Total inventory value: {total_value:,} cash")
    await interaction.response.send_message(embed=embed)
@app_commands.command(name="drugmarket", description="Check current drug market prices and demand")
async def drugmarket(interaction: discord.Interaction):
    current_prices = drug_market.get_current_prices()
    
    embed = discord.Embed(title="🏪 Drug Market Status (Last 3 Days)", color=0x00ff00)
    
    for drug, info in current_prices.items():
        multiplier = info["multiplier"]
        sales_3days = info["sales_3days"]
        
        # Determine trend and status
        if multiplier >= 1.4:
            trend = "🚀 VERY HIGH DEMAND"
            color_emoji = "🟢"
        elif multiplier >= 1.15:
            trend = "📈 HIGH DEMAND"
            color_emoji = "🟡"
        elif multiplier <= 0.6:
            trend = "💥 CRASHED"
            color_emoji = "🔴"
        elif multiplier <= 0.8:
            trend = "📉 FLOODED"
            color_emoji = "🟠"
        else:
            trend = "📊 STABLE"
            color_emoji = "⚪"
            
        # Determine market condition based on sales
        if sales_3days < 50:
            condition = "🔥 RARE"
        elif sales_3days < 100:
            condition = "⭐ LOW SUPPLY"
        elif sales_3days < 200:
            condition = "📦 MODERATE"
        elif sales_3days > 800:
            condition = "🌊 OVERSATURATED"
        elif sales_3days > 600:
            condition = "📊 HIGH VOLUME"
        elif sales_3days > 400:
            condition = "🔄 ACTIVE"
        else:
            condition = "✅ NORMAL"
            
        embed.add_field(
            name=f"{color_emoji} {drug.replace('_', ' ').title()}",
            value=f"**Sell: {info['sell_price']:,}** ({multiplier:.2f}x)\n"
                  f"3-day sales: {sales_3days}\n"
                  f"{condition}\n{trend}",
            inline=True
        )
    
    embed.set_footer(text="Prices adjust gradually (15% max per day) based on 3-day sales volume")
    await interaction.response.send_message(embed=embed)
async def setup(bot: commands.Bot):
    print("Loading IndustryCog...")
    await bot.add_cog(IndustryGroup(bot))