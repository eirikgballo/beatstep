# Scrollhjelper (bare Mac)

Live lar ikke scripts panorere arrangementet. Pad 11–14 i Record-modus sender derfor en melding til dette
programmet, som lager en scroll-hendelse slik styreflaten ville gjort.

## Bygge (én gang, og etter endringer i kildekoden)

```
cd tools/scrollhjelper
swiftc -O beatstep-scroll.swift -o beatstep-scroll
```

## Kjøre

Live-scriptet starter programmet selv når Live starter, og stopper det når Live lukkes. Det som blir skrevet ut
havner i `logs/scrollhjelper.log`. Programmet (eller Live) må ha tilgang under
Systeminnstillinger > Personvern og sikkerhet > Tilgjengelighet.

For å prøve det for hånd: `./beatstep-scroll` i en terminal, som da må ha den samme tilgangen.

## Bruk

- Musepekeren må ligge over arrangementet: hendelsen går til vinduet under pekeren.
- Steglengden er `PAN_STEG` i `Innstillinger.py`.
- Programmet skriver en linje for hver melding det får, og sier fra hvis det mangler tilgang.
