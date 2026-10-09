# Overlevering — status 2026-10-09 (kveld)

Scriptet virker i Live 11.3.43 på Macen. 2026-10-09 ble Sends-modus byttet ut med Record-modus (opptak, undo,
redo, metronom, markør, loop, zoom og panorering), sporvalg i Rack-modus armer sporet, og `Innstillinger.py`
fikk `STARTSPOR`, `SCRUB_SNAP`, `PAN_STEG` og `SHIFT_TRYKK`. Panoreringen går gjennom et hjelpeprogram utenfor
Live (`tools/scrollhjelper`, bare Mac). Denne Macen manglet GitHub-innlogging for git 2026-10-08, så sjekk
`git status -sb` for å se om alt er pushet.

## Grepene slik de er nå

| Grep | Gjør |
|---|---|
| pad | Velg spor. I Rack-modus armes sporet også (og de andre mister armingen) |
| shift + pad | Solo av/på uten å velge sporet |
| shift + encoder | Nullstill parameteren til standardverdi (makro, volum, send) |
| shift + transpose-hjulet | Nullstill volumet på valgt spor. Master-volum har ingen kontroll lenger |
| kort trykk på shift alene | Bytt mellom Session og Arrangement (som Tab). Holdt lenger enn `SHIFT_TRYKK` (0,4 s, i `Innstillinger.py`) eller brukt til noe: ingenting |
| ext sync | Sidevelger (16 spor per side) |
| chan / recall / store | Rack-, Volum- og Record-modus |
| Record-modus: pad 1–8 | Opptak av/på (arrangement), undo, redo, metronom, markør på nåla (lag/fjern), loop av/på, sett loopstart, sett loopslutt. Encoderne styrer makroene |
| Record-modus: pad 9 / 10 | Zoom inn / ut i arrangementet (bekreftet i Live) |
| Record-modus: pad 11–14 | Panorer arrangementet venstre / høyre / opp / ned. Krever scrollhjelperen (`tools/scrollhjelper`, bare Mac, må bygges med `swiftc`, ha Tilgjengelighet-tilgang). Scriptet starter den selv sammen med Live, og da må **Live** ha Tilgjengelighet-tilgang (og startes på nytt etter at den er gitt). Bekreftet i Live |
| (forutsetning) | Lives «Start Transport With Record» må være Off, ellers starter pad 1 avspilling |
| Record-modus: shift + pad | Velg og arm spor (padene viser sporene mens shift holdes). Ingen solo her |
| chan en gang til i Rack-modus | Variasjonsvelger: pad N henter makro-variasjon N (rød = valgt, magenta = finnes). Chan lukker |
| stop alene | Stopp, eller start avspilling (fra stoppunktet, eller fra dit det er scrubbet) |
| stop + pad 1–15 | Spill fra markør N (blå pads mens stop holdes) |
| stop + pad 16 | Spill fra loopstart (magenta pad) |
| stop + transpose-hjulet | Scrub i tidslinja |

Følsomheten justeres i `Innstillinger.py`: to tall 1–10 (rolig, rask) per modus og `KAST` (hvor fort man må spinne
for fullt steg). Fila leses på nytt mens Live kjører. Brukerens verdier nå: `RACK = (4, 8)`, `KAST = 5`.
`STARTSPOR` i samme fil er sporet som havner på pad 1 (brukeren har 3: de to øverste sporene hoppes over).
`SCRUB_SNAP` er rutenettet for scrubbing i slag (brukeren har 0.25: ett hakk = en sekstendel, 0 = fri).
Lives eget rutenett og «Snap to Grid» finnes ikke i API-et, så scriptet kan ikke følge dem.

## Det viktigste som ble funnet (detaljer og tall i `SIGNALS.md`)

- **BeatStepen mister sysex som kommer tettere enn ca. 1 ms.** Scriptet venter 3 ms mellom meldingene og sender
  opptil 16 per tick. Tilbakelesing fra BeatStepen viste 164 av 164 innstillinger riktige.
- **BeatStepen kan leses tilbake:** `F0 00 20 6B 7F 42 01 00 <cmd> <hw> F7` gir verdien til én innstilling.
- **Pad-lys:** firmwaren slukker padden ved slipp. Fargen sendes straks ved slipp, og bare endrede farger sendes
  ellers, så Lives hovedtråd ikke blokkeres. Levering fra pad til script: median 8 ms trykk, 18 ms slipp.
- **Chan + pad sender ingenting** (firmwaren bytter global MIDI-kanal). Chan + encoder sender som normalt.
  Stop + pad og shift + pad sender noter.
- **Encoder-fart:** vanlig vridning er 10–40 hakk/s, raskt spinn 70–900. Tid mellom to enkelthakk var for urolig,
  så farten måles nå som antall hakk siste 0,1 s.
- **Transport i Live:** `continue_playing()` går alltid tilbake til stoppunktet. `jump_by()` i stillstand regner
  fra startmarkøren, ikke nåla. Live utfører flytting etter at scriptet har returnert, så posisjonen kan ikke
  leses tilbake i samme kall. Scriptet holder selv rede på posisjonen under scrubbing i stillstand, setter
  `current_song_time`, starter med `start_playing()` og sjekker de første tickene at avspillingen havnet riktig.

## Ikke bekreftet i Live

- Stop + pad 16 (loopstart) fra stillstand. Bruker samme metode som scrubbing, som er bekreftet.
- Shift + transpose-hjulet nullstiller volumet på valgt spor.
- Volum-modus er lite prøvd (nullstilling og følsomhet der er bare testet i pytest).
- Record-modus og arming ved sporvalg (lagt til 2026-10-09, bare testet i pytest). Se notatene i `Endringsønsker.md`.
- Sidevelgeren og sequencer-varselet er ikke prøvd på Macen.

## Uforklart

- Etter scrubbing med `jump_by()` startet `start_playing()` tre ganger fra den grønne startmarkøren i vanlig bruk,
  mens samme kombinasjon traff i det automatiske forsøket. Dagens løsning bruker ikke `jump_by()` i stillstand og
  har en sjekk som retter opp, så dette er ikke et problem nå, men årsaken er ikke funnet.
- Nesten alle pads ble mørke da stop ble trykket. Windows-målingen sa «uendret». Scriptet maler alle pads på nytt
  etter stop-trykket uansett.

## Gjenstår (se også `Endringsønsker.md`)

- **Push** (brukeren, fra egen terminal).
- **Flytte scriptet ut av Live-appen** til `~/Music/Ableton/User Library/Remote Scripts/`. Klar til å gjøres.
  Husk at `Innstillinger.py`, `.venv` og `logs/` følger mappa.
- **`tools/bs.py` henger etter scriptet:** `setup` sender 140 meldinger (scriptet sender 164), `listen` kjenner
  ikke CC 28–33 (viser «ukjent»), og porten lukkes rett etter sending, som kan miste meldinger på Mac.
  Tilbakelesing (`readback`) og gap-testen ble gjort med engangsscript og bør inn som kommandoer i `bs.py`.
- **Falsk Live gir alltid samme sporobjekt**, så testene kunne ikke fange `is`-feilen på valgt spor.
- **Master-volum** har ingen kontroll. Forslag som ikke er målt: chan + transpose-hjulet.
- Åpne ønsker: følelsen i Volum (kan nå prøves i `Innstillinger.py`), filtrere enkelthakk i motsatt retning.
- Vise/skjule variasjonsvisningen i Live er ikke mulig: API-et har ingen egenskap for det.

## Praktisk for neste økt

- Live laster koden bare ved oppstart. Unntak: `Innstillinger.py` leses på nytt innen et sekund.
- `.venv` finnes i prosjektmappa på Macen. `.venv/bin/python -m pytest tests` kjører 169 tester uten hardware.
- `bs.py listen --log logs/x.log` kan kjøre samtidig med Live og er den raskeste måten å se hva BeatStepen sender.
- `DEBUG_MIDI` og `DEBUG_TRANSPORT` i `BeatStep.py` er av. Slå på for å logge til Lives Log.txt
  (innkommende MIDI, og hvor avspilling starter etter scrubbing).
- Live-oppførsel som ikke kan testes uten Live: lag et lite automatisk forsøk som logger hva Live svarer, i stedet
  for å gjette. Det løste transporten etter tre feilslåtte rettelser.
