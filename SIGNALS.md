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

## Burst og timing

- 16 LED-meldinger sendt uten pause: alle 16 tenner.
- Fullt oppsett (122 sysex, pads satt fra CC-modus til note-modus) etterfulgt av 16 LED-meldinger uten pause: alle tenner med riktig farge.

Burst-grensen på cirka 4 meldinger og behovet for 1,5 s pause før LED-maling lar seg ikke gjenskape fra Windows.
Feilen sett i Live skyldes trolig Live sin egen sysex-utsending (`_send_midi`), ikke BeatStep-firmwaren.

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
- Med klokka: verdi 1. Mot klokka: verdi 127. **Alltid ±1 per hakk, også ved rask vridning.**
- Rask vridning gir hakk med 8–25 ms mellomrom, sakte vridning rundt 0,6–0,9 s.

Akselerasjon må derfor baseres på tiden mellom hakk, slik `CMix._encoder_delta` gjør.
`DESIGN.md` sin beskrivelse av akselerasjon basert på verdienes størrelse virker ikke med denne konfigurasjonen.

## Annet

- CNTRL/SEQ-knappen lyser rødt uavhengig av scriptet (modusindikator i firmware).
