from collections import defaultdict

def overlaps(a, b):
    return any(slot in a for slot in b)

def get_common_times(avail_list):
    count = defaultdict(list)
    for avail in avail_list:
        for time in avail:
            count[time].append(True)
    return count