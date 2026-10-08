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
RACK      = (  3,    5 )    # encoder 1–16 i Rack-modus (makroer)
VOLUM     = (  3,    5 )    # encoder 1–16 i Volum-modus
SENDS     = (  3,    5 )    # encoder 1–16 i Sends-modus
TRANSPOSE = (  5,    5 )    # det store hjulet: volum på valgt spor
SCRUB     = (  3,    6 )    # det store hjulet mens stop holdes: flytter spillehodet

# ---------------------------------------------------------------------------
# Akselerasjonskurven, felles for alle. Tiden er sekunder mellom to hakk.
#
#   ROLIG_TID  Tregere enn dette mellom hakkene gir rolig steg. Vanlig sakte vridning: 0,2–0,5 s.
#   RASK_TID   Raskere enn dette gir fullt rask steg. Vanlig rask vridning: 0,03–0,06 s.
#              Mellom de to tidene glir steget fra rolig til rask.
#   KURVE      Formen på overgangen. 1.0 = jevn (rett linje). Høyere tall holder steget lite lenger
#              og øker det brått mot slutten: 2.0 = myk start, 3.0 = brå.
#
# Jevnere akselerasjon: senk KURVE mot 1.0, eller øk ROLIG_TID så overgangen strekkes over et større fartsområde.
# ---------------------------------------------------------------------------

ROLIG_TID = 0.30
RASK_TID  = 0.08
KURVE     = 2.0
