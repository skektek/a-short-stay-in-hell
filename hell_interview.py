"""
Local Xandern interview engine -- no API required.
Dynamic dialogue based on time-of-day, season, day-of-week,
special dates, answer content, and response timing.
"""

import time as _time
import textwrap
from datetime import datetime, date

# ── Temporal context ──────────────────────────────────────────────────────────

def _now():
    return datetime.now()

def time_of_day(dt: datetime) -> str:
    h = dt.hour
    if h < 4:   return "witching"
    if h < 7:   return "dawn"
    if h < 12:  return "morning"
    if h < 14:  return "noon"
    if h < 17:  return "afternoon"
    if h < 20:  return "evening"
    if h < 23:  return "night"
    return              "witching"

def season(dt: datetime) -> str:
    m = dt.month
    if m in (12, 1, 2):  return "winter"
    if m in (3, 4, 5):   return "spring"
    if m in (6, 7, 8):   return "summer"
    return                       "autumn"

def day_of_week(dt: datetime) -> str:
    return dt.strftime("%A").lower()  # monday, tuesday...

def special_day(dt: datetime) -> str | None:
    m, d = dt.month, dt.day
    doy  = dt.timetuple().tm_yday
    if m == 1  and d == 1:   return "new_year"
    if m == 2  and d == 14:  return "valentines"
    if m == 10 and d == 31:  return "halloween"
    if m == 12 and d == 25:  return "christmas"
    if m == 12 and d == 31:  return "new_years_eve"
    if doy in (172, 173):    return "solstice_summer"
    if doy in (355, 356):    return "solstice_winter"
    if doy in (80, 81):      return "equinox_spring"
    if doy in (266, 267):    return "equinox_autumn"
    if dt.weekday() == 4 and d >= 13 and d <= 19: return "friday_13th"
    return None

# ── Xandern's opening monologue ───────────────────────────────────────────────

def opening(dt: datetime) -> str:
    tod  = time_of_day(dt)
    seas = season(dt)
    dow  = day_of_week(dt)
    spec = special_day(dt)

    # Special days override everything
    if spec == "halloween":
        return ("Of all the nights to die, you chose this one. The veil was thin "
                "already -- you simply slipped through a tear that was already there. "
                "I am Xandern. I process the newly arrived. You are newly arrived. "
                "Before I assign you to the Library, I require certain information.")
    if spec == "new_year":
        return ("A new year began above ground moments ago. You will not see another. "
                "I am Xandern. I have processed souls on this date before -- they arrive "
                "smelling of champagne and regret. You arrived. That is enough. "
                "I require certain information before you are assigned.")
    if spec == "christmas":
        return ("They are opening gifts above ground. You are here. "
                "I am Xandern, and I have been processing souls since before your "
                "calendar was invented. The Library does not observe holidays. "
                "I require certain information.")
    if spec == "valentines":
        return ("Love brought many souls here eventually. You are simply earlier than most. "
                "I am Xandern. The Library requires certain information before I assign "
                "you to your search. We will speak of love, among other things.")
    if spec == "friday_13th":
        return ("You are not superstitious, I hope. Superstition implies the universe "
                "is paying attention. It is not. I am Xandern. I process the dead. "
                "You are dead. Before I assign you to the Library, I have questions.")
    if spec in ("solstice_winter", "solstice_summer"):
        return ("The longest night, or the shortest -- I confess I have stopped tracking. "
                "Time behaves differently here. I am Xandern. The Library requires "
                "certain information about you before you begin your search. Sit still.")
    if spec in ("equinox_spring", "equinox_autumn"):
        return ("Balance. Above ground they speak of balance today. Here there is no "
                "balance -- only the Library, and the search. I am Xandern. "
                "I require certain information before I assign you.")

    # Time of day
    if tod == "witching":
        return ("The witching hour. Even here we feel it -- a particular quality of "
                "silence, as if the Library itself is holding its breath. I am Xandern. "
                "You have died at an appropriately dramatic moment. I require information.")
    if tod == "dawn":
        return ("Dawn above ground. The light is changing in a world you will not see again. "
                "I am Xandern. I have been at this desk since before your civilization "
                "had a word for dawn. I require certain information.")
    if tod == "morning":
        return ("A morning death. Statistically unremarkable -- souls arrive at all hours. "
                "I am Xandern. The Library has been waiting for you specifically, "
                "though it would never admit it. I require certain information.")
    if tod == "noon":
        return ("You died at noon. The sun directly overhead, shadows at their shortest. "
                "A very definitive moment to choose. I am Xandern. "
                "Before the Library receives you, I must take your details.")
    if tod == "afternoon":
        tod_line = "The afternoon is the most common time to die. You are unremarkable in this."
    elif tod == "evening":
        tod_line = "An evening death. The day completed its business before releasing you."
    else:
        tod_line = "Night. The Library is indistinguishable from day, but I note it anyway."

    # Season flavor for non-special times
    seas_lines = {
        "winter": "You died in winter. The cold releases people more readily than warmth.",
        "spring": "Spring. Things are beginning above ground. Here, nothing begins.",
        "summer": "Summer. The living are busy. The dead arrive anyway.",
        "autumn": "Autumn. The season most suited to endings. You chose well, if inadvertently.",
    }

    return (f"{tod_line} {seas_lines[seas]} "
            f"I am Xandern. I process the newly arrived. You have arrived. "
            f"I require certain information before assigning you to the Library.")

# ── Per-question dialogue ─────────────────────────────────────────────────────

def ask_name(dt: datetime) -> str:
    dow = day_of_week(dt)
    lines = [
        "We will begin with the simplest fact: your name. Not what you were called -- "
        "what you were named. There is a difference.",

        f"It is {dow.capitalize()}. Names recorded on {dow.capitalize()}s have a particular "
        "weight in the Registry. Or perhaps not. State your name.",

        "The Registry requires a name. Not a nickname, not a title -- the name given "
        "at the beginning, before you had any say in the matter.",

        "Your name. The one your mother used when she was not angry with you, "
        "and the one she used when she was.",
    ]
    return lines[dt.minute % len(lines)]

def react_name(name: str, dt: datetime) -> str:
    name = name.strip()
    if not name:
        return "Silence is not a name. Try again."
    if len(name.split()) == 1:
        return (f"*The quill inscribes it.* {name}. A single name. "
                "Either you were known by only one, or you have decided to be modest "
                "in death. The Registry accepts both.")
    parts = name.split()
    first, last = parts[0], parts[-1]
    return (f"*The quill moves.* {name}. "
            f"The {last}s, or whatever family produced you, will not be notified. "
            "No one is notified. That is not how this works.")

def ask_birthdate(name: str, dt: datetime) -> str:
    first = name.split()[0] if name else "soul"
    lines = [
        f"Now, {first} -- when were you born? Day, month, year. "
        "The Library has existed longer than your calendar, but we use it for convenience.",

        f"The date of your birth, {first}. Not the date of your death -- "
        "that I already have. The beginning, not the end.",

        "Every soul arrives with a beginning and an ending. I have your ending. "
        "I require your beginning. When were you born?",
    ]
    return lines[dt.hour % len(lines)]

def react_birthdate(birthdate: str, name: str, dt: datetime) -> str:
    return (f"*The quill records it.* Born {birthdate}. "
            "You had a reasonable run, or you did not. The Library does not "
            "judge the length -- only the content.")

def ask_birthplace(name: str, dt: datetime) -> str:
    seas = season(dt)
    lines = [
        "Where were you born? City, town, village -- wherever the world first "
        "became specific to you.",

        f"The place of your birth, {name.split()[0] if name else 'soul'}. "
        "The Library contains books from everywhere. Yours is one of them.",

        "Geography matters less here than you might think, but the Registry "
        "requires it. Where were you born?",

        "Every soul comes from somewhere specific. A room, a city, a country "
        "that no longer exists perhaps. Where did you begin?",
    ]
    return lines[dt.minute % len(lines)]

def react_birthplace(birthplace: str, dt: datetime) -> str:
    birthplace = birthplace.strip()
    tod = time_of_day(dt)
    if tod in ("witching", "night"):
        return (f"*A pause.* {birthplace}. I have processed souls from there before. "
                "The nights are different there. Were, I should say.")
    return (f"{birthplace}. *The quill notes it without ceremony.* "
            "The place produced you and then continued without you, "
            "as places do. We move on.")

def ask_pet(name: str, dt: datetime) -> str:
    first = name.split()[0] if name else "soul"
    lines = [
        f"A childhood pet, {first}, or a favored animal if you had none. "
        "The Registry requires something small and innocent to offset the larger entries.",

        "We come now to the animal. A pet from your childhood, or simply "
        "an animal you loved. The Library finds these details clarifying.",

        f"Before we arrive at the names that cost something, {first} -- "
        "tell me of an animal. A pet, perhaps. Something that did not "
        "outlive you, or did, depending on the arithmetic.",
    ]
    return lines[dt.second % len(lines)]

def react_pet(pet: str, name: str, dt: datetime) -> str:
    pet = pet.strip()
    common_dogs = {"rover","rex","max","buddy","charlie","cooper","duke","bear","rocky"}
    common_cats = {"whiskers","mittens","shadow","luna","bella","kitty","felix","tiger"}
    if pet.lower() in common_dogs:
        return (f"*The quill pauses fractionally.* {pet}. A dog's name. "
                "Dogs arrive here too, in their own wing. I will not tell you more than that.")
    if pet.lower() in common_cats:
        return (f"{pet}. A cat. *The quill moves.* Cats require a separate Registry entirely. "
                "Suffice to say, {pet} is accounted for.")
    return (f"*The quill inscribes it carefully.* {pet}. "
            "An unusual name, or an unusual creature, or both. "
            "The Registry notes it without judgment.")

def ask_first_love(name: str, dt: datetime) -> str:
    first = name.split()[0] if name else "soul"
    seas  = season(dt)
    if seas == "spring":
        return (f"Spring above ground, {first}. An appropriate season for this question. "
                "Your first love -- the name, simply the name.")
    if seas == "autumn":
        return (f"Autumn. The season of things ending. But we speak now of beginnings. "
                f"Your first love, {first}. The name.")
    lines = [
        f"We arrive now at the names that carry weight. Your first love, {first}. "
        "Not your first infatuation -- your first love. There is a difference, "
        "and you know which I mean.",

        "First loves have a particular permanence. They lodge themselves in the "
        "architecture of a person. Give me the name.",

        f"The Registry requires the name of your first love, {first}. "
        "The one who opened the door. Whatever came after, this name came first.",
    ]
    return lines[dt.minute % len(lines)]

def react_first_love(first_love: str, name: str, dt: datetime) -> str:
    first_love = first_love.strip()
    return (f"*The quill hesitates -- a rare thing -- and then inscribes the name "
            f"with unusual deliberateness.* {first_love}. "
            "First loves have a peculiar permanence, do they not? "
            "They lodge themselves in the architecture of a person like a load-bearing wall. "
            f"Remove them and something structural shifts forever. {first_love}. It is recorded.")

def ask_last_love(name: str, first_love: str, dt: datetime) -> str:
    first = name.split()[0] if name else "soul"
    tod   = time_of_day(dt)
    if tod in ("witching", "night"):
        return (f"And now, {first}, the final entry. We began with {first_love}. "
                "First loves open the heart. Last loves -- close it, one way or another. "
                "When the curtain came down on your life, whose name was nearest to it?")
    return (f"We arrive at the last entry, {first}. "
            f"First loves open the heart. We have recorded {first_love}. "
            "Last loves close it -- some gently, some less so. "
            "Who was last?")

def react_last_love(last_love: str, first_love: str, name: str, dt: datetime) -> str:
    last_love  = last_love.strip()
    same       = last_love.lower() == first_love.lower()
    first_name = name.split()[0] if name else "soul"

    if same:
        return (f"*The quill stops.* {last_love}. The same name. "
                f"First and last, {first_love}. "
                "The Registry sees this occasionally. It means either great constancy "
                "or great difficulty with letting go. Possibly both. "
                f"*A long pause.* It is recorded, {first_name}.")
    return (f"*The quill moves with quiet finality.* {last_love}. "
            f"From {first_love} to {last_love}, with an entire life threaded between them. "
            "The distance between a first name and a last name is always "
            "the most interesting part of the file.")

# ── Closing dismissal ─────────────────────────────────────────────────────────

def closing(player: dict, dt: datetime) -> str:
    name       = player.get("name", "soul")
    birthdate  = player.get("birthdate", "an unrecorded date")
    birthplace = player.get("birthplace", "an unrecorded place")
    pet        = player.get("pet", "an unrecorded creature")
    first      = player.get("first_love", "an unrecorded name")
    last       = player.get("last_love", "an unrecorded name")
    first_name = name.split()[0] if name else "soul"
    tod        = time_of_day(dt)
    seas       = season(dt)

    tod_note = {
        "witching": "You arrived at the witching hour. The Library was waiting.",
        "dawn":     "You arrived at dawn. The Library does not sleep, but it noticed.",
        "morning":  "A morning arrival. The Library has had worse.",
        "noon":     "You arrived at noon, shadows at their shortest.",
        "afternoon":"An afternoon arrival. Unremarkable. The Library is not insulted.",
        "evening":  "An evening arrival. The day released you at the last.",
        "night":    "A night arrival. The Library is quieter at night. Slightly.",
    }.get(tod, "")

    pet_note = f"And {pet} is noted in the supplementary Registry."

    return (f"*The parchment rolls itself closed with a sound like distant thunder, "
            f"and a brass seal appears upon it unbidden.*\n\n"
            f"And so. The file of {name} -- born {birthdate}, in {birthplace} -- "
            f"is complete and sealed. "
            f"From {first} to {last}, with everything between. "
            f"You are hereby assigned to the Library of Eternal Record. "
            f"An attendant will collect you shortly. "
            f"{pet_note} {tod_note}\n\n"
            f"You may sit. Do not touch anything, {first_name}. "
            f"And do try not to take it personally. "
            f"The Library contains everyone.")

# ── Local win dismissal pool ──────────────────────────────────────────────────

WIN_DISMISSALS = [
    ("The file of {name} is closed. Born {birthdate} in {birthplace}, "
     "arrived in the Library, searched, and found. "
     "From {first_love} to {last_love} -- a complete story. "
     "{pet} is already waiting. You are released."),

    ("*A long silence.*\n\n"
     "In eleven thousand years of processing souls, {name}, "
     "I have dismissed perhaps forty who found their book. "
     "You are among them now. "
     "The file is sealed. You are free."),

    ("The Registry of {birthplace} is updated. "
     "The soul of {name}, who loved {first_love} first and {last_love} last, "
     "has completed the terms of their stay. "
     "The Library releases you. Do not thank me. "
     "Thank no one. Simply go."),

    ("Born {birthdate}. Arrived here. Searched. Found.\n\n"
     "The arithmetic is complete. The file of {name} closes. "
     "What waited after {last_love} -- after all of it -- "
     "is no longer my concern, and has become yours. "
     "You are released."),

    ("*The Great Clock notes the moment.*\n\n"
     "The search of {name} has ended. {birthplace} produced you. "
     "The Library held you. Now the Library releases you. "
     "Take {pet}'s memory with you. Take {first_love}. Take {last_love}. "
     "Take everything. The door is there."),

    ("I have processed your intake and I process your release. "
     "The file is complete: {name}, {birthplace}, {birthdate}. "
     "{first_love} and {last_love} and everything between. "
     "The Library found you worthy of release, which is to say: "
     "it found you. Go."),
]

def local_win_dismissal(player: dict, elapsed_seconds: float) -> str:
    name       = player.get("name", "soul")
    birthdate  = player.get("birthdate", "an unrecorded date")
    birthplace = player.get("birthplace", "an unrecorded place")
    pet        = player.get("pet", "your companion")
    first_love = player.get("first_love", "the first")
    last_love  = player.get("last_love", "the last")

    # Pick template based on time spent
    days = elapsed_seconds // 86400
    if days < 1:
        idx = 0
    elif days < 7:
        idx = 1
    elif days < 30:
        idx = 2
    elif days < 365:
        idx = 3
    elif days < 365 * 10:
        idx = 4
    else:
        idx = 5

    template = WIN_DISMISSALS[idx]
    return template.format(
        name=name, birthdate=birthdate, birthplace=birthplace,
        pet=pet, first_love=first_love, last_love=last_love,
    )

# ── Main interview function ───────────────────────────────────────────────────

def _speak(text: str):
    """Print Xandern's words with wrapping."""
    print()
    for line in text.split("\n"):
        if line.strip():
            for wrapped in textwrap.wrap(line, width=68):
                print(f"  {wrapped}")
        else:
            print()
    print()

def _ask(prompt: str = "  You: ") -> tuple[str, float]:
    """Get player input and measure response time."""
    t0  = _time.time()
    ans = input(prompt).strip()
    return ans, _time.time() - t0

def _slow_comment(elapsed: float) -> str | None:
    """Return a comment if the player was slow to respond."""
    if elapsed > 60:
        return "*Xandern regards you with the patience of something very old.* Take your time."
    if elapsed > 30:
        return "*A pause extends itself.*"
    return None

def run_local_interview() -> dict:
    """Run the fully local Xandern interview. Returns player dict."""
    dt = _now()
    print("\n" + "=" * 70)
    _speak(opening(dt))
    input("  Press Enter...")

    collected = {}

    # Question 1: Name
    print()
    _speak(ask_name(dt))
    ans, elapsed = _ask()
    comment = _slow_comment(elapsed)
    if comment:
        _speak(comment)
    _speak(react_name(ans, dt))
    collected["name"] = ans

    # Question 2: Birthdate
    _speak(ask_birthdate(collected["name"], dt))
    ans, elapsed = _ask()
    comment = _slow_comment(elapsed)
    if comment:
        _speak(comment)
    _speak(react_birthdate(ans, collected["name"], dt))
    collected["birthdate"] = ans

    # Question 3: Birthplace
    _speak(ask_birthplace(collected["name"], dt))
    ans, elapsed = _ask()
    comment = _slow_comment(elapsed)
    if comment:
        _speak(comment)
    _speak(react_birthplace(ans, dt))
    collected["birthplace"] = ans

    # Question 4: Pet
    _speak(ask_pet(collected["name"], dt))
    ans, elapsed = _ask()
    comment = _slow_comment(elapsed)
    if comment:
        _speak(comment)
    _speak(react_pet(ans, collected["name"], dt))
    collected["pet"] = ans

    # Question 5: First love
    _speak(ask_first_love(collected["name"], dt))
    ans, elapsed = _ask()
    comment = _slow_comment(elapsed)
    if comment:
        _speak(comment)
    _speak(react_first_love(ans, collected["name"], dt))
    collected["first_love"] = ans

    # Question 6: Last love
    _speak(ask_last_love(collected["name"], collected["first_love"], dt))
    ans, elapsed = _ask()
    comment = _slow_comment(elapsed)
    if comment:
        _speak(comment)
    _speak(react_last_love(ans, collected["first_love"], collected["name"], dt))
    collected["last_love"] = ans

    # Closing
    _speak(closing(collected, dt))
    print("=" * 70)

    return collected
