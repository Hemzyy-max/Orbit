"""Controlled local tools for ORBIT on Windows."""

from __future__ import annotations

import os
import re
import shutil
import sqlite3
import subprocess
import time
import webbrowser

from datetime import datetime
from pathlib import Path
from urllib.parse import quote, urlparse


WORKSPACE = Path.home() / "Documents" / "ORBIT Workspace"
NOTES_DIR = WORKSPACE / "Notes"
DB_PATH = WORKSPACE / "orbit_tasks.sqlite3"


class OrbitTools:
    """Tools restricted to a defined set of local actions."""

    def __init__(self):
        WORKSPACE.mkdir(parents=True, exist_ok=True)
        NOTES_DIR.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self):
        conn = sqlite3.connect(DB_PATH, timeout=10)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    due_date TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'open',
                    created_at TEXT NOT NULL
                )
                """
            )

    @staticmethod
    def _clean(value, max_length=5000):
        return str(value).strip()[:max_length]

    def open_application(self, app_name: str) -> str:
        """Open an application from an allow-list."""

        app = re.sub(
            r"\s+",
            " ",
            self._clean(app_name, 80).lower(),
        ).strip()

        try:
            if app == "calculator":
                subprocess.Popen(["calc.exe"], shell=False)
                return "Opened Calculator."

            if app == "notepad":
                subprocess.Popen(["notepad.exe"], shell=False)
                return "Opened Notepad."

            if app in {"file explorer", "explorer", "files"}:
                if os.name == "nt":
                    os.startfile(str(Path.home()))
                    return "Opened File Explorer."
                return "File Explorer is supported only on Windows."

            if app in {"browser", "web browser", "default browser"}:
                opened = webbrowser.open(
                    "https://www.google.com",
                    new=2,
                )
                return (
                    "Opened your default browser."
                    if opened
                    else "The browser launch was not confirmed."
                )

            if app in {
                "vscode",
                "vs code",
                "visual studio code",
            }:
                code_path = shutil.which("code")

                if not code_path:
                    return (
                        "I couldn't find the VS Code command. "
                        "Open VS Code or add its command to PATH."
                    )

                subprocess.Popen([code_path], shell=False)
                return "Opened Visual Studio Code."

            return (
                "That application is not approved. "
                "I can open Calculator, Notepad, File Explorer, "
                "your browser, or VS Code."
            )

        except (OSError, FileNotFoundError) as exc:
            return f"I couldn't open {app}: {exc}"

    @staticmethod
    def _active_window_title() -> str:
        """Read only the foreground window title."""

        if os.name != "nt":
            return ""

        try:
            import ctypes

            user32 = ctypes.windll.user32
            hwnd = user32.GetForegroundWindow()
            length = user32.GetWindowTextLengthW(hwnd)

            buffer = ctypes.create_unicode_buffer(length + 1)

            user32.GetWindowTextW(
                hwnd,
                buffer,
                length + 1,
            )

            return buffer.value

        except Exception:
            return ""

    def type_text_in_notepad(self, text: str) -> str:
        """Paste requested text only into active Notepad."""

        if os.name != "nt":
            return "Desktop typing is supported only on Windows."

        clean_text = self._clean(text, 8000)

        if not clean_text:
            return "No text was provided."

        title = self._active_window_title()

        if "notepad" not in title.casefold():
            shown_title = title[:120] if title else "unknown window"

            return (
                "I didn't type anything because Notepad is not "
                f"the active window. Active window: {shown_title}. "
                "Open Notepad and click inside its document, "
                "then ask me to type again."
            )

        try:
            import pyautogui
            import pyperclip

            previous_clipboard = None

            try:
                previous_clipboard = pyperclip.paste()
            except Exception:
                pass

            try:
                pyperclip.copy(clean_text)
                time.sleep(0.15)
                pyautogui.hotkey("ctrl", "v")
                time.sleep(0.35)

            finally:
                if previous_clipboard is not None:
                    try:
                        pyperclip.copy(previous_clipboard)
                    except Exception:
                        pass

            return (
                f"Pasted {len(clean_text)} characters "
                "into the active Notepad window."
            )

        except Exception as exc:
            return f"I couldn't type into Notepad: {exc}"

    def open_workspace_folder(self) -> str:
        """Open ORBIT's workspace in File Explorer."""

        if os.name != "nt":
            return f"Workspace location: {WORKSPACE}"

        try:
            os.startfile(str(WORKSPACE))
            return f"Opened the ORBIT workspace folder: {WORKSPACE}"

        except OSError as exc:
            return f"I couldn't open the workspace: {exc}"

    def open_website(self, url: str) -> str:
        """Open an HTTP or HTTPS website."""

        candidate = self._clean(url, 2048)

        if not candidate:
            return "Please provide a website address."

        if not re.match(
            r"^https?://",
            candidate,
            flags=re.IGNORECASE,
        ):
            candidate = "https://" + candidate

        parsed = urlparse(candidate)

        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.netloc
            or " " in parsed.netloc
            or parsed.username is not None
            or parsed.password is not None
        ):
            return "That doesn't look like a valid website address."

        try:
            opened = webbrowser.open(candidate, new=2)

            if opened:
                return f"Opened {parsed.netloc} in your browser."

            return "The browser launch was not confirmed."

        except Exception as exc:
            return f"I couldn't open the website: {exc}"

    def search_web(self, query: str) -> str:
        """Open a Google search; does not read the results."""

        phrase = self._clean(query, 300)

        if not phrase:
            return "Tell me what you want to search for."

        url = (
            "https://www.google.com/search?q="
            + quote(phrase)
        )

        try:
            opened = webbrowser.open(url, new=2)

            if opened:
                return (
                    f"Opened a Google search for {phrase}. "
                    "I haven't read or verified the search results."
                )

            return "The browser launch was not confirmed."

        except Exception as exc:
            return f"I couldn't open the search: {exc}"

    def create_note(self, title: str, content: str) -> str:
        """Create a new note without overwriting existing notes."""

        clean_title = self._clean(title, 120)
        clean_content = self._clean(content, 20000)

        if not clean_title:
            return "A note needs a title."

        if not clean_content:
            return "The note content is empty."

        slug = re.sub(
            r"[^a-zA-Z0-9 _-]",
            "",
            clean_title,
        ).strip().replace(" ", "_")

        slug = re.sub(r"_+", "_", slug)[:70] or "note"

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = NOTES_DIR / f"{slug}_{timestamp}.txt"

        try:
            with path.open("x", encoding="utf-8") as file:
                file.write(
                    f"{clean_title}\n"
                    f"{'=' * min(len(clean_title), 80)}\n\n"
                )
                file.write(clean_content)
                file.write("\n")

            return f"Created note: {path}"

        except OSError as exc:
            return f"I couldn't create the note: {exc}"

    def add_task(self, title: str, due_date: str = "") -> str:
        """Save a task in the local SQLite database."""

        clean_title = self._clean(title, 300)
        clean_due = self._clean(due_date, 120)

        if not clean_title:
            return "A task needs a title."

        try:
            with self._connect() as conn:
                cursor = conn.execute(
                    """
                    INSERT INTO tasks
                        (title, due_date, status, created_at)
                    VALUES (?, ?, 'open', ?)
                    """,
                    (
                        clean_title,
                        clean_due,
                        datetime.now().isoformat(
                            timespec="seconds"
                        ),
                    ),
                )

                task_id = cursor.lastrowid

            due_text = (
                f" Deadline: {clean_due}."
                if clean_due
                else ""
            )

            return (
                f"Saved task #{task_id}: "
                f"{clean_title}.{due_text}"
            )

        except sqlite3.Error as exc:
            return f"I couldn't save the task: {exc}"

    def list_tasks(self, include_completed: bool = False) -> str:
        """List tasks from the local database."""

        try:
            with self._connect() as conn:
                if include_completed:
                    rows = conn.execute(
                        """
                        SELECT id, title, due_date, status
                        FROM tasks
                        ORDER BY id DESC
                        LIMIT 50
                        """
                    ).fetchall()

                else:
                    rows = conn.execute(
                        """
                        SELECT id, title, due_date, status
                        FROM tasks
                        WHERE status = 'open'
                        ORDER BY id DESC
                        LIMIT 50
                        """
                    ).fetchall()

            if not rows:
                return (
                    "Your task list is empty."
                    if not include_completed
                    else "No tasks have been saved yet."
                )

            parts = []

            for row in rows:
                due = (
                    f"; deadline {row['due_date']}"
                    if row["due_date"]
                    else ""
                )

                parts.append(
                    f"Task {row['id']}: {row['title']} "
                    f"({row['status']}{due})"
                )

            return "Here are your tasks: " + ". ".join(parts)

        except sqlite3.Error as exc:
            return f"I couldn't read the task list: {exc}"

    def complete_task(self, task_id: int) -> str:
        """Mark an open task as completed."""

        try:
            with self._connect() as conn:
                cursor = conn.execute(
                    """
                    UPDATE tasks
                    SET status = 'completed'
                    WHERE id = ? AND status = 'open'
                    """,
                    (int(task_id),),
                )

                changed = cursor.rowcount

            if changed:
                return f"Marked task #{task_id} as completed."

            return (
                f"I couldn't find an open task with ID {task_id}. "
                "Ask me to list your tasks to check the ID."
            )

        except (ValueError, sqlite3.Error) as exc:
            return f"I couldn't complete that task: {exc}"