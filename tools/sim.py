"""
sim.py — kjør BeatStep mot ekte BeatStep og falsk Live, uten Ableton.

  python tools/sim.py [--tracks 20] [--log logs/sim.log]

Skriver én linje per hendelse: hva som kom inn, hva Live-tilstanden ble, og hvilke LED-er som ble sendt.
Lastes automatisk på nytt når en .py-fil i repoet endres (som å restarte Live).

Kommandoer kan skrives til logs/sim_cmd.txt (én per linje), for å simulere endringer i Live-UI-et:
  select N | solo N | add | del N | state | reload | sysex F0 .. F7
"""

import argparse
import os
import queue
import sys
import time

import mido

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fakelive'))

import bs  # noqa: E402  (portoppslag og tolkning av innkommende MIDI)
from harness import Harness, REPO, SCRIPT_FILES  # noqa: E402
from fake_song import default_song  # noqa: E402

CMD_FILE = os.path.join(REPO, 'logs', 'sim_cmd.txt')
COLOR_NAMES = {0: 'svart', 1: 'rød', 16: 'blå', 17: 'magenta'}


class Sim:

    def __init__(self, args):
        self.out = mido.open_output(bs._find_port(mido.get_output_names(), args.port))
        self.inp = mido.open_input(bs._find_port(mido.get_input_names(), args.port))
        self.log = open(args.log, 'a', encoding='utf-8') if args.log else None
        self.song = default_song(args.tracks)
        self.start = time.time()
        self.harness = None
        self._mtimes = {}
        self._snapshot = {}
        self._pending_leds = []

    # ------------------------------------------------------------------

    def emit(self, text):
        line = '%8.3f  %s' % (time.time() - self.start, text)
        print(line, flush=True)
        if self.log:
            self.log.write(line + '\n')
            self.log.flush()

    def _send(self, midi_bytes):
        self.out.send(mido.Message.from_bytes(list(midi_bytes)))
        self._pending_leds.append(midi_bytes)

    def _describe_out(self):
        """Slå sammen utgående meldinger siden sist til én lesbar linje."""
        if not self._pending_leds:
            return
        leds, other = [], 0
        for b in self._pending_leds:
            if len(b) == 12 and b[8] == 0x10:
                hw, color = b[9], b[10]
                name = 'pad %d' % (hw - 0x70 + 1) if 0x70 <= hw <= 0x7F else 'hw 0x%02X' % hw
                leds.append('%s=%s' % (name, COLOR_NAMES.get(color, color)))
            else:
                other += 1
        parts = []
        if other:
            parts.append('%d oppsett-sysex' % other)
        if leds:
            parts.append('%d LED: %s' % (len(leds), ', '.join(leds)))
        self.emit('   <- ' + ' | '.join(parts))
        self._pending_leds = []

    # ------------------------------------------------------------------

    def _state(self):
        pads = getattr(self.harness.script, '_pads', None)
        tracks = self.song.tracks
        state = {
            'valgt': self.song.view.selected_track.name,
            'side': pads._page + 1 if pads else '?',
            'solo': ','.join(t.name.replace('Spor ', '') for t in tracks if t.solo) or '-',
        }
        for t in list(tracks) + [self.song.master_track]:
            state['%s volum' % t.name] = round(t.mixer_device.volume.value, 3)
            for d in t.devices:
                if d.class_name == 'AudioEffectGroupDevice':
                    for p in d.parameters[1:]:
                        state['%s %s' % (d.name, p.name)] = round(p.value, 2)
        return state

    def _report_state(self):
        new = self._state()
        changes = ['%s: %s -> %s' % (k, self._snapshot.get(k), v)
                   for k, v in new.items() if self._snapshot.get(k) != v]
        self._snapshot = new
        if changes:
            self.emit('   == ' + ' | '.join(changes))

    def _print_full_state(self):
        s = self._state()
        self.emit('   tilstand: valgt=%s side=%s solo=%s spor=%d' % (s['valgt'], s['side'], s['solo'], len(self.song.tracks)))

    # ------------------------------------------------------------------

    def load(self):
        if self.harness:
            self.harness.disconnect()
            self._describe_out()
        self._mtimes = {f: os.path.getmtime(f) for f in SCRIPT_FILES}
        try:
            self.harness = Harness(self.song, self._send, lambda m: self.emit('   [statuslinje] ' + m))
            self.emit('Script lastet (%d spor, MIDI-kart: %d noter, %d CC)' % (
                len(self.song.tracks), len(self.harness.midi_map.notes), len(self.harness.midi_map.ccs)))
        except Exception as e:
            self.harness = None
            self.emit('FEIL ved lasting: %r' % e)
        self._snapshot = self._state() if self.harness else {}

    def _changed(self):
        return any(os.path.getmtime(f) != m for f, m in self._mtimes.items())

    def _run_commands(self):
        if not os.path.exists(CMD_FILE):
            return
        with open(CMD_FILE, encoding='utf-8') as f:
            lines = [l.strip() for l in f if l.strip()]
        os.remove(CMD_FILE)
        for line in lines:
            self.emit('>> ' + line)
            parts = line.split()
            cmd = parts[0]
            if cmd == 'sysex':
                self._send(tuple(int(b, 16) for b in parts[1:]))
                self._describe_out()
                continue
            arg = int(parts[1]) if len(parts) > 1 else None
            if cmd == 'select':
                self.song.view.selected_track = self.song.tracks[arg - 1]
            elif cmd == 'solo':
                track = self.song.tracks[arg - 1]
                track.solo = not track.solo
            elif cmd == 'add':
                self.song.create_track()
            elif cmd == 'del':
                self.song.delete_track(arg - 1)
            elif cmd == 'reload':
                self.load()
            elif cmd == 'state':
                self._print_full_state()
            self._after_event()

    def _after_event(self):
        if self.harness:
            self._report_state()
            self._describe_out()

    # ------------------------------------------------------------------

    def run(self):
        incoming = queue.Queue()
        self.inp.callback = incoming.put
        self.load()
        next_tick = time.time()
        try:
            while True:
                try:
                    msg = incoming.get(timeout=0.005)
                except queue.Empty:
                    msg = None
                if msg is not None and self.harness and msg.type not in ('clock', 'polytouch'):
                    raw = tuple(msg.bytes())
                    try:
                        delivered = self.harness.receive(raw)
                    except Exception as e:
                        self.emit('FEIL i receive_midi: %r' % e)
                        delivered = True
                    self.emit('-> %s%s' % (bs._describe(msg), '' if delivered else '  (filtrert bort av MIDI-kartet)'))
                    self._after_event()

                if time.time() >= next_tick:
                    next_tick += 0.1
                    if self.harness:
                        try:
                            self.harness.tick()
                        except Exception as e:
                            self.emit('FEIL i update_display: %r' % e)
                        self._after_event()
                    if self._changed():
                        self.emit('Endring i scriptet oppdaget, laster på nytt')
                        self.load()
                    self._run_commands()
        except KeyboardInterrupt:
            pass
        finally:
            if self.harness:
                self.harness.disconnect()
                self._describe_out()
            self.emit('Stoppet')


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--port', default='Arturia BeatStep')
    p.add_argument('--tracks', type=int, default=20)
    p.add_argument('--log')
    Sim(p.parse_args()).run()


if __name__ == '__main__':
    main()
