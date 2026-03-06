# getitdone

A terminal-based todo and notes app for project management, inspired by Git.  
Tasks and notes are stored as plain Markdown files inside `.getitdone/` so they
live alongside your code, are human-readable, and work naturally with version
control.

---

## Installation

```bash
pip install -e .
```

---

## Quick start

```bash
cd my-project
getitdone init                          # set up the project
getitdone add -m "Fix login bug" -m "Happens on Safari only"
getitdone status                        # check your tasks
getitdone                               # open the interactive TUI
```

---

## How it works

Running `getitdone init` creates a `.getitdone/` folder in the current
directory. This folder holds:

```
.getitdone/
├── tasks.md          # all tasks, one per entry
└── notes/
    ├── project-ideas.md
    └── meeting-notes.md
```

Every command reads and writes these plain Markdown files directly, so you can
also edit them in any text editor.

---

## Commands

### `getitdone init`

Initialise a new project in the current directory. Creates `.getitdone/` and
`tasks.md`. Run this once per project, similar to `git init`.

```bash
getitdone init
# Initialised empty getitdone project in .getitdone/
```

---

### `getitdone` *(bare, no sub-command)*

When run inside a project directory (one that contains `.getitdone/`), opens
the full interactive TUI immediately.

```bash
cd my-project
getitdone
```

When run outside a project directory, prints the help screen instead.

---

### `getitdone add`

Add a new task. The first `-m` is the task header; the optional second `-m` is
a short explanation, just like `git commit -m`.

```bash
# Header only
getitdone add -m "Write unit tests"

# Header + explanation
getitdone add -m "Fix login bug" -m "Happens on Safari only"
```

Tasks are stored in `.getitdone/tasks.md` and assigned a sequential ID
automatically.

---

### `getitdone status`

Print all tasks to the terminal, colour-coded by status (green = done, yellow =
todo). Similar to `git status`.

```bash
getitdone status
# Tasks:
# ○ 1. Fix login bug
#    Happens on Safari only
# ✓ 2. Write unit tests
```

---

### `getitdone note list`

List every note in the project with its title and filename.

```bash
getitdone note list
# Notes (2):
#   • Architecture Decisions  architecture-decisions.md
#   • Sprint Plan             sprint-plan.md
```

---

### `getitdone note new`

Create a new note. The first `-m` sets the title; every additional `-m` becomes
a body paragraph in the Markdown file — the same convention as `git commit`.

```bash
# Title only — creates an empty note
getitdone note new -m "Architecture Decisions"

# Title + body paragraphs
getitdone note new -m "Sprint Plan" \
    -m "Focus on the auth module this week." \
    -m "Target deploy by Friday."
```

The note is saved as a slugified Markdown file, e.g.
`.getitdone/notes/sprint-plan.md`:

```markdown
# Sprint Plan

Focus on the auth module this week.

Target deploy by Friday.
```

---

### `getitdone note show`

Print a note to the terminal with full Markdown rendering (headings, bold,
italic, lists, code blocks, blockquotes).

```bash
getitdone note show "Sprint Plan"
```

**Fuzzy title matching** — you don't have to type the full title. getitdone
uses the same lookup strategy git uses for branch names:

| Query | Matches |
|---|---|
| `"Sprint Plan"` | exact (case-insensitive) |
| `"sprint"` | prefix match |
| `"plan"` | substring match |

If the query is ambiguous (matches more than one note), an error is shown
listing all matches.

```bash
# Exact match
getitdone note show "Sprint Plan"

# Prefix match — finds "Sprint Plan" if it's the only note starting with "sp"
getitdone note show sp

# Substring match
getitdone note show plan
```

**`--raw` / `-r`** — print the plain Markdown source instead of the rendered
version. Useful for piping or scripting.

```bash
getitdone note show --raw "Sprint Plan"
getitdone note show -r sprint | grep "##"
```

---

## Interactive TUI

Run `getitdone` inside a project directory to open the TUI. It has two tabs
you can switch between by clicking the tab bar at the top.

### Tasks tab

Displays all tasks in a table. Use the keyboard or the buttons at the bottom
to manage them.

| Key | Action |
|---|---|
| `↑` / `↓` | Move between tasks |
| `D` | Mark selected task as **done** |
| `T` | Mark selected task as **todo** |
| `R` | Refresh the task list from disk |
| `Q` | Quit |

### Notes tab

Split into a **sidebar** (list of notes) and an **editor panel** (Markdown
editor or reader).

**Sidebar actions:**

| Button | Action |
|---|---|
| **New** | Opens a dialog — enter a title to create a new note |
| **Delete** | Asks for confirmation, then deletes the selected note |
| **Rename** | Opens a dialog — enter a new title to rename the selected note |

Click any note in the sidebar list to open it in the editor.

**Editor panel — Edit mode** (default):

A full text editor with Markdown syntax highlighting and line numbers. Edit
the note content directly.

| Key / Button | Action |
|---|---|
| `Ctrl+S` or **Save** button | Save the note to disk |
| `Ctrl+E` or **📖 Read** button | Switch to Reading mode |

**Editor panel — Reading mode:**

Renders the Markdown as styled text — headings, **bold**, *italic*, bullet
lists, code blocks, blockquotes and more. The editor is hidden; the rendered
view is scrollable.

| Key / Button | Action |
|---|---|
| `Ctrl+E` or **✏️ Edit** button | Switch back to Edit mode |
| `Ctrl+S` | Save the current editor content to disk (works in either mode) |

The title bar above the editor shows the current mode:
- `✏️  Editing: Note Title [filename.md]`
- `📖 Reading: Note Title [filename.md]`

> **Tip:** Switching to Reading mode renders whatever is currently in the
> editor, including unsaved edits — so you can preview before saving.

---

## File format

### tasks.md

```markdown
# Tasks

- [ ] 1. Fix login bug
  Happens on Safari only
- [x] 2. Write unit tests
```

Each task is a Markdown list item. `[ ]` = todo, `[x]` = done. The optional
indented line below is the explanation.

### notes/

Each note is a standalone `.md` file. The filename is a lowercase, hyphenated
slug derived from the title:

| Title | Filename |
|---|---|
| `Architecture Decisions` | `architecture-decisions.md` |
| `Sprint Plan` | `sprint-plan.md` |

You can edit these files directly in any editor — getitdone will pick up the
changes on the next read.

---

## Tips

- **Version control your notes and tasks** — commit `.getitdone/` to Git so
  your whole team shares the same task list and notes.
- **Pipe note content** — `getitdone note show --raw "title" > export.md` to
  export a note.
- **Partial titles** — `getitdone note show arch` is enough if only one note
  starts with "arch".
- **Multiple body paragraphs** — chain as many `-m` flags as you like when
  creating a note; each one becomes its own paragraph.
