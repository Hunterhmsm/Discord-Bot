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
        # Here the industries JSON is expected to have a top-level "facilities" key.
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
            for facility_name, facility_value in facilities.items():
                # Look up facility definition from the combined facilities dictionary.
                facility_def = None
                for cat in self.industries.values():
                    if facility_name in cat:
                        facility_def = cat[facility_name]
                        break
                if facility_def is None:
                    continue
                category = facility_def.get("category", "raw")
                if category == "oil":
                    # For oil facilities, facility_value is expected to be a list of oil well objects.
                    new_wells = []
                    total_extracted = 0
                    for well in facility_value:
                        remaining = well["capacity"] - well["extracted"]
                        if remaining <= 0:
                            continue  # Well is depleted.
                        extract = min(50, remaining)
                        well["extracted"] += extract
                        total_extracted += extract
                        if well["extracted"] < well["capacity"]:
                            new_wells.append(well)
                    record["facilities"][facility_name] = new_wells
                    inventory = record.get("inventory", {})
                    inventory["oil"] = inventory.get("oil", 0) + total_extracted
                    record["inventory"] = inventory
                else:
                    # For non-oil facilities, facility_value is expected to be a count.
                    count = facility_value  
                    # Determine production amount.
                    if "production" in facility_def:
                        prod_info = facility_def["production"]
                        # If production is a dict, sum the production values.
                        if isinstance(prod_info, dict):
                            prod_amount = sum(prod_info.values())
                        else:
                            prod_amount = prod_info
                    else:
                        base_prod = facility_def.get("base_prod")
                        prod_amount = sum(base_prod) / 2 if base_prod else 0
                    produced = prod_amount * count
                    resource = facility_def.get("resource")
                    if resource:
                        inventory = record.get("inventory", {})
                        inventory[resource] = inventory.get(resource, 0) + produced
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
        # Since our JSON now has a top-level "facilities" key:
        # Combine all facility definitions from all categories into one dictionary.
        facilities_data = {}
        for category in self.industries.values():
            facilities_data.update(category)
        
        if facility not in facilities_data:
            await interaction.response.send_message("Invalid facility.", ephemeral=True)
            return

        facility_info = facilities_data[facility]
        build_price = facility_info.get("cost")  # using "cost" for building price
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

        # We expect the industries JSON to have a "facilities" key.
        facilities = industries_json.get("facilities", {})
        if not facilities:
            await interaction.response.send_message("No facilities defined.", ephemeral=True)
            return

        embed = discord.Embed(title="Available Facilities", color=discord.Color.green())
        # Iterate through each facility in the "facilities" section.
        for facility_key, details in facilities.items():
            nice_name = facility_key.replace("_", " ").title()
            field_value = ""
            for key, value in details.items():
                # If the value is a list (like a production range), join it nicely.
                if isinstance(value, list):
                    value = " - ".join(map(str, value))
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
        # Load the user's record from data
        data = load_data()
        user_id = str(target.id)
        record = data.get(user_id, {"facilities": {}, "inventory": {}})
        facilities_owned = record.get("facilities", {})
        inventory = record.get("inventory", {})

        # Create an embed for the industry status
        embed = discord.Embed(
            title=f"{target.display_name}'s Industry Status",
            color=discord.Color.green()
        )

        if facilities_owned:
            facility_lines = []
            # Iterate over each facility the user owns
            for facility, value in facilities_owned.items():
                facility_info = self.industries.get("facilities", {}).get(facility, {})
                description = facility_info.get("description", "No description available.")
                category = facility_info.get("category", "raw")
                
                if category == "oil":
                    # For oil facilities, 'value' is expected to be a list of well objects
                    well_details = []
                    for idx, well in enumerate(value, start=1):
                        capacity = well.get("capacity", 0)
                        extracted = well.get("extracted", 0)
                        remaining = capacity - extracted
                        well_details.append(f"Well {idx}: Capacity: {capacity}, Extracted: {extracted}, Remaining: {remaining}")
                    prod_str = "Extracts 50 barrels/hr per well"
                    facility_line = (
                        f"**{facility.replace('_', ' ').title()}**\n"
                        f"*{description}*\n"
                        f"{prod_str}\n"
                        f"{chr(10).join(well_details)}"
                    )
                else:
                    # For non-oil facilities, 'value' is expected to be a count
                    count = value
                    if "production" in facility_info:
                        prod_info = facility_info["production"]
                        if isinstance(prod_info, dict):
                            prod_str = ", ".join([f"{k}: {prod_info[k]}/hr" for k in prod_info])
                        else:
                            prod_str = f"{prod_info}/hr"
                    else:
                        base_prod = facility_info.get("base_prod")
                        prod_str = f"{base_prod[0]} - {base_prod[1]}/hr" if base_prod else "None"
                    cons = facility_info.get("consumption", {})
                    cons_str = ", ".join([f"{k}: {cons[k]}/hr" for k in cons]) if cons else "None"
                    facility_line = (
                        f"**{facility.replace('_', ' ').title()}** (x{count})\n"
                        f"*{description}*\n"
                        f"Production: {prod_str}\n"
                        f"Consumption: {cons_str}"
                    )
                facility_lines.append(facility_line)
            embed.add_field(name="Facilities", value="\n\n".join(facility_lines), inline=False)
        else:
            embed.add_field(name="Facilities", value="None", inline=False)

        if inventory:
            inv_lines = [f"**{res.capitalize()}**: {qty}" for res, qty in inventory.items()]
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
        # Format each store item nicely.
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
        user_record = data.get(user_id, {"balance": 0, "industries": {}})
        user_industries = user_record.get("industries", {})

        if industry_key not in user_industries or user_industries[industry_key] <= 0:
            await interaction.response.send_message(f"You do not own any {industry} facilities.", ephemeral=True)
            return

        if quantity.lower() == "all":
            sell_quantity = user_industries[industry_key]
        else:
            try:
                sell_quantity = float(quantity)
            except ValueError:
                await interaction.response.send_message("Invalid quantity format. Please provide a number or 'all'.", ephemeral=True)
                return

        if sell_quantity <= 0 or sell_quantity > user_industries[industry_key]:
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

        base_price = facilities_def[industry_key].get("price")
        if base_price is None:
            await interaction.response.send_message(f"No price defined for {industry}.", ephemeral=True)
            return

        sale_value = 0.5 * base_price * sell_quantity

        user_industries[industry_key] -= sell_quantity
        if user_industries[industry_key] <= 0:
            del user_industries[industry_key]
        user_record["industries"] = user_industries
        user_record["balance"] += sale_value
        data[user_id] = user_record
        save_data(data)

        await interaction.response.send_message(f"Successfully sold {sell_quantity} {industry} facility(ies) for {sale_value} Beaned Bucks (half price).", ephemeral=False)

async def setup(bot: commands.Bot):
    print("Loading IndustryCog...")
    await bot.add_cog(IndustryGroup(bot))
