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
- Encoder N sender CC 9+N (encoder 8 = CC 17, målt).
- Med klokka: verdi 1. Mot klokka: verdi 127. Normalt ±1 per hakk, også ved rask vridning.
- Rask vridning gir hakk med 8–25 ms mellomrom, sakte vridning rundt 0,6–0,9 s.
- **Hardware-akselerasjon:** ved svært rask vridning (meldinger med cirka 3 ms mellomrom) hopper verdien til 12 (delta +12).

`CMix._encoder_delta` bruker bare retningen og tiden mellom hakk, og kaster bort størrelsen.
Enten bør størrelsen brukes, eller så slås hardware-akselerasjonen av via sysex.

## Annet

- CNTRL/SEQ-knappen lyser rødt uavhengig av scriptet (modusindikator i firmware).
