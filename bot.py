import discord
from discord.ext import commands, tasks
from datetime import datetime, timedelta
import json
import os
import flask
from threading import Thread
from typing import Literal

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

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
SUPPORT_KEYWORDS = ["Bard", "Paladin", "Artist"]
SAVE_FILE = "availability_data.json"
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

GUILD_ID = 1038251775662243870
GUILD = discord.Object(id=GUILD_ID)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    keep_alive()
    generate_groups.start()

    try:
        bot.tree.clear_commands(guild=GUILD)
        synced = await bot.tree.sync(guild=GUILD)
        print(f"Synced {len(synced)} command(s) to guild {GUILD_ID}.")
    except Exception as e:
        print(f"Command sync failed: {e}")

class ContinueAddingView(discord.ui.View):
    def __init__(self, user: discord.User, raid: str):
        super().__init__(timeout=60)
        self.user = user
        self.raid = raid

    @discord.ui.button(label="Add Another Character", style=discord.ButtonStyle.primary)
    async def add_more(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(CharacterModal(self.user, self.raid))
        self.stop()

    @discord.ui.button(label="Done", style=discord.ButtonStyle.secondary)
    async def done(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Finished adding characters.", ephemeral=True)
        self.stop()

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

        await interaction.response.send_message(
            f"Added {self.name.value} to {self.raid}.",
            view=ContinueAddingView(self.user, self.raid),
            ephemeral=True
        )

class FirstModal(discord.ui.Modal, title="Availability (Wed-Sun)"):
    def __init__(self, user):
        super().__init__()
        self.user = user
        self.add_item(discord.ui.TextInput(label="Wednesday Start (HH:MM)", required=False))
        self.add_item(discord.ui.TextInput(label="Wednesday End (HH:MM)", required=False))
        self.add_item(discord.ui.TextInput(label="Thursday Start (HH:MM)", required=False))
        self.add_item(discord.ui.TextInput(label="Thursday End (HH:MM)", required=False))
        self.add_item(discord.ui.TextInput(label="Friday Start (HH:MM)", required=False))
        self.add_item(discord.ui.TextInput(label="Friday End (HH:MM)", required=False))

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.send_modal(SecondModal(self.user, self.children))

class SecondModal(discord.ui.Modal, title="Availability (Sat-Sun)"):
    def __init__(self, user, first_inputs):
        super().__init__()
        self.user = user
        self.first_inputs = first_inputs
        self.add_item(discord.ui.TextInput(label="Saturday Start (HH:MM)", required=False))
        self.add_item(discord.ui.TextInput(label="Saturday End (HH:MM)", required=False))
        self.add_item(discord.ui.TextInput(label="Sunday Start (HH:MM)", required=False))
        self.add_item(discord.ui.TextInput(label="Sunday End (HH:MM)", required=False))

    async def on_submit(self, interaction: discord.Interaction):
        try:
            uid = str(self.user.id)
            if uid not in db:
                db[uid] = {}
            times = []
            entries = list(self.first_inputs) + list(self.children)
            for i, day in enumerate(DAYS):
                start = entries[i * 2].value
                end = entries[i * 2 + 1].value
                if start and end:
                    try:
                        s = datetime.strptime(start, "%H:%M")
                        e = datetime.strptime(end, "%H:%M")
                        while s <= e:
                            times.append(f"{day} {s.strftime('%H:%M')}")
                            s += timedelta(minutes=30)
                    except: continue
            db[uid]["times"] = times
            db[uid]["display_name"] = self.user.display_name
            with open(SAVE_FILE, "w") as f:
                json.dump(db, f, indent=2)
            await interaction.response.send_message("Availability saved! Use /add_character to register characters.", ephemeral=True)
        except Exception as e:
            print(e)
            await interaction.response.send_message("Error saving availability.", ephemeral=True)

@bot.tree.command(name="availability", description="Set weekly availability for all raids", guild=GUILD)
async def availability(interaction: discord.Interaction):
    try:
        await interaction.response.send_modal(FirstModal(interaction.user))
    except Exception as e:
        print(f"Error in availability command: {e}")
        await interaction.response.send_message("Could not open availability modal.", ephemeral=True)

@bot.tree.command(name="clear_availability", description="Clear only your availability times", guild=GUILD)
async def clear_availability(interaction: discord.Interaction):
    uid = str(interaction.user.id)
    if uid in db and "times" in db[uid]:
        db[uid].pop("times")
        with open(SAVE_FILE, "w") as f:
            json.dump(db, f, indent=2)
        await interaction.response.send_message("Your availability times have been cleared.", ephemeral=True)
    else:
        await interaction.response.send_message("You have no availability times to clear.", ephemeral=True)

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

        for user, user_data in db.items():
            if "times" not in user_data or raid not in user_data or "characters" not in user_data[raid]:
                continue

            display_name = user_data.get("display_name", user)
            for t in user_data["times"]:
                if t not in time_availability:
                    time_availability[t] = []
                for c in user_data[raid]["characters"]:
                    time_availability[t].append((display_name, c))

        for time_slot in sorted(time_availability.keys()):
            users_chars = time_availability[time_slot]
            characters = []
            for display_name, c in users_chars:
                if isinstance(c, dict) and "class" in c and "name" in c and "ilvl" in c:
                    characters.append({"owner": display_name, **c})
            full, partial = group_characters(characters)

            if full or partial:
                output += f"\n**{raid} - {time_slot}**\n"
                for i, group in enumerate(full):
                    output += f"Full Group {i+1}: " + ", ".join(
                        f"{c['name']} ({c['class']}, {c['owner']})" for c in group
                    ) + "\n"
                for i, group in enumerate(partial):
                    output += f"Partial Group {i+1}: " + ", ".join(
                        f"{c['name']} ({c['class']}, {c['owner']})" for c in group
                    ) + "\n"
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
        channel = bot.get_channel(1368251474286612500)
        if channel:
            await channel.send(post_brel_hm_group())
            await channel.send("\n**Homework Raid Groups:**\n")
            await channel.send(generate_homework_groups())

@bot.tree.command(name="add_character", description="Add a character to a raid")
async def add_character(interaction: discord.Interaction, raid: Literal["Aegir Normal", "Brelshaza Normal", "Aegir Hardmode"]):
    await interaction.response.send_modal(CharacterModal(interaction.user, raid))

if __name__ == "__main__":
    import asyncio
    async def main():
        async with bot:
            await bot.start(os.getenv("DISCORD_BOT_TOKEN"))
    asyncio.run(main())





















