"""
scenario.py — kjør et fast scenario mot falsk Live og skriv all utgående MIDI og tilstand som tekst.

  python tools/scenario.py > logs/fasit.txt

Brukes til å sjekke at refaktorering ikke endrer oppførsel: samme scenario skal gi identisk output.
Klokka er falsk, så dobbelttrykk og encoder-akselerasjon blir deterministiske.
"""

import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fakelive'))

from harness import Harness  # noqa: E402
from fake_song import audio_effect_rack  # noqa: E402


class FakeClock:

    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def main():
    clock = FakeClock()
    time.monotonic = clock
    h = Harness()
    out = []

    def step(label, fn=None, dt=0.0):
        # Time passes before the action, with update_display ticking every 100 ms like in Live.
        # Messages sent while ticking belong to this step.
        start = len(h.sent)
        end = clock.now + dt
        while clock.now + 0.1 <= end:
            clock.now += 0.1
            h.tick()
        clock.now = end
        if fn:
            fn()
        sent = ' '.join(''.join('%02X' % b for b in m[8:11]) for m in h.sent[start:])
        sel = h.song.view.selected_track
        racks = [d for d in sel.devices if d.class_name == 'AudioEffectGroupDevice']
        macros = '%.4f/%.4f' % (racks[0].parameters[1].value, racks[0].parameters[16].value) if racks else '-'
        state = 'valgt=%s solo=%s vol=%.4f makro1/16=%s' % (
            sel.name, ','.join(t.name for t in h.song.tracks if t.solo) or '-', sel.mixer_device.volume.value, macros)
        out.append('%-28s %s | %s' % (label, state, sent))

    def ticks(seconds):
        for _ in range(int(round(seconds / 0.1))):
            clock.now += 0.1
            h.tick()

    step('oppstart', lambda: ticks(2.2))
    step('pad 3 trykk', lambda: h.receive((0x99, 46, 127)), 1.0)
    step('pad 3 slipp', lambda: h.receive((0x89, 46, 0)), 0.05)
    step('pad 6 trykk', lambda: h.receive((0x99, 49, 127)), 1.0)
    step('pad 6 slipp', lambda: h.receive((0x89, 49, 0)), 0.05)
    step('shift trykk', lambda: h.receive((0xB9, 7, 127)), 0.5)
    step('shift+pad 6 (solo, valgt)', lambda: h.receive((0x99, 49, 127)), 0.1)
    step('pad 6 slipp', lambda: h.receive((0x89, 49, 0)), 0.05)
    step('shift+pad 8 (solo, ikke valgt)', lambda: h.receive((0x99, 51, 127)), 0.3)
    step('pad 8 slipp', lambda: h.receive((0x89, 51, 0)), 0.05)
    step('shift+pad 8 (solo av)', lambda: h.receive((0x99, 51, 127)), 0.3)
    step('pad 8 slipp', lambda: h.receive((0x89, 51, 0)), 0.05)
    step('shift slipp', lambda: h.receive((0xB9, 7, 0)), 0.1)
    step('blink 1 s', lambda: ticks(1.0))
    step('pad 1 trykk', lambda: h.receive((0x99, 44, 127)), 1.0)
    step('pad 1 slipp', lambda: h.receive((0x89, 44, 0)), 0.05)
    for i, dt in enumerate([5.0, 0.5, 0.2, 0.1, 0.05, 0.02, 0.01]):
        step('enc 1 +1 dt=%s' % dt, lambda: h.receive((0xB9, 10, 1)), dt)
    step('enc 1 +12', lambda: h.receive((0xB9, 10, 12)), 0.003)
    step('enc 1 -1', lambda: h.receive((0xB9, 10, 127)), 0.5)
    step('enc 16 +1', lambda: h.receive((0xB9, 25, 1)), 0.5)
    step('transpose +1', lambda: h.receive((0xB9, 27, 1)), 0.5)
    step('transpose -1', lambda: h.receive((0xB9, 27, 127)), 0.05)
    step('pad 5 trykk (ingen rack)', lambda: h.receive((0x99, 48, 127)), 1.0)
    step('enc 1 uten rack', lambda: h.receive((0xB9, 10, 1)), 0.5)
    step('legg til rack', lambda: h.song.tracks[4].devices.append(audio_effect_rack('Ny')))
    step('enc 1 med nytt rack', lambda: h.receive((0xB9, 10, 1)), 0.5)
    step('pad 16 trykk (Spor 16)', lambda: h.receive((0x99, 43, 127)), 1.0)
    step('pad 16 slipp', lambda: h.receive((0x89, 43, 0)), 0.05)
    step('shift trykk', lambda: h.receive((0xB9, 7, 127)), 1.0)
    step('shift+transpose (master)', lambda: h.receive((0xB9, 27, 1)), 0.5)
    step('shift slipp', lambda: h.receive((0xB9, 7, 0)), 0.1)
    step('ext sync trykk (velger)', lambda: h.receive((0xB9, 31, 127)), 0.5)
    step('ext sync slipp', lambda: h.receive((0xB9, 31, 0)), 0.1)
    step('pad 3 (tom side)', lambda: h.receive((0x99, 46, 127)), 0.1)
    step('pad 3 slipp', lambda: h.receive((0x89, 46, 0)), 0.05)
    step('pad 2 (side 2)', lambda: h.receive((0x99, 45, 127)), 0.1)
    step('pad 2 slipp', lambda: h.receive((0x89, 45, 0)), 0.05)
    step('ext sync trykk (velger)', lambda: h.receive((0xB9, 31, 127)), 0.5)
    step('ext sync trykk (avbryt)', lambda: h.receive((0xB9, 31, 127)), 0.5)
    step('pad 1 trykk (Spor 17)', lambda: h.receive((0x99, 44, 127)), 1.0)
    step('pad 1 slipp', lambda: h.receive((0x89, 44, 0)), 0.05)
    step('recall trykk (Volum, tidlig)', lambda: h.receive((0xB9, 5, 127)), 0.1)
    step('3 s uten noe', lambda: ticks(3.0))
    step('cntrl trykk (seq-modus)', lambda: h.receive((0xB9, 30, 127)), 0.5)
    step('cntrl slipp', lambda: h.receive((0xB9, 30, 0)), 0.1)
    step('velg spor 3 i Live (seq)', lambda: setattr(h.song.view, 'selected_track', h.song.tracks[2]), 0.5)
    step('cntrl trykk (kontroll)', lambda: h.receive((0xB9, 30, 127)), 0.5)
    step('cntrl slipp', lambda: h.receive((0xB9, 30, 0)), 0.1)
    step('kanal 1-note', lambda: h.receive((0x90, 40, 64)), 0.1)
    step('recall trykk (Volum)', lambda: h.receive((0xB9, 5, 127)), 0.5)
    step('recall slipp', lambda: h.receive((0xB9, 5, 0)), 0.1)
    step('enc 2 +1 (Spor 18 volum)', lambda: h.receive((0xB9, 11, 1)), 0.5)
    step('enc 16 +1 (Spor 32 finnes ikke)', lambda: h.receive((0xB9, 25, 1)), 0.5)
    step('store trykk (Record)', lambda: h.receive((0xB9, 32, 127)), 0.5)
    step('store slipp', lambda: h.receive((0xB9, 32, 0)), 0.1)
    step('enc 1 +1 (makro 1)', lambda: h.receive((0xB9, 10, 1)), 0.5)
    step('enc 9 +1 (makro 9)', lambda: h.receive((0xB9, 18, 1)), 0.5)
    step('chan trykk (Rack)', lambda: h.receive((0xB9, 33, 127)), 0.5)
    step('chan slipp', lambda: h.receive((0xB9, 33, 0)), 0.1)
    step('legg til spor', lambda: h.song.create_track(), 0.1)
    step('slett spor 2', lambda: h.song.delete_track(1), 0.1)
    step('solo spor 18 fra Live', lambda: setattr(h.song.tracks[16], 'solo', True), 0.1)
    step('disconnect', h.disconnect, 0.1)

    for name in ('Spor 1', 'Spor 5'):
        track = [t for t in h.song.tracks if t.name == name][0]
        out.append('%s volum=%.4f makro1=%.4f' % (name, track.mixer_device.volume.value,
                                                  track.devices[0].parameters[1].value if track.devices else -1))
    out.append('Master volum=%.4f' % h.song.master_track.mixer_device.volume.value)
    for name in ('Spor 9', 'Spor 18'):
        track = [t for t in h.song.tracks if t.name == name][0]
        out.append('%s volum=%.4f sends=%s' % (name, track.mixer_device.volume.value,
                                                ['%.4f' % s.value for s in track.mixer_device.sends]))
    out.append('meldinger: %s' % h.messages)
    print('\n'.join(out))


if __name__ == '__main__':
    main()
