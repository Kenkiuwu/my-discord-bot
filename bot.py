import discord
from discord.ext import commands, tasks
from discord import app_commands
import asyncio
import os  # <-- Needed for os.getenv
from scheduler import generate_homework_groups
from storage import HomeworkStorage

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

homework_storage = HomeworkStorage()

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    await tree.sync()
    schedule_group_generation.start()

@tree.command(name="homework", description="Submit your weekly availability and characters")
async def homework_command(interaction: discord.Interaction):
    await interaction.response.send_message("Check your DMs to submit your availability!", ephemeral=True)
    await homework_storage.collect_homework(interaction.user)

@tree.command(name="generate_groups", description="Manually trigger group generation")
@app_commands.checks.has_permissions(administrator=True)
async def generate_groups(interaction: discord.Interaction):
    await interaction.response.send_message("Generating groups...", ephemeral=True)
    groups = generate_homework_groups(homework_storage.get_all_homework())
    for group_msg in groups:
        await bot.get_channel(1368251474286612500).send(group_msg)

@tasks.loop(minutes=1)
async def schedule_group_generation():
    now = discord.utils.utcnow()
    if now.weekday() == 1 and now.hour == 20 and now.minute == 0:  # Tuesday 22:00 UTC+2
        groups = generate_homework_groups(homework_storage.get_all_homework())
        for group_msg in groups:
            await bot.get_channel(1368251474286612500).send(group_msg)

# ✅ Proper way to start the bot
async def main():
    async with bot:
        await bot.start(os.getenv("DISCORD_BOT_TOKEN"))

# 👇 This goes at the bottom and must be unindented
if __name__ == "__main__":
    asyncio.run(main())






















