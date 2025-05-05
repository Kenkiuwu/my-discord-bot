import discord
import os
from discord import app_commands
from discord.ext import commands, tasks
from datetime import datetime, timedelta, timezone
import pytz

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="/", intents=intents)
tree = bot.tree

FIXED_ROSTER = [
    "kenkixdd", "zitroone", "pastacino", ".__james__.", "rareshandaric",
    "beaume", "matnam", "optitv"
]

homework_availability = {}
SUPPORT_KEYWORDS = ["bard", "paladin", "artist"]
previous_characters = {}

CHANNEL_IDS = {
    "brel_n": 1330603021729533962,
    "brel_hm": 1340771270693879859,
    "aegir_n": 1368333245183299634,
    "aegir_h": 1318262633811673158
}

raid_groupings = {}
TZ = timezone(timedelta(hours=2))

# 🔘 View with Accept Button
class ConfirmView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.success)
    async def accept_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("✅ You have accepted your raid assignment!", ephemeral=True)

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
        homework_availability.clear()
        for user, data in homework_availability.items():
            if isinstance(data, dict):
                previous_characters[user] = data.get("characters", [])
        for user in homework_availability:
            homework_availability[user]["characters"] = []

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

@tree.command(name="admin_view_groups", description="Admin: View current groupings for all raids")
@app_commands.checks.has_permissions(administrator=True)
async def admin_view_groups(interaction: discord.Interaction):
    if not raid_groupings:
        await interaction.response.send_message("📭 No groupings generated yet.", ephemeral=True)
        return

    message = "📋 **Current Raid Groupings:**\n"
    for raid, groups in raid_groupings.items():
        message += f"\n**{raid.upper()}**:\n"
        for i, group in enumerate(groups, start=1):
            message += f"🔹 Group {i}:\n"
            for p in group:
                message += f"- {p['display_name']} | {p['character']} ({p['day']} at {p['start_time']} ST)\n"
    await interaction.response.send_message(message, ephemeral=True)

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

    homework_availability[username] = {"availability": availability_list, "characters": []}
    await interaction.response.send_message(f"✅ {username}'s availability set for {len(availability_list)} sessions")

@tree.command(name="update_availability", description="Update your availability for raids")
@app_commands.describe(entries="Multiple entries as 'Day Start End, Day Start End'")
async def update_availability(interaction: discord.Interaction, entries: str):
    username = interaction.user.name
    if username not in homework_availability:
        await interaction.response.send_message("❌ Use /homework_availability first.", ephemeral=True)
        return

    new_availability = []
    try:
        for entry in entries.split(","):
            parts = entry.strip().split()
            if len(parts) != 3:
                raise ValueError("Invalid entry")
            new_availability.append({"day": parts[0], "start_time": parts[1], "end_time": parts[2]})
    except Exception:
        await interaction.response.send_message("❌ Invalid format.", ephemeral=True)
        return

    homework_availability[username]["availability"] = new_availability
    await interaction.response.send_message(f"✅ {username}'s availability updated.")

@tree.command(name="homework", description="Add characters for a specific raid")
@app_commands.describe(raid="Raid name", characters="Characters and ilvl, e.g. 'Souleater 1670 Artillerist 1680'")
async def homework(interaction: discord.Interaction, raid: str, characters: str):
    username = interaction.user.name
    if username not in homework_availability:
        await interaction.response.send_message("❌ Use /homework_availability first", ephemeral=True)
        return

    char_list = []
    try:
        parts = characters.strip().split()
        for i in range(0, len(parts), 2):
            char_list.append({"character": parts[i], "ilvl": parts[i + 1], "raid": raid})
    except Exception:
        await interaction.response.send_message("❌ Invalid format.", ephemeral=True)
        return

    homework_availability[username]["characters"].extend(char_list)
    await interaction.response.send_message(f"✅ Registered {len(char_list)} characters for {raid}.")

def time_conflict(start1, end1, start2, end2):
    fmt = "%H:%M"
    s1 = datetime.strptime(start1, fmt)
    e1 = datetime.strptime(end1, fmt)
    s2 = datetime.strptime(start2, fmt)
    e2 = datetime.strptime(end2, fmt)
    return abs((s1 - e2).total_seconds()) < 2700 or abs((s2 - e1).total_seconds()) < 2700

async def generate_groups(raid):
    entries = []
    for user, data in homework_availability.items():
        for char in data.get("characters", []):
            if char["raid"] != raid:
                continue
            for slot in data.get("availability", []):
                member = discord.utils.get(bot.get_all_members(), name=user)
                display_name = member.display_name if member else user
                entries.append({"user": user, "display_name": display_name, "character": char["character"], "ilvl": char["ilvl"], "day": slot["day"], "start_time": slot["start_time"]})

    supports = [e for e in entries if any(role in e["character"].lower() for role in SUPPORT_KEYWORDS)]
    dps = [e for e in entries if e not in supports]

    groups = []
    used = set()
    if raid == "brel_hm":
        group = []
        for user in FIXED_ROSTER:
            member = discord.utils.get(bot.get_all_members(), name=user)
            display_name = member.display_name if member else user
            group.append({"user": user, "display_name": display_name, "character": "Fixed Role", "ilvl": "TBD", "day": "Tuesday", "start_time": "20:00"})
        groups.append(group)
    else:
        for s in supports:
            if s["user"] in used:
                continue
            for s2 in supports:
                if s2["user"] in used or s2 == s:
                    continue
                for d in dps:
                    if d["user"] in used or d["day"] != s["day"] or d["start_time"] != s["start_time"]:
                        continue
                    group = [s, s2]
                    d_count = 0
                    for d2 in dps:
                        if d2["user"] in used or d2 == d:
                            continue
                        if d2["day"] == s["day"] and d2["start_time"] == s["start_time"]:
                            group.append(d2)
                            d_count += 1
                        if d_count == 6:
                            break
                    if len(group) == 8:
                        used.update(p["user"] for p in group)
                        groups.append(group)
                        break

    if not groups:
        return

    raid_groupings[raid] = groups
    result = ""
    for i, group in enumerate(groups, 1):
        day = group[0]["day"]
        time = group[0]["start_time"]
        raid_title = raid.replace("_", " ").title()
        result += f"\n📆 **{raid_title} {time} {day}:**\n"
        for p in group:
            result += f"{p['display_name']}({p['character']} {p['ilvl']})\n"

    channel_id = CHANNEL_IDS.get(raid)
    if channel_id:
        channel = bot.get_channel(channel_id)
        if channel:
            await channel.send(result)

bot.run(os.getenv("DISCORD_BOT_TOKEN"))


