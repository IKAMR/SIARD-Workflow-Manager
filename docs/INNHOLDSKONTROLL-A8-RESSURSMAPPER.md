# a8: Tre separate eksterne ressursmapper

Dette er en korrigering innen samme a8, ikke en ny faglig kontrollversjon.

## Kataloger

De tre bibliotekene er uavhengige og kan ligge på forskjellige disker:

1. **Decom / SIARDMapper-maler.** Programmets eksisterende `json_template_dir`
   i `config.json` videreføres uendret. Den gamle katalogen flyttes ikke.
2. **KDRS Søk & Vis-maler.** Ny felles katalog `kdrs_sok_vis_dir` til
   fremtidig referanse og kartlegging. a8 leser **ikke** malene automatisk og
   utfører **ingen** KDRS-basert faglig kontroll ennå.
3. **Systemadaptere til generiske fagmodeller.** Ny katalog
   `system_adapter_dir`. Innholdskontrolls felt «Ekstern systemadapter
   (JSON)» starter filvelgeren i denne mappen og valgte adaptere leses kun
   etter eksplisitt valg. `proposed` er ikke automatisk godkjent.

### Oppsett i a8

Åpne **Innhold → Innholdskontroll → +** eller høyreklikk på en eksisterende
operasjon → **Konfigurer operasjon**. Klikk **Ressursmapper…** nederst,
velg de tre katalogene med **Bla…**, og klikk **Lagre mapper**.

Dette er et **felles oppsett for denne maskinen**, ikke en plassering av
prosjektfiler eller QA-rapporter. Dialogen ligger foreløpig i
**Innholdskontroll-oppsettet**, ikke under «Globale innstillinger».
Den lokale konfigurasjonen bruker:

- `config.json` → den *eksisterende* Decom-nøkkelen `json_template_dir`.
- `resource_folders.json` → KDRS- og systemadapterkatalogene. Filen er
  lagt i `.gitignore` og skal **ikke committes**.

Tom verdi er tillatt. Ikke-eksisterende mapper avvises ved lagring.
Kataloger gjennomsøkes ikke automatisk ved oppstart.

### Ekstern systeminfosamling

Eksempel på bibliotek (plassen er ditt valg):

```text
<ekstern-systeminfo-root>/
  6-18-sosialtjeneste/
    <fagsystem>/
      <fagsystem-id>_sosialtjeneste_proposed.json
      <systemspesifikk-dokumentasjon>.md
```

Flytt systemspesifikke adaptere og tilhørende dokumentasjon ut av
SWM-repositoryet og slett eventuelle gamle kopier fra `docs/adapters/` og
`docs/`. Systeminfo leveres separat fra generisk kildekode.

## Kompatibilitet og sikkerhet

Gamle `.siardwf`-filer med `resources_root` kan fortsatt brukes. Når ny
systemadaptermappe er konfigurert, overstyrer denne den gamle rotmappen.
Absolutte adapterstier utenfor den konfigurerte mappen blir da avvist med
forklarende feil; oppdater feltet «Ekstern systemadapter» og velg filen på nytt.

Ingen SIARD-filer, dokumenter eller andre depotdata følger med denne leveransen.
Ingen automatiske GitHub-endringer eller lokale filflyttinger utføres.
