import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime, timedelta, time
import json

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

class CharacterModal(discord.ui.Modal, title="Add Character"):
    name = discord.ui.TextInput(label="Character Name", max_length=32)
    ilvl = discord.ui.TextInput(label="Item Level", max_length=5)
    class_name = discord.ui.TextInput(label="Class", max_length=32)

    def __init__(self, user_id, raid):
        super().__init__()
        self.user_id = user_id
        self.raid = raid

    async def on_submit(self, interaction: discord.Interaction):
        name = self.name.value.strip()
        try:
            ilvl = int(self.ilvl.value.strip())
        except ValueError:
            await interaction.response.send_message("❌ Invalid ilvl. Must be a number.", ephemeral=True)
            return
        class_name = self.class_name.value.strip()

        if ilvl < RAID_MIN_ILVLS[self.raid]:
            await interaction.response.send_message(f"❌ ilvl too low for {self.raid} (min {RAID_MIN_ILVLS[self.raid]})", ephemeral=True)
            return

        char_key = f"{name.lower()}:{self.raid}"
        if char_key in db[self.user_id].get("characters", {}):
            await interaction.response.send_message(f"⚠️ `{name}` already submitted for {self.raid}.", ephemeral=True)
            return

        db[self.user_id]["characters"].setdefault(char_key, {"name": name, "ilvl": ilvl, "class": class_name})
        db[self.user_id]["raids"].setdefault(self.raid, []).append({"name": name, "ilvl": ilvl, "class": class_name})
        await interaction.response.send_message(f"✅ Added {name} ({ilvl}, {class_name}) to {self.raid}.", ephemeral=True)

class AddCharacterView(discord.ui.View):
    def __init__(self, user_id, raid):
        super().__init__(timeout=300)
        self.user_id = user_id
        self.raid = raid

    @discord.ui.button(label="Add Character", style=discord.ButtonStyle.primary)
    async def add_char(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(CharacterModal(self.user_id, self.raid))

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
    now_st = datetime.utcnow() + timedelta(hours=2)
    if now_st.weekday() == 0 and now_st.hour >= 19:
        db[user_id] = {"availability": {}, "raids": {}, "characters": db.get(user_id, {}).get("characters", {})}
        await interaction.response.send_message("Select your availability per day (time range):", ephemeral=True)

        for day in DAYS:
            view = discord.ui.View(timeout=300)

            class StartTime(discord.ui.Select):
                def __init__(self):
                    options = [discord.SelectOption(label=t, value=t) for t in TIME_INTERVALS]
                    super().__init__(placeholder=f"{day} start time", options=options, custom_id=f"start_{day}")

                async def callback(self, select_interaction: discord.Interaction):
                    start_time = self.values[0]
                    end_view = discord.ui.View(timeout=300)

                    class EndTime(discord.ui.Select):
                        def __init__(self):
                            options = [discord.SelectOption(label=t, value=t) for t in TIME_INTERVALS if t > start_time]
                            super().__init__(placeholder=f"{day} end time", options=options, custom_id=f"end_{day}")

                        async def callback(self2, select_interaction2: discord.Interaction):
                            end_time = self2.values[0]
                            time_range = [t for t in TIME_INTERVALS if start_time <= t <= end_time]
                            db[user_id]["availability"][day] = time_range
                            await select_interaction2.response.send_message(f"Saved availability for {day}: {start_time}–{end_time} ST.", ephemeral=True)

                    end_view.add_item(EndTime())
                    await select_interaction.followup.send(view=end_view, ephemeral=True)

            view.add_item(StartTime())
            await interaction.followup.send(view=view, ephemeral=True)

        await interaction.followup.send("Now adding characters. Use the buttons below to add for each raid.", ephemeral=True)
        for raid in RAID_MIN_ILVLS:
            await interaction.followup.send(f"➕ Add characters for **{raid}**:", view=AddCharacterView(user_id, raid), ephemeral=True)
    else:
        await interaction.response.send_message("⛔ Homework submission is only open from Monday 19:00 ST to Tuesday 20:00 ST.", ephemeral=True)

@tasks.loop(time=time(20, 0))
async def schedule_raid():
    now_utc = datetime.utcnow()
    now_st = now_utc + timedelta(hours=2)
    if now_st.weekday() != 1:
        return

    raid_groups = {raid: {} for raid in RAID_MIN_ILVLS}
    for user_id, data in db.items():
        availability = data.get("availability", {})
        for raid, characters in data.get("raids", {}).items():
            for character in characters:
                for day, times in availability.items():
                    for t in times:
                        key = f"{day} {t}"
                        raid_groups[raid].setdefault(key, []).append((user_id, character))

    for raid, time_slots in raid_groups.items():
        for time_slot, members in time_slots.items():
            supports = [m for uid, m in members if any(s in m['class'].lower() for s in SUPPORT_KEYWORDS)]
            dps = [m for uid, m in members if all(s not in m['class'].lower() for s in SUPPORT_KEYWORDS)]
            if len(supports) >= 1 and len(dps) >= 3:
                group_msg = f"Raid: {raid} @ {time_slot} ST\n"
                group_msg += "\n".join([f"- {m['name']} ({m['class']}, {m['ilvl']})" for uid, m in members])
                channel_id = get_channel_id(raid)
                if channel_id:
                    await send_to_server(group_msg, channel_id)

    await handle_fixed_brelshaza()

@tasks.loop(time=time(18, 0))
async def reset_entries():
    for user_id in db:
        db[user_id]["availability"] = {}
        db[user_id]["raids"] = {}
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











