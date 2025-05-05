import discord
import os
from discord import app_commands
from discord.ext import commands, tasks
from datetime import datetime, timedelta, timezone
import pytz
import json
from flask import Flask
import threading

# 🌐 Start dummy web server for Render
app = Flask(__name__)
@app.route('/')
def home():
    return "Bot is alive!"

def run_web():
    app.run(host='0.0.0.0', port=8080)

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="/", intents=intents)
tree = bot.tree

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

SUPPORT_PLAYERS = ["kenkixdd", "zitroone"]
SUPPORT_KEYWORDS = ["bard", "paladin", "artist"]

SAVE_FILE = "homework_data.json"

homework_availability = {}
previous_characters = {}
raid_groupings = {}

CHANNEL_IDS = {
    "brel_n": 1330603021729533962,
    "aegir_n": 1368333245183299634,
    "aegir_h": 1318262633811673158,
    "brel_hm": 1340771270693879859
}

TZ = timezone(timedelta(hours=2))

MIN_ILVL = {
    "aegir_n": 1660,
    "brel_n": 1670,
    "aegir_h": 1680
}

# Load data
if os.path.exists(SAVE_FILE):
    with open(SAVE_FILE, "r") as f:
        try:
            data = json.load(f)
            homework_availability = data.get("homework_availability", {})
            previous_characters = data.get("previous_characters", {})
        except Exception:
            print("⚠️ Failed to load saved data.")

def save_data():
    with open(SAVE_FILE, "w") as f:
        json.dump({
            "homework_availability": homework_availability,
            "previous_characters": previous_characters
        }, f)

class ConfirmView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.success)
    async def accept_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("✅ You have accepted your raid assignment!", ephemeral=True)

class RaidSelect(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.select(placeholder="Select a raid to register for", min_values=1, max_values=1, options=[
        discord.SelectOption(label="Brelshaza Normal", value="brel_n"),
        discord.SelectOption(label="Aegir Normal", value="aegir_n"),
        discord.SelectOption(label="Aegir Hardmode", value="aegir_h"),
    ])
    async def select_callback(self, interaction: discord.Interaction, select: discord.ui.Select):
        await interaction.response.send_message(f"Use `/homework raid:{select.values[0]} characters:<Class Ilvl Class Ilvl>` to register.", ephemeral=True)

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    try:
        synced = await tree.sync()
        print(f"🔧 Synced {len(synced)} command(s)")
    except Exception as e:
        print(f"❌ Sync failed: {e}")
    reset_task.start()
    group_generation_task.start()
    monday_reminder.start()

@tasks.loop(minutes=10)
async def reset_task():
    now = datetime.now(TZ)
    if now.weekday() == 0 and now.hour == 18 and 0 <= now.minute < 10:
        for user, data in homework_availability.items():
            if isinstance(data, dict):
                previous_characters[user] = data.get("characters", [])
        homework_availability.clear()
        save_data()
        for user in previous_characters:
            member = discord.utils.get(bot.get_all_members(), name=user)
            if member:
                try:
                    char_list = ", ".join(c["character"] for c in previous_characters[user])
                    await member.send(f"🔄 New week! Reuse these characters? {char_list}\nRegister again using /homework.")
                except Exception:
                    pass

@tasks.loop(minutes=5)
async def group_generation_task():
    now = datetime.now(TZ)
    if now.weekday() == 1 and now.hour == 20 and 0 <= now.minute < 5:
        await generate_groups("brel_hm")
        for raid in ["brel_n", "aegir_n", "aegir_h"]:
            await generate_groups(raid)
        for raid, groups in raid_groupings.items():
            for group in groups:
                for p in group:
                    member = discord.utils.get(bot.get_all_members(), name=p["user"])
                    if member:
                        try:
                            await member.send(
                                f"📌 Group for **{raid.upper()}** on {p['day']} at {p['start_time']} ST with {p['character']}.",
                                view=ConfirmView()
                            )
                        except Exception:
                            pass

@tasks.loop(hours=1)
async def monday_reminder():
    now = datetime.now(TZ)
    if now.weekday() == 0 and now.hour == 19:
        for guild in bot.guilds:
            for member in guild.members:
                if not member.bot:
                    try:
                        await member.send("📢 Reminder: Register availability and characters using /homework_availability and /homework. Deadline: Tuesday 8PM ST!")
                    except Exception:
                        pass

@tree.command(name="homework_availability", description="Set your general availability for homework raids")
@app_commands.describe(entries="Multiple entries as 'Day Start End, Day Start End'")
async def homework_availability_cmd(interaction: discord.Interaction, entries: str):
    username = interaction.user.name
    availability_list = []
    try:
        for entry in entries.split(","):
            parts = entry.strip().split()
            if len(parts) != 3:
                raise ValueError("Invalid entry")
            availability_list.append({"day": parts[0], "start_time": parts[1], "end_time": parts[2]})
    except Exception:
        await interaction.response.send_message("❌ Invalid format.", ephemeral=True)
        return

    if username not in homework_availability:
        homework_availability[username] = {}
    homework_availability[username]["availability"] = availability_list
    homework_availability[username].setdefault("characters", [])
    save_data()
    await interaction.response.send_message(f"✅ {username}'s availability set.", ephemeral=True)

@tree.command(name="homework", description="Add characters for a specific raid")
@app_commands.choices(raid=[
    app_commands.Choice(name="Brelshaza Normal", value="brel_n"),
    app_commands.Choice(name="Aegir Normal", value="aegir_n"),
    app_commands.Choice(name="Aegir Hardmode", value="aegir_h"),
])
@app_commands.describe(characters="e.g. 'Souleater 1670 Artillerist 1680'")
async def homework(interaction: discord.Interaction, raid: app_commands.Choice[str], characters: str):
    username = interaction.user.name
    raid_value = raid.value

    if username not in homework_availability:
        await interaction.response.send_message("❌ Use /homework_availability first.", ephemeral=True)
        return

    char_list = []
    try:
        parts = characters.strip().split()
        for i in range(0, len(parts), 2):
            char = parts[i]
            ilvl = int(parts[i + 1])
            if ilvl < MIN_ILVL[raid_value]:
                await interaction.response.send_message(f"❌ {char} does not meet ilvl requirement for {raid_value}.", ephemeral=True)
                return
            char_list.append({"character": char, "ilvl": ilvl, "raid": raid_value})
    except Exception:
        await interaction.response.send_message("❌ Invalid character input.", ephemeral=True)
        return

    homework_availability[username]["characters"].extend(char_list)
    save_data()
    await interaction.response.send_message(f"✅ Registered {len(char_list)} characters for {raid_value}.", ephemeral=True)

# 🟢 Launch web server and bot
if __name__ == "__main__":
    threading.Thread(target=run_web).start()
    bot.run(os.getenv("DISCORD_BOT_TOKEN"))






