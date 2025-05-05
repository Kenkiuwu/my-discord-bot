import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime, timedelta
import json
import os
import flask
from threading import Thread

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
TIME_INTERVALS = [f"{hour:02}:{minute:02}" for hour in range(12, 24) for minute in (0, 30)]

SUPPORT_KEYWORDS = ["bard", "paladin", "artist"]
SAVE_FILE = "homework_data.json"
db = {}

if os.path.exists(SAVE_FILE):
    with open(SAVE_FILE, "r") as f:
        db = json.load(f)

class CharacterModal(discord.ui.Modal, title="Add Character"):
    name = discord.ui.TextInput(label="Character Name", required=True, max_length=20)
    char_class = discord.ui.TextInput(label="Class", required=True, max_length=20)
    ilvl = discord.ui.TextInput(label="Item Level", required=True)

    def __init__(self, user_id: str, raid: str):
        super().__init__()
        self.user_id = user_id
        self.raid = raid

    async def on_submit(self, interaction: discord.Interaction):
        try:
            ilvl = int(self.ilvl.value)
        except ValueError:
            await interaction.response.send_message("Invalid item level.", ephemeral=True)
            return

        if ilvl < RAID_MIN_ILVLS[self.raid]:
            await interaction.response.send_message(f"Item level too low for {self.raid}.", ephemeral=True)
            return

        user_entry = db.setdefault(self.raid, {}).setdefault(self.user_id, {"characters": [], "times": []})
        user_entry["characters"].append({
            "name": self.name.value,
            "class": self.char_class.value.lower(),
            "ilvl": ilvl
        })

        with open(SAVE_FILE, "w") as f:
            json.dump(db, f, indent=2)

        await interaction.response.send_message("Character added!", ephemeral=True)

class TimeSelect(discord.ui.Select):
    def __init__(self, raid):
        self.raid = raid
        options = [
            discord.SelectOption(label=f"{day} {time}", value=f"{day} {time}")
            for day in DAYS for time in TIME_INTERVALS
        ]
        super().__init__(placeholder="Select times you're available (max 5)", min_values=1, max_values=5, options=options)

    async def callback(self, interaction: discord.Interaction):
        db.setdefault(self.raid, {}).setdefault(str(interaction.user.id), {"characters": [], "times": []})
        db[self.raid][str(interaction.user.id)]["times"] = self.values

        with open(SAVE_FILE, "w") as f:
            json.dump(db, f, indent=2)

        await interaction.response.send_message("Times saved! Please use `/add_character` to add characters.", ephemeral=True)

class TimeSelectView(discord.ui.View):
    def __init__(self, raid):
        super().__init__()
        self.add_item(TimeSelect(raid))

@tree.command(name="homework", description="Register availability for a raid")
@app_commands.describe(raid="Which raid")
@app_commands.choices(raid=[
    app_commands.Choice(name="Aegir Normal", value="Aegir Normal"),
    app_commands.Choice(name="Aegir Hardmode", value="Aegir Hardmode"),
    app_commands.Choice(name="Brelshaza Normal", value="Brelshaza Normal"),
])
async def homework(interaction: discord.Interaction, raid: app_commands.Choice[str]):
    await interaction.response.send_message(
        f"Select the times you're available for **{raid.value}** this week:", 
        view=TimeSelectView(raid.value), ephemeral=True
    )

@tree.command(name="add_character", description="Add a character for a raid")
@app_commands.describe(raid="Which raid")
@app_commands.choices(raid=[
    app_commands.Choice(name="Aegir Normal", value="Aegir Normal"),
    app_commands.Choice(name="Aegir Hardmode", value="Aegir Hardmode"),
    app_commands.Choice(name="Brelshaza Normal", value="Brelshaza Normal"),
])
async def add_character(interaction: discord.Interaction, raid: app_commands.Choice[str]):
    await interaction.response.send_modal(CharacterModal(str(interaction.user.id), raid.value))

@tasks.loop(minutes=1)
async def auto_generate():
    now = datetime.utcnow() + timedelta(hours=2)
    if now.strftime("%A %H:%M") == "Tuesday 20:00":
        channel = discord.utils.get(bot.get_all_channels(), name="homework")
        if not channel:
            print("No #homework channel found.")
            return

        await channel.send("Generating groups...")

        await post_brelshaza_hardmode(channel)
        for raid in db:
            if raid != "Brelshaza Hardmode":
                await post_groups_for_raid(channel, raid)

async def post_brelshaza_hardmode(channel):
    members = "\n".join([f"{name} - {cls}" for name, cls in FIXED_ROSTER.items()])
    await channel.send("**Brelshaza Hardmode Fixed Group:**\n" + members)

async def post_groups_for_raid(channel, raid):
    users = db.get(raid, {})
    support_groups = []
    dps_pool = []

    for uid, entry in users.items():
        for char in entry["characters"]:
            role = "support" if any(k in char["class"] for k in SUPPORT_KEYWORDS) else "dps"
            d = {"uid": uid, "name": char["name"], "class": char["class"], "role": role}
            if role == "support":
                support_groups.append(d)
            else:
                dps_pool.append(d)

    full_groups = []
    while len(support_groups) >= 2 and len(dps_pool) >= 6:
        group = support_groups[:2] + dps_pool[:6]
        full_groups.append(group)
        support_groups = support_groups[2:]
        dps_pool = dps_pool[6:]

    for i, group in enumerate(full_groups, start=1):
        msg = f"**{raid} Group {i}:**\n"
        for m in group:
            member = await bot.fetch_user(int(m["uid"]))
            msg += f"- {member.display_name}: {m['name']} ({m['class']})\n"
        await channel.send(msg)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    try:
        await tree.sync()
    except Exception as e:
        print(f"Command sync failed: {e}")
    auto_generate.start()
    keep_alive()

# Flask to keep alive
app = flask.Flask('')

@app.route('/')
def home():
    return "Bot is alive!", 200

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

if __name__ == "__main__":
    bot.run(os.getenv("DISCORD_TOKEN"))

















