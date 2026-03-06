from pathlib import Path
from typing import List, Optional
import re

GETITDONE_DIR = ".getitdone"
TASKS_FILE = "tasks.md"
NOTES_DIR = "notes"

class Task:
    def __init__(
        self,
        id: int,
        header: str,
        explanation: str,
        done: bool = False,
        started_at: str | None = None,
        ended_at: str | None = None,
        duration_seconds: int | None = None,
    ):
        self.id = id
        self.header = header
        self.explanation = explanation
        self.done = done
        self.started_at = started_at
        self.ended_at = ended_at
        self.duration_seconds = duration_seconds

    def __str__(self):
        """String representation safe for rich markup."""
        # Use unicode checkboxes to avoid rich markup conflict with [ ]
        status = "✓" if self.done else "○"
        expl = f"\n   {self.explanation}" if self.explanation else ""
        return f"{status} {self.id}. {self.header}{expl}"

def get_getitdone_dir() -> Path:
    """Get the .getitdone directory in current working dir."""
    return Path.cwd() / GETITDONE_DIR

def get_tasks_file() -> Path:
    """Get path to tasks.md"""
    return get_getitdone_dir() / TASKS_FILE

def init_storage() -> None:
    """Initialize .getitdone/ and tasks.md if not exists."""
    getitdone_dir = get_getitdone_dir()
    getitdone_dir.mkdir(exist_ok=True)
    tasks_file = get_tasks_file()
    if not tasks_file.exists():
        with open(tasks_file, "w") as f:
            f.write("# Tasks\n\n")
            f.write("Manage your tasks with getitdone.\n\n")

def load_tasks() -> List[Task]:
    """Load tasks from tasks.md using line-by-line parsing for reliability.
    
    Supports format:
    - [ ] 1. Header
      Explanation text
      - Started: 2026-03-04T10:15:00
      - Ended: 2026-03-04T11:05:30
      - Duration: 3030s
    - [x] 2. Another task
    """
    tasks = []
    tasks_file = get_tasks_file()
    if not tasks_file.exists():
        return tasks
    
    with open(tasks_file, "r") as f:
        lines = f.readlines()
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        # Match task line: - [ ] ID. Header
        if line.startswith("- [") and "]" in line and any(c.isdigit() for c in line) and ". " in line:
            # Parse status, id, header
            try:
                # Format: - [ ] 1. Buy groceries   or - [x] ...
                # Split on '] ' to get after status
                status_part, rest = line.split("] ", 1)
                status_char = status_part[-1]  # ' ' or 'x'
                # Then split id. header
                id_part, header_part = rest.split(". ", 1)
                task_id = int(id_part.strip())
                header = header_part.strip()
                done = status_char == "x"

                explanation = ""
                started_at = None
                ended_at = None
                duration_seconds = None

                i += 1
                while i < len(lines):
                    next_line = lines[i].rstrip("\n")
                    if not next_line.startswith("  "):
                        break
                    stripped = next_line.strip()
                    if stripped.startswith("- Started:"):
                        started_at = stripped.split(":", 1)[1].strip() or None
                    elif stripped.startswith("- Ended:"):
                        ended_at = stripped.split(":", 1)[1].strip() or None
                    elif stripped.startswith("- Duration:"):
                        duration_value = stripped.split(":", 1)[1].strip()
                        if duration_value.endswith("s"):
                            duration_value = duration_value[:-1]
                        try:
                            duration_seconds = int(duration_value)
                        except ValueError:
                            duration_seconds = None
                    elif not stripped.startswith("- ["):
                        if not explanation:
                            explanation = stripped
                    i += 1

                tasks.append(
                    Task(
                        task_id,
                        header,
                        explanation,
                        done,
                        started_at,
                        ended_at,
                        duration_seconds,
                    )
                )
                continue  # already advanced i
            except (ValueError, IndexError):
                # Skip malformed task lines
                pass
        i += 1
    
    return sorted(tasks, key=lambda t: t.id)

def save_tasks(tasks: List[Task]) -> None:
    """Save tasks back to tasks.md in markdown format."""
    tasks_file = get_tasks_file()
    with open(tasks_file, "w") as f:
        f.write("# Tasks\n\n")
        f.write("Manage your tasks with getitdone.\n\n")
        for task in sorted(tasks, key=lambda t: t.id):
            status = "x" if task.done else " "
            f.write(f"- [{status}] {task.id}. {task.header}\n")
            if task.explanation:
                f.write(f"  {task.explanation}\n")
            if task.started_at:
                f.write(f"  - Started: {task.started_at}\n")
            if task.ended_at:
                f.write(f"  - Ended: {task.ended_at}\n")
            if task.duration_seconds is not None:
                f.write(f"  - Duration: {task.duration_seconds}s\n")
            f.write("\n")

def add_task(header: str, explanation: str = "") -> Task:
    """Add a new task with next consecutive ID."""
    tasks = load_tasks()
    next_id = max([t.id for t in tasks], default=0) + 1
    new_task = Task(next_id, header, explanation, False)
    tasks.append(new_task)
    save_tasks(tasks)
    return new_task

def update_task(
    task_id: int,
    done: bool,
    started_at: str | None = None,
    ended_at: str | None = None,
    duration_seconds: int | None = None,
) -> Optional[Task]:
    """Update task status by ID."""
    tasks = load_tasks()
    for task in tasks:
        if task.id == task_id:
            task.done = done
            if started_at is not None:
                task.started_at = started_at
            if ended_at is not None:
                task.ended_at = ended_at
            if duration_seconds is not None:
                task.duration_seconds = duration_seconds
            save_tasks(tasks)
            return task
    return None

def get_next_id() -> int:
    """Get next ID for new task."""
    tasks = load_tasks()
    return max([t.id for t in tasks], default=0) + 1


# ---------------------------------------------------------------------------
# Notes storage
# ---------------------------------------------------------------------------

class Note:
    """Represents a project note stored as a .md file."""

    def __init__(self, filename: str, title: str, content: str):
        self.filename = filename  # e.g. "ideas.md"
        self.title = title        # derived from filename (without .md)
        self.content = content    # full markdown text

    def __str__(self) -> str:
        return f"{self.title} ({self.filename})"


def get_notes_dir() -> Path:
    """Return the path to .getitdone/notes/."""
    return get_getitdone_dir() / NOTES_DIR


def _slugify(name: str) -> str:
    """Convert a note title to a safe filename (lowercase, hyphens)."""
    slug = name.strip().lower()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug or "note"


def _title_from_filename(filename: str) -> str:
    """Derive a human-readable title from a .md filename."""
    stem = Path(filename).stem          # strip .md
    return stem.replace("-", " ").replace("_", " ").title()


def init_notes_storage() -> None:
    """Ensure .getitdone/notes/ directory exists."""
    get_notes_dir().mkdir(parents=True, exist_ok=True)


def list_notes() -> List[Note]:
    """Return all notes sorted alphabetically by filename."""
    notes_dir = get_notes_dir()
    if not notes_dir.exists():
        return []
    notes = []
    for path in sorted(notes_dir.glob("*.md")):
        content = path.read_text(encoding="utf-8")
        notes.append(Note(path.name, _title_from_filename(path.name), content))
    return notes


def load_note(filename: str) -> Optional[Note]:
    """Load a single note by filename. Returns None if not found."""
    path = get_notes_dir() / filename
    if not path.exists():
        return None
    content = path.read_text(encoding="utf-8")
    return Note(filename, _title_from_filename(filename), content)


def create_note(title: str) -> Note:
    """Create a new note with the given title. Returns the new Note."""
    init_notes_storage()
    slug = _slugify(title)
    notes_dir = get_notes_dir()
    # Avoid collisions: append a counter if needed
    candidate = f"{slug}.md"
    counter = 1
    while (notes_dir / candidate).exists():
        candidate = f"{slug}-{counter}.md"
        counter += 1
    initial_content = f"# {title}\n\n"
    (notes_dir / candidate).write_text(initial_content, encoding="utf-8")
    return Note(candidate, _title_from_filename(candidate), initial_content)


def save_note(filename: str, content: str) -> Note:
    """Overwrite the content of an existing note. Returns the updated Note."""
    init_notes_storage()
    path = get_notes_dir() / filename
    path.write_text(content, encoding="utf-8")
    return Note(filename, _title_from_filename(filename), content)


def delete_note(filename: str) -> bool:
    """Delete a note by filename. Returns True if deleted, False if not found."""
    path = get_notes_dir() / filename
    if not path.exists():
        return False
    path.unlink()
    return True


def find_note_by_title(title: str) -> Optional[Note]:
    """Find a note whose title matches *title* (case-insensitive).

    Tries an exact case-insensitive match first, then a prefix match, then a
    substring match — the same fuzzy-lookup strategy git uses for branch names.
    Returns the single best match, or None when nothing matches.  Raises
    ValueError when the query is ambiguous (multiple notes match).
    """
    notes = list_notes()
    query = title.strip().lower()

    # 1. Exact match (case-insensitive)
    exact = [n for n in notes if n.title.lower() == query]
    if len(exact) == 1:
        return exact[0]
    if len(exact) > 1:
        raise ValueError(f"Ambiguous note title {title!r}: matches {[n.title for n in exact]}")

    # 2. Prefix match
    prefix = [n for n in notes if n.title.lower().startswith(query)]
    if len(prefix) == 1:
        return prefix[0]
    if len(prefix) > 1:
        raise ValueError(f"Ambiguous note title {title!r}: matches {[n.title for n in prefix]}")

    # 3. Substring match
    sub = [n for n in notes if query in n.title.lower()]
    if len(sub) == 1:
        return sub[0]
    if len(sub) > 1:
        raise ValueError(f"Ambiguous note title {title!r}: matches {[n.title for n in sub]}")

    return None


def rename_note(old_filename: str, new_title: str) -> Optional[Note]:
    """Rename a note (changes filename). Returns the new Note or None if not found."""
    old_path = get_notes_dir() / old_filename
    if not old_path.exists():
        return None
    content = old_path.read_text(encoding="utf-8")
    slug = _slugify(new_title)
    notes_dir = get_notes_dir()
    candidate = f"{slug}.md"
    counter = 1
    while (notes_dir / candidate).exists() and candidate != old_filename:
        candidate = f"{slug}-{counter}.md"
        counter += 1
    new_path = notes_dir / candidate
    old_path.rename(new_path)
    return Note(candidate, _title_from_filename(candidate), content)
