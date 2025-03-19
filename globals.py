import json

#load configuration from file
with open("config.json", "r") as f:
    config = json.load(f)

#global configuration variables
TOKEN = config["token"]
GUILD_ID = int(config["guild_id"])
TARGET_MEMBER_ID = int(config["target_member_id"])
TARGET_USER_ID = 398607026176917535
DATA_FILE = "data.json"
ALLOWED_ROLES = ["him"]
STOCK_FILE = "stocks.json"
STOCK_HISTORY_FILE = "stock_history.json"
UPDATE_INTERVAL_MINUTES = 20 
LOTTERY_FILE = "lottery.json"
OPTIONS_FILE = "options.json"
AFK_CHANNEL_ID = 574668552557297666