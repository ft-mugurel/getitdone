import sys
import select
import termios
import tty
import time
from datetime import datetime

import typer
from rich.console import Console
from rich.markdown import Markdown as RichMarkdown

from rich.panel import Panel
from rich.text import Text
from rich import box

# ASCII art digits for big timer display
_DIGITS = {
    '0': ['  _  ', ' / \ ', '|   |', '|   |', ' \_/ '],
    '1': ['     ', '  |  ', '  |  ', '  |  ', '  |  '],
    '2': ['  _  ', '   | ', '  _  ', ' |   ', '  ___'],
    '3': ['  _  ', '   | ', '  _  ', '   | ', '  _  '],
    '4': ['     ', ' | | ', ' |_| ', '   | ', '   | '],
    '5': ['  _  ', ' |   ', '  _  ', '   | ', '  _  '],
    '6': ['  _  ', ' |   ', '  _  ', ' | | ', '  _  '],
    '7': ['  __ ', '    |', '    |', '    |', '    |'],
    '8': ['  _  ', ' | | ', '  _  ', ' | | ', '  _  '],
    '9': ['  _  ', ' | | ', '  _  ', '   | ', '  _  '],
    ':': ['     ', '  o  ', '     ', '  o  ', '     '],
    'P': ['     ', 'PAUSE', '     ', '     ', '     '],
    'R': ['     ', 'RUN  ', '     ', '     ', '     '],
}

def _render_big_time(hours: int, minutes: int, seconds: int, paused: bool) -> str:
    """Render time as ASCII art digits."""
    time_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    lines = ['', '', '', '', '']
    for char in time_str:
        digit = _DIGITS.get(char, ['     '] * 5)
        for i in range(5):
            lines[i] += digit[i] + ' '
    # Add status indicator
    status = 'P' if paused else 'R'
    for i in range(5):
        lines[i] += '  ' + _DIGITS[status][i]
    return '\n'.join(lines)

from .storage import (
    init_storage,
    load_tasks,
    add_task,
    Task,
    get_getitdone_dir,
    list_notes,
    create_note,
    save_note,
    find_note_by_title,
    Note,
    update_task,
)

# ---------------------------------------------------------------------------
# Root app
# ---------------------------------------------------------------------------

app = typer.Typer(
    help="getitdone - Terminal todo & notes app, inspired by Git.",
    invoke_without_command=True,  # lets the callback run when no sub-command is given
    no_args_is_help=False,        # we handle the no-args case ourselves in the callback
)
console = Console()


@app.callback()
def _main(ctx: typer.Context) -> None:
    """getitdone - Terminal todo & notes app, inspired by Git.

    Run bare (no sub-command) inside a project directory to open the TUI:

        getitdone

    Otherwise use one of the sub-commands listed below.
    """
    # Only act when no sub-command was provided
    if ctx.invoked_subcommand is not None:
        return

    if get_getitdone_dir().exists():
        # Inside a project — launch the TUI directly
        from .tui import run_tui
        run_tui()
    else:
        # Not a project directory — show help so the user knows what to do
        console.print(ctx.get_help())


def _require_project() -> None:
    """Abort with a helpful message if no project has been initialised."""
    if not get_getitdone_dir().exists():
        console.print(
            "[red]No getitdone project found.[/red] "
            "Run [bold]getitdone init[/bold] first."
        )
        raise typer.Exit(code=1)


# ---------------------------------------------------------------------------
# Top-level commands
# ---------------------------------------------------------------------------

@app.command()
def init():
    """Initialise a new getitdone project in the current directory.

    Creates .getitdone/ and tasks.md, similar to 'git init'.
    """
    try:
        init_storage()
        console.print(
            "[green]Initialised empty getitdone project in [bold].getitdone/[/bold][/green]"
        )
    except Exception as e:
        console.print(f"[red]Error initialising: {e}[/red]")
        raise typer.Exit(code=1)


@app.command()
def add(
    messages: list[str] = typer.Option(
        ...,
        "-m", "--message",
        help="Task header and optional explanation. "
             "Use -m twice: -m 'Header' -m 'Explanation'",
    )
):
    """Add a new task.

    Example:

        getitdone add -m "Fix login bug" -m "Happens on Safari only"
    """
    _require_project()
    if len(messages) == 0:
        console.print("[red]Provide at least a header with -m[/red]")
        raise typer.Exit(code=1)
    header = messages[0]
    explanation = " ".join(messages[1:]) if len(messages) > 1 else ""
    try:
        task = add_task(header, explanation)
        console.print(f"[green]Added task [bold]#{task.id}[/bold]: {task.header}[/green]")
    except Exception as e:
        console.print(f"[red]Error adding task: {e}[/red]")
        raise typer.Exit(code=1)


@app.command()
def status():
    """Show the status of all tasks, like 'git status'."""
    _require_project()
    tasks = load_tasks()
    if not tasks:
        console.print("[yellow]No tasks yet. Use 'getitdone add' to create tasks.[/yellow]")
        return
    console.print("[bold]Tasks:[/bold]")
    for task in tasks:
        color = "green" if task.done else "yellow"
        console.print(f"[{color}]{task}[/{color}]")
        if task.duration_seconds is not None:
            console.print(
                f"[dim]   Time: {task.duration_seconds}s"
                f" (start {task.started_at or 'n/a'} → end {task.ended_at or 'n/a'})[/dim]"
            )


# ---------------------------------------------------------------------------
# Time tracking commands
# ---------------------------------------------------------------------------

def _read_keypress() -> str | None:
    if select.select([sys.stdin], [], [], 0)[0]:
        return sys.stdin.read(1)
    return None


class _RawTerminal:
    def __enter__(self) -> "_RawTerminal":
        self._fd = sys.stdin.fileno()
        self._old_settings = termios.tcgetattr(self._fd)
        tty.setcbreak(self._fd)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        termios.tcsetattr(self._fd, termios.TCSADRAIN, self._old_settings)


@app.command()
def track(
    task_id: int = typer.Argument(..., help="ID of the task to track."),
):
    """Track time for a task with pause/resume controls."""
    _require_project()
    tasks = load_tasks()
    task = next((t for t in tasks if t.id == task_id), None)
    if task is None:
        console.print(f"[red]No task with ID {task_id}[/red]")
        raise typer.Exit(code=1)

    if task.done:
        console.print(f"[yellow]Task {task_id} is already done.[/yellow]")
        raise typer.Exit(code=1)

    start_time = datetime.now()
    active_start = start_time
    elapsed_seconds = task.duration_seconds or 0
    paused = False
    start_label = task.started_at or start_time.isoformat(timespec="seconds")
    with _RawTerminal():
        # Clear screen and move cursor to top
        console.print("\033[2J\033[H", end="")
        console.print(f"[cyan]Tracking task {task.id}:[/cyan] {task.header}")
        console.print("[dim]Controls: P=Pause, R=Resume, D=Done, Q=Quit[/dim]\n")
        if task.duration_seconds:
            console.print(f"[dim]Resuming from {task.duration_seconds}s already tracked.[/dim]\n")
        
        while True:
            if not paused:
                elapsed_seconds = int(
                    (datetime.now() - active_start).total_seconds()
                ) + elapsed_seconds
                active_start = datetime.now()
            minutes, seconds = divmod(elapsed_seconds, 60)
            hours, minutes = divmod(minutes, 60)
            
            # Save cursor position, move to line 5, clear lines, draw timer, restore cursor
            timer_art = _render_big_time(hours, minutes, seconds, paused)
            color = "yellow" if paused else "green"
            
            # Move cursor to line 5 (after header lines) and clear the timer area
            console.print(f"\033[s", end="")  # Save cursor
            console.print(f"\033[5;0H", end="")  # Move to line 5
            console.print(f"\033[J", end="")  # Clear from cursor to end
            
            # Print the big timer
            for line in timer_art.split('\n'):
                console.print(f"[{color}]{line}[/{color}]")
            
            console.print(f"\033[u", end="")  # Restore cursor
            sys.stdout.flush()

            key = _read_keypress()
            if key:
                key = key.lower()
                if key == "p" and not paused:
                    elapsed_seconds = int(
                        (datetime.now() - active_start).total_seconds()
                    ) + elapsed_seconds
                    paused = True
                    console.print(f"\033[10;0H[yellow]Paused. Press R to resume, D to finish, Q to quit.[/yellow]    ")
                elif key == "r" and paused:
                    active_start = datetime.now()
                    paused = False
                    console.print(f"\033[10;0H[green]Resumed.[/green]                                                  ")
                elif key == "d":
                    end_time = datetime.now()
                    if not paused:
                        elapsed_seconds = int(
                            (end_time - active_start).total_seconds()
                        ) + elapsed_seconds
                    end_label = end_time.isoformat(timespec="seconds")
                    updated = update_task(
                        task.id,
                        done=True,
                        started_at=start_label,
                        ended_at=end_label,
                        duration_seconds=elapsed_seconds,
                    )
                    console.print(f"\033[10;0H", end="")
                    if updated:
                        console.print(
                            "\n[green]Task marked done.[/green] "
                            f"Tracked {elapsed_seconds}s (start {start_label} → end {end_label})."
                        )
                    else:
                        console.print("\n[red]Failed to update task.[/red]")
                    raise typer.Exit(code=0)
                elif key == "q":
                    end_time = datetime.now()
                    if not paused:
                        elapsed_seconds = int(
                            (end_time - active_start).total_seconds()
                        ) + elapsed_seconds
                    end_label = end_time.isoformat(timespec="seconds")
                    update_task(
                        task.id,
                        done=False,
                        started_at=start_label,
                        ended_at=end_label,
                        duration_seconds=elapsed_seconds,
                    )
                    console.print(f"\033[10;0H", end="")
                    console.print(
                        "\n[yellow]Tracking stopped.[/yellow] "
                        f"Saved {elapsed_seconds}s (start {start_label} → end {end_label})."
                    )
                    raise typer.Exit(code=0)
            time.sleep(1)


# ---------------------------------------------------------------------------
# `note` sub-command group  (git-style: getitdone note <verb> ...)
# ---------------------------------------------------------------------------

note_app = typer.Typer(
    help="Manage project notes.",
    no_args_is_help=True,
)
app.add_typer(note_app, name="note")


@note_app.command("list")
def note_list():
    """List all notes in the project.

        getitdone note list
    """
    _require_project()
    notes = list_notes()
    if not notes:
        console.print("[yellow]No notes yet. Use 'getitdone note new' to create one.[/yellow]")
        return
    console.print(f"[bold]Notes[/bold] ({len(notes)}):")
    for note in notes:
        console.print(f"  [cyan]•[/cyan] [bold]{note.title}[/bold]  [dim]{note.filename}[/dim]")


@note_app.command("show")
def note_show(
    title: str = typer.Argument(..., help="Title (or unique prefix/substring) of the note to show."),
    raw: bool = typer.Option(
        False, "--raw", "-r",
        help="Print the raw Markdown source instead of the rendered version.",
    ),
):
    """Print a note to the terminal.

    The title is matched case-insensitively. A unique prefix or substring is
    enough — the same fuzzy lookup git uses for branch names:

        getitdone note show "Project Ideas"
        getitdone note show project          # prefix match
        getitdone note show ideas            # substring match

    Use --raw / -r to see the plain Markdown source.
    """
    _require_project()
    try:
        note = find_note_by_title(title)
    except ValueError as e:
        console.print(f"[red]error:[/red] {e}")
        raise typer.Exit(code=1)

    if note is None:
        console.print(
            f"[red]error:[/red] no note matching [bold]{title!r}[/bold]\n"
            "Run [bold]getitdone note list[/bold] to see available notes."
        )
        raise typer.Exit(code=1)

    if raw:
        # Plain source — pipe-friendly, no colour codes
        console.print(note.content)
    else:
        # Rendered Markdown inside a titled panel
        console.print(
            Panel(
                RichMarkdown(note.content),
                title=f"[bold cyan]{note.title}[/bold cyan]",
                subtitle=f"[dim]{note.filename}[/dim]",
                border_style="cyan",
                box=box.ROUNDED,
                padding=(1, 2),
            )
        )


@note_app.command("new")
def note_new(
    messages: list[str] = typer.Option(
        ...,
        "-m", "--message",
        help=(
            "Note title and optional body paragraphs. "
            "First -m is the title, every subsequent -m becomes a body paragraph. "
            "Example: -m 'My Note' -m 'First paragraph.' -m 'Second paragraph.'"
        ),
    ),
):
    """Create a new note, like 'git commit -m'.

    The first -m sets the title; every additional -m adds a body paragraph:

        getitdone note new -m "Architecture Decisions"
        getitdone note new -m "Sprint Plan" -m "Focus on auth this week." -m "Deploy by Friday."
    """
    _require_project()
    if not messages:
        console.print("[red]Provide at least a title with -m[/red]")
        raise typer.Exit(code=1)

    title = messages[0].strip()
    if not title:
        console.print("[red]Title cannot be empty[/red]")
        raise typer.Exit(code=1)

    # Build markdown content: H1 title + each extra -m as its own paragraph
    body_paragraphs = [m.strip() for m in messages[1:] if m.strip()]
    content = f"# {title}\n\n"
    if body_paragraphs:
        content += "\n\n".join(body_paragraphs) + "\n"

    try:
        note = create_note(title)
        # Overwrite the stub that create_note wrote with the full content
        if body_paragraphs:
            save_note(note.filename, content)
        console.print(
            f"[green]Created note [bold]{note.title}[/bold] → "
            f"[dim]{note.filename}[/dim][/green]"
        )
    except Exception as e:
        console.print(f"[red]Error creating note: {e}[/red]")
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
