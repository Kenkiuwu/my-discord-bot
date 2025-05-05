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
available_times = []

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
            available_times = data.get("available_times", [])
            raid_groupings = data.get("raid_groupings", {})
        except Exception:
            print("⚠️ Failed to load saved data.")

def save_data():
    with open(SAVE_FILE, "w") as f:
        json.dump({
            "homework_availability": homework_availability,
            "previous_characters": previous_characters,
            "available_times": available_times,
            "raid_groupings": raid_groupings
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
        if not interaction.response.is_done():
            await interaction.response.send_message(
                f"Use `/homework raid:{select.values[0]}` and enter each character's name, class, and ilvl.", ephemeral=True
            )
        else:
            await interaction.followup.send(
                f"Use `/homework raid:{select.values[0]}` and enter each character's name, class, and ilvl.", ephemeral=True
            )

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
        for raid_name, time_slots in raid_groupings.items():
            channel_id = CHANNEL_IDS.get(raid_name)
            if not channel_id:
                continue
            channel = bot.get_channel(channel_id)
            if not channel:
                continue

            for time_key, group in time_slots.items():
                formatted_time = time_key.replace("_", " ")
                display_lines = []
                for user in group:
                    member = discord.utils.get(channel.guild.members, name=user)
                    username_to_display = member.display_name if member else f"{user} (not found)"
                    display_lines.append(f"- {username_to_display}")
                message = f"🗖️ **{raid_name.replace('_', ' ').title()} - {formatted_time}**\n" + "\n".join(display_lines)
                await channel.send(message)

@tree.command(name="homework_availability", description="Set your general availability for homework raids")
@app_commands.describe(entries="Multiple entries as 'Day Start End, Day Start End'")
async def homework_availability_cmd(interaction: discord.Interaction, entries: str):
    username = interaction.user.name
    display_name = interaction.user.display_name
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
    await interaction.response.send_message(f"✅ {display_name}'s availability set.", ephemeral=True)

@tree.command(name="homework", description="Add characters for a specific raid")
@app_commands.choices(raid=[
    app_commands.Choice(name="Brelshaza Normal", value="brel_n"),
    app_commands.Choice(name="Aegir Normal", value="aegir_n"),
    app_commands.Choice(name="Aegir Hardmode", value="aegir_h"),
])
@app_commands.describe(
    raid="Raid to register for",
    character1_name="Character 1 Name", character1_class="Character 1 Class", character1_ilvl="Character 1 ilvl",
    character2_name="Character 2 Name", character2_class="Character 2 Class", character2_ilvl="Character 2 ilvl",
    character3_name="Character 3 Name", character3_class="Character 3 Class", character3_ilvl="Character 3 ilvl"
)
async def homework(
    interaction: discord.Interaction,
    raid: app_commands.Choice[str],
    character1_name: str, character1_class: str, character1_ilvl: int,
    character2_name: str = None, character2_class: str = None, character2_ilvl: int = None,
    character3_name: str = None, character3_class: str = None, character3_ilvl: int = None
):
    username = interaction.user.name
    display_name = interaction.user.display_name
    raid_value = raid.value

    if username not in homework_availability:
        await interaction.response.send_message("❌ Use /homework_availability first.", ephemeral=True)
        return

    char_list = []
    inputs = [
        (character1_name, character1_class, character1_ilvl),
        (character2_name, character2_class, character2_ilvl),
        (character3_name, character3_class, character3_ilvl),
    ]

    for name, char_class, ilvl in inputs:
        if name and char_class and ilvl:
            if ilvl < MIN_ILVL[raid_value]:
                await interaction.response.send_message(
                    f"❌ {name} does not meet ilvl requirement for {raid.name} ({MIN_ILVL[raid_value]}).", ephemeral=True
                )
                return
            char_list.append({
                "character": name,
                "class": char_class,
                "ilvl": ilvl,
                "raid": raid_value
            })

    homework_availability[username]["characters"].extend(char_list)
    save_data()
    await interaction.response.send_message(f"✅ {display_name} registered {len(char_list)} characters for {raid.name}.", ephemeral=True)

# 🟢 Launch web server and bot
if __name__ == "__main__":
    threading.Thread(target=run_web).start()
    bot.run(os.getenv("DISCORD_BOT_TOKEN"))







