from __future__ import annotations

from datetime import datetime

from textual.app import App, ComposeResult
from textual.containers import Vertical, Horizontal, VerticalScroll
from textual.widgets import (
    Header,
    Footer,
    DataTable,
    Button,
    Static,
    TabbedContent,
    TabPane,
    TextArea,
    Input,
    Label,
    ListView,
    ListItem,
    Markdown,
)
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.timer import Timer
from rich.text import Text

from .storage import (
    load_tasks,
    update_task,
    Task,
    Note,
    list_notes,
    create_note,
    save_note,
    delete_note,
    rename_note,
)


# ---------------------------------------------------------------------------
# Modal dialogs
# ---------------------------------------------------------------------------

class InputModal(ModalScreen[str | None]):
    """Generic single-line input modal.  Returns the entered text or None."""

    DEFAULT_CSS = """
    InputModal {
        align: center middle;
    }
    #dialog {
        width: 60;
        height: 14;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }
    #dialog Label {
        margin-bottom: 1;
    }
    #dialog Input {
        margin-bottom: 1;
    }
    #dialog #btn-row {
        align: center middle;
        height: 3;
        margin-top: 1;
    }
    #dialog Button {
        min-width: 12;
        height: 3;
        margin: 0 1;
    }
    """

    def __init__(self, prompt: str, placeholder: str = "", default: str = "") -> None:
        super().__init__()
        self._prompt = prompt
        self._placeholder = placeholder
        self._default = default

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Label(self._prompt)
            yield Input(value=self._default, placeholder=self._placeholder, id="modal-input")
            with Horizontal(id="btn-row"):
                yield Button("OK", variant="primary", id="ok")
                yield Button("Cancel", variant="default", id="cancel")

    def on_mount(self) -> None:
        self.query_one("#modal-input", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "ok":
            self.dismiss(self.query_one("#modal-input", Input).value.strip())
        else:
            self.dismiss(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.dismiss(event.value.strip())


class ConfirmModal(ModalScreen[bool]):
    """Yes/No confirmation modal."""

    DEFAULT_CSS = """
    ConfirmModal {
        align: center middle;
    }
    #dialog {
        width: 50;
        height: 9;
        border: thick $error;
        background: $surface;
        padding: 1 2;
    }
    #dialog Label {
        margin-bottom: 1;
    }
    #dialog #btn-row {
        align: center middle;
        height: 3;
    }
    #dialog Button {
        min-width: 12;
        margin: 0 1;
    }
    """

    def __init__(self, message: str) -> None:
        super().__init__()
        self._message = message

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Label(self._message)
            with Horizontal(id="btn-row"):
                yield Button("Yes", variant="error", id="yes")
                yield Button("No", variant="default", id="no")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "yes")


# ---------------------------------------------------------------------------
# Main app
# ---------------------------------------------------------------------------

class GetItDoneTUI(App):
    """TUI for managing getitdone tasks and notes using Textual.

    Tabs:
      • Tasks  – view / mark done / mark todo
      • Notes  – create / edit / delete markdown notes
    """

    CSS = """
    /* ── Global ──────────────────────────────────────────────────────── */
    Screen {
        layout: vertical;
        overflow: hidden;
    }
    Header, Footer {
        height: 1;
    }

    /* ── Tasks tab ───────────────────────────────────────────────────── */
    #tasks-pane {
        layout: vertical;
    }
    #tasks-hint {
        height: 1;
        padding: 0 2;
        color: $text-muted;
    }
    DataTable {
        height: 1fr;
    }
    #task-actions {
        height: 3;
        padding: 0 1;
        align: center middle;
        background: $surface;
    }

    /* ── Notes tab ───────────────────────────────────────────────────── */
    #notes-pane {
        layout: horizontal;
    }
    #notes-sidebar {
        width: 26;
        border-right: solid $primary;
        layout: vertical;
    }
    #notes-sidebar-title {
        height: 1;
        padding: 0 1;
        background: $primary;
        color: $text;
        text-style: bold;
    }
    ListView {
        height: 1fr;
    }
    #notes-sidebar-actions {
        height: 9;
        layout: vertical;
        padding: 0;
        background: $surface;
    }
    /* Sidebar buttons fill the full sidebar width, stacked vertically */
    #notes-sidebar-actions Button {
        width: 1fr;
        min-width: 0;
        height: 3;
        margin: 0;
        border: tall $primary;
    }
    #notes-editor-area {
        width: 1fr;
        layout: vertical;
    }
    #notes-editor-title {
        height: 1;
        padding: 0 1;
        background: $primary-darken-2;
        color: $text;
        text-style: italic;
    }
    TextArea {
        height: 1fr;
    }
    /* Reading-mode viewer (the scroll container wrapping Markdown) */
    #note-viewer-scroll {
        height: 1fr;
        background: $surface;
        display: none;
    }
    #note-viewer-scroll.reading {
        display: block;
    }
    #note-viewer {
        padding: 1 2;
    }
    TextArea.reading {
        display: none;
    }
    #notes-editor-actions {
        height: 3;
        align: center middle;
        padding: 0 1;
        background: $surface;
    }
    /* Reading-mode toggle button gets a distinct accent colour */
    #btn-toggle-mode {
        background: $secondary;
        border: tall $secondary;
    }
    #btn-toggle-mode.reading {
        background: $primary-darken-1;
        border: tall $primary-darken-1;
    }

    /* ── Shared button style ─────────────────────────────────────────── */
    Button {
        height: 3;
        min-width: 16;
        margin: 0 1;
        padding: 0 2;
        border: tall $primary;
        background: $primary;
        color: $text;
        content-align: center middle;
    }
    """

    BINDINGS = [
        # Tasks tab
        Binding("d", "mark_done", "Mark Done", show=True),
        Binding("t", "mark_todo", "Mark Todo", show=True),
        Binding("r", "refresh_tasks", "Refresh", show=True),
        Binding("s", "start_timer", "Start Timer", show=True),
        Binding("p", "pause_timer", "Pause Timer", show=True),
        Binding("e", "stop_timer", "Stop Timer", show=True),
        Binding("c", "resume_timer", "Resume Timer", show=True),
        # Notes tab
        Binding("ctrl+s", "save_note", "Save Note", show=True, priority=True),
        Binding("ctrl+e", "toggle_read_mode", "Read/Edit", show=True, priority=True),
        # Global
        Binding("q", "quit", "Quit", show=True),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.tasks: list[Task] = []
        self.notes: list[Note] = []
        self._active_note: Note | None = None  # note currently open in editor
        self._reading_mode: bool = False        # False = edit, True = read
        self._timer_task_id: int | None = None
        self._timer_started_at: datetime | None = None
        self._timer_paused: bool = False
        self._timer_elapsed_seconds: int = 0
        self._timer_handle: Timer | None = None

    # ------------------------------------------------------------------ #
    # Compose                                                              #
    # ------------------------------------------------------------------ #

    def compose(self) -> ComposeResult:
        yield Header()
        with TabbedContent(id="tabs"):
            # ── Tasks tab ──────────────────────────────────────────────
            with TabPane("Tasks", id="tab-tasks"):
                with Vertical(id="tasks-pane"):
                    yield Static(
                        "↑↓ select  D=done  T=todo  R=refresh  S=start  P=pause  C=resume  E=stop",
                        id="tasks-hint",
                    )
                    yield DataTable(id="task-table")
                    with Horizontal(id="task-actions"):
                        yield Button("Mark Done (D)", variant="success", id="btn-done")
                        yield Button("Mark Todo (T)", variant="default", id="btn-todo")
                        yield Button("Start (S)", variant="primary", id="btn-start")
                        yield Button("Pause (P)", variant="warning", id="btn-pause")
                        yield Button("Resume (C)", variant="primary", id="btn-resume")
                        yield Button("Stop (E)", variant="warning", id="btn-stop")
                        yield Button("Refresh (R)", id="btn-refresh")
                        yield Button("Quit (Q)", variant="error", id="btn-quit")

            # ── Notes tab ──────────────────────────────────────────────
            with TabPane("Notes", id="tab-notes"):
                with Horizontal(id="notes-pane"):
                    with Vertical(id="notes-sidebar"):
                        yield Static("📝 Notes", id="notes-sidebar-title")
                        yield ListView(id="notes-list")
                        with Vertical(id="notes-sidebar-actions"):
                            yield Button("New", variant="success", id="btn-new-note")
                            yield Button("Delete", variant="error", id="btn-delete-note")
                            yield Button("Rename", id="btn-rename-note")
                    with Vertical(id="notes-editor-area"):
                        yield Static("(no note selected)", id="notes-editor-title")
                        yield TextArea(
                            "",
                            language="markdown",
                            id="note-editor",
                            show_line_numbers=True,
                        )
                        yield VerticalScroll(
                            Markdown("", id="note-viewer"),
                            id="note-viewer-scroll",
                        )
                        with Horizontal(id="notes-editor-actions"):
                            yield Button("Save  Ctrl+S", variant="primary", id="btn-save-note")
                            yield Button("📖 Read  Ctrl+E", id="btn-toggle-mode")
        yield Footer()

    # ------------------------------------------------------------------ #
    # Lifecycle                                                            #
    # ------------------------------------------------------------------ #

    def on_mount(self) -> None:
        table = self.query_one("#task-table", DataTable)
        table.add_column("ID", width=4, key="id")
        table.add_column("Status", width=10, key="status")
        table.add_column("Header", width=30, key="header")
        table.add_column("Explanation", width=40, key="expl")
        table.add_column("Timer", width=12, key="timer")
        self._refresh_tasks()
        table.focus()
        self._refresh_notes_list()

    # ------------------------------------------------------------------ #
    # Tasks helpers                                                        #
    # ------------------------------------------------------------------ #

    def _refresh_tasks(self) -> None:
        """Reload tasks from disk and repopulate the table."""
        table = self.query_one("#task-table", DataTable)
        self.tasks = load_tasks()
        table.clear()
        for task in self.tasks:
            status = "✓ Done" if task.done else "○ Todo"
            expl = (
                task.explanation[:50] + "…"
                if len(task.explanation) > 50
                else task.explanation
            )
            style = "green" if task.done else "yellow"
            timer_text = ""
            if self._timer_task_id == task.id and self._timer_started_at:
                elapsed = self._timer_elapsed_seconds
                if not self._timer_paused:
                    elapsed += int((datetime.now() - self._timer_started_at).total_seconds())
                minutes, seconds = divmod(elapsed, 60)
                timer_text = f"{minutes:02d}:{seconds:02d}"
            elif task.duration_seconds is not None:
                minutes, seconds = divmod(task.duration_seconds, 60)
                timer_text = f"{minutes:02d}:{seconds:02d}"
            table.add_row(
                str(task.id),
                Text(status, style=style),
                Text(task.header, style=f"{style} bold"),
                Text(expl, style="dim" if task.done else f"{style} dim"),
                Text(timer_text, style="cyan" if timer_text else "dim"),
            )

    def _toggle_task(self, done: bool) -> None:
        table = self.query_one("#task-table", DataTable)
        if table.row_count == 0:
            self.notify("No tasks", severity="warning")
            return
        row = table.cursor_row
        if row is not None and row < len(self.tasks):
            task = self.tasks[row]
            started_at = None
            ended_at = None
            duration_seconds = None
            if done and self._timer_task_id == task.id and self._timer_started_at:
                ended_at_dt = datetime.now()
                elapsed_seconds = self._timer_elapsed_seconds
                if not self._timer_paused:
                    elapsed_seconds += int(
                        (ended_at_dt - self._timer_started_at).total_seconds()
                    )
                duration_seconds = elapsed_seconds
                started_at = self._timer_started_at.isoformat(timespec="seconds")
                ended_at = ended_at_dt.isoformat(timespec="seconds")
                self._clear_timer()
            updated = update_task(
                task.id,
                done,
                started_at=started_at,
                ended_at=ended_at,
                duration_seconds=duration_seconds,
            )
            if updated:
                self._refresh_tasks()
                self.notify(
                    f"Task {task.id} marked as {'done' if done else 'todo'}",
                    severity="information",
                )
                table.move_cursor(row=row)
            else:
                self.notify("Task not found", severity="error")

    # ------------------------------------------------------------------ #
    # Notes helpers                                                        #
    # ------------------------------------------------------------------ #

    def _refresh_notes_list(self) -> None:
        """Reload notes from disk and repopulate the sidebar list."""
        self.notes = list_notes()
        lv = self.query_one("#notes-list", ListView)
        lv.clear()
        for note in self.notes:
            lv.append(ListItem(Label(note.title), name=note.filename))

    def _clear_timer(self) -> None:
        if self._timer_handle:
            self._timer_handle.stop()
        self._timer_handle = None
        self._timer_task_id = None
        self._timer_started_at = None
        self._timer_paused = False
        self._timer_elapsed_seconds = 0

    def _tick_timer(self) -> None:
        if self._timer_task_id is None:
            return
        if not self._timer_paused and self._timer_started_at:
            self._refresh_tasks()

    def _open_note(self, note: Note) -> None:
        """Load a note into the editor (or viewer if in reading mode)."""
        self._active_note = note
        self._update_title_bar()
        editor = self.query_one("#note-editor", TextArea)
        editor.load_text(note.content)
        if self._reading_mode:
            self._render_markdown(note.content)
        else:
            editor.focus()

    def _clear_editor(self) -> None:
        self._active_note = None
        self.query_one("#notes-editor-title", Static).update("(no note selected)")
        self.query_one("#note-editor", TextArea).load_text("")
        self.query_one("#note-viewer", Markdown).update("")

    def _update_title_bar(self) -> None:
        """Refresh the title bar to reflect current mode and note."""
        if self._active_note is None:
            self.query_one("#notes-editor-title", Static).update("(no note selected)")
            return
        icon = "📖 Reading" if self._reading_mode else "✏️  Editing"
        self.query_one("#notes-editor-title", Static).update(
            f"{icon}: {self._active_note.title}  [{self._active_note.filename}]"
        )

    def _render_markdown(self, content: str) -> None:
        """Push markdown content into the viewer widget."""
        self.query_one("#note-viewer", Markdown).update(content)

    # ------------------------------------------------------------------ #
    # Event handlers – buttons                                             #
    # ------------------------------------------------------------------ #

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        # Tasks
        if bid == "btn-done":
            self.action_mark_done()
        elif bid == "btn-todo":
            self.action_mark_todo()
        elif bid == "btn-start":
            self.action_start_timer()
        elif bid == "btn-pause":
            self.action_pause_timer()
        elif bid == "btn-resume":
            self.action_resume_timer()
        elif bid == "btn-stop":
            self.action_stop_timer()
        elif bid == "btn-refresh":
            self.action_refresh_tasks()
        elif bid == "btn-quit":
            self.action_quit()
        # Notes
        elif bid == "btn-new-note":
            self._do_new_note()
        elif bid == "btn-delete-note":
            self._do_delete_note()
        elif bid == "btn-rename-note":
            self._do_rename_note()
        elif bid == "btn-save-note":
            self.action_save_note()
        elif bid == "btn-toggle-mode":
            self.action_toggle_read_mode()

    # ------------------------------------------------------------------ #
    # Event handlers – list                                                #
    # ------------------------------------------------------------------ #

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Open the selected note in the editor."""
        if event.item.name:
            filename = event.item.name
            note = next((n for n in self.notes if n.filename == filename), None)
            if note:
                self._open_note(note)

    # ------------------------------------------------------------------ #
    # Notes actions                                                        #
    # ------------------------------------------------------------------ #

    def _do_new_note(self) -> None:
        def _on_title(title: str | None) -> None:
            if not title:
                return
            note = create_note(title)
            self._refresh_notes_list()
            self._open_note(note)
            # Highlight the new note in the sidebar
            lv = self.query_one("#notes-list", ListView)
            for i, n in enumerate(self.notes):
                if n.filename == note.filename:
                    lv.index = i
                    break
            self.notify(f"Created note '{note.title}'", severity="information")

        self.push_screen(InputModal("New note title:", placeholder="My Note"), _on_title)

    def _do_delete_note(self) -> None:
        if self._active_note is None:
            self.notify("Select a note first", severity="warning")
            return
        note = self._active_note

        def _on_confirm(confirmed: bool) -> None:
            if not confirmed:
                return
            deleted = delete_note(note.filename)
            if deleted:
                self._clear_editor()
                self._refresh_notes_list()
                self.notify(f"Deleted '{note.title}'", severity="information")
            else:
                self.notify("Could not delete note", severity="error")

        self.push_screen(
            ConfirmModal(f"Delete note '{note.title}'?"), _on_confirm
        )

    def _do_rename_note(self) -> None:
        if self._active_note is None:
            self.notify("Select a note first", severity="warning")
            return
        note = self._active_note

        def _on_new_title(new_title: str | None) -> None:
            if not new_title:
                return
            renamed = rename_note(note.filename, new_title)
            if renamed:
                self._refresh_notes_list()
                self._open_note(renamed)
                lv = self.query_one("#notes-list", ListView)
                for i, n in enumerate(self.notes):
                    if n.filename == renamed.filename:
                        lv.index = i
                        break
                self.notify(f"Renamed to '{renamed.title}'", severity="information")
            else:
                self.notify("Could not rename note", severity="error")

        self.push_screen(
            InputModal("New title:", default=note.title), _on_new_title
        )

    # ------------------------------------------------------------------ #
    # Key-bound actions                                                    #
    # ------------------------------------------------------------------ #

    def action_mark_done(self) -> None:
        self._toggle_task(True)

    def action_mark_todo(self) -> None:
        self._toggle_task(False)

    def action_refresh_tasks(self) -> None:
        self._refresh_tasks()
        self.notify("Tasks refreshed", severity="information")

    def action_start_timer(self) -> None:
        table = self.query_one("#task-table", DataTable)
        if table.row_count == 0:
            self.notify("No tasks", severity="warning")
            return
        row = table.cursor_row
        if row is None or row >= len(self.tasks):
            self.notify("Select a task first", severity="warning")
            return
        task = self.tasks[row]
        if task.done:
            self.notify("Task is already done", severity="warning")
            return
        if self._timer_task_id is not None and self._timer_task_id != task.id:
            self.notify("Another task timer is already running", severity="warning")
            return
        if self._timer_task_id == task.id:
            self.notify("Timer already running for this task", severity="information")
            return
        self._timer_task_id = task.id
        self._timer_started_at = datetime.now()
        self._timer_paused = False
        self._timer_elapsed_seconds = 0
        self._timer_handle = self.set_interval(1, self._tick_timer)
        self.notify(f"Started timer for task {task.id}", severity="information")
        self._refresh_tasks()

    def action_pause_timer(self) -> None:
        if self._timer_task_id is None or self._timer_started_at is None:
            self.notify("No active timer", severity="warning")
            return
        if self._timer_paused:
            self.notify("Timer already paused", severity="information")
            return
        self._timer_elapsed_seconds += int(
            (datetime.now() - self._timer_started_at).total_seconds()
        )
        self._timer_paused = True
        self.notify("Timer paused", severity="information")
        self._refresh_tasks()

    def action_resume_timer(self) -> None:
        if self._timer_task_id is None or self._timer_started_at is None:
            self.notify("No active timer", severity="warning")
            return
        if not self._timer_paused:
            self.notify("Timer is already running", severity="information")
            return
        self._timer_started_at = datetime.now()
        self._timer_paused = False
        self.notify("Timer resumed", severity="information")
        self._refresh_tasks()

    def action_stop_timer(self) -> None:
        if self._timer_task_id is None or self._timer_started_at is None:
            self.notify("No active timer", severity="warning")
            return
        end_time = datetime.now()
        duration_seconds = self._timer_elapsed_seconds
        if not self._timer_paused:
            duration_seconds += int((end_time - self._timer_started_at).total_seconds())
        started_label = self._timer_started_at.isoformat(timespec="seconds")
        ended_label = end_time.isoformat(timespec="seconds")
        updated = update_task(
            self._timer_task_id,
            done=True,
            started_at=started_label,
            ended_at=ended_label,
            duration_seconds=duration_seconds,
        )
        self._clear_timer()
        if updated:
            self._refresh_tasks()
            self.notify(
                f"Task {updated.id} marked done with {duration_seconds}s tracked",
                severity="information",
            )
        else:
            self.notify("Task not found", severity="error")

    def action_save_note(self) -> None:
        """Save the currently open note (Ctrl+S or button)."""
        if self._active_note is None:
            self.notify("No note open to save", severity="warning")
            return
        editor = self.query_one("#note-editor", TextArea)
        content = editor.text
        updated = save_note(self._active_note.filename, content)
        self._active_note = updated
        self._refresh_notes_list()
        self.notify(f"Saved '{updated.title}'", severity="information")

    def action_toggle_read_mode(self) -> None:
        """Switch between Edit mode (plain TextArea) and Read mode (rendered Markdown)."""
        self._reading_mode = not self._reading_mode

        editor = self.query_one("#note-editor", TextArea)
        viewer_scroll = self.query_one("#note-viewer-scroll")
        btn = self.query_one("#btn-toggle-mode", Button)

        if self._reading_mode:
            # ── Entering reading mode ──────────────────────────────────
            # Render whatever is currently in the editor (unsaved edits included)
            self._render_markdown(editor.text)
            editor.add_class("reading")
            viewer_scroll.add_class("reading")
            btn.label = "✏️  Edit  Ctrl+E"
            btn.add_class("reading")
        else:
            # ── Returning to edit mode ─────────────────────────────────
            editor.remove_class("reading")
            viewer_scroll.remove_class("reading")
            btn.label = "📖 Read  Ctrl+E"
            btn.remove_class("reading")
            editor.focus()

        self._update_title_bar()

    def action_quit(self) -> None:
        self.exit()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run_tui() -> None:
    """Entry point to run the TUI."""
    app = GetItDoneTUI()
    app.run()
