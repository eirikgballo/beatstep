# Overlevering — status 2026-10-08

Mac-feilen er funnet og rettet. Scriptet virker i Live 11.3.43 på Macen: oppsettet kommer fram, og pads, encodere,
solo og Rack-modus er bekreftet av brukeren på hardware.

## Hva som var galt

1. **BeatStepen mister sysex som kommer tettere enn ca. 1 ms.** Målt direkte fra Macen uten Live: 0 ms avstand
   mister 61–68 av 164, 2 ms eller mer mister ingen. Med 4 meldinger per tick fra Live kom bare 94 av 164 fram
   (alle kanal-meldinger manglet). Tall og målemetode står i `SIGNALS.md`.
   **Fiks:** `MIDI_MESSAGE_GAP = 0.003` i `BeatStep.py`, `time.sleep` mellom meldingene i `_flush_midi`.
   Etter omstart av Live: 164 av 164 riktige ved tilbakelesing (målt med 4 per tick).
2. **Valgt spor ble ikke rødt.** `TrackPads.py` sammenlignet spor med `is`. Byttet til `==`.
   Antatt årsak: Live gir et nytt Python-objekt for samme spor ved hvert oppslag. Brukeren bekreftet at det
   virker etter omstart, men selve antakelsen er ikke målt.
3. **Padden ble mørk en stund før den ble rød.** Firmwaren slukker padden ved slipp, og fargen ventet i køen
   bak ny maling av alle 16 pads (4 per tick). **Fiks:** fargen til en sluppet pad går forbi køen og sendes straks
   (`urgent` i `_queue_midi`), og `MIDI_MESSAGES_PER_TICK` er økt fra 4 til 16.
   Målt etter omstart: 164 av 164 riktige med 16 per tick. Brukeren merket bedring, men fortsatt en liten
   forsinkelse, særlig rett etter oppstart.
4. **Resten av forsinkelsen ligger i Live.** Live leverer pad-hendelser til scriptet median 40 ms sent, og slipp
   kom ofte senere enn trykk (se `SIGNALS.md`). Mulig årsak: ny maling av 16 pads blokkerte hovedtråden i ca. 50 ms.
   **Fiks:** `TrackPads` sender bare farger som er endret (`_shown`), unntatt etter oppsett, pad-slipp og
   knappeslipp, der firmwaren har malt over. Målt etter omstart: trykk median 8 ms, slipp median 18 ms (maks 32).
   Brukeren bekreftet at det ser bra ut.

## Nyttig måleverktøy (ikke i repoet ennå)

BeatStepen svarer på lesing av én parameter: `F0 00 20 6B 7F 42 01 00 <cmd> <hw> F7`. Hele oppsettet kan leses
tilbake og sammenlignes med det scriptet sender. Det ble gjort med et engangsscript. Bør inn i `tools/bs.py`
som egen kommando (`readback`).

## Gjenstår

- **Ikke testet i Live ennå:** Volum- og Sends-modus (bare at knappene sender riktig CC), sidevelger på ext sync,
  sequencer-varselet, følelsen i Volum/Sends (`KNOB_FEEL`).
- **`DEBUG_MIDI` er fortsatt på.** Den skriver «MIDI queue drained» i Log.txt hvert 0,3 s så lenge et spor står i solo.
- **`tools/bs.py` henger etter scriptet:** `setup` sender 140 meldinger (scriptet sender 164), `listen` kjenner ikke
  CC 28–33 (viser «ukjent»), og porten lukkes rett etter sending, som kan miste meldinger på Mac.
- **Falsk Live gir alltid samme sporobjekt**, så testene kunne ikke fange `is`-feilen. Vurder å la den gi nye
  objekter per oppslag.
- Flytte scriptet ut av Live-appen og de andre punktene i `Endringsønsker.md`.
