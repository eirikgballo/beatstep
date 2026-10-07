# Overlevering — status 2026-10-07

Arbeidet så langt ble gjort på en Windows-PC uten Ableton, med BeatStepen på USB. Der virker alt.
I Live på Macen virker det ikke. Neste økt kjører på Macen for å måle direkte der feilen skjer.

## Hva som er gjort (alt testet på hardware fra Windows)

- Testoppsett: `tools/bs.py` (sniffer/sender), `tools/sim.py` (scriptet mot ekte BeatStep og falsk Live),
  `tests/` (75 pytest-tester), `tools/scenario.py` (regresjonssjekk ved refaktorering).
- Feil rettet: pad mistet farge ved slipp (firmware slukker den), sequencer-noter på CH1 valgte spor,
  rack-cache ble utdatert, oppsett på nytt ved hvert recall-trykk, encoder-akselerasjon.
- Nytt: Rack/Volum/Sends-modus (chan/recall/store), 16 spor per side, sidevelger på ext sync,
  solo med shift + pad, solo-blink, varsel for sequencer-modus, ny maling etter knappeslipp.
- Filstruktur: `BeatStep.py`, `TrackPads.py`, `Encoders.py`, `RackMode.py`, `VolumeMode.py`, `SendsMode.py`, `Sysex.py`.

## Problemet på Macen

Live 11.3.43, scriptet laster uten feil (`(BeatStep) Initializing...`, ingen Traceback i Log.txt).

1. Første forsøk (alt sendt i én byge, 164 oppsett-sysex + 23 LED):
   `_send_midi` returnerte `True` for alle. LED-ene ble tilfeldig spredt (pad 1, 2, 5, 10, 11, 12, 14 lyste).
   Ingen `IN`-linjer i Log.txt da brukeren trykket pads og vred encoder (DEBUG_MIDI var på).
2. Andre forsøk (kø i `BeatStep._flush_midi`, maks 4 meldinger per 100 ms-tick, commit 3fb1293):
   Fortsatt feil. Pad 1 blinket magenta, 2 og 3 magenta, 7 rød, tilfeldige blå. Pad 13 ble blå ved trykk
   (ikke rød). Shift + pad så ut som vanlig BeatStep. Log.txt fra denne runden er ikke lest ennå.

## Hypoteser (ingen er bevist)

**H1 (mest sannsynlig): BeatStepen dropper sysex som kommer for tett.** På Windows sender WinMM én
sysex om gangen med blokkerende kall, altså naturlig pause, og alt kom fram selv med `--gap 0`.
CoreMIDI på Mac kan pakke mange sysex i samme USB-overføring. Den eldste notatet i prosjektet sa at
«BeatStep dropper LED-sysex når for mange kommer tett, bare ~4 kommer fram». Køen sender fortsatt 4 i
samme tick, altså tett.

**H2: Live dropper eller slår sammen utgående MIDI.** Ikke skilt fra H1 ennå.

**H3: BeatStepen på Macen står i en annen tilstand** (sequencer-modus, annen preset). Ingen IN-linjer kan
også bety at padene ikke sender på CH10 fordi oppsettet aldri kom fram (følge av H1/H2).

## Måleplan på Macen (gjør i rekkefølge)

1. Les siste del av Log.txt: `grep "BeatStep:" ~/Library/Preferences/Ableton/Live*/Log.txt | tail -40`.
   Kom det `IN`-linjer i andre forsøk? På hvilken kanal (99 = note CH10, 90 = note CH1)?
2. **Uten Live:** `bs.py listen` i bakgrunnen, trykk pads. Hvilken kanal og hvilke noter sender BeatStepen nå?
3. **Uten Live:** `bs.py clear`, så `bs.py led 1 2 ... 16 --color red` med `--gap 0`, `--gap 2`, `--gap 5`, `--gap 20`.
   Brukeren teller hvor mange som lyser. Bekrefter eller avkrefter H1 og gir minste trygge avstand.
4. **Uten Live:** `bs.py setup` med samme gap-verdier, så `listen` og trykk pads: kom oppsettet fram (CH10, note 44 på pad 1)?
5. **Med Live kjørende:** `bs.py listen` samtidig (CoreMIDI deler porten). Se hva BeatStepen sender etter at
   scriptet har startet. Skiller H1/H2 fra H3.

## Mulige fikser avhengig av funn

- H1: Live kan ikke vente mellom meldinger innenfor en tick. `update_display` går hvert 100 ms, så
  1 melding per tick gir ~19 s for fullt oppsett. Alternativer å vurdere: sende oppsettet bare når det
  trengs (konfigurasjonen blir i BeatStepen til strømmen går), slå sammen/redusere meldinger, eller
  undersøke om Live har raskere planlegging (`schedule_message`, egne timere).
- H2: samme kø, men finn grensen Live tåler.
- `MIDI_MESSAGES_PER_TICK` i `BeatStep.py` kan endres direkte på Macen for raske forsøk (restart Live).

## Opprydding når feilen er løst

- Slå av `DEBUG_MIDI` i `BeatStep.py` (eller fjern loggingen).
- Vurder å flytte scriptet fra Live-appen til `~/Music/Ableton/User Library/Remote Scripts/`
  (filer inne i appen kan forsvinne ved Live-oppdatering).
- Følelsen i Volum/Sends (`KNOB_FEEL`) er ikke vurdert i Live ennå.
