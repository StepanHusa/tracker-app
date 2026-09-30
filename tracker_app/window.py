from __future__ import annotations

import copy
import logging
from datetime import datetime
from typing import Callable, Optional

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, GLib, Gtk

from tracker_app.model import TrackerModel, format_duration, parse_duration

log = logging.getLogger(__name__)

_HINT = "Space=start/stop   r=reset   e=edit time   m=note   n=new   d/Del=delete   F2=rename   Ctrl+U=undo   Esc=close"


class TrackerRow(Gtk.ListBoxRow):
    def __init__(
        self,
        model: TrackerModel,
        on_start_stop: Callable[["TrackerRow"], None],
        on_reset: Callable[["TrackerRow"], None],
        on_rename_commit: Callable[["TrackerRow", str], None],
        on_note: Callable[["TrackerRow"], None],
        on_edit_time: Callable[["TrackerRow"], None],
    ) -> None:
        super().__init__()
        self.model = model
        self._on_start_stop = on_start_stop
        self._on_reset = on_reset
        self._on_rename_commit = on_rename_commit
        self._on_note = on_note
        self._on_edit_time = on_edit_time
        self._renaming = False
        self._build()

    def _build(self) -> None:
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        box.set_margin_top(4)
        box.set_margin_bottom(4)
        box.set_margin_start(8)
        box.set_margin_end(8)

        # Name label + rename entry (stacked, one visible at a time)
        self._name_label = Gtk.Label(label=self.model.name, xalign=0)
        self._name_label.set_hexpand(True)
        self._name_label.set_ellipsize(3)  # PANGO_ELLIPSIZE_END

        self._name_entry = Gtk.Entry()
        self._name_entry.set_hexpand(True)
        self._name_entry.set_no_show_all(True)
        self._name_entry.set_visible(False)
        self._name_entry.connect("activate", self._on_entry_activate)
        self._name_entry.connect("focus-out-event", self._on_entry_focus_out)
        self._name_entry.connect("key-press-event", self._on_entry_key)

        # Elapsed time
        self._elapsed_label = Gtk.Label(label="00:00:00")
        self._elapsed_label.set_width_chars(8)
        ctx = self._elapsed_label.get_style_context()
        ctx.add_class("monospace")

        # Start/Stop button
        self._toggle_btn = Gtk.Button(label="▶")
        self._toggle_btn.connect("clicked", lambda _: self._on_start_stop(self))

        # Reset button
        reset_btn = Gtk.Button(label="↺")
        reset_btn.connect("clicked", lambda _: self._on_reset(self))

        # Edit time button
        self._edit_time_btn = Gtk.Button(label="±")
        self._edit_time_btn.set_tooltip_text("Adjust elapsed time")
        self._edit_time_btn.connect("clicked", lambda _: self._on_edit_time(self))

        # Note button
        self._note_btn = Gtk.Button(label="✎")
        self._note_btn.connect("clicked", lambda _: self._on_note(self))

        # Last reset date
        self._date_label = Gtk.Label()
        self._date_label.set_width_chars(11)
        ctx2 = self._date_label.get_style_context()
        ctx2.add_class("dim-label")

        box.pack_start(self._name_label, True, True, 0)
        box.pack_start(self._name_entry, True, True, 0)
        box.pack_start(self._elapsed_label, False, False, 0)
        box.pack_start(self._toggle_btn, False, False, 0)
        box.pack_start(reset_btn, False, False, 0)
        box.pack_start(self._edit_time_btn, False, False, 0)
        box.pack_start(self._note_btn, False, False, 0)
        box.pack_start(self._date_label, False, False, 0)

        self.add(box)
        self.refresh(datetime.now())

    def refresh(self, now: datetime) -> None:
        elapsed = self.model.elapsed_seconds(now)
        h = int(elapsed // 3600)
        m = int((elapsed % 3600) // 60)
        s = int(elapsed % 60)
        self._elapsed_label.set_text(f"{h:02d}:{m:02d}:{s:02d}")

        adjusted = self.model.current_section.adjustment_seconds()
        if adjusted:
            self._elapsed_label.set_tooltip_text(
                f"includes manual adjustment {format_duration(adjusted)}"
            )
        else:
            self._elapsed_label.set_tooltip_text(None)
        self._toggle_btn.set_label("■" if self.model.is_running() else "▶")

        reset_date = self.model.last_reset_date()
        if reset_date:
            self._date_label.set_text(reset_date.strftime("%Y-%m-%d"))
        else:
            self._date_label.set_text("")

        self._name_label.set_text(self.model.name)

        note_ctx = self._note_btn.get_style_context()
        if self.model.current_section.note:
            note_ctx.add_class("suggested-action")
        else:
            note_ctx.remove_class("suggested-action")

    # ------------------------------------------------------------------
    # Rename
    # ------------------------------------------------------------------

    def start_rename(self) -> None:
        self._renaming = True
        self._name_entry.set_text(self.model.name)
        self._name_label.set_visible(False)
        self._name_entry.set_visible(True)
        self._name_entry.grab_focus()
        self._name_entry.select_region(0, -1)

    def _commit_rename(self) -> None:
        if not self._renaming:
            return
        text = self._name_entry.get_text().strip()
        if text:
            self._on_rename_commit(self, text)
        self._cancel_rename()

    def _cancel_rename(self) -> None:
        self._renaming = False
        self._name_entry.set_visible(False)
        self._name_label.set_visible(True)

    def _on_entry_activate(self, _entry) -> None:
        self._commit_rename()

    def _on_entry_focus_out(self, _entry, _event) -> None:
        self._commit_rename()

    def _on_entry_key(self, _entry, event) -> bool:
        if event.keyval == Gdk.KEY_Escape:
            self._cancel_rename()
            return True
        return False

    @property
    def is_renaming(self) -> bool:
        return self._renaming


class TrackerWindow(Gtk.Window):
    def __init__(
        self,
        trackers: list[TrackerModel],
        on_save: Callable[[TrackerModel], None],
        on_delete: Callable[[TrackerModel], None],
    ) -> None:
        super().__init__(title="Tracker")
        self._trackers = trackers
        self._on_save = on_save
        self._on_delete = on_delete
        self._rows: list[TrackerRow] = []
        self._selected_idx: int = 0
        self._tick_source_id: Optional[int] = None
        # Undo stack entries: ("mutate", snapshot) | ("create", model_id) | ("delete", snapshot, idx)
        self._undo_stack: list[tuple] = []

        self._build_ui()
        self._start_tick()
        self.connect("delete-event", self._on_delete_event)
        self.connect("key-press-event", self._on_key)

        self.set_default_size(580, 400)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_keep_above(True)

    def _build_ui(self) -> None:
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        # Top bar with Undo button
        top_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        top_bar.set_margin_start(4)
        top_bar.set_margin_top(4)
        top_bar.set_margin_bottom(4)
        self._undo_btn = Gtk.Button(label="↩ Undo")
        self._undo_btn.set_sensitive(False)
        self._undo_btn.connect("clicked", lambda _: self._action_undo())
        top_bar.pack_start(self._undo_btn, False, False, 0)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_vexpand(True)

        self._listbox = Gtk.ListBox()
        self._listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self._listbox.connect("row-selected", self._on_row_selected)

        for model in self._trackers:
            self._add_row(model)

        scrolled.add(self._listbox)

        hint = Gtk.Label(label=_HINT)
        hint.set_margin_top(4)
        hint.set_margin_bottom(4)
        ctx = hint.get_style_context()
        ctx.add_class("dim-label")

        vbox.pack_start(top_bar, False, False, 0)
        vbox.pack_start(scrolled, True, True, 0)
        vbox.pack_start(hint, False, False, 0)
        self.add(vbox)

        # Select first row
        if self._rows:
            self._listbox.select_row(self._rows[0])

    def _add_row(self, model: TrackerModel) -> TrackerRow:
        row = TrackerRow(
            model,
            on_start_stop=self._action_toggle,
            on_reset=self._action_reset,
            on_rename_commit=self._action_rename,
            on_note=self._action_note,
            on_edit_time=self._action_edit_time,
        )
        row.connect("button-press-event", self._on_row_double_click)
        self._listbox.add(row)
        self._rows.append(row)
        row.show_all()
        row._name_entry.set_no_show_all(True)
        row._name_entry.set_visible(False)
        return row

    # ------------------------------------------------------------------
    # Tick
    # ------------------------------------------------------------------

    def _start_tick(self) -> None:
        self._tick_source_id = GLib.timeout_add(1000, self._on_tick)

    def _on_tick(self) -> bool:
        now = datetime.now()
        for row in self._rows:
            if row.model.is_running():
                row.refresh(now)
        return True

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _action_toggle(self, row: TrackerRow) -> None:
        now = datetime.now()
        self._push_undo_mutate(row.model)
        if row.model.is_running():
            row.model.stop(now)
            log.info("Stopped '%s'", row.model.name)
        else:
            row.model.start(now)
            log.info("Started '%s'", row.model.name)
        self._on_save(row.model)
        row.refresh(now)

    def _action_reset(self, row: TrackerRow) -> None:
        now = datetime.now()
        self._push_undo_mutate(row.model)
        log.info("Reset '%s'", row.model.name)
        row.model.reset(now)
        self._on_save(row.model)
        row.refresh(now)

    def _action_rename(self, row: TrackerRow, new_name: str) -> None:
        self._push_undo_mutate(row.model)
        log.info("Renamed '%s' -> '%s'", row.model.name, new_name)
        row.model.name = new_name
        self._on_save(row.model)
        row.refresh(datetime.now())

    def _action_note(self, row: TrackerRow) -> None:
        dialog = Gtk.Dialog(
            title="Section Note",
            transient_for=self,
            modal=True,
        )
        dialog.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
            Gtk.STOCK_OK, Gtk.ResponseType.OK,
        )
        dialog.set_default_response(Gtk.ResponseType.OK)

        entry = Gtk.Entry()
        entry.set_placeholder_text("Note for this session")
        entry.set_text(row.model.current_section.note)
        entry.set_activates_default(True)
        entry.set_width_chars(40)
        entry.set_margin_top(8)
        entry.set_margin_bottom(8)
        entry.set_margin_start(8)
        entry.set_margin_end(8)

        dialog.get_content_area().add(entry)
        dialog.show_all()
        response = dialog.run()
        text = entry.get_text().strip()
        dialog.destroy()

        if response == Gtk.ResponseType.OK:
            now = datetime.now()
            self._push_undo_mutate(row.model)
            sec = row.model.current_section
            sec.note = text
            sec.note_created = now if text else None
            log.info("Note set on '%s': %r", row.model.name, text)
            self._on_save(row.model)
            row.refresh(now)

    def _action_edit_time(self, row: TrackerRow) -> None:
        dialog = Gtk.Dialog(
            title="Adjust Time",
            transient_for=self,
            modal=True,
        )
        dialog.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
            Gtk.STOCK_OK, Gtk.ResponseType.OK,
        )
        dialog.set_default_response(Gtk.ResponseType.OK)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.set_margin_top(8)
        box.set_margin_bottom(8)
        box.set_margin_start(8)
        box.set_margin_end(8)

        entry = Gtk.Entry()
        entry.set_placeholder_text("+7m, -30s, 1h 15m, 0:45")
        entry.set_activates_default(True)
        entry.set_width_chars(24)

        error_label = Gtk.Label(xalign=0)
        error_label.get_style_context().add_class("dim-label")

        current = row.model.current_section.adjustment_seconds()
        if current:
            error_label.set_text(f"current adjustment: {format_duration(current)}")

        box.pack_start(entry, False, False, 0)
        box.pack_start(error_label, False, False, 0)
        dialog.get_content_area().add(box)
        dialog.show_all()

        while True:
            response = dialog.run()
            if response != Gtk.ResponseType.OK:
                dialog.destroy()
                return
            seconds = parse_duration(entry.get_text())
            if seconds is None:
                error_label.set_text("Cannot read that duration — try \"+7m\".")
                entry.grab_focus()
                continue
            dialog.destroy()
            break

        now = datetime.now()
        self._push_undo_mutate(row.model)
        row.model.adjust(seconds, now)
        log.info("Adjusted '%s' by %s", row.model.name, format_duration(seconds))
        self._on_save(row.model)
        row.refresh(now)

    def _action_new(self) -> None:
        dialog = Gtk.Dialog(
            title="New Tracker",
            transient_for=self,
            modal=True,
        )
        dialog.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
            Gtk.STOCK_OK, Gtk.ResponseType.OK,
        )
        dialog.set_default_response(Gtk.ResponseType.OK)

        entry = Gtk.Entry()
        entry.set_placeholder_text("Tracker name")
        entry.set_activates_default(True)
        entry.set_margin_top(8)
        entry.set_margin_bottom(8)
        entry.set_margin_start(8)
        entry.set_margin_end(8)

        dialog.get_content_area().add(entry)
        dialog.show_all()
        response = dialog.run()
        name = entry.get_text().strip()
        dialog.destroy()

        if response == Gtk.ResponseType.OK and name:
            model = TrackerModel.new(name)
            log.info("Created tracker '%s'", name)
            self._trackers.append(model)
            self._on_save(model)
            row = self._add_row(model)
            self._select_idx(len(self._rows) - 1)
            self._push_undo_create(model.id)

    def _action_delete(self) -> None:
        if not self._rows:
            return
        idx = self._selected_idx
        model = self._rows[idx].model

        dialog = Gtk.MessageDialog(
            transient_for=self,
            modal=True,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.YES_NO,
            text=f"Delete tracker '{model.name}'?",
        )
        response = dialog.run()
        dialog.destroy()

        if response == Gtk.ResponseType.YES:
            log.info("Deleted tracker '%s'", model.name)
            self._push_undo_delete(model, idx)
            self._on_delete(model)
            row = self._rows.pop(idx)
            self._trackers.pop(idx)
            self._listbox.remove(row)
            new_idx = min(idx, len(self._rows) - 1)
            self._select_idx(new_idx)

    # ------------------------------------------------------------------
    # Undo
    # ------------------------------------------------------------------

    def _push_undo_mutate(self, model: TrackerModel) -> None:
        self._undo_stack.append(("mutate", copy.deepcopy(model)))
        self._undo_btn.set_sensitive(True)

    def _push_undo_create(self, model_id: str) -> None:
        self._undo_stack.append(("create", model_id))
        self._undo_btn.set_sensitive(True)

    def _push_undo_delete(self, model: TrackerModel, idx: int) -> None:
        self._undo_stack.append(("delete", copy.deepcopy(model), idx))
        self._undo_btn.set_sensitive(True)

    def _action_undo(self) -> None:
        if not self._undo_stack:
            return
        entry = self._undo_stack.pop()
        self._undo_btn.set_sensitive(bool(self._undo_stack))

        kind = entry[0]

        if kind == "mutate":
            snapshot: TrackerModel = entry[1]
            for i, t in enumerate(self._trackers):
                if t.id == snapshot.id:
                    t.name = snapshot.name
                    t.sections = snapshot.sections
                    self._on_save(t)
                    self._rows[i].refresh(datetime.now())
                    log.info("Undo mutation on '%s'", t.name)
                    break

        elif kind == "create":
            model_id: str = entry[1]
            for i, t in enumerate(self._trackers):
                if t.id == model_id:
                    log.info("Undo create '%s'", t.name)
                    self._on_delete(t)
                    row = self._rows.pop(i)
                    self._trackers.pop(i)
                    self._listbox.remove(row)
                    new_idx = min(self._selected_idx, len(self._rows) - 1)
                    self._select_idx(new_idx)
                    break

        elif kind == "delete":
            snapshot: TrackerModel = entry[1]
            idx: int = entry[2]
            log.info("Undo delete '%s'", snapshot.name)
            insert_at = min(idx, len(self._trackers))
            self._trackers.insert(insert_at, snapshot)
            self._on_save(snapshot)
            # Rebuild listbox to insert row at correct position
            self._rebuild_listbox()
            self._select_idx(insert_at)

    def _rebuild_listbox(self) -> None:
        for row in self._rows:
            self._listbox.remove(row)
        self._rows.clear()
        for model in self._trackers:
            self._add_row(model)

    # ------------------------------------------------------------------
    # Selection
    # ------------------------------------------------------------------

    def _select_idx(self, idx: int) -> None:
        if not self._rows:
            return
        idx = max(0, min(idx, len(self._rows) - 1))
        self._selected_idx = idx
        self._listbox.select_row(self._rows[idx])

    def _on_row_selected(self, _listbox, row) -> None:
        if row is not None:
            try:
                self._selected_idx = self._rows.index(row)
            except ValueError:
                pass

    def _on_row_double_click(self, row, event) -> bool:
        if event.type == Gdk.EventType.DOUBLE_BUTTON_PRESS and event.button == 1:
            row.start_rename()
            return True
        return False

    # ------------------------------------------------------------------
    # Keyboard
    # ------------------------------------------------------------------

    def _on_key(self, _widget, event) -> bool:
        kv = event.keyval

        # If any row is in rename mode, let it handle keys
        for row in self._rows:
            if row.is_renaming:
                return False

        # Esc — hide window
        if kv == Gdk.KEY_Escape:
            self.hide()
            return True

        # 1–9 — select by index
        if Gdk.KEY_1 <= kv <= Gdk.KEY_9:
            self._select_idx(kv - Gdk.KEY_1)
            return True

        # Arrow keys — move selection
        if kv == Gdk.KEY_Up:
            self._select_idx(self._selected_idx - 1)
            return True
        if kv == Gdk.KEY_Down:
            self._select_idx(self._selected_idx + 1)
            return True

        # Space — start/stop selected
        if kv == Gdk.KEY_space:
            if self._rows:
                self._action_toggle(self._rows[self._selected_idx])
            return True

        # r — reset selected
        if kv == Gdk.KEY_r:
            if self._rows:
                self._action_reset(self._rows[self._selected_idx])
            return True

        # e — edit (adjust) time of selected
        if kv == Gdk.KEY_e:
            if self._rows:
                self._action_edit_time(self._rows[self._selected_idx])
            return True

        # m — note on selected
        if kv == Gdk.KEY_m:
            if self._rows:
                self._action_note(self._rows[self._selected_idx])
            return True

        # n — new tracker
        if kv == Gdk.KEY_n:
            self._action_new()
            return True

        # d or Delete — delete selected
        if kv in (Gdk.KEY_d, Gdk.KEY_Delete):
            self._action_delete()
            return True

        # F2 — rename selected
        if kv == Gdk.KEY_F2:
            if self._rows:
                self._rows[self._selected_idx].start_rename()
            return True

        # Ctrl+U — undo
        if kv == Gdk.KEY_u and event.state & Gdk.ModifierType.CONTROL_MASK:
            self._action_undo()
            return True

        return False

    # ------------------------------------------------------------------
    # Window close
    # ------------------------------------------------------------------

    def _on_delete_event(self, _widget, _event) -> bool:
        self.hide()
        return True  # prevent actual destroy
