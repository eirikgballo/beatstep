# Innstillinger for BeatStep-scriptet.
#
# Lagre fila, så leser scriptet den på nytt innen et sekund. Live trenger ikke restartes.
# Skrivefeil gir en melding i statuslinja nederst i Live, og de forrige verdiene beholdes.

# ---------------------------------------------------------------------------
# Følsomhet: to tall fra 1 (finest) til 10 (grovest). Desimaler er lov, f.eks. 3.5.
#
#   rolig = steget per hakk når du vrir sakte
#   rask  = steget per hakk når du vrir fort (akselerasjon). Sett lik rolig for å slå av akselerasjon.
#
#   Trinn                 1      2      3      4      5      6      7      8      9     10
#   rolig, % av området   0,08   0,13   0,2    0,3    0,5    0,8    1,2    2,0    3,1    4,9
#   rask,  % av området   0,4    0,7    1,0    1,5    2,2    3,3    5,0    7,4   11     17
#   SCRUB rolig, slag     0,1    0,16   0,25   0,4    0,6    1,0    1,6    2,5    3,9    6,2
#   SCRUB rask,  slag     0,5    0,8    1,2    1,8    2,8    4,1    6,2    9,3   14     21
# ---------------------------------------------------------------------------

#            rolig  rask
RACK      = (  4,    8 )    # encoder 1–16 i Rack-modus (makroer)
VOLUM     = (  3,    5 )    # encoder 1–16 i Volum-modus
TRANSPOSE = (  5,    5 )    # det store hjulet: volum på valgt spor
SCRUB     = (  3,    6 )    # det store hjulet mens stop holdes: flytter spillehodet

# ---------------------------------------------------------------------------
# KAST: hvor fort du må spinne for å få det raske steget. 1 (lett) til 10 (må spinne hardt).
#
# Scriptet måler farten i hakk per sekund. Vanlig vridning er 10–40 hakk/s, et raskt spinn 70–900.
# Under en tredel av kastefarten får du alltid det rolige steget. Derfra øker steget jevnt, og ved
# kastefarten får du hele det raske steget.
#
#   KAST                     1     2     3     4     5     6     7     8     9    10
#   fullt rask ved, hakk/s   47    61    80   104   135   176   228   297   386   501
#   akselerasjon fra, hakk/s 16    20    27    35    45    59    76    99   129   167
#
# Hopper den for lett ved vanlig vridning: øk KAST. Må du spinne for hardt for å nå maks: senk KAST.
# ---------------------------------------------------------------------------

KAST = 5

# ---------------------------------------------------------------------------
# STARTSPOR: sporet i Live som havner på pad 1. Med 3 hopper padene over de to øverste sporene,
# som da ikke kan velges, soloes eller armes fra BeatStepen. Gjelder også encoderne i Volum-modus.
# 1 = alle spor er med.
# ---------------------------------------------------------------------------

STARTSPOR = 3

# ---------------------------------------------------------------------------
# SCRUB_SNAP: rutenett for scrubbing (stop + det store hjulet), i slag. Hvert hakk flytter nåla minst
# ett steg og lander alltid på rutenettet. Raskt spinn flytter flere steg per hakk (styres av SCRUB over).
#
#   0.25 = sekstendeler    0.5 = åttedeler    1 = slag    4 = takter i 4/4    0 = av (fri scrubbing)
#
# Scriptet kan ikke lese rutenettet i Live, så dette følger ikke «Snap to Grid» der.
# ---------------------------------------------------------------------------

SCRUB_SNAP = 0.25

# ---------------------------------------------------------------------------
# PAN_STEG: hvor langt bildet flytter seg per trykk på pad 11–14 i Record-modus, i piksler.
# Krever at scrollhjelperen kjører (tools/scrollhjelper) og at musepekeren ligger over arrangementet.
# ---------------------------------------------------------------------------

PAN_STEG = 200

# ---------------------------------------------------------------------------
# SHIFT_TRYKK: et kort trykk på shift alene bytter mellom Session og Arrangement (som Tab).
# Tallet er hvor lenge, i sekunder, shift kan holdes og fortsatt regnes som et kort trykk.
# Bytter den når du ikke mente det: senk tallet. Må du trykke for kjapt: øk det. 0 = av.
# ---------------------------------------------------------------------------

SHIFT_TRYKK = 0.4
