import datetime
import json
import os
import webbrowser

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import (
    Button,
    Footer,
    Header,
    Input,
    Label,
    ListItem,
    ListView,
    Static,
)
from textual.binding import Binding

from .api import TickTickClient, TickTickError

CONFIG_DIR = os.path.expanduser("~/.config/eztick")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")


def parse_due(raw: str) -> datetime.datetime | None:
    if not raw:
        return None
    norm = raw.replace("Z", "+0000")
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            return datetime.datetime.strptime(norm, fmt).astimezone()
        except ValueError:
            continue
    return None


def format_due(date: datetime.date) -> str:
    local_tz = datetime.datetime.now().astimezone().tzinfo
    midnight = datetime.datetime.combine(date, datetime.time(0, 0), tzinfo=local_tz)
    return midnight.strftime("%Y-%m-%dT%H:%M:%S%z")


def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE) as f:
            return json.load(f)
    return {}


def save_config(data):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f)


class TaskItem(ListItem):
    def __init__(self, task: dict, selected: bool = False):
        self.task_data = task
        self._selected = selected
        super().__init__()

    def compose(self):
        title = self.task_data.get("title", "")
        dt = parse_due(self.task_data.get("dueDate", ""))
        date_str = f"[{dt.day:02d}-{dt.month:02d}] " if dt else ""
        marker = "\u25cf " if self._selected else ""
        yield Label(f"{marker}{date_str}{title}")


SETUP_INSTRUCTIONS = """
To use the TickTick API you need a Developer App.

1. Go to https://developer.ticktick.com
2. Create a new app (name: "EZTick", etc.)
3. Set redirect URI to http://localhost:8765/callback
4. Copy the Client ID and Client Secret below
"""

AUTH_INSTRUCTIONS = """
Open the URL below in your browser, authorize EZTick,
then paste the code from the redirected URL.

The code will be in the URL bar after "?code="
"""


class SetupScreen(Screen):
    def compose(self):
        yield Vertical(
            Static("EZTick - App Setup", classes="login-title"),
            Static(SETUP_INSTRUCTIONS, id="instructions"),
            Input(placeholder="Client ID", id="client-id-input"),
            Input(placeholder="Client Secret", id="client-secret-input"),
            Input(
                value="http://localhost:8765/callback",
                placeholder="Redirect URI",
                id="redirect-input",
            ),
            Button("Save & Continue", id="save-btn", variant="primary"),
            id="login-form",
        )

    def on_mount(self):
        self.query_one("#client-id-input", Input).focus()

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "save-btn":
            self.save()

    def on_input_submitted(self, event: Input.Submitted):
        self.save()

    def save(self):
        cid = self.query_one("#client-id-input", Input).value.strip()
        secret = self.query_one("#client-secret-input", Input).value.strip()
        redirect = self.query_one("#redirect-input", Input).value.strip()
        if not cid or not secret or not redirect:
            self.notify("All fields required", severity="error")
            return
        self.app.client.setup_app(cid, secret, redirect)
        save_config({"client_id": cid, "client_secret": secret, "redirect_uri": redirect})
        self.app.switch_screen(AuthScreen())


class AuthScreen(Screen):
    def compose(self):
        url = self.app.client.get_authorize_url()
        yield Vertical(
            Static("EZTick - Authorize", classes="login-title"),
            Static(AUTH_INSTRUCTIONS, id="instructions"),
            Static(url, id="auth-url"),
            Horizontal(
                Button("Open in Browser", id="open-btn"),
                Button("Authorize", id="auth-btn", variant="primary"),
            ),
            Input(placeholder="Paste the code from the URL here", id="code-input"),
            id="login-form",
        )

    def on_mount(self):
        self.query_one("#code-input", Input).focus()

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "open-btn":
            url = self.app.client.get_authorize_url()
            webbrowser.open(url)
            self.notify("Browser opened (or check your terminal for the link)")
        elif event.button.id == "auth-btn":
            self.authorize()

    def on_input_submitted(self, event: Input.Submitted):
        self.authorize()

    def authorize(self):
        code = self.query_one("#code-input", Input).value.strip()
        if not code:
            self.notify("Code is required", severity="error")
            return
        try:
            self.app.client.exchange_code(code)
        except TickTickError as e:
            self.notify(f"Authorization failed: {e}", severity="error")
            return
        except Exception as e:
            self.notify(f"Error: {e}", severity="error")
            return
        config = load_config()
        config["access_token"] = self.app.client.access_token
        config["refresh_token"] = self.app.client.refresh_token
        save_config(config)
        self.app.switch_screen(MainScreen())


class TaskEditScreen(Screen):
    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

    def __init__(self, task: dict | None = None):
        super().__init__()
        self._edit_task = task

    @property
    def is_new(self):
        return self._edit_task is None

    def compose(self):
        title = self._edit_task.get("title", "") if self._edit_task else ""
        due = ""
        if self._edit_task:
            dt = parse_due(self._edit_task.get("dueDate", ""))
            if dt:
                due = f"{dt.day:02d}-{dt.month:02d}"
        yield Vertical(
            Static("New Task" if self.is_new else "Edit Task", classes="login-title"),
            Input(value=title, placeholder="Task title", id="title-input"),
            Input(
                value=due,
                placeholder="Due date (DD-MM, optional)",
                id="date-input",
            ),
            Horizontal(
                Button("Save", id="save-btn", variant="primary"),
                Button("Cancel", id="cancel-btn"),
            ),
        )

    def on_mount(self):
        self.query_one("#title-input", Input).focus()

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "save-btn":
            self.save()
        elif event.button.id == "cancel-btn":
            self.dismiss(False)

    def on_input_submitted(self, event: Input.Submitted):
        if event.input.id == "title-input":
            self.query_one("#date-input", Input).focus()
        elif event.input.id == "date-input":
            self.save()

    def save(self):
        title = self.query_one("#title-input", Input).value.strip()
        if not title:
            self.notify("Title is required", severity="error")
            return
        date_raw = self.query_one("#date-input", Input).value.strip()
        due_date = None
        if date_raw:
            parsed = self._parse_due_date(date_raw)
            if parsed is None:
                self.notify("Date must be DD-MM", severity="error")
                return
            due_date = format_due(parsed)
        try:
            client = self.app.client
            if self.is_new:
                client.create_task(title, due_date)
            else:
                client.update_task(
                    self._edit_task["projectId"],
                    self._edit_task["id"],
                    self._edit_task,
                    title,
                    due_date,
                )
        except TickTickError as e:
            self.notify(f"Error: {e}", severity="error")
            return
        except Exception as e:
            self.notify(f"Error: {e}", severity="error")
            return
        self.dismiss(True)

    def action_cancel(self):
        self.dismiss(False)

    @staticmethod
    def _parse_due_date(raw: str) -> datetime.date | None:
        parts = raw.split("-")
        if len(parts) != 2:
            return None
        try:
            day = int(parts[0])
            month = int(parts[1])
        except ValueError:
            return None
        today = datetime.date.today()
        try:
            candidate = datetime.date(today.year, month, day)
        except ValueError:
            return None
        if candidate < today:
            try:
                candidate = datetime.date(today.year + 1, month, day)
            except ValueError:
                return None
        return candidate


class MainScreen(Screen):
    BINDINGS = [
        Binding("j", "move_down", "Down", show=True, priority=True),
        Binding("k", "move_up", "Up", show=True, priority=True),
        Binding("space", "select_task", "Select", show=True),
        Binding("d", "delete_task", "Delete", show=True),
        Binding("e", "edit_task", "Edit", show=True),
        Binding("n", "new_task", "New", show=True),
        Binding("r", "refresh", "Refresh", show=True),
        Binding("ctrl+z", "undo", "Undo", show=True),
        Binding("q", "quit", "Quit", show=True),
    ]

    def __init__(self):
        super().__init__()
        self.tasks = []
        self.selected_ids = set()
        self.undo_stack = []

    def compose(self):
        yield Header(show_clock=False)
        yield ListView(id="task-list")
        yield Footer()

    def on_mount(self):
        self.load_tasks()
        self.query_one("#task-list", ListView).focus()

    def load_tasks(self):
        try:
            raw = self.app.client.get_inbox_tasks()
            self.tasks = [t for t in raw if t.get("status", 0) != 2]
        except TickTickError as e:
            self.notify(f"Failed to load tasks: {e}", severity="error")
            return
        except Exception as e:
            self.notify(f"Connection error: {e}", severity="error")
            return
        self._sort_tasks()
        self.rebuild_list()

    def _sort_tasks(self):
        def key(t):
            dt = parse_due(t.get("dueDate", ""))
            return (0, dt.date()) if dt else (1, datetime.date.max)
        self.tasks.sort(key=key)

    def rebuild_list(self):
        lv = self.query_one("#task-list", ListView)
        prev_index = lv.index
        lv.clear()
        for task in self.tasks:
            item = TaskItem(task, task["id"] in self.selected_ids)
            lv.append(item)
        if self.tasks:
            target = 0 if prev_index is None else min(prev_index, len(self.tasks) - 1)
            self.call_after_refresh(self._restore_index, target)
        lv.focus()

    def _restore_index(self, index: int):
        lv = self.query_one("#task-list", ListView)
        lv.index = index

    def on_list_view_selected(self, event: ListView.Selected):
        task_data = getattr(event.item, "task_data", None)
        if task_data:
            self.complete_task(task_data)
        event.stop()

    def complete_task(self, task: dict):
        try:
            self.app.client.complete_task(task["projectId"], task["id"], task)
        except TickTickError as e:
            self.notify(f"Error: {e}", severity="error")
            return
        except Exception as e:
            self.notify(f"Error: {e}", severity="error")
            return
        self.undo_stack.append(task)
        self.tasks.remove(task)
        self.selected_ids.discard(task["id"])
        self.rebuild_list()
        self.notify("Done! Ctrl+Z to undo.")

    def action_move_down(self):
        lv = self.query_one("#task-list", ListView)
        if not self.tasks:
            return
        if lv.index is None:
            lv.index = 0
        else:
            lv.index = min(lv.index + 1, len(self.tasks) - 1)

    def action_move_up(self):
        lv = self.query_one("#task-list", ListView)
        if not self.tasks:
            return
        if lv.index is None:
            lv.index = 0
        else:
            lv.index = max(lv.index - 1, 0)

    def action_select_task(self):
        lv = self.query_one("#task-list", ListView)
        if lv.index is not None and lv.index < len(self.tasks):
            task = self.tasks[lv.index]
            tid = task["id"]
            if tid in self.selected_ids:
                self.selected_ids.discard(tid)
            else:
                self.selected_ids.add(tid)
            self.rebuild_list()

    def action_delete_task(self):
        lv = self.query_one("#task-list", ListView)
        to_delete = []
        if self.selected_ids:
            to_delete = [t for t in self.tasks if t["id"] in self.selected_ids]
        elif lv.index is not None and lv.index < len(self.tasks):
            to_delete = [self.tasks[lv.index]]
        if not to_delete:
            return
        for task in to_delete:
            try:
                self.app.client.delete_task(task["projectId"], task["id"])
            except TickTickError as e:
                self.notify(f"Error deleting: {e}", severity="error")
                continue
            except Exception as e:
                self.notify(f"Error: {e}", severity="error")
                continue
            self.tasks.remove(task)
            self.selected_ids.discard(task["id"])
        self.rebuild_list()
        self.notify(f"Deleted {len(to_delete)} task(s)")

    def action_edit_task(self):
        lv = self.query_one("#task-list", ListView)
        if lv.index is not None and lv.index < len(self.tasks):
            task = self.tasks[lv.index]
            self.app.push_screen(TaskEditScreen(task), self._on_edit_done)

    def action_new_task(self):
        self.app.push_screen(TaskEditScreen(), self._on_edit_done)

    def _on_edit_done(self, saved: bool | None):
        if saved:
            self.load_tasks()

    def action_refresh(self):
        self.load_tasks()
        self.notify("Refreshed")

    def action_undo(self):
        if not self.undo_stack:
            self.notify("Nothing to undo")
            return
        task = self.undo_stack.pop()
        try:
            self.app.client.uncomplete_task(task["projectId"], task["id"])
        except TickTickError as e:
            self.notify(f"Error: {e}", severity="error")
            return
        except Exception as e:
            self.notify(f"Error: {e}", severity="error")
            return
        self.tasks.append(task)
        self._sort_tasks()
        self.rebuild_list()
        self.notify("Undone!")

class EZTickApp(App):
    CSS = """
    Screen {
        background: $surface;
    }
    #login-form {
        align: center middle;
        width: 40;
        height: auto;
        border: solid $primary;
        padding: 1 2;
        background: $panel;
    }
    .login-title {
        text-style: bold;
        content-align: center middle;
        height: 3;
    }
    #login-form Input {
        margin: 0 0 1 0;
    }
    #instructions {
        height: auto;
        margin: 0 0 1 0;
        color: $text-muted;
    }
    #auth-url {
        height: auto;
        margin: 0 0 1 0;
        color: $accent;
        background: $boost;
        padding: 0 1;
    }
    #login-form > Horizontal Button {
        margin: 1 0 0 0;
    }
    #task-list {
        height: 1fr;
        border: none;
    }
    ListItem {
        padding: 0 1;
    }
    ListView:focus-within {
        border: none;
    }
    """

    def __init__(self):
        super().__init__()
        self.client = TickTickClient()

    def on_mount(self):
        config = load_config()
        cid = config.get("client_id")
        secret = config.get("client_secret")
        redirect = config.get("redirect_uri")
        if cid and secret and redirect:
            self.client.setup_app(cid, secret, redirect)
            token = config.get("access_token")
            if token:
                self.client.access_token = token
                self.client.refresh_token = config.get("refresh_token")
                if self.client.verify_token():
                    self.push_screen(MainScreen())
                    return
            self.push_screen(AuthScreen())
        else:
            self.push_screen(SetupScreen())

    def action_quit(self):
        self.exit()
