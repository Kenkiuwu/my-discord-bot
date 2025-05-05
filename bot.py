import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime, timedelta, time
import json
import os

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

def load_db():
    global db
    if os.path.exists(SAVE_FILE):
        with open(SAVE_FILE, "r") as f:
            db = json.load(f)
    else:
        db = {}

def save_db():
    with open(SAVE_FILE, "w") as f:
        json.dump(db, f, indent=2)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    load_db()
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} commands")
    except Exception as e:
        print(f"Error syncing commands: {e}")

@bot.tree.command(name="homework", description="Submit weekly homework availability and character info.")
async def homework(interaction: discord.Interaction):
    user_id = interaction.user.id
    now_st = datetime.utcnow() + timedelta(hours=2)
    if now_st.weekday() == 0 and now_st.hour >= 19:  # Monday 19:00 ST
        db[user_id] = {"availability": {}, "raids": {}, "characters": db.get(user_id, {}).get("characters", {})}
        await interaction.response.send_message("Check your DMs to enter availability.", ephemeral=True)

        try:
            await interaction.user.send("Let's go day-by-day to set your availability.")
            for day in DAYS:
                await ask_availability_day(interaction.user, day)
        except discord.Forbidden:
            await interaction.followup.send("❌ I couldn't DM you. Please enable DMs from server members.", ephemeral=True)
            return

        await interaction.followup.send("Now collecting your characters per raid. Please check your DMs.", ephemeral=True)
        await collect_character_info(interaction.user)
    else:
        await interaction.response.send_message("⛔ Homework submission is only open from Monday 19:00 ST to Tuesday 20:00 ST.", ephemeral=True)

async def ask_availability_day(user: discord.User, day: str):
    class StartEndView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=300)
            self.start_time = None
            self.end_time = None

            self.start_select = discord.ui.Select(
                placeholder="Start Time",
                options=[discord.SelectOption(label=t) for t in TIME_INTERVALS]
            )
            self.end_select = discord.ui.Select(
                placeholder="End Time",
                options=[discord.SelectOption(label=t) for t in TIME_INTERVALS]
            )

            self.start_select.callback = self.start_callback
            self.end_select.callback = self.end_callback

            self.add_item(self.start_select)
            self.add_item(self.end_select)

        async def start_callback(self, interaction: discord.Interaction):
            self.start_time = self.start_select.values[0]
            await interaction.response.send_message(f"Start time set: {self.start_time}", ephemeral=True)

        async def end_callback(self, interaction: discord.Interaction):
            self.end_time = self.end_select.values[0]
            if self.start_time and self.end_time > self.start_time:
                time_range = [t for t in TIME_INTERVALS if self.start_time <= t <= self.end_time]
                db[user.id]["availability"][day] = time_range
                save_db()
                await interaction.response.send_message(f"✅ Saved availability for {day}: {self.start_time}–{self.end_time} ST.", ephemeral=True)
                self.stop()
            else:
                await interaction.response.send_message("❌ End time must be after start time.", ephemeral=True)

    view = StartEndView()
    await user.send(f"Select your availability for **{day}**:")
    await user.send(view=view)
    await view.wait()

async def collect_character_info(user: discord.User):
    def check(m):
        return m.author == user and isinstance(m.channel, discord.DMChannel)

    try:
        await user.send("Enter characters per raid (up to 12).\nFormat: `Name, ilvl, Class`\nType `done` or `skip`.")

        seen_characters = set()
        db[user.id]["characters"] = db.get(user.id, {}).get("characters", {})

        for raid in RAID_MIN_ILVLS:
            await user.send(f"Enter for **{raid}**:")
            characters = []
            while len(characters) < 12:
                msg = await bot.wait_for('message', check=check, timeout=300)
                content = msg.content.strip().lower()
                if content in ["done", "skip"]:
                    break
                try:
                    name, ilvl, class_name = map(str.strip, msg.content.split(","))
                    ilvl = int(ilvl)
                    char_key = f"{name.lower()}:{raid}"
                    if char_key in seen_characters:
                        await user.send(f"⚠️ `{name}` already submitted for **{raid}**.")
                        continue
                    if ilvl < RAID_MIN_ILVLS[raid]:
                        await user.send(f"⚠️ `{name}` ilvl too low for **{raid}**.")
                        continue
                    seen_characters.add(char_key)
                    characters.append({"name": name, "ilvl": ilvl, "class": class_name})
                    db[user.id]["characters"][char_key] = {"name": name, "ilvl": ilvl, "class": class_name}
                    await user.send(f"✅ Added: {name}, {ilvl}, {class_name}")
                except ValueError:
                    await user.send("❌ Invalid format. Use: `Name, ilvl, Class`")
            if characters:
                db[user.id]["raids"][raid] = characters

        save_db()
        await user.send("✅ Character submission complete.")
    except Exception as e:
        await user.send(f"An error occurred: {e}")

@tasks.loop(time=time(20, 0))
async def schedule_raid():
    now_utc = datetime.utcnow()
    now_st = now_utc + timedelta(hours=2)
    if now_st.weekday() != 1:  # Only run on Tuesday
        return

    raid_groups = {raid: {} for raid in RAID_MIN_ILVLS.keys()}
    for user_id, data in db.items():
        availability = data.get("availability", {})
        for raid, characters in data.get("raids", {}).items():
            for character in characters:
                for day, times in availability.items():
                    for t in times:
                        key = f"{day} {t}"
                        if key not in raid_groups[raid]:
                            raid_groups[raid][key] = []
                        raid_groups[raid][key].append((user_id, character))

    for raid, time_slots in raid_groups.items():
        for time_slot, members in time_slots.items():
            supports = [m for uid, m in members if any(s in m['class'].lower() for s in SUPPORT_KEYWORDS)]
            dps = [m for uid, m in members if all(s not in m['class'].lower() for s in SUPPORT_KEYWORDS)]
            if len(supports) >= 1 and len(dps) >= 3:
                group_msg = f"Raid: {raid} @ {time_slot} ST\n"
                group_msg += "\n".join([
                    f"- {m['name']} ({m['class']}, {m['ilvl']}) [{bot.get_user(uid).display_name if bot.get_user(uid) else 'Unknown'}]"
                    for uid, m in members
                ])
                channel_id = get_channel_id(raid)
                if channel_id:
                    await send_to_server(group_msg, channel_id)

    await handle_fixed_brelshaza()

@tasks.loop(time=time(18, 0))
async def reset_entries():
    for user_id in db:
        db[user_id]["availability"] = {}
        db[user_id]["raids"] = {}
    save_db()
    print("✅ Entries reset (except characters)")

def get_channel_id(raid):
    return {
        "Brelshaza Normal": 1330603021729533962,
        "Aegir Hardmode": 1318262633811673158,
        "Aegir Normal": 1368333245183299634,
    }.get(raid)

async def handle_fixed_brelshaza():
    fixed_msg = "Fixed Roster: Brelshaza Hardmode (ST 20:00 Wednesday)\n"
    for name, cls in FIXED_ROSTER.items():
        fixed_msg += f"- {name} ({cls})\n"
    channel = bot.get_channel(1340771270693879859)
    await channel.send(fixed_msg)

async def send_to_server(group: str, channel_id: int):
    channel = bot.get_channel(channel_id)
    await channel.send(group)

schedule_raid.start()
reset_entries.start()

bot.run("YOUR_TOKEN")











