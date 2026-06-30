# A Short Stay in Hell

> *"The library contains every book that can possibly be written on 410 pages,
> with 40 lines of 80 characters on each page. Your book is in there.
> Find it, and you are free."*

A terminal-based existential exploration inspired by the novella
**[A Short Stay in Hell](https://stevepeckniche.com/)** by **Steven L. Peck** (2012).

In Peck's vision, Hell is not fire and brimstone. It is a library —
vast beyond comprehension — containing every book that could possibly
exist. Somewhere in its infinite stacks is a book that tells the
complete story of your life. Find it, and you are released. The
catch: the library contains 95^1,312,000 books. The universe will
end long before you finish looking.

This program is a faithful computational implementation of that library.
Your book is genuinely in there. So is everyone else's.

---

## Credit

This project is a loving tribute to **A Short Stay in Hell** by
**Steven L. Peck**, a philosopher, ecologist, and novelist at Brigham
Young University. The novella is a masterwork of existential horror —
brief, devastating, and impossible to forget.

The library structure is based on **"The Library of Babel"** (1941)
by **Jorge Luis Borges**, which Peck used as the foundation for his
own vision of Hell.

Please read both works. They will change how you think about infinity,
meaning, and the terrifying arithmetic of everything.

- Steven L. Peck: [stevepeckniche.com](https://stevepeckniche.com/)
- *A Short Stay in Hell* on [Goodreads](https://www.goodreads.com/book/show/13456414-a-short-stay-in-hell)
- *The Library of Babel* by Borges — available in *Labyrinths* (1962)

---

## The Library

The library in this program is mathematically faithful to Peck's description:

- **410 pages** per book
- **40 lines** per page
- **80 characters** per line
- **95 printable ASCII characters** in the character set
- **95^1,312,000 total books** — a number with approximately 2.6 million digits

The library is arranged on floors, each shaped like an enormous "O"
with two sides (Left and Right) connected at each end. Each floor
contains shelf units of 8 rows × 35 books. Navigation is on foot.
There is a gap between the two sides of each floor. You can jump in.

Every book is generated deterministically from its position number.
The same position always produces the same book. Nothing is stored.
The entire library exists as pure mathematics.

---

## Your Book

When you first run the program, Xandern — the intake demon — conducts
a brief interview. Your answers (name, birthdate, birthplace, pet,
first love, last love) are combined and hashed to produce a unique
position number in the library. That position is the address of the
book that contains the story of your life.

**Your book genuinely exists at that address.** It is not randomly
assigned after the fact. It was always there, waiting, in the
mathematical structure of the library — before you were born,
before the program existed, before the universe began.

You will almost certainly never find it.

---

## Can You Cheat?

Yes. But, also no.

`find_notable.py` exists for exactly this purpose. It walks the Library
far faster than any soul could on foot, checking thousands of books per
second instead of one book at a time, sorting through the noise for
fragments of real language. Run it across multiple CPU cores and you
can tiptoe through the Library at whatever speed your compute cores
allow you to operate — a privilege denied to every soul inside the
story itself.

It does not matter.

The library contains 95^1,312,000 books. At a generous ten thousand
books per second across many cores, searching the entire library would
take approximately 10^(1,312,000) seconds. The current age of the
universe is about 10^10 years, which is roughly 10^17 seconds.

Run the numbers yourself: the speedup `find_notable.py` provides over
a human turning pages by hand is enormous and the distance remaining
is enormous beyond enormous. Multiplying a very large number by a
very large speedup leaves you with a number that is, for all practical
purposes, exactly as large. The decimal point does not move far enough
to notice.

Cheating does not move the needle. It makes the needle irrelevant.

The only way to find your book is to find it.

---

## Sharing Books

The Library is not entirely solitary. Souls share what they find.

When you discover a book of unusual interest — one that contains
fragments of coherent text, a phrase that moves you, or something
that feels almost meaningful — you can **mark it** (`m`) with a
label and export it as a small `.hell` file. Send that file to
another soul. They can **import** it (`X`) and jump directly to
that book in their own Library.

More profoundly: if you find another soul's **life book** — the
one that tells the story of their life — and you validate it
successfully, you have hastened their release from Hell. They
are transcended. You have done for them what they could not do
alone: stood in the right place at the right time.

Share files live in `~/.hell_shares/` as `<code>.hell` files
(approximately 1MB each). They can be sent by email, posted in
forums, or dropped in a shared folder. The 8-character code
in the filename identifies the book uniquely.

You cannot fake a life book match. The validation is
mathematically exact.

---

## Installation

### Prerequisites: Python 3.12 or later

**Windows:**
Download from [python.org](https://python.org) and check
"Add Python to PATH" during installation. Or install from
the Microsoft Store (search "Python 3.12").

**macOS:**
```bash
brew install python
```
Or download from [python.org](https://python.org).

**Linux (Ubuntu/Debian):**
```bash
sudo apt install python3 python3-pip
```

**Linux (Fedora):**
```bash
sudo dnf install python3 python3-pip
```

Verify: `python3 --version` should show 3.12 or later.

---

### Get the Files

Download both files into the same directory:

- `hell.py` — the main program
- `hell_interview.py` — the local interview engine

---

### Install Python Dependencies

**Minimum install** (spelling + readability scoring, local interview):
```bash
pip install pyspellchecker textstat nltk
```

**With AI interview** (requires an Anthropic API key):
```bash
pip install anthropic
```
Get a free API key at [console.anthropic.com](https://console.anthropic.com).
You will be asked for it on first run. Press Enter to skip.

**With grammar checking** (most complete scoring — requires Java):

First install Java:
- **Windows / macOS:** Download Temurin 17 LTS from [adoptium.net](https://adoptium.net)
- **Linux:** `sudo apt install default-jre`

Then:
```bash
pip install language_tool_python
```

On Linux, if you receive a system package warning:
```bash
pip install pyspellchecker textstat nltk anthropic language_tool_python --break-system-packages
```

---

### First Run

```bash
python3 hell.py
```

On Windows:
```
python hell.py
```

**Notes on first run:**
- You will be asked if you have an Anthropic API key. Press Enter
  to skip — the local interview engine works without one.
- If grammar checking is installed, the first use of
  "Validate my Life's Book" (`?`) will pause for 30–60 seconds
  while the grammar tool initializes. Subsequent uses are instant.
- Your save file is written to `~/.hell_state.json`. **Do not
  delete it** — once you enter the Library, you cannot start over
  until you find your book.

---

## Navigation

```
NAVIGATE:  n/p = next/prev page       f/b = next/prev book
           F/B = next/prev shelf unit  J   = jump N shelf units
           U/D = up/down one floor     u/d = up/down one row
           W   = fall floors (the gap between sides)

ACTIONS:   t = take book              i = inventory (pillowcase)
           m = mark/share book        X = jump to share
           ? = Validate my Life's Book
           q = save and quit
```

**Jumping (J):** Enter a positive number to move right along the
shelf, negative to move left. You can jump millions of shelf units
at once. It will not help as much as you hope.

**Falling (W):** You can jump into the gap between the two sides
of a floor and fall any number of floors. Falls under 5 floors
leave you bruised. Falls over 100 floors result in death and
revival, per Rule Four of the Library.

**The pillowcase (i):** You can carry up to 12 books. When full,
you must discard one to take another. Books removed from the shelf
leave an empty slot. Returned books go back to their original place.

---

## Validating Your Book (`?`)

Standing before any book, press `?` to ask: *Is this my book?*

The program analyses the current page for:

| Component | Weight | Requires |
|-----------|--------|----------|
| Spelling | 20% | pyspellchecker |
| Readability | 20% | textstat |
| Grammar | 20% | language_tool_python + Java |
| Personal resonance | 40% | your interview answers |

If grammar checking is unavailable, its weight is redistributed
across the other components.

A random book scores near 0% on everything. A book containing
your name, birthplace, and the names of your loves would score
dramatically higher. Your life book scores 100% and triggers
the win condition.

Press `w` after a failed validation to see the detailed breakdown.

---

## The Great Clock

The header displays the Great Clock — elapsed time since your
first arrival in the Library, measured in:

```
Reckonings : 0   Ages : 0   Eons : 0   Millennia : 0
Centuries  : 0   Decades : 0   Years : 0   Days : 2
Hours : 5   Minutes : 22   Seconds : 47
```

The upper units (Reckonings, Ages, Eons) are shown as zero for
any human timescale. They are there to remind you of what the
Library was built for. A Reckoning is defined as 95^1,312,000
seconds — the time required to read every book in the Library
at one page per second.

The clock cannot be paused. It runs from the moment of your
arrival regardless of whether the program is open.

---

## Save File

Your state is saved automatically to `~/.hell_state.json` after
every action. This includes:

- Your position in the Library (a ~2.6 million digit number)
- Your current page
- The contents of your pillowcase
- All shelf slots you have emptied
- Your arrival time
- Your books read count

The save file is plain JSON and can be edited manually. If you
need to set a specific arrival time, add:

```json
"arrival_time": 1751234567.0
```

where the value is a Unix timestamp (seconds since January 1, 1970).
To find the timestamp for a specific date:
```bash
date -d "2026-06-26 14:00:00" +%s    # Linux/macOS
```

---

## Technical Notes

- Books are generated using Python's `random.Random` seeded with
  `position * 410 + page_number`. The same seed always produces
  the same page. No books are stored.
- Your life book position is derived from your interview answers
  via SHA-512, then mapped into the library range. It is fixed
  and deterministic.
- Share files use zlib compression of the raw position integer,
  approximately 1MB per file.
- The program requires `sys.set_int_max_str_digits(0)` to handle
  the ~2.6 million digit position numbers. This is set automatically.

---

## License

This program is offered freely as a tribute to Steven L. Peck's work.
Please read the novella.

*The Library does not require attribution. It contains everything,
including this README.*
