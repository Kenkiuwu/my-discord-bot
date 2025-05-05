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
    db[user_id] = {"availability": {}, "raids": {}}

    await interaction.response.send_message("Select your availability per day:", ephemeral=True)

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

    await interaction.followup.send("Now collecting your characters per raid. Please check your DMs.", ephemeral=True)
    await collect_character_info(interaction.user)

async def collect_character_info(user: discord.User):
    def check(m):
        return m.author == user and isinstance(m.channel, discord.DMChannel)

    try:
        await user.send("Now we'll assign your characters **per raid**. You can enter up to 12 characters per raid.\nFormat: `Name, ilvl, Class`\nType `done` when finished with that raid, or `skip` to skip the raid.")

        seen_characters = set()

        for raid in RAID_MIN_ILVLS:
            await user.send(f"Enter characters for **{raid}** or type `skip` to skip.")

            characters = []
            while len(characters) < 12:
                msg = await bot.wait_for('message', check=check, timeout=300)
                content = msg.content.strip().lower()
                if content == "done":
                    break
                if content == "skip":
                    characters = []
                    break

                try:
                    name, ilvl, class_name = map(str.strip, msg.content.split(","))
                    ilvl = int(ilvl)
                    char_key = f"{name.lower()}:{raid}"
                    if char_key in seen_characters:
                        await user.send(f"⚠️ `{name}` already submitted for **{raid}**. Skipping duplicate.")
                        continue
                    if ilvl < RAID_MIN_ILVLS[raid]:
                        await user.send(f"⚠️ `{name}` does not meet the ilvl for **{raid}** ({RAID_MIN_ILVLS[raid]}).")
                        continue
                    seen_characters.add(char_key)
                    characters.append({"name": name, "ilvl": ilvl, "class": class_name})
                    await user.send(f"✅ Added: {name}, {ilvl}, {class_name}")
                except ValueError:
                    await user.send("❌ Invalid format. Please use: `Name, ilvl, Class`")

            if characters:
                db[user.id]["raids"][raid] = characters

        await user.send("✅ All character submissions complete. Thanks!")

        summary = ""
        for raid, chars in db[user.id]["raids"].items():
            summary += f"\n**{raid}**:\n" + "\n".join([f"- {c['name']} ({c['class']}, {c['ilvl']})" for c in chars])
        await user.send(f"Here’s what you submitted:\n{summary}")

    except Exception as e:
        await user.send(f"An error occurred: {e}")

@tasks.loop(time=datetime.now().replace(hour=20, minute=0, second=0, microsecond=0))
async def schedule_raid():
    raid_groups = {raid: [] for raid in RAID_MIN_ILVLS.keys()}
    used_users_per_raid = {raid: set() for raid in RAID_MIN_ILVLS}
    used_characters = set()

    for user_id, data in db.items():
        availability = data["availability"]
        for raid, characters in data["raids"].items():
            if user_id in used_users_per_raid[raid]:
                continue
            for character in characters:
                char_id = (character['name'].lower(), raid)
                if char_id in used_characters:
                    continue
                for day, times in availability.items():
                    for time in times:
                        raid_groups[raid].append(f"User {user_id} - {character['name']} ({character['class']}) @ {day} {time}")
                        used_users_per_raid[raid].add(user_id)
                        used_characters.add(char_id)
                        break
                    if user_id in used_users_per_raid[raid]:
                        break
                if user_id in used_users_per_raid[raid]:
                    break

    await send_to_server(raid_groups["Brelshaza Hardmode"], 1340771270693879859)
    await send_to_server(raid_groups["Brelshaza Normal"], 1330603021729533962)
    await send_to_server(raid_groups["Aegir Hardmode"], 1318262633811673158)
    await send_to_server(raid_groups["Aegir Normal"], 1368333245183299634)

async def send_to_server(group: list, channel_id: int):
    channel = bot.get_channel(channel_id)
    raid_message = f"Raid scheduled:\n" + "\n".join(group)
    await channel.send(raid_message)

bot.run("YOUR_TOKEN")









