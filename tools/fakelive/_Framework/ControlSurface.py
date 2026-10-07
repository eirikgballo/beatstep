"""Falsk `_Framework.ControlSurface`: tynt lag over c_instance, som i Live."""

from . import Task


class ControlSurface:

    def __init__(self, c_instance):
        self._c_instance = c_instance
        self._task_group = Task.TaskGroup()

    def song(self):
        return self._c_instance.song()

    def log_message(self, *message):
        self._c_instance.log_message(' '.join(str(m) for m in message))

    def show_message(self, message):
        self._c_instance.show_message(message)

    def _send_midi(self, midi_event_bytes, optimized=None):
        self._c_instance.send_midi(midi_event_bytes)
        return True

    def request_rebuild_midi_map(self):
        self._c_instance.request_rebuild_midi_map()

    def build_midi_map(self, midi_map_handle):
        pass

    def receive_midi(self, midi_bytes):
        pass

    def port_settings_changed(self):
        pass

    def update_display(self):
        # Live kaller denne hvert 100 ms, og det er den som driver tasks.
        self._task_group.update(0.1)

    def disconnect(self):
        self._task_group.clear()
