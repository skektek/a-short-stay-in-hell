#!/usr/bin/env python3
"""
A Short Stay in Hell
Based on the novella by Steven L. Peck.
A library containing every possible book of 410 pages, 40 lines, 80 characters.
Find the book that contains the story of your life.
"""

import os
import sys
import json
import random
import hashlib
import textwrap
import time
import math
from pathlib import Path

# Allow conversion of astronomically large integers (positions have ~2.6M digits)
sys.set_int_max_str_digits(0)  # 0 = unlimited

# -- Dependencies -------------------------------------------------------------
# Required (hard fail if missing)
_missing_required = []
try:
    from spellchecker import SpellChecker
except ImportError:
    _missing_required.append("pyspellchecker")
try:
    import textstat
except ImportError:
    _missing_required.append("textstat")
try:
    import nltk
except ImportError:
    _missing_required.append("nltk")

if _missing_required:
    print(f"Missing required packages: {', '.join(_missing_required)}")
    print(f"Run: pip install {' '.join(_missing_required)}")
    sys.exit(1)

import logging
logging.getLogger("nltk").setLevel(logging.ERROR)
nltk.download("words", quiet=True)
nltk.download("punkt", quiet=True)
from nltk.corpus import words as nltk_words

# Optional -- graceful fallback if unavailable
try:
    import anthropic
    _ANTHROPIC_AVAILABLE = True
except ImportError:
    _ANTHROPIC_AVAILABLE = False

try:
    import language_tool_python
    _GRAMMAR_AVAILABLE = True
except ImportError:
    _GRAMMAR_AVAILABLE = False

# Inform user of optional missing packages (once, at startup)
_optional_missing = []
if not _ANTHROPIC_AVAILABLE:
    _optional_missing.append("anthropic (pip install anthropic) -- enables AI interview")
if not _GRAMMAR_AVAILABLE:
    _optional_missing.append("language_tool_python + Java -- enables grammar checking")
if _optional_missing:
    print()
    print("  Optional packages not available:")
    for m in _optional_missing:
        print(f"    - {m}")
    print()

# -- Constants ----------------------------------------------------------------
PAGES_PER_BOOK  = 410
LINES_PER_PAGE  = 40
CHARS_PER_LINE  = 80
CHARS_PER_PAGE  = LINES_PER_PAGE * CHARS_PER_LINE   # 3,200
CHARS_PER_BOOK  = PAGES_PER_BOOK * CHARS_PER_PAGE   # 1,312,000
CHARSET         = ''.join(chr(i) for i in range(32, 127))  # 95 printable ASCII
CHARSET_SIZE    = len(CHARSET)                              # 95
ROWS_PER_UNIT   = 8
BOOKS_PER_ROW   = 35
BOOKS_PER_UNIT  = ROWS_PER_UNIT * BOOKS_PER_ROW            # 280
SIDES_PER_FLOOR = 2
UNITS_PER_FLOOR = 20_000 * BOOKS_PER_UNIT

# -- Fall physics (sea-level Earth standard) ----------------------------------
GRAVITY_MS2          = 9.81     # m/s^2
TERMINAL_VELOCITY_MS = 53.0     # m/s, average human belly-to-earth position
FLOOR_HEIGHT_M       = 2.9      # meters per floor (matches library design)
DEHYDRATION_DAYS     = 3.0      # days to die of dehydration without water
DEHYDRATION_SECONDS  = DEHYDRATION_DAYS * 86400

# Total books = 95^1,312,000
TOTAL_BOOKS = CHARSET_SIZE ** CHARS_PER_BOOK

STATE_FILE  = Path.home() / ".hell_state.json"
SHARES_FILE = Path.home() / ".hell_shares"   # directory for .hell share files

# -- ANSI colors --------------------------------------------------------------
YELLOW = "\033[93m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
RESET  = "\033[0m"

# -- Failure taunts -----------------------------------------------------------
def get_taunts(player: dict) -> list:
    name       = player.get("name", "soul")
    pet        = player.get("pet", "your pet")
    first      = player.get("first_love", "your first love")
    last       = player.get("last_love", "your last love")
    birthplace = player.get("birthplace", "wherever you came from")
    return [
        "The Library mocks you with its silence. This is not your book.",
        "Eleven thousand souls have thought the same thing. They were wrong too.",
        f"The pages know nothing of you, {name}. Move on.",
        "Not yours. Not even close. The shelf awaits.",
        f"{pet} would not recognize a single word on these pages.",
        f"You think of {first}. The book does not.",
        f"Somewhere between {first} and {last}, your story was written. It is not here.",
        f"The shelves of {birthplace} produced more coherent text than this.",
        "This book has never heard your name. It never will.",
        "You have an eternity to keep looking. Do not waste it here.",
        f"The numbers do not lie, {name}. This is not the one.",
        f"Move along. {last} would want you to keep searching.",
    ]

# -- Fall damage messages -----------------------------------------------------
FALL_MESSAGES = [
    (1,   5,   ("You stumble down several levels, catching a railing at the last moment.\n"
                "You are bruised but upright. The books watch impassively.")),
    (6,   20,  ("You fall hard, bouncing off railings, landing in a heap on a lower floor.\n"
                "Something aches that did not ache before. You lie still for a moment.")),
    (21,  50,  ("The fall is long enough that you have time to regret it.\n"
                "You hit the floor with a sound that echoes through the stacks.\n"
                "Something may be broken. You are not sure. You get up anyway.")),
    (51,  99,  ("You fall for what feels like minutes.\n"
                "The impact is enormous. You lie on the floor a long time,\n"
                "staring up at the shelves receding into darkness above you.\n"
                "Eventually you rise. There is nothing else to do.")),
    (100, None,("The fall takes long enough that you lose consciousness.\n"
                "When you open your eyes the ceiling is unfamiliar.\n"
                "A distant voice -- bureaucratic, immense, faintly bored -- says:\n"
                "  \'Rule Four. Death within the Library is temporary.\n"
                "   You have been restored to the nearest floor.\n"
                "   Please resume your search.\'\n"
                "You are exactly where you started, minus the dignity.")),
]

def fall_message(floors: int) -> str:
    for min_f, max_f, msg in FALL_MESSAGES:
        if max_f is None or floors <= max_f:
            return msg
    return FALL_MESSAGES[-1][2]

# -- Anthropic client (optional) ---------------------------------------------
def get_anthropic_client(api_key: str | None) -> object | None:
    """Return an Anthropic client if a key is available, else None."""
    if not api_key or not _ANTHROPIC_AVAILABLE:
        return None
    try:
        return anthropic.Anthropic(api_key=api_key)
    except Exception:
        return None

# -- Book generation ----------------------------------------------------------
def generate_page(book_position: int, page_number: int) -> str:
    """Generate a deterministic page of text from book position and page number."""
    seed = book_position * PAGES_PER_BOOK + page_number
    rng  = random.Random(seed)
    chars = [rng.choice(CHARSET) for _ in range(CHARS_PER_PAGE)]
    lines = [''.join(chars[i * CHARS_PER_LINE:(i + 1) * CHARS_PER_LINE])
             for i in range(LINES_PER_PAGE)]
    return '\n'.join(lines)

# -- Position <-> physical location -------------------------------------------
def position_to_location(pos: int) -> dict:
    book_in_unit = pos % BOOKS_PER_UNIT
    row          = book_in_unit // BOOKS_PER_ROW
    col          = book_in_unit % BOOKS_PER_ROW
    unit_number  = pos // BOOKS_PER_UNIT
    side         = unit_number % SIDES_PER_FLOOR
    floor_unit   = unit_number // SIDES_PER_FLOOR
    return {
        "floor": floor_unit,
        "side":  "Left" if side == 0 else "Right",
        "unit":  unit_number,
        "row":   row + 1,
        "col":   col + 1,
    }

def format_big(n: int, digits: int = 6) -> str:
    s = str(n)
    if len(s) <= digits * 2 + 3:
        return f"{n:,}"
    return f"{s[:digits]}...{s[-digits:]} ({len(s)} digits)"

# -- Life book position -------------------------------------------------------
def derive_life_book_position(player: dict) -> int:
    combined = "|".join([
        player.get("name", ""),
        player.get("birthdate", ""),
        player.get("birthplace", ""),
        player.get("pet", ""),
        player.get("first_love", ""),
        player.get("last_love", ""),
    ]).encode("utf-8")
    digest = hashlib.sha512(combined).hexdigest()
    raw    = int(digest, 16)
    return raw % TOTAL_BOOKS

# -- Coherence scoring --------------------------------------------------------
_spell   = None
_lt_tool = None

def _get_spell():
    global _spell
    if _spell is None:
        _spell = SpellChecker()
    return _spell

def _get_lt():
    global _lt_tool
    if not _GRAMMAR_AVAILABLE:
        return None
    if _lt_tool is None:
        _lt_tool = language_tool_python.LanguageTool("en-US")
    return _lt_tool

def score_page(page_text: str, player: dict,
               book_position: int, life_position: int) -> dict:
    # Extract actual words (3+ letters) from the noise using regex
    # Raw split() gives full 80-char lines as tokens which never match dictionary
    import re as _re
    _words       = _re.findall(r'[a-zA-Z]{3,}', page_text)
    total_tokens = max(len(_words), 1)

    # Spelling -- what fraction of extracted words are real English words
    spell         = _get_spell()
    _wf           = spell.word_frequency
    known_count   = sum(1 for w in _words if w.lower() in _wf)
    spelling_score = known_count / total_tokens

    # Readability
    try:
        flesch           = textstat.flesch_reading_ease(page_text)
        readability_score = max(0.0, min(flesch / 100.0, 1.0))
    except Exception:
        readability_score = 0.0

    # Grammar (optional -- requires language_tool_python + Java)
    grammar_score     = None   # None = unavailable
    grammar_available = _GRAMMAR_AVAILABLE
    try:
        lt = _get_lt()
        if lt is not None:
            matches       = lt.check(page_text)
            error_rate    = len(matches) / total_tokens
            grammar_score = max(0.0, 1.0 - error_rate)
    except Exception:
        grammar_score = None

    # Personal resonance
    personal_fields = [
        player.get("name", ""),
        player.get("birthplace", ""),
        player.get("pet", ""),
        player.get("first_love", ""),
        player.get("last_love", ""),
        player.get("birthdate", ""),
    ]
    page_lower    = page_text.lower()
    hits          = sum(1 for f in personal_fields if f and f.lower() in page_lower)
    personal_score = hits / len(personal_fields)

    # Reweight if grammar unavailable -- redistribute its 20% to others
    if grammar_score is None:
        overall = (
            spelling_score    * 0.267 +
            readability_score * 0.267 +
            personal_score    * 0.466
        )
    else:
        overall = (
            spelling_score    * 0.20 +
            readability_score * 0.20 +
            grammar_score     * 0.20 +
            personal_score    * 0.40
        )

    is_life_book = (book_position == life_position)

    return {
        "spelling":          spelling_score,
        "readability":       readability_score,
        "grammar":           grammar_score,       # None if unavailable
        "grammar_available": grammar_score is not None,
        "personal":          personal_score,
        "overall":           overall,
        "is_life_book":      is_life_book,
        "page_text":         page_text,
    }

# -- Display ------------------------------------------------------------------
def clear():
    os.system("clear")

def highlight_personal(page_text: str, player: dict) -> str:
    """Return page text with personal details highlighted in yellow."""
    fields = [f for f in [
        player.get("name", ""),
        player.get("birthplace", ""),
        player.get("pet", ""),
        player.get("first_love", ""),
        player.get("last_love", ""),
        player.get("birthdate", ""),
    ] if f]

    result = page_text
    for field in fields:
        # Case-insensitive replacement preserving original case
        import re
        pattern = re.compile(re.escape(field), re.IGNORECASE)
        result  = pattern.sub(lambda m: f"{YELLOW}{BOLD}{m.group()}{RESET}", result)
    return result


# -- Great Clock --------------------------------------------------------------
# Time hierarchy (in seconds):
_SPY  = 365 * 24 * 3600          # seconds per year
_SDEC = 10   * _SPY              # per decade
_SCEN = 100  * _SPY              # per century
_SMIL = 1_000      * _SPY        # per millennium
_SEON = 1_000_000_000   * _SPY   # per eon  (1 billion years)
_SAGE = 1_000_000_000_000 * _SPY # per Age  (1 trillion years)
# 1 Reckoning = 95^1,312,000 seconds -- shown symbolically, always 0

def format_elapsed(seconds: float) -> str:
    """Format elapsed seconds into the full cosmological clock display."""
    s = int(seconds)

    # Break out all units
    ages,       rem  = divmod(s,   _SAGE)
    eons,       rem  = divmod(rem, _SEON)
    millennia,  rem  = divmod(rem, _SMIL)
    centuries,  rem  = divmod(rem, _SCEN)
    decades,    rem  = divmod(rem, _SDEC)
    years,      rem  = divmod(rem, _SPY)
    days,       rem  = divmod(rem, 86400)
    hours,      rem  = divmod(rem, 3600)
    minutes,    secs = divmod(rem, 60)

    def u(n, singular, plural=None):
        if plural is None:
            plural = singular + "s"
        return f"{n:,} {singular if n == 1 else plural}"

    # Always show Reckonings → Ages → Eons → Millennia → Centuries with
    # leading zeros so the player can see what awaits them
    lines = []
    lines.append(f"  Reckonings : 0")
    lines.append(f"  Ages       : {ages:,}")
    lines.append(f"  Eons       : {eons:,}")
    lines.append(f"  Millennia  : {millennia:,}")
    lines.append(f"  Centuries  : {centuries:,}")
    lines.append(f"  Decades    : {decades:,}")
    lines.append(f"  Years      : {years:,}")
    lines.append(f"  Days       : {days:,}")
    lines.append(f"  Hours      : {hours:,}")
    lines.append(f"  Minutes    : {minutes:,}")
    lines.append(f"  Seconds    : {secs:,}")
    return "\n".join(lines)

def clock_comment(seconds: float) -> str:
    """A Xandern-flavored comment based on elapsed time."""
    s = int(seconds)
    m = s  // 60
    h = s  // 3600
    d = h  // 24
    y = d  // 365

    # First hour: comments every ~10 minutes
    if s <   600:  return "You have only just arrived."
    if s <  1200:  return "The doors are behind you. There are no doors."
    if s <  1800:  return "The first hour is the longest. Or so they say."
    if s <  2400:  return "You are beginning to notice the smell of old paper."
    if s <  3000:  return "Your eyes are adjusting to the light. It does not change."
    if s <  3600:  return "You are beginning to understand."
    # Hours 1-6: comments every ~hour
    if h <   2:    return "The books are indifferent to your haste."
    if h <   3:    return "Others passed this shelf before you. None found what they sought."
    if h <   4:    return "The silence here is not empty. It is full of failed searches."
    if h <   6:    return "You have walked further than you know."
    if h <  12:    return "Half a day. The Library has not noticed."
    if h <  18:    return "The vending machines are further than you remember."
    if h <  24:    return "You have been here nearly a full day. It feels longer."
    # Days 1-7: comments every day or two
    if d <   2:    return "The shelves looked the same yesterday."
    if d <   3:    return "You are developing a sense of the architecture. It does not help."
    if d <   5:    return "Three days. Four. The numbers blur."
    if d <   7:    return "A week in the Library. Your life above had weeks like this too."
    # Weeks 1-4
    if d <  10:    return "The shelves do not miss you when you are gone."
    if d <  14:    return "Nearly two weeks. The shelves have not changed. You have."
    if d <  21:    return "Others arrived after you. They are still looking too."
    if d <  30:    return "The Library is the same in every direction. You know this now."
    # Months 1-12
    if d <  45:    return "A month and a half. You are becoming efficient, for all the good it does."
    if d <  60:    return "Two months. You have stopped counting pages."
    if d <  90:    return "Others arrived after you. They are not catching up."
    if d < 120:    return "You have worn a groove in the floor no one else will notice."
    if d < 180:    return "Half a year. The world above has moved on without you."
    if d < 270:    return "Nine months. Something was born above ground while you searched here."
    if d < 365:    return "A season has passed above ground. Here, nothing changes."
    # Years 1-10: comments every year or two
    if y <   2:    return "A full year. Others have been here longer."
    if y <   3:    return "Two years. You have read more books than most libraries contain."
    if y <   4:    return "You are learning the patience of the Library."
    if y <   5:    return "Four years. The vending machine still works."
    if y <   7:    return "You have begun to dream of shelves."
    if y <  10:    return "A decade. The Library has barely registered your presence."
    # Decades
    if y <  15:    return "The Library has begun to feel familiar. That is not good."
    if y <  20:    return "Two decades. Some souls have given up searching. Not you. Not yet."
    if y <  25:    return "You are becoming part of the Library."
    if y <  30:    return "Thirty years. You remember the world above in pieces now."
    if y <  40:    return "You have outlasted several small civilisations in here."
    if y <  50:    return "Half a century. Your name sounds strange when you say it aloud."
    # Generations
    if y <  75:    return "Few remember the world above as clearly as you once did."
    if y < 100:    return "A century. The clock is unsurprised."
    if y < 150:    return "The Library is all there has ever been."
    if y < 200:    return "The Library is all there is. The Library has always been."
    if y < 300:    return "Other souls have arrived and despaired while you searched."
    if y < 500:    return "Your arrival is a distant rumour, even to yourself."
    # Centuries → millennia
    if y < 750:    return "The world you knew has crumbled into archaeology."
    if y <1000:    return "Millennia are the Library's native currency."
    if y <2000:    return "Over a thousand years. The clock does not shrug. It has no shoulders."
    if y <5000:    return "You have outlasted languages, empires, and certainties."
    if y <10000:   return "Ten millennia. The Library remains unimpressed."
    # Deep time
    if y < 1_000_000:
                   return "The stars have shifted since you arrived. Slightly."
    if y < 1_000_000_000:
                   return "The clock notes your persistence without admiration."
    if y < 1_000_000_000_000:
                   return "The Eons turn. The Library does not."
    return                "The Reckoning has not yet begun. It will."

def format_clock(state: dict) -> tuple[str, str]:
    """Return (elapsed_str, comment_str) for the Great Clock."""
    arrival = state.get("arrival_time", None)
    if arrival is None:
        return "  (arrival unrecorded)", "The clock did not record your arrival."
    import time as _time
    elapsed = _time.time() - arrival
    return format_elapsed(elapsed), clock_comment(elapsed)

def display_header(state: dict):
    loc     = position_to_location(state["position"])
    taken   = state["position"] in state["taken_books"]
    elapsed, comment = format_clock(state)
    # -- Title & location block
    print("=" * 70)
    print("  A SHORT STAY IN HELL")
    print(f"  Floor: {format_big(loc['floor'])}   Side: {loc['side']}   "
          f"Unit: {format_big(loc['unit'])}")
    print(f"  Shelf: {loc['row']}/8   Position: {loc['col']}/35   "
          f"Book: {format_big(state['position'])}")
    books_read = state.get("books_read", 0)
    mode_label = f"{DIM}[AI]{RESET}" if state.get("api_key") else f"{DIM}[local]{RESET}"
    print(f"  Page: {state['page'] + 1} / {PAGES_PER_BOOK}   Books Read: {books_read:,}   {mode_label}")
    if taken:
        print("  *** SLOT EMPTY -- book has been taken ***")
    # -- Clock block
    print("-" * 70)
    print("  THE GREAT CLOCK")
    # Render clock units on two rows of 6
    units = elapsed.split("\n")   # 11 lines: Reckonings..Seconds
    # Parse into label:value pairs
    pairs = []
    for line in units:
        line = line.strip()
        if ":" in line:
            label, val = line.split(":", 1)
            pairs.append(f"{label.strip()}: {val.strip()}")
    # Print in two rows
    row1 = "   ".join(pairs[:6])
    row2 = "   ".join(pairs[6:])
    print(f"  {row1}")
    print(f"  {row2}")
    print(f"  {DIM}{comment}{RESET}")
    print("-" * 70)

def display_page(state: dict):
    clear()
    display_header(state)
    if state["position"] in state["taken_books"]:
        print()
        print("  [ missing book ]")
        print()
    else:
        page_text = generate_page(state["position"], state["page"])
        print()
        for line in page_text.split("\n"):
            print(f"  {line}")
        print()
    display_controls()


# -- Book sharing -------------------------------------------------------------
import zlib as _zlib
import hashlib as _hashlib

def book_share_code(position: int) -> str:
    """8-char hex code uniquely identifying a book position."""
    return _hashlib.sha256(str(position).encode()).hexdigest()[:8]

def export_share(position: int, label: str) -> Path:
    """Write a .hell share file and return its path."""
    SHARES_FILE.mkdir(exist_ok=True)
    code      = book_share_code(position)
    pos_bytes = position.to_bytes((position.bit_length() + 7) // 8, "big")
    compressed = _zlib.compress(pos_bytes, level=9)
    data = (code.encode("ascii") + b"\x00" +
            label.encode("utf-8") + b"\x00" +
            compressed)
    out_path = SHARES_FILE / f"{code}.hell"
    out_path.write_bytes(data)
    return out_path

def import_share(path: str) -> dict | None:
    """Read a .hell share file. Returns {code, label, position} or None."""
    try:
        data     = Path(path).read_bytes()
        code     = data[:8].decode("ascii")
        rest     = data[9:]
        lbl_end  = rest.index(b"\x00")
        label    = rest[:lbl_end].decode("utf-8")
        comp     = rest[lbl_end + 1:]
        pos_bytes = _zlib.decompress(comp)
        position  = int.from_bytes(pos_bytes, "big")
        return {"code": code, "label": label, "position": position}
    except Exception as e:
        return None

def list_shares() -> list[dict]:
    """Return all shares in the shares directory."""
    if not SHARES_FILE.exists():
        return []
    results = []
    for f in sorted(SHARES_FILE.glob("*.hell")):
        entry = import_share(str(f))
        if entry:
            results.append(entry)
    return results

def mark_book(state: dict) -> None:
    """Mark the current book with a label and export a share file."""
    pos = state["position"]
    if pos in state["taken_books"]:
        print("  This slot is empty -- nothing to mark.")
        time.sleep(1)
        return
    code  = book_share_code(pos)
    print()
    print(f"  Book code: {BOLD}{code}{RESET}")
    label = input("  Enter a label for this book (or blank to cancel): ").strip()
    if not label:
        print("  Cancelled.")
        time.sleep(1)
        return
    out = export_share(pos, label)
    print()
    print(f"  Marked. Share file saved to:")
    print(f"  {out}")
    print()
    print(f"  Send that file to another soul. They can import it with the")
    print(f"  \'X\' command and jump directly to this book.")
    input("\n  Press Enter to continue...")

def jump_to_share(state: dict) -> None:
    """Import a .hell file or jump to a known share code."""
    print()
    print("  OPTIONS:")
    print("  [1] Import a .hell share file")
    print("  [2] Jump to a share code already in your collection")
    print("  [q] Cancel")
    print()
    choice = input("  Choice: ").strip().lower()

    if choice == "1":
        path = input("  Path to .hell file: ").strip()
        entry = import_share(path)
        if entry is None:
            print("  Could not read that file.")
            time.sleep(1.5)
            return
        # Copy into shares dir
        export_share(entry["position"], entry["label"])
        print()
        print(f"  Imported: [{entry['code']}] \"{entry['label']}\"")
        go = input("  Jump to it now? [y/n]: ").strip().lower()
        if go == "y":
            state["position"]  = entry["position"]
            state["page"]      = 0
            state["books_read"] = state.get("books_read", 0) + 1
            save_state(state)

    elif choice == "2":
        shares = list_shares()
        if not shares:
            print("  No shares in your collection yet.")
            time.sleep(1.5)
            return
        print()
        print("  YOUR COLLECTION:")
        print("-" * 60)
        for i, s in enumerate(shares, 1):
            print(f"  [{i:2}] {s['code']}  \"{s['label']}\"")
        print("-" * 60)
        raw = input("  Jump to number (or blank to cancel): ").strip()
        if not raw:
            return
        try:
            idx = int(raw) - 1
            if 0 <= idx < len(shares):
                state["position"]  = shares[idx]["position"]
                state["page"]      = 0
                state["books_read"] = state.get("books_read", 0) + 1
                save_state(state)
                print(f"  Jumping to [{shares[idx]['code']}]...")
                time.sleep(0.8)
        except ValueError:
            pass

def display_controls():
    print("-" * 70)
    print("  NAVIGATE:  n/p = next/prev page       f/b = next/prev book")
    print("             F/B = next/prev shelf unit  J   = jump N shelf units")
    print("             U/D = up/down one floor     u/d = up/down one row")
    print("  ACTIONS:   t = take book    i = inventory    W = fall floors")
    print("             m = mark/share book    X = jump to share")
    print("             ? = Validate my Life's Book   q = quit")
    print("=" * 70)
    print()

def display_score(scores: dict, player: dict, taunt_index: int):
    """Show verdict first; offer breakdown on request."""
    taunts = get_taunts(player)
    taunt  = taunts[taunt_index % len(taunts)]

    print()
    print("-" * 60)
    print("  This is not your book.")
    print(f"  {DIM}{taunt}{RESET}")
    print("-" * 60)
    print()
    cmd = input("  [w] Why not?   [Enter] Continue: ").strip().lower()

    if cmd == "w":
        print()
        print("-" * 60)
        print(f"  Spelling:      {scores['spelling']    * 100:6.2f}%")
        print(f"  Readability:   {scores['readability'] * 100:6.2f}%")
        if scores.get("grammar_available"):
            print(f"  Grammar:       {scores['grammar'] * 100:6.2f}%")
        else:
            print(f"  Grammar:       {DIM}n/a (install language_tool_python + Java){RESET}")
        print(f"  Personal:      {scores['personal']    * 100:6.2f}%")
        print(f"  {chr(8212) * 25}")
        print(f"  Overall:       {scores['overall']     * 100:6.2f}%")
        print("-" * 60)
        input("\n  Press Enter to continue...")

# -- Win condition ------------------------------------------------------------
XANDERN_RELEASE_SYSTEM = """You are Xandern, the ancient demon who processed this soul at intake.
You are speaking to them for the last time -- they have found their book.
You know everything about them from their intake file.
Speak a brief, formal dismissal (4-6 sentences). Acknowledge the specific details of their life:
their name, birthplace, the names of their loves, their pet.
Note how long the search felt, and that it is now over.
Be neither warm nor cruel -- ancient, measured, final.
Do not use JSON. Just speak plainly."""

def _last_page_of_life(state: dict) -> str:
    """Generate page 410 of the player's life book -- the last lines."""
    return generate_page(state["life_book_position"], PAGES_PER_BOOK - 1)

def dramatic_win_reveal(state: dict, client, scores: dict):
    """The dramatic reveal sequence when the player finds their book."""
    player   = state["player"]
    page_text = scores["page_text"]

    clear()
    print()
    print("=" * 70)
    print()
    print("  Analysing...")
    print()
    time.sleep(1.5)

    # Animate the stats climbing
    labels = ["Spelling", "Readability", "Grammar", "Personal"]
    keys   = ["spelling", "readability", "grammar", "personal"]
    for label, key in zip(labels, keys):
        if key == "grammar" and not scores.get("grammar_available"):
            print(f"  {label:<14} {DIM}n/a{RESET}")
        else:
            val = scores[key] * 100
            print(f"  {label:<14} {val:6.2f}%")
        time.sleep(0.4)

    print(f"  {'─' * 25}")
    time.sleep(0.6)
    print(f"  {'Overall':<14} {scores['overall'] * 100:6.2f}%")
    time.sleep(1.5)

    clear()
    print()
    print("=" * 70)
    print()
    print(f"  {YELLOW}{BOLD}  . . . something is different . . .{RESET}")
    print()
    time.sleep(2)

    # Show the page with personal details highlighted
    highlighted = highlight_personal(page_text, player)
    print("-" * 70)
    for line in highlighted.split("\n"):
        print(f"  {line}")
        time.sleep(0.05)
    print("-" * 70)
    print()
    time.sleep(2)

    input(f"  {YELLOW}Press Enter to continue...{RESET}\n")

    # Xandern's final dismissal via API
    clear()
    print()
    print("=" * 70)
    print()
    print("  A presence you have not felt since the beginning makes itself known.")
    print()
    time.sleep(2)

    # Xandern's dismissal -- API if available, local pool otherwise
    elapsed_secs = time.time() - state.get("arrival_time", time.time())
    try:
        if client is not None:
            summary = (
                f"Soul: {player.get('name')}, born {player.get('birthdate')} "
                f"in {player.get('birthplace')}. "
                f"Pet: {player.get('pet')}. "
                f"First love: {player.get('first_love')}. "
                f"Last love: {player.get('last_love')}. "
                f"They have found their book after searching the Library."
            )
            response = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=400,
                system=XANDERN_RELEASE_SYSTEM,
                messages=[{"role": "user", "content": summary}],
            )
            speech = response.content[0].text.strip()
        else:
            speech = local_win_dismissal(player, elapsed_secs)
    except Exception:
        speech = local_win_dismissal(player, elapsed_secs)

    # Show the last page of the life book
    last_page = _last_page_of_life(state)
    highlighted_last = highlight_personal(last_page, player)

    print()
    for para in speech.split("\n"):
        if para.strip():
            for line in textwrap.wrap(para.strip(), width=66):
                print(f"  {line}")
                time.sleep(0.04)
        else:
            print()
    print()
    time.sleep(2)

    # Reveal the last page of the life book
    input(f"  {YELLOW}Press Enter to read the last page of your book...{RESET}\n")
    clear()
    print()
    print("=" * 70)
    print(f"  {YELLOW}{BOLD}THE LAST PAGE OF YOUR LIFE'S BOOK{RESET}")
    print(f"  {DIM}Page 410 of 410{RESET}")
    print("-" * 70)
    print()
    for line in highlighted_last.split("\n"):
        print(f"  {line}")
        time.sleep(0.04)
    print()
    print("-" * 70)
    time.sleep(2)

    print()
    print(f"  {YELLOW}{BOLD}You are free.{RESET}")
    print()
    time.sleep(3)

    # Delete save file -- the soul is released
    if STATE_FILE.exists():
        STATE_FILE.unlink()

    input("  Press Enter to leave the Library...\n")
    clear()
    sys.exit(0)

# -- State persistence --------------------------------------------------------
INVENTORY_MAX = 12

def save_state(state: dict):
    out = state.copy()
    out["position"]           = str(state["position"])
    out["life_book_position"] = str(state["life_book_position"])
    # inventory: ordered list of big-int positions (the pillowcase)
    out["inventory"]          = [str(p) for p in state.get("inventory", [])]
    # taken_books: set of all positions ever removed from shelf (inventory + discarded slots)
    out["taken_books"]        = [str(p) for p in state.get("taken_books", set())]
    out["taunt_index"]        = state.get("taunt_index", 0)
    out["arrival_time"]       = state.get("arrival_time", None)
    out["books_read"]         = state.get("books_read", 0)
    out["api_key"]            = state.get("api_key", "")
    STATE_FILE.write_text(json.dumps(out, indent=2))

def load_state() -> dict | None:
    if not STATE_FILE.exists():
        return None
    try:
        raw = json.loads(STATE_FILE.read_text())
        raw["position"]           = int(raw["position"])
        raw["life_book_position"] = int(raw["life_book_position"])
        raw["inventory"]          = [int(p) for p in raw.get("inventory", [])]
        raw["taken_books"]        = set(int(p) for p in raw.get("taken_books", []))
        raw.setdefault("taunt_index", 0)
        raw.setdefault("arrival_time", None)
        raw.setdefault("books_read", 0)
        raw.setdefault("api_key", "")
        return raw
    except Exception:
        return None

# -- Xandern interview --------------------------------------------------------
from hell_interview import run_local_interview, local_win_dismissal

XANDERN_API_SYSTEM = """You are Xandern, an 8-foot tall demon who processes newly-arrived souls in Hell.
You are ancient, bureaucratically efficient, faintly contemptuous, and darkly amused by mortals.
You speak in a formal, slightly archaic register. You are not cruel -- merely indifferent.
Your task is to conduct an intake interview to collect six pieces of information from the soul
before you assign them to the Library. You must collect:
  1. Their full name
  2. Their date of birth
  3. Their place of birth
  4. The name of a childhood pet (or favorite animal if they had none)
  5. The name of their first love
  6. The name of their last love

Weave the questions naturally into atmospheric pronouncements about their situation and fate.
Do not number the questions. React subtly to their answers.
When you have all six, end with a formal dismissal sending them to the Library.

Respond ONLY in JSON with three fields:
  "speech": your spoken words (plain text)
  "collected": dict of data gathered so far (keys: name, birthdate, birthplace, pet, first_love, last_love)
  "done": true only when you have all six and are dismissing them, false otherwise
"""

def xandern_interview_api(client) -> dict:
    """Run interview via Anthropic API."""
    print("\n" + "=" * 70 + "\n")
    conversation = []
    collected    = {}

    conversation.append({
        "role": "user",
        "content": "A new soul has arrived. Begin the intake interview."
    })

    while True:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1000,
            system=XANDERN_API_SYSTEM,
            messages=conversation,
        )
        raw = response.content[0].text.strip()

        if raw.startswith("```"):
            parts = raw.split("```")
            raw   = parts[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            data = {"speech": raw, "collected": {}, "done": False}

        speech = data.get("speech", "")
        collected.update(data.get("collected", {}))
        done = data.get("done", False)

        print()
        for line in textwrap.wrap(speech, width=68):
            print(f"  {line}")
        print()

        if done:
            break

        conversation.append({"role": "assistant", "content": raw})
        soul_input = input("  You: ").strip() or "(silence)"
        conversation.append({
            "role": "user",
            "content": (
                f"The soul says: {soul_input}\n\n"
                f"Continue. Collected so far: {json.dumps(collected)}"
            )
        })

    print("=" * 70)
    return collected

def run_interview(client) -> dict:
    """Run the interview -- API if available, local otherwise."""
    if client is not None:
        try:
            return xandern_interview_api(client)
        except Exception:
            print("  (API unavailable -- using local interview)")
    return run_local_interview()

# -- Inventory ----------------------------------------------------------------
INVENTORY_LABEL_LEN = 38

def inventory_label(pos: int) -> str:
    """First N printable chars of page 1 as a label."""
    page  = generate_page(pos, 0)
    label = page[:INVENTORY_LABEL_LEN].replace("\n", " ")
    return label

def show_inventory(state: dict):
    inv = state.get("inventory", [])
    print()
    print("=" * 70)
    print(f"  PILLOWCASE  ({len(inv)}/{INVENTORY_MAX})")
    print("-" * 70)
    if not inv:
        print("  (empty)")
    for i, pos in enumerate(inv, 1):
        label = inventory_label(pos)
        print(f"  [{i:2}]  {format_big(pos, 4):<28}  \"{label}\"")
    if len(inv) < INVENTORY_MAX:
        for i in range(len(inv) + 1, INVENTORY_MAX + 1):
            print(f"  [{i:2}]  --")
    print("-" * 70)
    print("  Enter number to read  |  d <number> to discard  |  q to close")
    print("=" * 70)
    print()

def inventory_controls():
    print("-" * 70)
    print("  READING FROM PILLOWCASE")
    print("  n/p = next/prev page    ? = Validate my Life's Book")
    print("  r   = return book to shelf                   q = back to inventory")
    print("=" * 70)
    print()

def read_inventory_book(state: dict, inv_index: int, client):
    """Read a book from the pillowcase. Returns when player exits."""
    inv = state.get("inventory", [])
    if inv_index < 0 or inv_index >= len(inv):
        return
    pos  = inv[inv_index]
    page = 0

    while True:
        clear()
        print("=" * 70)
        print("  A SHORT STAY IN HELL  --  IN INVENTORY")
        print("-" * 70)
        label = inventory_label(pos)
        print(f"  Pillowcase slot:  {inv_index + 1} of {len(inv)}")
        print(f'  Label:  \"{label}\"')
        print(f"  Page:   {page + 1} / {PAGES_PER_BOOK}")
        print("-" * 70)
        page_text = generate_page(pos, page)
        print()
        for line in page_text.split("\n"):
            print(f"  {line}")
        print()
        inventory_controls()

        cmd = input("  Command: ").strip()

        if cmd == "q":
            break
        elif cmd == "n":
            if page < PAGES_PER_BOOK - 1:
                page += 1
            else:
                print("  (Last page.)")
                time.sleep(0.8)
        elif cmd == "p":
            if page > 0:
                page -= 1
            else:
                print("  (First page.)")
                time.sleep(0.8)
        elif cmd == "r":
            # Return to shelf
            inv.pop(inv_index)
            state["inventory"] = inv
            state["taken_books"].discard(pos)
            save_state(state)
            print(f"  You slide the book back onto the shelf.")
            time.sleep(1.2)
            break
        elif cmd == "?":
            print("\n  Consulting the signs...")
            scores = score_page(generate_page(pos, page), state["player"],
                                pos, state["life_book_position"])
            if scores["is_life_book"]:
                dramatic_win_reveal(state, client, scores)
                return
            taunt_index = state.get("taunt_index", 0)
            display_score(scores, state["player"], taunt_index)
            state["taunt_index"] = taunt_index + 1
            save_state(state)

def inventory_loop(state: dict, client):
    """Main inventory screen loop."""
    while True:
        show_inventory(state)
        cmd = input("  Command: ").strip().lower()

        if cmd == "q":
            break

        elif cmd.startswith("d "):
            # Discard a book
            try:
                idx = int(cmd[2:].strip()) - 1
                inv = state.get("inventory", [])
                if idx < 0 or idx >= len(inv):
                    print("  Invalid slot.")
                    time.sleep(1)
                    continue
                pos = inv.pop(idx)
                state["inventory"] = inv
                state["taken_books"].discard(pos)
                save_state(state)
                print(f"  You slide the book back onto the shelf. The slot is open.")
                time.sleep(1.2)
            except ValueError:
                print("  Usage: d <number>")
                time.sleep(1)

        else:
            # Try to read a book by number
            try:
                idx = int(cmd) - 1
                inv = state.get("inventory", [])
                if idx < 0 or idx >= len(inv):
                    print("  Invalid slot.")
                    time.sleep(1)
                    continue
                read_inventory_book(state, idx, client)
            except ValueError:
                pass  # unknown command, redisplay

# -- Actions ------------------------------------------------------------------
def take_book(state: dict):
    pos = state["position"]
    inv = state.get("inventory", [])

    if pos in state["taken_books"]:
        print("  There is no book here to take.")
        time.sleep(1.2)
        return

    if len(inv) >= INVENTORY_MAX:
        # Pillowcase full -- offer to discard one
        print()
        print("  Your pillowcase is full.")
        print("  Do you want to throw out a book to make room?")
        print()
        show_inventory(state)
        raw = input("  Discard which book? (number, or blank to cancel): ").strip()
        if not raw:
            print("  Never mind.")
            time.sleep(1)
            return
        try:
            idx = int(raw) - 1
            if idx < 0 or idx >= len(inv):
                print("  Invalid slot. Cancelled.")
                time.sleep(1)
                return
            discarded = inv.pop(idx)
            state["taken_books"].discard(discarded)
            print(f"  You toss the book aside. It lands somewhere on the shelf.")
            time.sleep(0.8)
        except ValueError:
            print("  Cancelled.")
            time.sleep(1)
            return

    # Take the book
    inv.append(pos)
    state["inventory"]  = inv
    state["taken_books"].add(pos)
    save_state(state)
    print(f"  You stuff the book into your pillowcase. ({len(inv)}/{INVENTORY_MAX})")
    time.sleep(1.2)

def examine_book(state: dict, client):
    """'Is this my book?' -- score the current book with colorful feedback."""
    pos = state["position"]

    if pos in state["taken_books"]:
        print("  This slot is empty. Enter a book position to examine (or blank to cancel):")
        raw = input("  Position: ").strip()
        if not raw:
            return
        try:
            pos = int(raw)
        except ValueError:
            print("  Invalid position.")
            time.sleep(1)
            return

    print("\n  Consulting the signs...")
    page_text = generate_page(pos, state["page"])
    scores    = score_page(
        page_text,
        state["player"],
        pos,
        state["life_book_position"],
    )

    if scores["is_life_book"]:
        dramatic_win_reveal(state, client, scores)
        return  # unreachable -- win reveal calls sys.exit

    taunt_index = state.get("taunt_index", 0)
    display_score(scores, state["player"], taunt_index)
    state["taunt_index"] = taunt_index + 1
    save_state(state)

# -- Falling ------------------------------------------------------------------
def fall_physics(n_floors: int) -> dict:
    """
    Compute the real-world physics of falling n_floors at sea-level
    terminal velocity, including how many dehydration-deaths would be
    required if a single fall takes longer than DEHYDRATION_SECONDS.

    Returns a dict with: distance_m, fall_seconds, deaths_required,
    survivable_floors (the floors actually reached before death/limit).
    """
    distance_m = n_floors * FLOOR_HEIGHT_M

    # Time to fall at terminal velocity (ignoring the brief acceleration
    # phase -- negligible at any scale worth falling)
    fall_seconds = distance_m / TERMINAL_VELOCITY_MS

    if fall_seconds <= DEHYDRATION_SECONDS:
        # Survivable in a single fall -- no deaths required
        return {
            "distance_m":        distance_m,
            "fall_seconds":      fall_seconds,
            "deaths_required":   0,
            "survivable_floors": n_floors,
        }

    # Distance coverable before dehydration claims you
    distance_per_life_m = TERMINAL_VELOCITY_MS * DEHYDRATION_SECONDS
    floors_per_life      = distance_per_life_m / FLOOR_HEIGHT_M

    # How many death-cycles to cover the requested distance
    deaths_required = math.ceil(n_floors / floors_per_life)

    return {
        "distance_m":        distance_m,
        "fall_seconds":      fall_seconds,
        "deaths_required":   deaths_required,
        "floors_per_life":   floors_per_life,
        "survivable_floors": n_floors,   # the fall itself is "successful" --
                                          # it just takes many lifetimes
    }

def format_fall_duration(seconds: float) -> str:
    """Human-readable duration, scaling up to cosmological terms if needed."""
    if seconds < 60:
        return f"{seconds:.1f} seconds"
    if seconds < 3600:
        return f"{seconds/60:.1f} minutes"
    if seconds < 86400:
        return f"{seconds/3600:.1f} hours"
    days = seconds / 86400
    if days < 365:
        return f"{days:,.1f} days"
    years = days / 365
    if years < 1000:
        return f"{years:,.1f} years"
    # Beyond this, use log-scale notation
    log10_years = math.log10(years)
    return f"10^{log10_years:,.0f} years"

def fall_floors(state: dict):
    """Player jumps/falls down N floors -- with real fall physics."""

    # Already at the bottom -- there is nothing to fall into
    if state["position"] == 0:
        clear()
        print()
        print("=" * 70)
        print()
        print("  You are already at the bottom of the Library.")
        time.sleep(0.6)
        print("  There is a floor here. There is nowhere lower to go.")
        time.sleep(0.6)
        print("  You could jump, if you wanted. You would simply land")
        print("  exactly where you are standing.")
        time.sleep(0.8)
        print()
        print("=" * 70)
        input("\n  Press Enter to continue...\n")
        return

    try:
        raw = input("  Fall how many floors? ").strip()
        n   = int(raw)
        if n <= 0:
            print("  You think better of it.")
            time.sleep(1)
            return
    except ValueError:
        print("  Never mind.")
        time.sleep(1)
        return

    # Clamp the actual floors fallen to what the library allows
    # (position can never go below 0 -- the literal bottom of the library)
    current_pos       = state["position"]
    requested_units   = n * UNITS_PER_FLOOR
    actual_units      = min(requested_units, current_pos)
    actual_floors     = actual_units // UNITS_PER_FLOOR
    reaches_bottom    = (actual_units >= current_pos)

    # Physics is computed on the floors ACTUALLY fallen, not the request
    physics = fall_physics(actual_floors)

    state["position"] = clamp(current_pos - actual_units)
    state["page"]     = 0

    # Advance the Great Clock by the time the fall actually took.
    # A fall through dehydration deaths still costs real time -- the
    # Library does not let you skip the suffering, only survive it.
    state["arrival_time"] = state.get("arrival_time", time.time()) - physics["fall_seconds"]

    save_state(state)

    clear()
    print()
    print("=" * 70)
    print()

    if reaches_bottom and requested_units > current_pos:
        # They asked to fall further than the library allows -- and made it
        print("  You fall, and fall, and fall.")
        time.sleep(0.6)
        print("  Eventually there is a floor beneath you, because the")
        print("  Library, vast as it is, is not infinite in this direction.")
        time.sleep(0.8)
        print()
        print(f"  You requested {n:,} floors. Only {format_big(actual_floors)}")
        print(f"  existed beneath you.")
        time.sleep(0.8)
        print()
        print("  You strike the bottom.")
        time.sleep(0.6)
        print("  There is a floor here, same as all the others -- same")
        print("  shelves, same silence, same impossible mathematics")
        print("  stretching back up into darkness you cannot see the end of.")
        time.sleep(0.6)
        print("  You have arrived at the only verifiably finite point in")
        print("  the entire Library.")
        time.sleep(0.8)
        print("  It does not help.")
        time.sleep(1.0)
    elif reaches_bottom:
        # They asked for exactly enough to reach bottom
        print("  You fall the requested distance, precisely.")
        time.sleep(0.5)
        print()
        print("  You strike the bottom.")
        time.sleep(0.6)
        print("  There is a floor here, same as all the others -- same")
        print("  shelves, same silence, same impossible mathematics")
        print("  stretching back up into darkness you cannot see the end of.")
        time.sleep(0.6)
        print("  You have arrived at the only verifiably finite point in")
        print("  the entire Library.")
        time.sleep(0.8)
        print("  It does not help.")
        time.sleep(1.0)
    else:
        msg = fall_message(min(n, 1_000_000))  # cap message lookup at sane range
        for line in msg.split("\n"):
            print(f"  {line}")
            time.sleep(0.3)

    print()
    print(f"  Floors fallen:     {format_big(actual_floors)}")
    print(f"  Distance:          {physics['distance_m']:,.0f} meters "
          f"({physics['distance_m']/1000:,.1f} km)")

    if physics["deaths_required"] > 0:
        print()
        print(f"  At terminal velocity ({TERMINAL_VELOCITY_MS:.0f} m/s) this fall")
        print(f"  would take {format_fall_duration(physics['fall_seconds'])}.")
        print(f"  You cannot survive that long without water.")
        print()
        if physics["deaths_required"] > 10**6:
            log10_deaths = math.log10(physics["deaths_required"])
            print(f"  Deaths required to complete this fall: 10^{log10_deaths:,.0f}")
        else:
            print(f"  Deaths required to complete this fall: {physics['deaths_required']:,}")
        print(f"  The Great Clock has been advanced accordingly.")
        print(f"  You arrive having already lived through all of it.")
    else:
        print(f"  Fall time:         {format_fall_duration(physics['fall_seconds'])}")
        print(f"  (survived without incident)")

    print()
    print("=" * 70)
    input("\n  Press Enter to collect yourself...\n")

# -- Navigation ---------------------------------------------------------------
def clamp(pos: int) -> int:
    return max(0, min(pos, TOTAL_BOOKS - 1))

def navigate(state: dict, cmd: str) -> bool:
    pos  = state["position"]
    page = state["page"]
    old_pos = pos

    if cmd == "n":
        if page < PAGES_PER_BOOK - 1:
            state["page"] = page + 1
        else:
            print("  (Last page.)")
            time.sleep(0.8)
            return False
    elif cmd == "p":
        if page > 0:
            state["page"] = page - 1
        else:
            print("  (First page.)")
            time.sleep(0.8)
            return False
    elif cmd == "f":
        state["position"] = clamp(pos + 1)
        state["page"] = 0
    elif cmd == "b":
        state["position"] = clamp(pos - 1)
        state["page"] = 0
    elif cmd == "F":
        state["position"] = clamp(pos + BOOKS_PER_UNIT)
        state["page"] = 0
    elif cmd == "B":
        state["position"] = clamp(pos - BOOKS_PER_UNIT)
        state["page"] = 0
    elif cmd == "J":
        try:
            n = int(input("  Jump how many shelf units? (positive = right, negative = left): ").strip())
            state["position"] = clamp(pos + n * BOOKS_PER_UNIT)
            state["page"] = 0
        except ValueError:
            return False
    elif cmd == "U":
        state["position"] = clamp(pos + UNITS_PER_FLOOR)
        state["page"] = 0
    elif cmd == "D":
        state["position"] = clamp(pos - UNITS_PER_FLOOR)
        state["page"] = 0
    elif cmd == "u":
        state["position"] = clamp(pos + BOOKS_PER_ROW)
        state["page"] = 0
    elif cmd == "d":
        state["position"] = clamp(pos - BOOKS_PER_ROW)
        state["page"] = 0
    else:
        return False
    # If position changed, count it as a new book read
    if state["position"] != old_pos:
        state["books_read"] = state.get("books_read", 0) + 1
    return True



# -- Main game loop -----------------------------------------------------------
def game_loop(state: dict, client):
    while True:
        display_page(state)
        cmd = input("  Command: ").strip()

        if cmd == "q":
            save_state(state)
            print("\n  Your place has been saved. Hell persists.")
            print("  You will return.\n")
            sys.exit(0)
        elif cmd == "t":
            take_book(state)
        elif cmd == "i":
            inventory_loop(state, client)
        elif cmd == "W":
            fall_floors(state)
        elif cmd == "m":
            mark_book(state)
        elif cmd == "X":
            jump_to_share(state)
        elif cmd == "?":
            examine_book(state, client)
        elif cmd in ("n", "p", "f", "b", "F", "B", "J", "U", "D", "u", "d"):
            changed = navigate(state, cmd)
            if changed:
                save_state(state)

# -- Entry point --------------------------------------------------------------
def main():
    # Determine API key -- check env, then saved state, then ask
    api_key  = os.environ.get("ANTHROPIC_API_KEY")
    existing = load_state()

    if not api_key and existing:
        api_key = existing.get("api_key")

    client = get_anthropic_client(api_key)

    if existing:
        clear()
        print("\n" + "=" * 70)
        print()
        print("  You open your eyes.")
        print()
        print(f"  Welcome back, {existing['player'].get('name', 'soul')}.")
        print()
        print("  The shelves stretch away in both directions, unchanged.")
        print("  You are exactly where you left off.")
        print()
        print("=" * 70)
        # Rebuild client from saved key if env key not set
        if not api_key:
            saved_key = existing.get("api_key", "")
            if saved_key:
                client = get_anthropic_client(saved_key)
        input("\n  Press Enter to continue your search...\n")
        game_loop(existing, client)

    else:
        clear()
        print("\n" + "=" * 70)
        print()
        print("  You become aware that you are seated.")
        print("  The chair is metal. It is cold.")
        print("  Somewhere nearby, people are screaming.")
        print()
        print("=" * 70)
        input("\n  Press Enter...\n")

        # Ask for API key if not already set
        if not api_key:
            print()
            print("  An Anthropic API key enables a richer interview experience.")
            print("  You can get one free at console.anthropic.com")
            raw_key = input("  API key (or press Enter to skip): ").strip()
            if raw_key:
                api_key = raw_key
                client  = get_anthropic_client(api_key)

        mode_str = "AI-powered" if client is not None else "local engine"
        print()
        print(f"  {DIM}[ Interview: {mode_str} ]{RESET}")
        print()
        player = run_interview(client)

        for key in ("name", "birthdate", "birthplace", "pet", "first_love", "last_love"):
            if key not in player or not player[key]:
                player[key] = input(
                    f"  (Please provide your {key.replace('_', ' ')}): "
                ).strip()

        life_pos  = derive_life_book_position(player)
        start_pos = random.randint(0, TOTAL_BOOKS - 1)

        import time as _time
        state = {
            "player":            player,
            "position":          start_pos,
            "page":              0,
            "taken_books":       set(),
            "inventory":         [],
            "life_book_position": life_pos,
            "taunt_index":       0,
            "arrival_time":      _time.time(),
            "books_read":        0,
            "api_key":           api_key or "",
        }

        save_state(state)

        clear()
        print("\n" + "=" * 70)
        print()
        print("  A door opens.")
        print()
        print("  The Library stretches before you -- impossibly vast,")
        print("  impossibly silent, save for the soft sound of your")
        print("  own breathing.")
        print()
        print("  Your book is here. Somewhere.")
        print()
        print("=" * 70)
        input("\n  Press Enter to begin your search...\n")

        game_loop(state, client)

if __name__ == "__main__":
    main()
