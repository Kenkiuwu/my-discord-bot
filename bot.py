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

if os.path.exists(SAVE_FILE):
    with open(SAVE_FILE, "r") as f:
        db = json.load(f)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} commands")
    except Exception as e:
        print(f"Error syncing commands: {e}")

class CharacterModal(discord.ui.Modal, title="Add a character"):
    name = discord.ui.TextInput(label="Character Name", max_length=30)
    ilvl = discord.ui.TextInput(label="Item Level", max_length=5)
    class_name = discord.ui.TextInput(label="Class", max_length=30)

    def __init__(self, user_id, raid, count):
        super().__init__(timeout=300)
        self.user_id = user_id
        self.raid = raid
        self.count = count

    async def on_submit(self, interaction: discord.Interaction):
        try:
            name = self.name.value.strip()
            ilvl = int(self.ilvl.value.strip())
            class_name = self.class_name.value.strip()

            if self.raid not in RAID_MIN_ILVLS:
                await interaction.response.send_message(f"❌ Raid **{self.raid}** is not a valid entry raid.", ephemeral=True)
                return

            if ilvl < RAID_MIN_ILVLS[self.raid]:
                await interaction.response.send_message(f"❌ `{name}` ilvl too low for **{self.raid}**.", ephemeral=True)
                return

            if self.user_id not in db:
                db[self.user_id] = {"availability": {}, "raids": {}, "characters": {}}

            char_key = f"{name.lower()}:{self.raid}"
            if char_key in db[self.user_id].get("characters", {}):
                await interaction.response.send_message(f"⚠️ `{name}` already submitted for **{self.raid}**.", ephemeral=True)
                return

            character = {"name": name, "ilvl": ilvl, "class": class_name}
            db[self.user_id].setdefault("characters", {})[char_key] = character
            db[self.user_id].setdefault("raids", {}).setdefault(self.raid, []).append(character)

            await interaction.response.send_message(f"✅ Added: {name}, {ilvl}, {class_name} for {self.raid}", ephemeral=True)
            if self.count < 12:
                await interaction.followup.send_modal(CharacterModal(self.user_id, self.raid, self.count + 1))
        except ValueError:
            await interaction.response.send_message("❌ Invalid item level.", ephemeral=True)

@tree.command(name="homework", description="Submit weekly homework availability and character info.")
async def homework(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    now_st = datetime.utcnow() + timedelta(hours=2)
    if now_st.weekday() == 0 and now_st.hour >= 18 or now_st.weekday() == 1 and now_st.hour < 20:
        db[user_id] = {"availability": {}, "raids": {}, "characters": db.get(user_id, {}).get("characters", {})}
        await interaction.response.send_message("Select your availability per day (time range):", ephemeral=True)

        for day in DAYS:
            view = discord.ui.View(timeout=300)

            class StartTime(discord.ui.Select):
                def __init__(self):
                    options = [discord.SelectOption(label=time, value=time) for time in TIME_INTERVALS]
                    super().__init__(placeholder=f"{day} start time", min_values=1, max_values=1, options=options)

                async def callback(self, select_interaction: discord.Interaction):
                    view.stop()
                    start_time = self.values[0]
                    await select_interaction.response.send_message(f"Start time selected: {start_time} ST. Now select end time.", ephemeral=True)

                    end_view = discord.ui.View(timeout=300)

                    class EndTime(discord.ui.Select):
                        def __init__(self):
                            options = [discord.SelectOption(label=time, value=time) for time in TIME_INTERVALS if time > start_time]
                            super().__init__(placeholder=f"{day} end time", min_values=1, max_values=1, options=options)

                        async def callback(self2, select_interaction2: discord.Interaction):
                            end_time = self2.values[0]
                            time_range = [t for t in TIME_INTERVALS if start_time <= t <= end_time]
                            db[user_id]["availability"][day] = time_range
                            await select_interaction2.response.send_message(f"Saved availability for {day}: {start_time}–{end_time} ST.", ephemeral=True)

                    end_view.add_item(EndTime())
                    await select_interaction.followup.send(view=end_view, ephemeral=True)

            view.add_item(StartTime())
            await interaction.followup.send(view=view, ephemeral=True)

        for raid in RAID_MIN_ILVLS:
            await interaction.followup.send(f"Now adding characters for **{raid}**", ephemeral=True)
            await interaction.followup.send_modal(CharacterModal(user_id, raid, 1))
    else:
        await interaction.response.send_message("⛔ Homework submission is only open from Monday 18:00 ST to Tuesday 20:00 ST.", ephemeral=True)

def get_channel_id(raid):
    return {
        "Brelshaza Normal": 1330603021729533962,
        "Aegir Hardmode": 1318262633811673158,
        "Aegir Normal": 1368333245183299634,
        "Brelshaza Hardmode": 1340771270693879859,
    }.get(raid)

async def handle_fixed_brelshaza():
    fixed_msg = "Fixed Roster: Brelshaza Hardmode (ST 20:00 Tuesday)\n"
    for name, cls in FIXED_ROSTER.items():
        fixed_msg += f"- {name} ({cls})\n"
    channel = bot.get_channel(get_channel_id("Brelshaza Hardmode"))
    await channel.send(fixed_msg)

async def send_to_server(group: str, channel_id: int):
    channel = bot.get_channel(channel_id)
    await channel.send(group)

@tasks.loop(time=time(20, 0))
async def schedule_raid():
    now_st = datetime.utcnow() + timedelta(hours=2)
    if now_st.weekday() != 1:
        return

    await handle_fixed_brelshaza()

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
            group_msg = f"Raid: {raid} @ {time_slot} ST\n"
            if len(supports) >= 1 and len(dps) >= 3 and len(members) >= 8:
                group_msg += "\n".join([f"- {m['name']} ({m['class']}, {m['ilvl']})" for uid, m in members])
                channel_id = get_channel_id(raid)
                if channel_id:
                    await send_to_server(group_msg, channel_id)
            elif len(supports) >= 1 and len(dps) >= 3:
                group_msg += "Partial Group (4+):\n"
                group_msg += "\n".join([f"- {m['name']} ({m['class']}, {m['ilvl']})" for uid, m in members])
                channel_id = get_channel_id(raid)
                if channel_id:
                    await send_to_server(group_msg, channel_id)

@tasks.loop(time=time(18, 0))
async def reset_entries():
    now_st = datetime.utcnow() + timedelta(hours=2)
    if now_st.weekday() != 0:
        return
    for user_id in db:
        db[user_id]["availability"] = {}
        db[user_id]["raids"] = {}
    with open(SAVE_FILE, "w") as f:
        json.dump(db, f)
    print("✅ Entries reset (except characters)")

@bot.event
async def setup_hook():
    schedule_raid.start()
    reset_entries.start()

bot.run("YOUR_TOKEN")












