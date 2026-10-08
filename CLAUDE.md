# BeatStep_Q — instrukser for Claude

MIDI Remote Script for Arturia BeatStep i Ableton Live 11 (Python 3.7). Hobbyprosjekt.

## Kommunikasjon og git

- Norsk i all kommunikasjon og alle commits. Bruk æøå, aldri ae/oe/aa.
- Ikke overbruk tankestrek. Bruk punktum, komma, kolon eller parentes.
- Spør før commit og push: vis filer og commit-melding, vent på ja.
- Ingen Claude-attribusjon i commits (ingen Co-Authored-By, ingen footer).
- Branch: `first-refactoring`. Remote: github.com/eirikgballo/beatstep.
- Korte kodekommentarer (maks to–tre linjer) om hvorfor, ikke hva.
- Ikke kjør script mot hardware eller Live uoppfordret når brukeren bare ber om endringer. Spør først.

## Les først

1. `handoff/HANDOFF.md`: status og neste steg.
2. `SIGNALS.md`: målt hardware-oppførsel. Fasit når den er i strid med DESIGN.md.
3. `DESIGN.md`: spec. Koden skal følge den.
4. `Endringsønsker.md`: brukerens ønsker. Nye ønsker registreres der med malen, og flyttes til «Gjennomført» når de er gjort.

## Arbeidsmåte

Hypotese → mål direkte mot hardware → skriv funnet i SIGNALS.md → test i pytest → fiks.
Ikke konkluder uten måling. Én ting om gangen, og la brukeren bekrefte det som vises på BeatStepen.

Interaktiv testing: jeg sender noe (f.eks. LED-farger), brukeren sier hva som skjedde, jeg leser
`tools/bs.py listen`-loggen for det BeatStepen sender. Gjentas til oppførselen er kartlagt.

Felle: står BeatStepen i sequencer-modus (etter cntrl/seq), sender padene ingenting. Sjekk modus før
en kombinasjon konkluderes med å ikke virke.

## Kommandoer

```
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest tests                 # 75 tester, ingen hardware
.venv/bin/python tools/bs.py ports               # MIDI-porter
.venv/bin/python tools/bs.py listen --log logs/x.log   # logg alt BeatStepen sender
.venv/bin/python tools/bs.py --gap 5 led 1 2 3 --color red
.venv/bin/python tools/sim.py --log logs/sim.log # scriptet mot ekte BeatStep + falsk Live
```

`tools/sim.py` åpner både inn- og utport. På Mac (CoreMIDI) kan flere programmer dele porter,
så `bs.py listen` kan kjøre samtidig med Live.

## Stier på Macen

- Scriptet: `/Applications/Ableton Live 11 Suite.app/Contents/App-Resources/MIDI Remote Scripts/Beatstep_Q`
  (mappenavnet er det Live viser som Control Surface). Live laster koden bare ved oppstart.
- Live-logg: `~/Library/Preferences/Ableton/Live 11.3.43/Log.txt`. Scriptets linjer starter med `(BeatStep) BeatStep:`.
