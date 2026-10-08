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

### Nullstille parameter med shift + encoder
- **Dato:** 2026-10-08
- **Ønske:** hold shift og vri en encoder for å nullstille parameteren den styrer, slik dobbeltklikk gjør i Ableton.
- **Hvorfor:** viktig i bruk. I dag må man vri tilbake til 0 for hånd, eller bruke musa i Live.
- **Status:** klar
- **Notater:**
  - Dobbeltklikk i Ableton setter parameteren til **standardverdien**, ikke alltid 0: makro 0, volum 0 dB, sends −∞.
    Live har `parameter.default_value`, så bruk den for å oppføre seg likt.
  - Gjelder alle tre modusene: makro i Rack, volum i Volum, send A/B i Sends.
  - Shift + encoder sender vanlig CC i kontrollmodus (målt, se `SIGNALS.md`). Shift + transpose er master-volum
    og berøres ikke.
  - Ett hakk mens shift holdes bør være nok til å nullstille. Videre vridning med shift inne bør ikke endre verdien.
  - Falsk Live (`tools/fakelive/fake_song.py`) må få `default_value` på `Parameter`.

### Følelsen i Volum- og Sends-modus
- **Dato:** 2026-10-07
- **Ønske:** egen encoder-følelse for Volum og Sends, f.eks. minste steg 0,5 % som transpose-knappen.
- **Hvorfor:** et sakte hakk flytter bare 0,2 % av området, så det tar lang tid å flytte volum og sends.
- **Status:** avklares (må kjennes på i Live)
- **Notater:** innstillingene ligger i `Encoders.py` (`KNOB_FEEL`, `TRANSPOSE_FEEL`).

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

### Solo uten å velge sporet
- **Dato:** 2026-10-07, commit 5b5398d
- **Ønske:** kunne solo et spor uten at det blir valgt.
- **Løsning:** shift + pad. Dobbelttrykk ble prøvd først, men ga enten valg på første trykk eller 0,4 s forsinkelse.

### Solo-spor blinker magenta
- **Dato:** 2026-10-07, commit 5b5398d
- **Ønske:** tydeligere visning av solo-spor.
- **Løsning:** solo-spor som ikke er valgt blinker magenta/av. Valgt og solo blinker rød/magenta.
