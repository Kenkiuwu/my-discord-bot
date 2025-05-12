from collections import defaultdict
from utils import overlaps, get_common_times

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

def generate_homework_groups(homework_data):
    messages = []
    fixed_avail = {user: data["availability"] for user, data in homework_data.items() if user in FIXED_ROSTER}
    
    support_times = get_common_times([
        fixed_avail.get(user, {}) for user, role in FIXED_ROSTER.items()
        if role in ("Paladin", "Artist", "Bard")
    ])
    
    best_time = max(support_times.items(), key=lambda x: len(x[1]), default=(None, []))[0]

    if best_time:
        dps = [user for user, role in FIXED_ROSTER.items() if role not in ("Paladin", "Artist")]
        dps_available = [d for d in dps if best_time in fixed_avail.get(d, {})]
        supports = [user for user, role in FIXED_ROSTER.items() if role in ("Paladin", "Artist")]
        group = supports + dps_available
        msg = f"**Brelshaza Hardmode (Fixed Group) - {best_time}**\n" + "\n".join(group)
        messages.append(msg)

    # No filtering — include everyone
    dynamic_pool = homework_data
     aegir_hard = []
     brel_normal = []
     aegir_normal = []

    for user, data in dynamic_pool.items():
        ilvl = max(c["ilvl"] for c in data["characters"])
        if ilvl >= 1680:
            aegir_hard.append((user, data))
        elif ilvl >= 1670:
            brel_normal.append((user, data))
        elif ilvl >= 1660:
            aegir_normal.append((user, data))

    def form_groups(pool, raid_name, size=8):
        temp, results = [], []
        for user, data in pool:
            temp.append(user)
            if len(temp) == size:
                results.append(temp)
                temp = []
        if temp:
            results.append(temp)
        for g in results:
            messages.append(f"**{raid_name} Group**\n" + "\n".join(g))

    form_groups(aegir_hard, "Aegir Hardmode")
    form_groups(brel_normal, "Brelshaza Normal")
    form_groups(aegir_normal, "Aegir Normal")

    return messages