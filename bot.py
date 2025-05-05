import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime, timedelta
import json

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="/", intents=intents)
tree = bot.tree

# Constants for Raids and Time Slots
RAID_MIN_ILVLS = {
    "Brelshaza Hardmode": 1690,
    "Brelshaza Normal": 1670,
    "Aegir Hardmode": 1680,
    "Aegir Normal": 1660,
}

DAYS = ["Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
TIME_INTERVALS = [f"{hour:02}:{minute:02}" for hour in range(12, 24) for minute in (0, 30)]

# Fixed 8-man Brelshaza Hardmode Roster (Support priority)
FIXED_ROSTER = {
    "kenkixdd": "Paladin",
    "zitroone": "Artist",
    "pastacino": "Sorc",
    ".__james__": "Blade",
    "rareshandaric": "Sorc",
    "beaume": "Souleater",
    "matnam": "Arcana",
    "optitv": "Destroyer"
}

SUPPORT_PLAYERS = ["kenkixdd", "zitroone"]  # Priority for Paladin, Bard, Artist
SUPPORT_KEYWORDS = ["bard", "paladin", "artist"]

SAVE_FILE = "homework_data.json"

# Homework storage (in-memory)
db = {}

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} commands")
    except Exception as e:
        print(f"Error syncing commands: {e}")

@bot.tree.command(name="homework", description="Submit weekly homework availability and character info.")
async def homework(interaction: discord.Interaction):
    user_id = interaction.user.id
    db[user_id] = {"availability": {}, "characters": []}

    await interaction.response.send_message("Select your availability per day:", ephemeral=True)

    # Collect availability for each day
    for day in DAYS:
        view = discord.ui.View(timeout=300)

        class DaySelect(discord.ui.Select):
            def __init__(self):
                options = [discord.SelectOption(label=time, value=time) for time in TIME_INTERVALS]
                super().__init__(placeholder=f"{day}: Select available times", min_values=1, max_values=len(options), options=options, custom_id=day)

            async def callback(self, select_interaction: discord.Interaction):
                db[user_id]["availability"][day] = self.values
                await select_interaction.response.send_message(f"Saved availability for {day}.", ephemeral=True)

        view.add_item(DaySelect())
        await interaction.followup.send(view=view, ephemeral=True)

    # After collecting availability, prompt for character info
    await interaction.followup.send("Now collecting your characters. Please check your DMs.", ephemeral=True)
    await collect_character_info(interaction.user)

async def collect_character_info(user: discord.User):
    def check(m):
        return m.author == user and isinstance(m.channel, discord.DMChannel)

    try:
        await user.send("Please enter up to 12 characters. Format: `Name, ilvl, Class`\nType `done` when finished.")
        characters = []

        while len(characters) < 12:
            msg = await bot.wait_for('message', check=check, timeout=300)
            if msg.content.lower() == 'done':
                break

            try:
                name, ilvl, class_name = map(str.strip, msg.content.split(","))
                if int(ilvl) < RAID_MIN_ILVLS.get(class_name, 0):
                    await user.send(f"Your character {name} does not meet the minimum item level for {class_name}. Please try again.")
                    continue
                characters.append({"name": name, "ilvl": ilvl, "class": class_name})
                await user.send(f"Added: {name}, {ilvl}, {class_name}")
            except ValueError:
                await user.send("Invalid format. Please use: Name, ilvl, Class")

        db[user.id]["characters"] = characters
        await user.send("Character collection complete. Thanks!")

        # Show confirmation message
        confirmation_msg = f"Availability: {db[user.id]['availability']}\nCharacters: {characters}"
        await user.send(f"Confirmation of your submission:\n{confirmation_msg}")

    except Exception as e:
        await user.send(f"An error occurred: {e}")

# Automatic scheduling of raid groups on Tuesday at 8:00 PM
@tasks.loop(time=datetime.now().replace(hour=20, minute=0, second=0, microsecond=0))
async def schedule_raid():
    available_users = []

    # Filter and collect all users with their availability and character info
    for user_id, data in db.items():
        availability = data["availability"]
        characters = data["characters"]
        for day, times in availability.items():
            for time in times:
                for character in characters:
                    raid_name = character["class"]
                    raid_ilvl = int(character["ilvl"])
                    # Ensure they meet raid minimum ilvl requirements
                    if raid_name in RAID_MIN_ILVLS and raid_ilvl >= RAID_MIN_ILVLS[raid_name]:
                        available_users.append({"user_id": user_id, "day": day, "time": time, "character": character})

    # Sort users by earliest time for scheduling
    available_users.sort(key=lambda x: (DAYS.index(x["day"]), TIME_INTERVALS.index(x["time"])))

    # Create raid groups based on priority
    raid_groups = {"Brelshaza Hardmode": [], "Brelshaza Normal": [], "Aegir Hardmode": [], "Aegir Normal": []}

    for user in available_users:
        user_id = user["user_id"]
        raid_name = user["character"]["class"]
        raid_time = user["time"]
        raid_day = user["day"]

        # Skip users who already have a raid assigned
        if raid_name in ["Paladin", "Artist"] and raid_time not in FIXED_ROSTER.get("kenkixdd", []):
            continue  # Paladin gets priority only for Brelshaza Hardmode, others are skipped

        raid_groups[raid_name].append(f"User {user_id} - {raid_time}")

    # Send the raid groups and timings to the server channels
    await send_to_server(raid_groups["Brelshaza Hardmode"], 1340771270693879859)
    await send_to_server(raid_groups["Brelshaza Normal"], 1330603021729533962)
    await send_to_server(raid_groups["Aegir Hardmode"], 1318262633811673158)
    await send_to_server(raid_groups["Aegir Normal"], 1368333245183299634)

async def send_to_server(group: list, channel_id: int):
    # Send the generated raid groups to the server
    channel = bot.get_channel(channel_id)  # Send to specific raid channel
    raid_message = f"Raid scheduled:\n" + "\n".join(group)
    await channel.send(raid_message)

# Run the bot
bot.run("YOUR_TOKEN")








