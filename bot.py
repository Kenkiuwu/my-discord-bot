import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime, timedelta, time
import json
import os
import flask
from threading import Thread
from typing import Literal

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="/", intents=intents)
tree = bot.tree

RAID_MIN_ILVLS = {
    "Brelshaza Normal": 1670,
    "Aegir Hardmode": 1680,
    "Aegir Normal": 1660,
}

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

DAYS = ["Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
SUPPORT_KEYWORDS = ["bard", "paladin", "artist"]
SAVE_FILE = "homework_data.json"
db = {}

if os.path.exists(SAVE_FILE):
    with open(SAVE_FILE, "r") as f:
        db = json.load(f)

# Flask server to keep bot alive
app = flask.Flask('')

@app.route('/')
def home():
    return "Bot is alive!", 200

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} commands")
    except Exception as e:
        print(f"Error syncing commands: {e}")
    keep_alive()
    generate_groups.start()

class CharacterModal(discord.ui.Modal, title="Add Character"):
    name = discord.ui.TextInput(label="Character Name", required=True)
    class_name = discord.ui.TextInput(label="Class", required=True)
    ilvl = discord.ui.TextInput(label="Item Level", required=True)

    def __init__(self, user: discord.User, raid: str):
        super().__init__()
        self.user = user
        self.raid = raid

    async def on_submit(self, interaction: discord.Interaction):
        uid = str(self.user.id)
        if uid not in db:
            db[uid] = {}
        if self.raid not in db[uid]:
            db[uid][self.raid] = {"characters": []}

        try:
            ilvl_val = int(self.ilvl.value)
        except ValueError:
            await interaction.response.send_message("Invalid item level.", ephemeral=True)
            return

        if ilvl_val < RAID_MIN_ILVLS[self.raid]:
            await interaction.response.send_message(f"Item level too low for {self.raid}.", ephemeral=True)
            return

        db[uid][self.raid]["characters"].append({
            "name": self.name.value,
            "class": self.class_name.value.lower(),
            "ilvl": ilvl_val
        })
        db[uid]["display_name"] = self.user.display_name

        with open(SAVE_FILE, "w") as f:
            json.dump(db, f, indent=2)

        await interaction.response.send_message(f"Added {self.name.value} to {self.raid}.", ephemeral=True)

class MultiDayTimeModal(discord.ui.Modal, title="Set Weekly Availability"):
    def __init__(self, user: discord.User):
        super().__init__()
        self.user = user
        for day in DAYS:
            self.add_item(discord.ui.TextInput(label=f"{day} Start Time (HH:MM)", required=False))
            self.add_item(discord.ui.TextInput(label=f"{day} End Time (HH:MM)", required=False))

    async def on_submit(self, interaction: discord.Interaction):
        uid = str(self.user.id)
        if uid not in db:
            db[uid] = {}

        times = []
        for i, day in enumerate(DAYS):
            start_input = self.children[i * 2].value
            end_input = self.children[i * 2 + 1].value

            if start_input and end_input:
                try:
                    start = datetime.strptime(start_input, "%H:%M")
                    end = datetime.strptime(end_input, "%H:%M")
                except ValueError:
                    continue
                current = start
                while current <= end:
                    times.append(f"{day} {current.strftime('%H:%M')}")
                    current += timedelta(minutes=30)

        db[uid]["times"] = times
        db[uid]["display_name"] = self.user.display_name

        with open(SAVE_FILE, "w") as f:
            json.dump(db, f, indent=2)

        await interaction.response.send_message("Availability times saved!", ephemeral=True)

@tree.command(name="homework")
async def homework(interaction: discord.Interaction):
    await interaction.response.send_modal(MultiDayTimeModal(interaction.user))

def is_support(class_name):
    return any(support in class_name.lower() for support in SUPPORT_KEYWORDS)

def group_characters(characters):
    full_groups = []
    partial_groups = []

    supports = [c for c in characters if is_support(c['class'])]
    dps = [c for c in characters if not is_support(c['class'])]

    while len(supports) >= 2 and len(dps) >= 6:
        group = supports[:2] + dps[:6]
        full_groups.append(group)
        supports = supports[2:]
        dps = dps[6:]

    while len(supports) >= 1 and len(dps) >= 3:
        group = supports[:1] + dps[:3]
        partial_groups.append(group)
        supports = supports[1:]
        dps = dps[3:]

    return full_groups, partial_groups

def generate_homework_groups():
    output = ""
    for raid in RAID_MIN_ILVLS:
        time_availability = {}

        for user, raids in db.items():
            if raid in raids and "characters" in raids[raid] and "times" in db[user]:
                for t in db[user]["times"]:
                    if t not in time_availability:
                        time_availability[t] = []
                    for c in raids[raid]["characters"]:
                        time_availability[t].append((user, c))

        for time_slot in sorted(time_availability.keys()):
            users_chars = time_availability[time_slot]
            characters = [c for _, c in users_chars]
            full, partial = group_characters(characters)

            if full or partial:
                output += f"\n**{raid} - {time_slot}**\n"
                for i, group in enumerate(full):
                    output += f"Full Group {i+1}: " + ", ".join(f"{c['name']} ({c['class']})" for c in group) + "\n"
                for i, group in enumerate(partial):
                    output += f"Partial Group {i+1}: " + ", ".join(f"{c['name']} ({c['class']})" for c in group) + "\n"
    return output or "No groups could be formed."

def post_brel_hm_group():
    output = "**Brelshaza Hardmode Fixed Group:**\n"
    for user, cls in FIXED_ROSTER.items():
        output += f"{user} ({cls})\n"
    return output

@tasks.loop(minutes=1)
async def generate_groups():
    now = datetime.utcnow() + timedelta(hours=2)
    if now.weekday() == 1 and now.hour == 20 and now.minute == 0:
        channel = discord.utils.get(bot.get_all_channels(), name="raid-planner")
        if channel:
            async def send_groups():
                await channel.send(post_brel_hm_group())
                await channel.send("\n**Homework Raid Groups:**\n")
                await channel.send(generate_homework_groups())
            bot.loop.create_task(send_groups())

@tree.command(name="add_character")
@app_commands.describe(raid="Select the raid")
async def add_character(interaction: discord.Interaction, raid: Literal["Aegir Normal", "Brelshaza Normal", "Aegir Hardmode"]):
    await interaction.response.send_modal(CharacterModal(interaction.user, raid))

if __name__ == "__main__":
    bot.run(os.getenv("DISCORD_TOKEN"))



















