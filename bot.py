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

    def __init__(self, user_id, raid, count, all_raids=None):
        super().__init__(timeout=300)
        self.user_id = user_id
        self.raid = raid
        self.count = count
        self.all_raids = all_raids or list(RAID_MIN_ILVLS.keys())

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
                await interaction.followup.send_modal(CharacterModal(self.user_id, self.raid, self.count + 1, self.all_raids))
            else:
                next_index = self.all_raids.index(self.raid) + 1
                if next_index < len(self.all_raids):
                    next_raid = self.all_raids[next_index]
                    await interaction.followup.send(f"Now adding characters for **{next_raid}**", ephemeral=True)
                    await interaction.followup.send_modal(CharacterModal(self.user_id, next_raid, 1, self.all_raids))
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

        first_raid = list(RAID_MIN_ILVLS.keys())[0]
        await interaction.followup.send(f"Now adding characters for **{first_raid}**", ephemeral=True)
        await interaction.followup.send_modal(CharacterModal(user_id, first_raid, 1))
    else:
        await interaction.response.send_message("⛔ Homework submission is only open from Monday 18:00 ST to Tuesday 20:00 ST.", ephemeral=True)

def is_support(class_name):
    return any(role in class_name.lower() for role in SUPPORT_KEYWORDS)

def get_display_name(user_id):
    user = bot.get_user(int(user_id))
    return user.display_name if user else user_id

def group_characters(characters):
    supports = [c for c in characters if is_support(c['class'])]
    dps = [c for c in characters if not is_support(c['class'])]

    groups = []
    used = set()

    # Full 8-man groups
    while len(supports) >= 2 and len(dps) >= 6:
        group = [supports.pop(), supports.pop()]
        group += [dps.pop() for _ in range(6)]
        groups.append(group)

    # Partial 4-man groups (1 support + 3 DPS)
    while len(supports) >= 1 and len(dps) >= 3:
        group = [supports.pop()]
        group += [dps.pop() for _ in range(3)]
        groups.append(group)

    return groups

@tasks.loop(minutes=1)
async def check_schedule():
    now = datetime.utcnow() + timedelta(hours=2)
    if now.weekday() == 1 and now.hour == 20 and now.minute == 0:  # Tuesday 20:00 ST
        await post_all_groups()

@check_schedule.before_loop
async def before_check():
    await bot.wait_until_ready()

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    check_schedule.start()

async def post_all_groups():
    channel_id = int(os.getenv("ANNOUNCE_CHANNEL_ID", "YOUR_CHANNEL_ID"))
    channel = bot.get_channel(channel_id)

    if channel is None:
        print("Error: Channel not found.")
        return

    await post_brelshaza_hardmode(channel)

    for raid in RAID_MIN_ILVLS.keys():
        await post_raid_groups(channel, raid)

async def post_brelshaza_hardmode(channel):
    embed = discord.Embed(title="🟣 Brelshaza Hardmode Group", color=0x9b59b6)
    for username, class_name in FIXED_ROSTER.items():
        display = get_display_name(username)
        embed.add_field(name=display, value=class_name, inline=True)
    await channel.send(embed=embed)

async def post_raid_groups(channel, raid_name):
    characters = []
    for user_data in db.values():
        for char in user_data.get("raids", {}).get(raid_name, []):
            characters.append(char)

    if not characters:
        return

    groups = group_characters(characters)
    for i, group in enumerate(groups):
        embed = discord.Embed(title=f"{raid_name} – Group {i+1}", color=0x3498db)
        for char in group:
            embed.add_field(name=char["name"], value=f"{char['class']} ({char['ilvl']})", inline=True)
        await channel.send(embed=embed)

bot.run(os.getenv("DISCORD_BOT_TOKEN"))
















