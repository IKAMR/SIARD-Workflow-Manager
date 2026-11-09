# SIARD Workflow Manager – innholdskontroll a7

**Versjon:** `v1.4.23-ikamr-04-a7`  
**Utgangspunkt:** committet a6 på `feature/innholdskontroll`.

## Endringer

### Generisk innholdskontroll
- Den generiske QA-dialogen har ikke lenger et ePhorte/Noark 4-valg.
- Generisk QA kjører med eksplisitt fagmodell, ekstern JSON-adapter og skrivebeskyttet SIARD-kilde.
- Den eldre ePhorte-adaptergeneratoren i `core/content_qa/ephorte_noark4.py` er **ikke slettet**; den er ikke lenger koblet til generisk QA. Bakoverkompatibilitet ligger i `migration_a6.py`, og godkjente standardmetrikker rutes via `domain_metrics.py`. Eldre prosjektfiler med `propose_ephorte_noark4_adapter=true` får advarsel og oppretter **ingen** adapterforslag. Eksisterende adapterfiler endres ikke.
- Semantiske Noark 4-metrikker produseres fortsatt kun når en godkjent adapter med `standard_id=noark4` er eksplisitt valgt. Ubekreftede kartleggingsforslag er fortsatt ikke datakontroller.

### Status og rapportering
- QA-rapporten viser teknisk kontroll og QA-vurdering separat. Teknisk fullføring innebærer ikke faglig godkjenning.
- Katalogmodus omtales nå som tabeller *funnet* og rader *ikke skannet*; ikke som en feilet radkontroll.
- JSON-rapporten får et eksplisitt `execution_status=KONTROLL_FULLFORT`, mens eksisterende `status` fortsetter å beskrive QA-vurderingen. Operasjonsresultatet får `qa_execution_status=FULLFORT`.
- Betegnelsen «Ubekreftede adapterbindinger» skiller seg fra automatisk genererte tabellkandidater.

### Prosjektfil, Lagre som og gjenkjøring
- Hver fullført operasjon lagrer et øyeblikksbilde av innstillingene som faktisk ble kjørt, i `completed_params`.
- Når innstillingene endres, behandles fullføringsstatusen som **pending**, og resultatet gjenbrukes ikke. Gammel a6-prosjektfil (.siardwf) støttes.
- «Lagre prosjekt» med **nytt filnavn** oppretter en frisk prosjektstatus med samme operasjoner/innstillinger. Den gamle prosjektfilen og eksisterende rapportfiler beholdes.
- Når parametere endres gjennom den ordinære parameterdialogen, fjernes synlig ferdighake for operasjonen.

## Avgrensninger
- Ingen endring av plassering for rapportfiler, logger eller prosjektfiler; standard plassering ved SIARD-filen beholdes.
- Ingen ny vedvarende analysedatabase, BaseX-integrasjon, automatisk utpakking eller ekstra radskanning.
- **Kjørerapport (PDF)** har fortsatt en egen statusmodell for teknisk arbeidsflyt; dens forside inngår ikke i denne leveransen. Ikke tolk «GODKJENT» i eldre kjørerapporter som en arkivfaglig godkjenning. QA-rapportens status er den autoritative faglige statusen i a7.

## Lokal installasjon og kontroll
1. Pakk ut a7-delta-ZIP over repo-roten fra a6. Dette er en ren filoverlegging, uten integrasjons- eller backupskript.
2. Kjør `test-innholdskontroll.bat` og kontroller `SLUTTSTATUS: OK`.
3. Start vanlig `start.bat`. Kontroller at den generiske QA-dialogen ikke har ePhorte-spesifikke valg.
4. For gjenkjøring: bruk sirkelpilen ved «Kjør workflow» for eksplisitt nullstilling; ved endret parameter skal checkpoint-kontrollen også tvinge ny kjøring.

Ingen filer i GitHub endres ved utpakking.
