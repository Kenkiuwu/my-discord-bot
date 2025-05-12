from collections import defaultdict

class HomeworkStorage:
    def __init__(self):
        self._homework = {}

    def get_all_homework(self):
        return self._homework

    async def collect_homework(self, user):
        def check(m): return m.author == user and isinstance(m.channel, discord.DMChannel)
        await user.send("Please enter your availability for Wednesday to Sunday (e.g. Wed: 18-22, Thu: 19-23):")
        avail_msg = await user.bot.wait_for('message', check=check)
        availability = parse_availability(avail_msg.content)

        await user.send("Now send your characters, one per line in this format: Name - Class - Ilvl")
        char_msg = await user.bot.wait_for('message', check=check)
        characters = []
        for line in char_msg.content.strip().split("\n"):
            name, cls, ilvl = map(str.strip, line.split("-"))
            characters.append({"name": name, "class": cls, "ilvl": int(ilvl)})

        self._homework[user.name.lower()] = {
            "availability": availability,
            "characters": characters
        }

def parse_availability(text):
    days = ["wed", "thu", "fri", "sat", "sun"]
    availability = defaultdict(set)
    for part in text.split(","):
        if ":" in part:
            day, times = part.split(":")
            day = day.strip().lower()[:3]
            if day in days:
                start, end = map(int, times.strip().split("-"))
                for hour in range(start, end):
                    availability[f"{day}_{hour}"].add(True)
    return availability