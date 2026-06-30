#!/usr/bin/env python3
"""
find_notable.py -- Search the Library for books with unusually high
spelling scores, suitable for use as example finds to share with others.

Usage:
    python3 find_notable.py [--target 7] [--books 100000] [--pages 1] [--workers 4]

Options:
    --target   Minimum spelling score %% to qualify (default: 7)
    --books    Number of books to search this run (default: 100000)
    --pages    Pages to check per book (default: 1)
    --workers  CPU workers for parallel search (default: all cores)
    --seed     Random seed -- only used on a fresh start, ignored on resume
    --output   Output JSON filename (default: notable_finds.json)
    --reset    Discard saved state and start fresh

Runs accumulate: results and RNG state are saved between runs so you
can stop and resume at any time. Each new run continues from where the
last one left off, appending new finds to the existing collection.

Both hell.py and find_notable.py must be in the same directory.
"""

import sys
import os
import re
import json
import time
import random
import argparse
import signal
import multiprocessing
from pathlib import Path

sys.set_int_max_str_digits(0)

try:
    import hell
except ImportError:
    try:
        import hell_core as hell
    except ImportError:
        print("Neither hell.py nor hell_core.py found in this directory.")
        print("Drop at least one of them alongside find_notable.py.")
        sys.exit(1)

try:
    from spellchecker import SpellChecker
    import textstat
except ImportError:
    print("Run: pip install pyspellchecker textstat")
    sys.exit(1)

# ── Word list ─────────────────────────────────────────────────────────────────
# Built once in the main process; workers import their own copy on startup.
print("  Loading word list...", end="", flush=True)
_spell = SpellChecker()
_wf    = _spell.word_frequency
print(" done.")

_PREFILTER = 0.05

def spelling_score(page_text: str) -> float:
    words = re.findall(r'[a-zA-Z]{3,}', page_text)
    if not words:
        return 0.0
    return sum(1 for w in words if w.lower() in _wf) / len(words)

def quick_score(page_text: str) -> tuple[float, float]:
    sp = spelling_score(page_text)
    if sp >= _PREFILTER:
        try:
            flesch = textstat.flesch_reading_ease(page_text)
            rd     = max(0.0, min(flesch / 100.0, 1.0))
        except Exception:
            rd = 0.0
    else:
        rd = 0.0
    return sp, rd

def real_words(page_text: str) -> list[str]:
    return [w for w in re.findall(r'[a-zA-Z]{3,}', page_text)
            if w.lower() in _wf]

def longest_word_info(words: list[str]) -> tuple[str, int]:
    """Return (longest_word, length). Empty string/0 if no words found."""
    if not words:
        return "", 0
    longest = max(words, key=len)
    return longest, len(longest)

def length_weighted_score(words: list[str], total_fragments: int) -> float:
    """
    Score that rewards rare long words far more than common short ones.
    A 3-letter match contributes 1 point, 4-letter contributes 4,
    5-letter contributes 9, 6-letter contributes 16, etc. -- since
    longer real-word matches are exponentially less likely by chance,
    this surfaces genuinely improbable finds rather than just word-dense
    pages full of cheap 3-letter coincidences.
    """
    if not words or total_fragments == 0:
        return 0.0
    weighted_sum = sum((len(w) - 2) ** 2 for w in words)
    return weighted_sum / total_fragments

# ── Worker function (runs in a subprocess) ────────────────────────────────────
def _worker_init():
    """Initialise per-worker state. Called once when each worker starts."""
    # Workers need their own SpellChecker instance -- the global _wf is
    # inherited via fork on Linux but not on Windows/macOS spawn.
    global _wf
    try:
        from spellchecker import SpellChecker
        _wf = SpellChecker().word_frequency
    except Exception:
        pass

def _score_batch(args: tuple) -> list[dict]:
    """
    Score a batch of book positions. Called in a worker process.
    args = (positions, pages_per_book, target, min_word_length)
    Returns a list of qualifying result dicts (may be empty).

    A book qualifies if EITHER its spelling score clears `target`,
    OR it contains a real word at least `min_word_length` letters long
    (since long words are individually remarkable regardless of the
    overall page's spelling percentage).
    """
    positions, pages_per_book, target, min_word_length = args
    results = []

    for pos in positions:
        best_sp      = 0.0
        best_rd      = 0.0
        best_pg      = 0
        best_txt     = ""
        best_words   = []
        best_longest = ("", 0)

        for page_num in range(pages_per_book):
            page_text = hell.generate_page(pos, page_num)
            sp, rd    = quick_score(page_text)
            words     = real_words(page_text) if sp > 0 else []
            longest   = longest_word_info(words)

            combined      = sp * 0.7 + rd * 0.3
            prev_combined = best_sp * 0.7 + best_rd * 0.3

            # Track whichever page is more interesting: higher spelling
            # score OR a longer word found, whichever comes first
            is_better = (combined > prev_combined or
                         longest[1] > best_longest[1])

            if is_better:
                best_sp      = sp
                best_rd      = rd
                best_pg      = page_num
                best_txt     = page_text
                best_words   = words
                best_longest = longest

        qualifies = (best_sp >= target) or (best_longest[1] >= min_word_length)

        if qualifies:
            weighted = length_weighted_score(best_words, len(re.findall(r'[a-zA-Z]{3,}', best_txt)) or 1)
            results.append({
                "position":      pos,
                "page":          best_pg,
                "spelling":      round(best_sp, 4),
                "readability":   round(best_rd, 4),
                "combined":      round(best_sp * 0.7 + best_rd * 0.3, 4),
                "weighted":      round(weighted, 4),
                "longest_word":  best_longest[0],
                "longest_len":   best_longest[1],
                "words_found":   best_words[:20],
                "preview":       best_txt[:200].replace("\n", " "),
            })

    return results

# ── State persistence ─────────────────────────────────────────────────────────
def state_file(output_file: str) -> str:
    p = Path(output_file)
    return str(p.parent / (p.stem + "_state.json"))

def load_state(output_file: str) -> dict | None:
    sf = state_file(output_file)
    if not Path(sf).exists():
        return None
    try:
        with open(sf) as f:
            return json.load(f)
    except Exception:
        return None

def save_state(output_file: str, rng: random.Random,
               found: list, total_checked: int,
               target_pct: float, pages_per_book: int):
    sf    = state_file(output_file)
    state = {
        "rng_state":      list(rng.getstate()[1]),
        "rng_version":    rng.getstate()[0],
        "total_checked":  total_checked,
        "total_found":    len(found),
        "target_pct":     target_pct,
        "pages_per_book": pages_per_book,
        "saved_at":       time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    with open(sf, "w") as f:
        json.dump(state, f, indent=2)

def load_finds(output_file: str) -> list:
    if not Path(output_file).exists():
        return []
    try:
        with open(output_file) as f:
            return json.load(f)
    except Exception:
        return []

def save_finds(output_file: str, found: list):
    with open(output_file, "w") as f:
        json.dump(found, f, indent=2)

def restore_rng(state: dict) -> random.Random:
    rng = random.Random()
    rng.setstate((state["rng_version"], tuple(state["rng_state"]), None))
    return rng

# ── Progress bar ──────────────────────────────────────────────────────────────
def progress(checked: int, target_n: int, found: int,
             total_checked: int, best: float, longest: int,
             rate: float, workers: int):
    pct   = checked / target_n * 100
    eta_s = (target_n - checked) / rate if rate > 0 else 0
    eta   = time.strftime("%H:%M:%S", time.gmtime(eta_s))
    blen  = 20
    bar   = "█" * int(blen * checked / target_n) + "░" * (blen - int(blen * checked / target_n))
    print(
        f"\r  [{bar}] {pct:5.1f}%  "
        f"Run: {checked:,}/{target_n:,}  "
        f"Total: {total_checked:,} / {found} found  "
        f"Best: {best*100:5.2f}%  Longest word: {longest}  "
        f"{rate:,.0f}/s ({workers}w)  ETA: {eta}  ",
        end="", flush=True
    )

# ── Search ────────────────────────────────────────────────────────────────────
# Batch size: how many positions each worker processes per task.
# Larger = less IPC overhead; smaller = more responsive progress updates.
_BATCH = 500

def search(target_pct: float, n_books: int, pages_per_book: int,
           output_file: str, seed: int | None, n_workers: int,
           min_word_length: int) -> list:

    target      = target_pct / 100.0
    MAX_POS     = 10 ** 18
    interrupted = False

    # ── Load or initialise state ──────────────────────────────────────────────
    saved = load_state(output_file)
    found = load_finds(output_file)

    seen_positions = set()
    deduped = []
    for f in found:
        if f["position"] not in seen_positions:
            seen_positions.add(f["position"])
            deduped.append(f)
    found = deduped
    found.sort(key=lambda x: (x.get("longest_len", 0),
                               x.get("weighted", 0),
                               x.get("combined", 0)), reverse=True)

    if saved:
        rng           = restore_rng(saved)
        total_checked = saved["total_checked"]
        print(f"  Resuming from previous run.")
        print(f"  All-time: {total_checked:,} books checked, {len(found)} notable finds.")
        if saved.get("target_pct") != target_pct:
            print(f"  Note: previous runs used target {saved['target_pct']}%, "
                  f"this run uses {target_pct}%.")
    else:
        rng           = random.Random(seed)
        total_checked = 0
        if seed is not None:
            print(f"  Fresh start with seed {seed}.")
        else:
            print(f"  Fresh start (no seed -- each run explores new territory).")

    print()

    best_global       = max((f["spelling"] for f in found), default=0.0)
    longest_global    = max((f.get("longest_len", 0) for f in found), default=0)
    rate        = 1.0
    start       = time.time()
    run_checked = 0

    # ── Signal handling -- workers must ignore SIGINT, main process handles it ─
    original_sigint = signal.getsignal(signal.SIGINT)

    def handle_interrupt(sig, frame):
        nonlocal interrupted
        interrupted = True

    signal.signal(signal.SIGINT, handle_interrupt)

    # ── Worker pool ───────────────────────────────────────────────────────────
    # initializer=_worker_init ensures each worker rebuilds its word list.
    # maxtasksperchild recycles workers periodically to avoid memory creep.
    ctx = multiprocessing.get_context("fork" if os.name != "nt" else "spawn")

    with ctx.Pool(
        processes       = n_workers,
        initializer     = _worker_init,
        maxtasksperchild = 200,
    ) as pool:

        while run_checked < n_books and not interrupted:
            # Generate a batch of positions in the main process (maintains RNG sequence)
            remaining  = n_books - run_checked
            batch_size = min(_BATCH * n_workers, remaining)
            positions  = [rng.randint(0, MAX_POS) for _ in range(batch_size)]

            # Split into per-worker chunks
            chunk_size = max(1, batch_size // n_workers)
            chunks     = [
                positions[i:i + chunk_size]
                for i in range(0, len(positions), chunk_size)
            ]
            tasks = [(chunk, pages_per_book, target, min_word_length) for chunk in chunks]

            # Dispatch to workers and collect results
            try:
                batch_results = pool.map(_score_batch, tasks, chunksize=1)
            except Exception:
                break

            # Flatten and merge results
            for worker_results in batch_results:
                for result in worker_results:
                    pos = result["position"]
                    if pos not in seen_positions:
                        seen_positions.add(pos)
                        found.append(result)
                        best_global    = max(best_global, result["spelling"])
                        longest_global = max(longest_global, result.get("longest_len", 0))

            # Sort by longest word found first (the rarer, more interesting
            # signal), then by weighted score, then by raw spelling percentage
            found.sort(key=lambda x: (x.get("longest_len", 0),
                                       x.get("weighted", 0),
                                       x["combined"]), reverse=True)

            run_checked   += batch_size
            total_checked += batch_size

            # Save every ~5000 books
            if run_checked % 1000 < batch_size or interrupted:
                save_finds(output_file, found)
                save_state(output_file, rng, found, total_checked,
                           target_pct, pages_per_book)

            elapsed = time.time() - start
            rate    = run_checked / elapsed if elapsed > 0 else 1
            progress(run_checked, n_books, len(found),
                     total_checked, best_global, longest_global, rate, n_workers)

    print()

    # Final save
    save_finds(output_file, found)
    save_state(output_file, rng, found, total_checked,
               target_pct, pages_per_book)

    signal.signal(signal.SIGINT, original_sigint)
    return found

# ── Display results ───────────────────────────────────────────────────────────
def show_results(found: list, output_file: str):
    if not found:
        print("\n  No books found meeting the target yet.")
        print("  Try lowering --target, lowering --min-word-length,")
        print("  or running again to search more books.")
        return

    print(f"\n  {len(found)} notable book(s) in collection. Top 10")
    print("  (sorted by longest word found, then weighted rarity, then spelling %):")
    print()
    print("  " + "=" * 66)
    print("  NOTABLE FINDS")
    print("  " + "=" * 66)

    for i, book in enumerate(found[:10], 1):
        code      = hell.book_share_code(book["position"])
        longest   = book.get("longest_word", "")
        long_len  = book.get("longest_len", 0)
        weighted  = book.get("weighted", 0)

        if long_len >= 5:
            label = f"notable find #{i} — \"{longest}\" ({long_len} letters)"
        else:
            label = f"notable find #{i} — spelling {book['spelling']*100:.1f}%"

        print(f"\n  [{i:2}] Code:          {code}")
        print(f"        Position:      {book['position']}")
        print(f"        Page:          {book['page'] + 1} / {hell.PAGES_PER_BOOK}")
        if longest:
            print(f"        Longest word:  \"{longest}\" ({long_len} letters)")
        print(f"        Spelling:      {book['spelling']    * 100:6.2f}%")
        print(f"        Readability:   {book['readability'] * 100:6.2f}%")
        print(f"        Weighted:      {weighted:6.2f}  (rewards rare long words)")
        print(f"        Words found:   {book['words_found'][:10]}")
        print(f"        Preview:       \"{book['preview'][:70]}...\"")

        try:
            out = hell.export_share(book["position"], label)
            print(f"        Share file:    {out}")
        except Exception as e:
            print(f"        Share export failed: {e}")

    print()
    print("  " + "=" * 66)
    print()
    print("  Results saved to:      " + output_file)
    print("  Search state saved to: " + state_file(output_file))
    print()
    print("  Run again to continue searching. State is preserved automatically.")
    print("  Import a find: run hell.py → X → option 1 → enter .hell file path")
    print("  Share a find:  post the 8-character code in Discussions or FOUND.md")

# ── Entry point ───────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="Search the Library for notable books. Resumes automatically."
    )
    parser.add_argument("--target",  type=float, default=7.0,
        help="Minimum spelling %% to qualify (default: 7)")
    parser.add_argument("--books",   type=int,   default=100_000,
        help="Books to search this run (default: 100000)")
    parser.add_argument("--pages",   type=int,   default=1,
        help="Pages per book to check (default: 1)")
    parser.add_argument("--workers", type=int,
        default=multiprocessing.cpu_count(),
        help=f"Parallel workers (default: {multiprocessing.cpu_count()} = all cores)")
    parser.add_argument("--seed",    type=int,   default=None,
        help="Random seed for fresh starts (ignored on resume)")
    parser.add_argument("--output",  type=str,   default="notable_finds.json",
        help="Output file (default: notable_finds.json)")
    parser.add_argument("--reset",   action="store_true",
        help="Discard saved state and start fresh")
    parser.add_argument("--min-word-length", type=int, default=999,
        help="Also qualify any book containing a real word at least this "
             "long, regardless of overall spelling %% (default: 999, "
             "effectively disabled -- try 5 or 6 to hunt for rare long words)")
    args = parser.parse_args()

    # Clamp workers to something sensible
    n_workers = max(1, min(args.workers, multiprocessing.cpu_count()))

    print()
    print("  ================================================================")
    print("  A SHORT STAY IN HELL -- Notable Book Finder")
    print("  ================================================================")
    print()

    if args.reset:
        sf = state_file(args.output)
        for f in [args.output, sf]:
            if Path(f).exists():
                Path(f).unlink()
                print(f"  Removed: {f}")
        print("  State cleared. Starting fresh.")
        print()

    print(f"  Searching {args.books:,} books this run, {args.pages} page(s) each.")
    print(f"  Workers: {n_workers} (of {multiprocessing.cpu_count()} available cores)")
    print(f"  Target: spelling score >= {args.target:.0f}%")
    if args.min_word_length < 999:
        print(f"  Also qualifying: any book with a real word >= "
              f"{args.min_word_length} letters long")
    print(f"  A typical random book scores ~3%. A 7% book is remarkable.")
    print(f"  Longer words (5+ letters) are exponentially rarer than short ones.")
    print(f"  Press Ctrl+C at any time -- progress is saved automatically.")
    print()

    found = search(
        target_pct      = args.target,
        n_books         = args.books,
        pages_per_book  = args.pages,
        output_file     = args.output,
        seed            = args.seed,
        n_workers       = n_workers,
        min_word_length = args.min_word_length,
    )

    show_results(found, args.output)

if __name__ == "__main__":
    main()
