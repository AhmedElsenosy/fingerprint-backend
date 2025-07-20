from app.models.counter import Counter

MAX_UID = 60000

async def get_next_sequence(name: str) -> int:
    counter = await Counter.find_one({"name": name})
    if not counter:
        counter = Counter(name=name, value=10022)
        await counter.insert()
    else:
        if counter.value >= MAX_UID:
            raise ValueError(f"{name} value exceeds MAX_UID ({MAX_UID})")
        counter.value += 1
        await counter.save()
    return int(counter.value)  # Ensure it's int

