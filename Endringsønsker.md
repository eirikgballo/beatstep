# Endringsønsker

Ønsker og ideer for BeatStep-scriptet. Nye ønsker legges øverst under «Åpne».
Når et ønske er gjennomført, flyttes det til «Gjennomført» med dato og commit.

Mal:

```
### Kort tittel
- **Dato:** ÅÅÅÅ-MM-DD
- **Ønske:** hva som skal endres, sett fra bruk
- **Hvorfor:** hva som er tungvint eller mangler i dag
- **Status:** ny / avklares / klar / i arbeid
- **Notater:** spørsmål, idéer, hva som må måles først
```

## Åpne

### Enkel justering av encoder-følsomhet
- **Dato:** 2026-10-08
- **Ønske:** justere følsomheten for encoderne selv, enkelt, uten å lete i koden. For eksempel et tall fra 1 til 10
  for rolig vridning og ett for rask vridning (akselerasjon), samlet øverst i en fil eller i en egen fil.
- **Hvorfor:** følelsen må prøves fram i bruk, og i dag ligger den som fem tall per knappetype i `Encoders.py`.
- **Status:** i arbeid (kode og tester ferdige 2026-10-08, må prøves i Live)
- **Notater:**
  - Avklart med brukeren: per modus, skala 1–10.
  - Løsning: `Innstillinger.py` med to tall (rolig, rask) for RACK, VOLUM, SENDS, TRANSPOSE og SCRUB, og
    akselerasjonskurven (ROLIG_TID, RASK_TID, KURVE). Fila leses på nytt mens Live kjører.
  - Brukeren vil også se på jevnere akselerasjon. Start med KURVE og ROLIG_TID i fila.

### Spille fra markører (locators) med pads
- **Dato:** 2026-10-08
- **Ønske:** starte avspilling i Live fra en markør med en knapp + pad. Pad 1 spiller fra markør 1, pad 2 fra markør 2 osv.
- **Hvorfor:** kunne hoppe rundt i låta fra BeatStepen uten å bruke musa.
- **Status:** i arbeid (kode og tester ferdige 2026-10-08, må prøves i Live)
- **Notater:**
  - Knapp: hold stop + pad. Shift + pad er solo, ext sync er sidevelgeren, og stop var ledig.
  - Målt: padene sender noter mens stop holdes, og firmwaren slukker padene ved stop-trykket (se `SIGNALS.md`).
    Scriptet maler derfor markørene på padene mens stop holdes (blå = markør finnes).
  - Live: `song.cue_points` sortert på tid, `cue_point.jump()`, `song.continue_playing()` hvis låta står stille.
  - Markørene bekreftet i Live 2026-10-08. Hopp mens låta spiller følger Lives globale kvantisering.
  - Lagt til etter første prøve (må prøves i Live): stop alene stopper avspillingen (ved slipp),
    stop + pad 16 spiller fra loopstart (pad 16 lyser magenta), stop + transpose scrubber i tidslinja.
  - Maks 15 markører, siden pad 16 er loopstart.
  - Bekreftet i Live 2026-10-08: stop alene stopper, scrub virker både med og uten avspilling.
  - Justert etter prøve: stop alene starter avspilling når låta står stille, og scrub er finere
    (1/4 slag per hakk sakte, opptil 4 slag fort, mot 1–8 før).
  - Rettet og bekreftet i Live: avspilling etter scrubbing i stillstand starter fra den nye posisjonen,
    og scrubbing etter stopp regner fra der nåla står (se `SIGNALS.md`).
  - Ikke bekreftet: stop + pad 16 (loopstart) mens låta står stille.

### Følelsen i Volum- og Sends-modus
- **Dato:** 2026-10-07
- **Ønske:** egen encoder-følelse for Volum og Sends, f.eks. minste steg 0,5 % som transpose-knappen.
- **Hvorfor:** et sakte hakk flytter bare 0,2 % av området, så det tar lang tid å flytte volum og sends.
- **Status:** avklares (må kjennes på i Live)
- **Notater:** kan nå prøves direkte i `Innstillinger.py`: `VOLUM = (5, 5)` gir 0,5 % per hakk som transpose-hjulet.

### Filtrere enkelthakk i motsatt retning
- **Dato:** 2026-10-07
- **Ønske:** ignorere et enkelt hakk i motsatt retning rett etter en rask vridning.
- **Hvorfor:** encoder 1 ga ett hakk tilbake mot slutten av en vridning i simulatoren.
- **Status:** avklares (skjer det ofte nok til å være et problem?)

### Flytte scriptet ut av Live-appen
- **Dato:** 2026-10-07
- **Ønske:** legge scriptet i `~/Music/Ableton/User Library/Remote Scripts/` i stedet for inne i Live-appen.
- **Hvorfor:** filer inne i appen kan forsvinne når Live oppdateres, og skriving dit kan kreve ekstra rettigheter.
- **Status:** klar (etter at Mac-feilen i `handoff/HANDOFF.md` er løst)

## Gjennomført

### Velge makro-variasjoner (snapshots) i Rack-modus
- **Dato:** 2026-10-08, commit 4e212c1
- **Ønske:** velge mellom rack-ets makro-variasjoner fra BeatStepen.
- **Løsning:** trykk chan en gang til i Rack-modus, så viser padene variasjonene (rød = valgt, magenta = finnes).
  Pad N henter fram variasjon N, og velgeren blir stående åpen til chan trykkes igjen. Bekreftet i Live.
  Lagring gjøres i Live. Vise/skjule variasjonsvisningen i Live er ikke laget: API-et har ingen egenskap for det.

### Bytte mellom Session og Arrangement (som Tab)
- **Dato:** 2026-10-08, commit 4e212c1
- **Ønske:** en knapp som bytter mellom Session View og Arrangement View.
- **Løsning:** shift + ext sync. Ext sync alene er fortsatt sidevelgeren. Bekreftet i Live.

### Nullstille parameter med shift + encoder
- **Dato:** 2026-10-08, commit 9d8f3ac
- **Ønske:** hold shift og vri en encoder for å nullstille parameteren den styrer, slik dobbeltklikk gjør i Ableton.
- **Løsning:** ett hakk med shift inne setter parameteren til `default_value`. Gjelder makro, volum og sends.
  Bekreftet i Live i Rack-modus.

### Solo uten å velge sporet
- **Dato:** 2026-10-07, commit 5b5398d
- **Ønske:** kunne solo et spor uten at det blir valgt.
- **Løsning:** shift + pad. Dobbelttrykk ble prøvd først, men ga enten valg på første trykk eller 0,4 s forsinkelse.

### Solo-spor blinker magenta
- **Dato:** 2026-10-07, commit 5b5398d
- **Ønske:** tydeligere visning av solo-spor.
- **Løsning:** solo-spor som ikke er valgt blinker magenta/av. Valgt og solo blinker rød/magenta.
