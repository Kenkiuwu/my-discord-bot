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

    await interaction.response.send_message("Select your availability per day (time range):", ephemeral=True)

    for day in DAYS:
        view = discord.ui.View(timeout=300)

        class StartTime(discord.ui.Select):
            def __init__(self):
                options = [discord.SelectOption(label=time, value=time) for time in TIME_INTERVALS]
                super().__init__(placeholder=f"{day} start time", min_values=1, max_values=1, options=options, custom_id=f"start_{day}")

            async def callback(self, select_interaction: discord.Interaction):
                view.stop()
                start_time = self.values[0]
                await select_interaction.response.send_message(f"Start time selected: {start_time} ST. Now select end time.", ephemeral=True)

                end_view = discord.ui.View(timeout=300)

                class EndTime(discord.ui.Select):
                    def __init__(self):
                        options = [discord.SelectOption(label=time, value=time) for time in TIME_INTERVALS if time > start_time]
                        super().__init__(placeholder=f"{day} end time", min_values=1, max_values=1, options=options, custom_id=f"end_{day}")

                    async def callback(self2, select_interaction2: discord.Interaction):
                        end_time = self2.values[0]
                        time_range = []
                        for t in TIME_INTERVALS:
                            if start_time <= t <= end_time:
                                time_range.append(t)
                        db[user_id]["availability"][day] = time_range
                        await select_interaction2.response.send_message(f"Saved availability for {day}: {start_time}–{end_time} ST.", ephemeral=True)

                end_view.add_item(EndTime())
                await select_interaction.followup.send(view=end_view, ephemeral=True)

        view.add_item(StartTime())
        await interaction.followup.send(view=view, ephemeral=True)

    await interaction.followup.send("Now collecting your characters per raid. Please check your DMs.", ephemeral=True)
    await collect_character_info(interaction.user)

async def collect_character_info(user: discord.User):
    def check(m):
        return m.author == user and isinstance(m.channel, discord.DMChannel)

    try:
        await user.send("Enter characters per raid (up to 12).\nFormat: `Name, ilvl, Class`\nType `done` or `skip`.")

        seen_characters = set()

        for raid in RAID_MIN_ILVLS:
            await user.send(f"Enter for **{raid}**:")
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
                        await user.send(f"⚠️ `{name}` already submitted for **{raid}**.")
                        continue
                    if ilvl < RAID_MIN_ILVLS[raid]:
                        await user.send(f"⚠️ `{name}` ilvl too low for **{raid}**.")
                        continue
                    seen_characters.add(char_key)
                    characters.append({"name": name, "ilvl": ilvl, "class": class_name})
                    await user.send(f"✅ Added: {name}, {ilvl}, {class_name}")
                except ValueError:
                    await user.send("❌ Invalid format. Use: `Name, ilvl, Class`")
            if characters:
                db[user.id]["raids"][raid] = characters

        await user.send("✅ Character submission complete.")
    except Exception as e:
        await user.send(f"An error occurred: {e}")

@tasks.loop(minutes=30)
async def schedule_raid():
    now_utc = datetime.utcnow()
    now_st = now_utc + timedelta(hours=2)
    if now_st.time() < time(20, 0) or now_st.time() > time(20, 30):
        return

    raid_groups = {raid: {} for raid in RAID_MIN_ILVLS.keys()}
    for user_id, data in db.items():
        availability = data["availability"]
        for raid, characters in data["raids"].items():
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
                group_msg += "\n".join([f"- {m['name']} ({m['class']}, {m['ilvl']})" for uid, m in members])
                channel_id = get_channel_id(raid)
                if channel_id:
                    await send_to_server(group_msg, channel_id)

    await handle_fixed_brelshaza()

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

bot.run("YOUR_TOKEN")










