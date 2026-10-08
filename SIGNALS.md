# BeatStep: målte signaler

Fasit målt direkte mot hardware fra Windows med `tools/bs.py` (mido/rtmidi, uten Ableton).
Står noe her i strid med `DESIGN.md`, er det denne fila som gjelder.

## Pad-LED (sysex `F0 00 20 6B 7F 42 02 00 10 <hw> <farge> F7`)

| hw | Fysisk pad |
|----|------------|
| 0x70–0x77 | Øverste rad, pad 1–8 fra venstre |
| 0x78–0x7F | Nederste rad, pad 9–16 fra venstre (antatt, ikke målt enkeltvis) |

Rekkefølgen er radvis. `DESIGN.md` sin påstand om kolonnevis rekkefølge (0x70–0x73 = pad 1, 5, 9, 13) er feil.

Farger bekreftet: 0 = av, 1 = rød, 16 = blå, 17 = magenta.

**Firmwaren slukker en pad når den slippes**, og overskriver fargen scriptet sendte mens padden var nede.
Fargen må sendes på nytt ved note off.

## Knappe-LED (samme sysex, cmd 0x10)

| hw | Knapp | Lys |
|----|-------|-----|
| 0x58 | play | Hvit, av/på (1 og 127 gir begge hvit) |
| 0x59 | stop | Ingen lys |
| 0x5A | cntrl/seq | Som pads: 1 = rød, 16 = blå, 17/127 = magenta |
| 0x5B | ext sync | Blå, av/på |
| 0x5C | recall | Blå, av/på (1, 17 og 127 gir alle blå) |
| 0x5D | store | Rød, av/på |
| 0x5E | shift | Blå, av/på |
| 0x5F | chan | Blå, av/på |

Verdi 0 slukker alle. Cntrl/seq lyser rødt fra firmware ved oppstart, men kan overstyres.

## Knapper som CC (oppsett: mode 8, CH10, behaviour 1, CC via cmd 0x03)

Alle knappene kan programmeres til å sende CC (127 ved trykk, 0 ved slipp). Målt med CC 28–33:
play 28, stop 29, cntrl/seq 30, ext sync 31, store 32, chan 33. Recall (CC 5) og shift (CC 7) som før.

**Firmwaren beholder sin egen funksjon i tillegg til CC-en:**

| Knapp | Firmware-funksjon | Pads mens knappen holdes | Etter slipp |
|-------|-------------------|--------------------------|-------------|
| play | Starter sequencer: MIDI Start `FA` + sekvensnoter CH1 | Uendret | |
| stop | MIDI Stop `FC` | Uendret | |
| cntrl/seq | Bytter til sequencer-modus, pads slukker og blir værende slik | | Må trykkes igjen for å komme tilbake |
| ext sync | Slår ekstern synk av/på, bare lyset endres | Uendret | |
| store | Store + pad lagrer preset | Alle av, pad 1 blinker rødt (aktiv preset) | Firmwarens farger (alle blå) |
| recall | Recall + pad laster preset | Alle av, pad 1 blinker rødt | Firmwarens farger (alle blå) |
| chan | Chan + pad bytter global MIDI-kanal | Alle av, pad 10 blå (kanal 10) | Firmwarens farger (alle blå) |
| shift | Shift-funksjoner i firmware | Pad 1, 9 og 13 blå, resten av | Firmwarens farger (alle blå) |

Etter et overlegg setter firmwaren tilbake **sine** pad-farger, ikke scriptets. Scriptet må male alle pads
på nytt når store, recall, chan, shift eller cntrl/seq slippes.

## Stop holdt inne (målt 2026-10-08 på Mac, med scriptet i Live)

- Trykk: MIDI Stop `FC`, så CC 29 = 127 på CH10. Slipp: CC 29 = 0.
- Padene sender vanlige noter på CH10 mens stop holdes (pad 1 og 2 målt).
- **Nesten alle pads ble mørke da stop ble trykket** (brukerens observasjon, hvilke som ble stående er ikke notert).
  Det strider mot tabellen over, som sier «Uendret» for stop fra Windows-målingen. Ikke avklart hvorfor.
  Scriptet maler derfor alle pads på nytt rett etter stop-trykket, ikke bare etter slipp.

## Chan holdt inne (målt 2026-10-08 på Mac, med scriptet i Live)

- Trykk: CC 33 = 127 på CH10. Slipp: CC 33 = 0.
- **Pad trykket mens chan holdes sender ingenting** (pad 3 trykket, ingen note). Firmwaren bruker trykket til å
  bytte global MIDI-kanal. Chan + pad kan derfor ikke brukes av scriptet.
- Encoder vridd mens chan holdes sender vanlig CC på CH10 (encoder 1, CC 10).
- Etter chan + pad 3 sender pads og encodere fortsatt på CH10 (pad 5 og encoder 2 målt), siden scriptet setter
  kanalen fast på hver kontroll.

## Live: transport fra scriptet (observert av brukeren 2026-10-08)

Live holder tre posisjoner fra hverandre når låta står stille:

- Låta stoppes, `song.jump_by()` flytter posisjonen, så `song.continue_playing()`:
  Live spiller fra der låta ble stoppet, ikke fra den nye posisjonen.
- Samme, men med `song.start_playing()` i stedet: Live spiller fra den nye posisjonen (bekreftet).
- Spill fra A, scrub til B mens låta spiller, stopp. `song.jump_by()` i stillstand flytter da nåla tilbake til A
  og regner derfra. `jump_by()` i stillstand går altså ut fra der avspillingen ble startet, ikke der nåla står.
- Scriptet setter derfor `song.current_song_time` direkte når det scrubbes i stillstand. Da regnes det fra der
  nåla står (B), og `start_playing()` spiller fra den nye posisjonen (bekreftet av brukeren).

## Burst og timing

- 16 LED-meldinger sendt uten pause: alle 16 tenner.
- Fullt oppsett (122 sysex, pads satt fra CC-modus til note-modus) etterfulgt av 16 LED-meldinger uten pause: alle tenner med riktig farge.

Dette gjelder fra Windows, der WinMM sender én sysex om gangen med blokkerende kall. På Mac går det tapt
meldinger når de sendes helt tett, se neste avsnitt.

## Tett sysex går tapt på Mac (målt 2026-10-08, direkte mot BeatStep med mido, uten Live imellom)

BeatStepen svarer på lesing av én parameter: `F0 00 20 6B 7F 42 01 00 <cmd> <hw> F7` gir
`F0 00 20 6B 7F 42 02 00 <cmd> <hw> <verdi> F7`. Slik kan hele oppsettet leses tilbake og sammenlignes.

Måling: alle kanal-, behaviour- og nummer-verdier satt til en kjent feil verdi (50 ms mellom hver, kontrollert
med tilbakelesing), så hele oppsettet (164 sysex) sendt med fast avstand, og lest tilbake.

| Avstand mellom meldinger | Tapt av 164 |
|--------------------------|-------------|
| 0 ms | 61, 68 |
| 0,25 ms | 71 |
| 0,5 ms | 4, 1 |
| 0,75 ms | 0 |
| 1 ms | 0, 0, 1, 0 |
| 2 ms | 0, 0 |
| 5, 10, 20 ms | 0 |

- Tapet skjer altså uten Live. Det er avstanden mellom meldingene som avgjør, ikke hvem som sender.
  Om det er CoreMIDI/USB eller firmwaren som mister dem er ikke skilt.
- Live kjørte under målingen og sendte solo-blink (én LED-sysex per 0,3 s). Det ene tapet ved 1 ms kan være
  en kollisjon med den. Trygg avstand: 2 ms eller mer.
- Enkeltmeldinger med 300 ms mellomrom slår alltid inn (7 av 7 parametre målt).

**Live-scriptet med 4 meldinger per tick (commit 3fb1293):** tilbakelesing etter at køen var tømt viste 94 av 164
riktige. Alle 41 kanal-meldinger manglet, behaviour manglet på alle encodere og knapper, nummer manglet på
6 av 8 knapper. Scriptet sender mode, kanal, behaviour, nummer for én kontroll i samme tick, så meldinger
midt i en tick går tapt. Padene sendte likevel på CH10 fordi kanal sto på 65 (følg global) og global kanal er 10.
Shift og recall sendte på CH1 uten slipp-melding, encoder 1 sendte 65 i stedet for 1 (relative mode 1).

**Med 3 ms pause mellom meldingene i en tick (`MIDI_MESSAGE_GAP`, `time.sleep` i `_flush_midi`):** BeatStepen
fikk først en kjent feil grunntilstand, så ble Live startet på nytt. Tilbakelesing ga 164 av 164 riktige
(tre lesinger, hver med 1–2 spørringer uten svar, ulike hver gang, ingen feil verdier). Live sender altså hver
melding straks `_send_midi` kalles, og pausen i scriptet når helt fram til BeatStepen.

Spørringer uten svar: når Live sender solo-blink samtidig, forsvinner av og til en spørring. Les flere ganger
og se på verdiene, ikke på manglende svar.

**Med 16 meldinger per tick og 3 ms pause:** 164 av 164 riktige etter omstart av Live (to lesinger).

## Forsinkelse fra pad til script i Live (målt 2026-10-08)

Samme 25 pad-trykk sett av `bs.py listen` og av scriptet (`IN`-linjer i Log.txt), sammenlignet relativt til den
raskeste hendelsen. Live leverte hendelsene median 40 ms senere, for det meste 5–90 ms.
5 av de første 12 trykkene etter oppstart av Live kom 280–430 ms sent (årsak ikke målt).
Senere i rekka kom trykk etter 10–25 ms, men slipp ofte etter 70–90 ms. Mulig årsak: valg av spor la 16 LED-meldinger
i kø, og neste tick blokkerte Lives hovedtråd i ca. 50 ms mens de ble sendt.

Etter at scriptet bare sender farger som er endret (ny omstart, 25 nye trykk, samme metode):
trykk median 8 ms (maks 19), slipp median 18 ms (maks 32). Ingen trykk over 32 ms, heller ikke rett etter oppstart.

Felle på Mac: `bs.py` åpner porten, sender og lukker straks. Da kan meldinger gå tapt i lukkingen
(5 spørringer på rad ga 0 svar). Hold porten åpen en stund etter sending når noe skal måles.

## Innkommende fra pads

- Trykk: note on på CH10 (`99 <note> <vel>`). Pad 1 = note 44.
- Slipp: ekte note off (`89 <note> 00`), ikke note on med velocity 0.
- Mens padden holdes inne: strøm av polyfonisk aftertouch (`A9 <note> <trykk>`), rundt 20 meldinger per trykk.

Alle 16 pads målt: øverste rad note 44–51, nederste rad note 36–43, venstre til høyre. Stemmer med `PAD_MSG_IDS`.

## Funksjonsknapper

| Knapp | Sender |
|-------|--------|
| shift | CC 7 på CH10, 127 ved trykk og 0 ved slipp |
| recall | CC 5 på CH10, 127 ved trykk og 0 ved slipp |
| shift+recall | shift 127, recall 127, recall 0, shift 0 (vanlig rekkefølge, ingen egen melding) |
| cntrl/seq, chan, store | Ingenting. Håndteres internt i firmware |
| play | Starter den interne sequenceren (se under) |
| stop | MMC Stop `F0 7F 7F 06 01 F7`, MIDI Stop `FC`, note off på siste sekvensnote |

## Sequencer (play)

Play sender MMC Play `F0 7F 7F 06 02 F7`, MIDI Start `FA`, MIDI clock `F8` (24 per taktslag)
og sekvensnotene på **CH1** (målt: note 60, vel 64).

Konsekvens for scriptet: `receive_midi` godtar note on på alle kanaler, og `build_midi_map`
videresender pad-notene på CH1. Sekvensnoter i området 36–51 vil da tolkes som pad-trykk.

## Encodere (relative mode 2, slik `setup` konfigurerer dem)

- Encoder 1 sender CC 10 på CH10, transpose sender CC 27 på CH10.
- Encoder N sender CC 9+N (encoder 8 = CC 17, målt).
- Med klokka: verdi 1. Mot klokka: verdi 127. Normalt ±1 per hakk, også ved rask vridning.
- Rask vridning gir hakk med 8–25 ms mellomrom, sakte vridning rundt 0,6–0,9 s.
- **Hardware-akselerasjon:** ved svært rask vridning (meldinger med cirka 3 ms mellomrom) hopper verdien til 12 (delta +12).

`CMix._encoder_delta` bruker bare retningen og tiden mellom hakk, og kaster bort størrelsen.
Enten bør størrelsen brukes, eller så slås hardware-akselerasjonen av via sysex.

## Sequencer-modus (etter cntrl/seq)

- **Padene sender ingen noter.** Encoderne redigerer sekvensens steg og sender noter på CH1 i stedet for CC.
- BeatStepen blir stående i sequencer-modus til cntrl/seq trykkes igjen. Det finnes ingen melding som forteller hvilken modus den står i.
- Pad-LED kan fortsatt styres med sysex (målt: alle 16 blinket rødt).
- Play starter sekvensen og bruker padene som stegindikator.

**Felle under testing:** tester gjort mens BeatStepen sto i sequencer-modus ser ut som «firmwaren sluker trykket».
Sjekk alltid modus før en kombinasjon konkluderes med å ikke virke.

## Kombinasjoner i kontrollmodus

| Kombinasjon | Sendes |
|-------------|--------|
| shift + pad | Pad-noten (og firmwaren endrer en sequencer-innstilling i bakgrunnen) |
| shift + encoder | Encoder-CC |
| shift + transpose | Transpose-CC |

## Annet

- CNTRL/SEQ-knappen lyser rødt uavhengig av scriptet (modusindikator i firmware).
