#!/usr/bin/env python3
# One-time local documentation merge for IKAMR SIARD Workflow Manager.
# Does not delete legacy docs, commit, push, or modify program logic.
from __future__ import annotations

import hashlib
import os
import re
import sys
import tempfile
from pathlib import Path

# Unified current description. The full local originals are appended as
# collapsed technical references, including unpublished A8 documentation.
CANONICAL = r'''
# Innholdskontroll (QA) av SIARD

Innholdskontroll er et **generisk, skrivebeskyttet** rammeverk for kartlegging og kontroll av databasetabeller og faglige informasjonsbærere i SIARD. De faglige modellene er arbeidsutkast; kontrollresultater må ikke forveksles med fullstendig arkivfaglig godkjenning.

Denne filen er den **eneste samlede funksjonsdokumentasjonen** for innholdskontroll. Historiske detaljer fra tidligere deldokumenter er bevart nederst, uten å kreve egne versjonsnavngitte Markdown-filer.

## Ansvar og avgrensning

- QA-kjernen leser SIARD-metadata og, når valgt, datarader. Den endrer verken mottatt `.siard` eller en eksisterende utpakket kilde.
- Kataloginformasjon, uverifiserte kartleggingsforslag, faktisk utførte datakontroller og faglige konklusjoner skal holdes tydelig atskilt.
- Fagmodellene uttrykker **konsepter**, ikke bestemte leverandørers tabell- eller kolonnenavn. En fysisk kobling krever en eksplisitt valgt og gjennomgått adapter.
- En automatisk navnematch, en deklarert fremmednøkkel eller en historisk SQL-referanse er ikke i seg selv dokumentasjon på riktig faglig mapping.
- Dette erstatter ikke Arkade 5, DBPTK, Noark 4-/Noark 5-validering eller sammenligning mot arkivskapers produksjonssystem.

## Kilder og plassering i arbeidsflyten

Velg **Kilde for innholdskontroll** under operasjonen i GUI:

| Kildevalg | Adferd |
| --- | --- |
| **Automatisk** (standard) | Bruk gyldig utpakket SIARD-arbeidsmappe når den finnes; ellers aktiv `.siard`-fil. |
| **Utpakket SIARD** | Bruk eksplisitt valgt eller arbeidsflytens utpakkede mappe; manglende/ugyldig mappe er en feil, ikke grunnlag for stille fallback. |
| **SIARD-fil** | Bruk den aktive SIARD-filen selv om en utpakket mappe finnes. |

En valgfri **Utpakket SIARD-mappe** må ha `header/metadata.xml`. Den brukes ved automatisk eller eksplisitt utpakket-kildevalg, men overstyrer ikke **SIARD-fil**. Kildevalget lagres med operasjonsparametrene i prosjektet.

Typiske kjeder:

- `Pakk ut SIARD → konvertering/retting → Innholdskontroll → Pakk sammen SIARD` kontrollerer arbeidskopien før sammenpakking.
- `Pakk ut SIARD → konvertering/retting → Pakk sammen SIARD → Innholdskontroll` kontrollerer den ferdige SIARD-filen.
- Innholdskontroll kan også kjøres direkte på en `.siard` uten utpakking.

Rapporten og loggen dokumenterer valgt og faktisk kildetype, kildeopprinnelse og identifikasjon. Rapportnavn tar utgangspunkt i SIARD-filen som behandles, ikke et tilfeldig navn på en midlertidig mappe.

## Tekniske kontroller

### SIARD-katalog og kartleggingsforslag

`header/metadata.xml` brukes til katalog over skjemaer, tabeller, kolonner, datatyper og beskrivelser, deklarerte radantall, primærnøkler, kandidatnøkler og fremmednøkler. Motoren kan rangere tabellkandidater for faglige informasjonsbærere ved navnelikhet og metadatabeskrivelser. Også mulige nøkkel-, status- og datokolonner kan foreslås.

Forslagene er **UBEKREFTET** og skal ikke automatisk fylle inn `source`, `key`, `status_column`, `date_column` eller `relations` i en aktiv profil. Metadata-deklarerte fremmednøkler må også skilles fra relasjoner som bare er navneforslag.

### Radskanning, nøkler og relasjoner

Med **Tell og kontroller alle tabellrader = Ja** kan motoren:

- Strømme `tableX.xml` og sammenligne observert radantall med SIARD-metadata.
- Kontrollere deklarerte primærnøkler for reelle `NULL`-verdier og duplikater når kontrollen er aktivert.
- Kontrollere eksplisitt kartlagte faglige informasjonsbærere, unike/sammensatte nøkler, manglende nøkkelverdier og forventede antall (`exact`, `min`, `max`).
- Kontrollere aktiverte relasjoner mot refererte nøkler og registrere foreldreløse referanser og manglende påkrevde fremmednøkler.
- Beregne status- og årsfordelinger fra eksplisitt angitte felt, samt `distinct_metrics` for godkjente kolonnekombinasjoner.

Dette er bevisst ikke en generell SQL-motor. Programmet leser tabellrader strømmet, bruker en midlertidig SQLite-indeks for nøkler/referanser og lagrer bare nøklede HMAC-fingeravtrykk av identifikatorer. Den midlertidige databasen slettes når kjøringen er ferdig. Rå person-/identifikatorverdier skal ikke havne i rapporter.

**Tomme strenger er ikke SQL `NULL`:** En eksisterende XML-celle med `<c1/>` eller `<c1></c1>` behandles som tom streng; en utelatt celle eller `xsi:nil="true"` behandles som `NULL`. Tom streng i en deklarert primærnøkkel gir merknad (`metadata_pk_empty`, teller `pk_empty`), mens faktisk `NULL` og duplikat er avvik. Dette skillet ble viktig ved kontroll av `dbo.LAGRFORMAT.LF_KODE` i et ePhorte-uttrekk.

For sammensatte `DISTINCT`-målinger inngår ikke `NULL`-nøkler i antallet; manglende verdier registreres separat som `distinct_missing`.

## Generiske fagmodeller

Biblioteket under `siard_workflow/models/` er **data-only JSON** og består av:

- `index.json`: eksplisitt indeks over moduler, domener og taksonomi.
- `common/*.json`: fellesmoduler for blant annet person, kontaktopplysninger, klientregister, sak, registrering/journalpost, hendelseslogg, dokumentkjede, filreferanse, tilgang og tjenester/tiltak.
- `domains/*.json`: foreløpige domener for `saksarkiv`, `barnevern`, `skole`, `ppt`, `helsetjeneste`, `pleie_omsorg` og `sosialtjeneste`.
- `taxonomies/kommunale_systemkategorier.json`: historisk kategorigrunnlag med ni ASTA/KAISA-hovedkategorier og 20 kommunale kategorier.
- `standards/noark4_saksarkiv_reference.json`: konseptuelle Noark 4-kryssreferanser, **ikke** verifisert databaseskjema.

Alle domenemodellene kan ha status `draft` eller `pilot`, og de foreliggende modellene er arbeidsutkast. En systemkategori betyr ikke at programmet har en fullstendig modell, bestemte tabeller eller dokumenterte fagkrav. Manglende fagområder skal ikke fylles med ubegrunnede antakelser.

### Systemadaptere og eksplisitt godkjenning

En adapter er en separat JSON-fil med versjonert struktur. Den velger `domain_id` og kan angi `standard_id`, konkrete `source`-tabeller, `key`-kolonner, andre felt og relasjoner. Den legges normalt i en **privat fagressursmappe**, utenfor Git-repoet.

Eksempel med **syntetiske** navn:

```json
{
  "format_version": 1,
  "id": "syntetisk_saksarkiv",
  "label": "Demoadapter",
  "domain_id": "saksarkiv",
  "visibility": "internal",
  "bindings": [
    {
      "entity_id": "case_file",
      "review_status": "approved",
      "source": {"schema": "schema0", "table": "SAK"},
      "key": ["SAK_ID"]
    }
  ],
  "relations": []
}
```

Kun bindinger med `review_status: "approved"` brukes i reell faglig radkontroll. `proposed` er et uverifisert forslag, ikke en aktiv kontroll. Godkjenning i JSON er en erklæring fra operatøren og **ikke** automatisk depotgodkjenning. `approved` krever fysisk tabell og nøkkel. Uten godkjent adapter er fagbegreper `IKKE_KONTROLLERT`, også om tabellopptellingene er korrekte.

Adapterens domene må stemme med valgt fagmodell. Hvis modell ikke er eksplisitt valgt, kan adapterens `domain_id` velge domene. Ukjente felt, ugyldige verdier og usikre relative adapterstier avvises. Det kjøres ikke SQL eller Python-uttrykk fra adapterfilen. Et eldre QA-profilformat kan være relevant ved migrering, men er ikke lenger et eget generisk valg i GUI.

### Fagressursmapper og lokale maler

Under **Innhold → Innholdskontroll** kan brukeren peke til en eksisterende lokal fagressursmappe med for eksempel `templates/decom/`, `templates/kdrs-sok-og-vis/`, `adapters/` og `vendor-documentation/`. Stiene skal velges av brukeren, ikke hardkodes. Programmet skal ikke opprette, endre eller kopiere private originalmaler automatisk.

Decom-/KDRS-maler kan oppbevares som referansemateriale, men de importeres ikke automatisk uten egen, validert importfunksjon. Sensitive, kildespesifikke kartlegginger og leverandørdokumentasjon skal ikke legges i det offentlige repoet. Ressursbibliotek er noe annet enn SIARD-kilde, arbeidsmappe og rapportutdata.

## Noark 4- og ePhorte-referanse (fagspesifikt tillegg)

Generisk innholdskontroll skal ikke være avhengig av ePhorte. Historisk ble en separat Noark 4-orientert pilot brukt til å prøve arkivfaglige begreper, SQL-katalogreferanser og en **privat** adaptergenerator. `siard_workflow/core/content_qa/ephorte_noark4.py` eksisterer fortsatt som fagsystemspesifikk kode, men den generiske QA-dialogen tilbyr **ikke** automatisk generering av ePhorte-adaptere. Gammel prosjektparameter `propose_ephorte_noark4_adapter=true` skal kun gi migreringsadvarsel, og skal ikke skrive adapterfil.

Noark 4-referansen kan blant annet omfatte begrepene arkiv, arkivdel, arkivperiode, ordningsprinsipp, ordningsverdi, sak, journalpost, avsender/mottaker, dokumenttilknytning, dokumentbeskrivelse, dokumentrepresentasjon og merknad. Noark 4-fagbegreper og DTD-/SQL-kontroll-ID-er er **ikke** bevis for hvilke fysiske tabeller/kolonner en bestemt ePhorte-versjon faktisk har.

I dokumentkjeden må disse observerte målene holdes adskilt:

| Mål | Betydning |
| --- | --- |
| `document_link.count` | Antall koblingsrader mellom journalposter og dokumentbeskrivelser. |
| `document_description.count` | Antall dokumentbeskrivelser. |
| `document_representation.count` | Antall representasjoner (versjon × variant), ikke nødvendigvis unike dokumenter. |
| `document_version.count` | Unike dokument-/versjonskombinasjoner, **bare** når eksplisitt DISTINCT-kartlegging er godkjent. |

Spesielle faglige metrikker produseres bare når en valgt, godkjent adapter oppgir `standard_id: "noark4"`. `semantic_results` kan da inneholde `concept_id`, `metric_id`, `scope`, `method`, `value`, `state`, `source_table`, modell-/adapterhash og historisk SQL-ID. `not_measured` representeres med `value: null`, ikke tallet null. SQL-ID betyr referanse, **ikke** at historisk SQL er kjørt. Resultatet er et foreløpig faglig analysegrunnlag, ikke en komplett Noark 4.1-validering eller endelig DWM-importkontrakt.

En tidligere pilottjeneste kunne foreslå private adaptere fra allerede lagret QA-JSON. Den funksjonen er ikke lenger koblet til generisk QA; eksisterende private adaptere beholdes uendret. Alle fysiske bindinger må fortsatt godkjennes manuelt mot faktisk systemversjon og dokumentasjon.

## Rapportering og status

Ulike rapportnivåer skal ikke blandes:

- **Teknisk kjøringsstatus** viser om selve QA-operasjonen fullførte. Operasjonsresultatet bruker `qa_execution_status`; JSON-rapporten bruker `execution_status`, eksempelvis `KONTROLL_FULLFORT`.
- **Faglig QA-status** viser kvaliteten og dekningsgraden til kontrollene. JSON-resultatets `status` og operasjonsresultatets `qa_status` skal fortsatt kunne vise `DELVIS_KONTROLLERT` selv etter vellykket teknisk kjøring.
- **Kjørerapport (PDF)** kan ha en annen historisk statusmodell for arbeidsflyten. «GODKJENT» i denne rapporten betyr ikke nødvendigvis arkivfaglig godkjenning.

| QA-status | Betydning |
| --- | --- |
| `GODKJENT` | Alle relevante, konfigurerte kontroller er faktisk gjennomført uten avvik. |
| `DELVIS_KONTROLLERT` | Faglige bindinger, relasjoner eller radskanning mangler, selv om teknisk kontroll er fullført. |
| `AVVIK` | Gjennomført kontroll fant faktisk brudd på datakvalitets-/integritetskrav. |
| `IKKE_KONTROLLERT` | En konkret informasjonsbærer eller kontroll mangler tilstrekkelig grunnlag. |

Katalogmodus (`scan_rows=false`) betyr tabeller **funnet**, men rader **ikke skannet**. Dette er ikke en mislykket radskanning. `DELVIS_KONTROLLERT` skal tydelig merkes **IKKE FAGLIG GODKJENT**, men kan gi teknisk fullført operasjonssteg. Faktiske avvik eller tekniske feil skal ikke maskeres av en grønn kjøringsstatus.

QA leverer PDF og JSON, samt CSV for tabeller, informasjonsbærere og avvik. Kartleggingsrapportering kan også produsere `_kartleggingsforslag.json`, `_kartleggingsforslag.csv`, `_fremmednokler.csv` og `_relasjonsforslag.csv`. Godkjente standardmetrikker kan gi `*_innholdskontroll_faglige_metrikker.csv`. Tabellenes faktiske schema-/tabellnavn og rapportenes referanser er teknisk evidens; private adapterfiler og personidentifikatorer skal ikke pakkes inn i rapporten.

Rapporten skal vise profil-ID, SHA-256 for modell/adapter der tilgjengelig, valgt kildetype, relevante kontrollvalg, antall og status. Fremdriften må ikke fremstille uverifiserte forslag som utførte kontrollresultater.

## Prosjektfiler, fullføringsstatus og ny kjøring

En fullført operasjon lagrer et øyeblikksbilde av innstillingene som faktisk ble kjørt (`completed_params`). Endrede innstillinger gjør at tidligere resultat ikke skal gjenbrukes som om de fortsatt gjaldt. Ferdigmarkeringen fjernes når parametre endres i den ordinære dialogen. Eldre `.siardwf`-prosjekter skal fortsatt kunne leses.

**Lagre prosjekt med nytt filnavn** skal gi en ny, frisk prosjektstatus med samme arbeidsflyt og innstillinger, uten å endre den gamle prosjektfilen eller slette eksisterende rapporter. Ved ny kjøring kan arbeidsflyten nullstilles eksplisitt med sirkelpilen ved «Kjør workflow». En eksisterende fullført operasjon skal ikke automatisk hoppes over når relevante parametre er endret.

Utdata for rapporter/logg/prosjekt følger appens etablerte plassering. Ingen dokumentasjonsopprydding skal endre disse stiene eller føre til ny vedvarende analysedatabase, BaseX-integrasjon eller ekstra automatisk radskanning.

## Bruk i GUI

1. Velg en SIARD-fil og legg til **Innhold → Innholdskontroll** som vanlig arbeidsflytoperasjon.
2. Velg **Kilde for innholdskontroll**: automatisk, utpakket mappe eller SIARD-fil.
3. Velg **Fagmodell** (standard: `saksarkiv`). Velg eventuelt eksisterende **Fagressursbibliotek** og en ekstern, gjennomgått JSON-adapter.
4. Velg om alle tabellrader skal skannes og om deklarerte primærnøkler skal kontrolleres. For rask kartlegging kan radskanning skrus av.
5. Kjør operasjonen. Se separat på teknisk fullføring, faglig status, kartleggingsforslag og rapporter.
6. Godkjenn fysisk mapping **utenfor** programmet før ny faktisk fagkontroll. Vurder avvik og resultater opp mot systemdokumentasjon og kildemateriale.

En generisk dialog skal ikke vise leverandørspesifikke ePhorte-valg. Ressurs- og adapterstier er lokale valg, aldri universelle standardstier.

## CLI (utvalgte eksempler)

Kjør fra repositoryroten. Kildevalg og parametre styres av den installerte programversjonen; kontrollér `--help` ved avvik.

```bat
python -X utf8 -m siard_workflow.core.content_qa "D:\SIARD\eksempel.siard" --out "D:\SIARD\kontroll"
python -X utf8 -m siard_workflow.core.content_qa "D:\SIARD\eksempel.siard" --metadata-only
python -X utf8 -m siard_workflow.core.content_qa --list-domains
python -X utf8 -m siard_workflow.core.content_qa "D:\SIARD\eksempel.siard" --domain saksarkiv --metadata-only
python -X utf8 -m siard_workflow.core.content_qa "D:\SIARD\eksempel.siard" --domain saksarkiv --adapter "D:\fagressurser\adapters\mapping.json"
```

Den eldre `--profile`-parameteren kan fortsatt være tilgjengelig for eksisterende QA-maler, men bør ikke brukes som et automatisk, fagspesifikt standardvalg. Dokumenterte CLI-returkoder for innholdskontroll er `0` godkjent, `1` program-/filfeil, `2` delvis kontrollert og `3` avvik.

## Test og regresjon

Kjør `test-innholdskontroll.bat` fra repositoryroten. Den skal kontrollere registrering av QA-operasjonen, relevante avhengigheter, enhetstester for innholdskontroll og Python-syntaks. Ved GUI-endringer testes dessuten praktisk via `start.bat` på Windows. Rapporter og adaptertolkning bør verifiseres mot syntetiske data før de brukes på reelle SIARD-er.

Viktige regresjonsområder:

- Skillet mellom teknisk fullføring og faglig vurdering.
- At tom streng, utelatt celle og `xsi:nil` ikke blandes.
- At `NULL`/duplikat i nøkkel ikke maskeres; statusfordeling og DISTINCT måles korrekt.
- At bare eksplisitt godkjente adapterbindinger brukes; foreslåtte bindinger er inaktive.
- At generiske fagbegreper **ikke** får leverandørspesifikke tabell-/feltnavn som aliaser.
- At kildedata ikke endres, og at ingen person-/nøkkelverdier lekker til logg/CSV/PDF.
- At nye prosjektfiler, endrede parametre og gjenkjøring ikke feilaktig gjenbruker ferdigstatus.

## Begrensninger og videre arbeid

Det er ikke dokumentert at alle fagsystemer, Noark-versjoner, datafelter, statuser, kodeverk eller referanser er fullstendig kartlagt. Decom-/KDRS-maler er foreløpig referanser, ikke generell automatisk import. Ekte SIARD-eksport kan avvike fra produksjonsdatabasen. Bruk faglige kontrollkilder og eksplisitt mapping før konklusjoner trekkes.

En framtidig DWM-integrasjon må importere QA-resultat som **ekstern evidens** uten å overskrive egne autoritative målinger. Fysisk systemmapping, formelle Noark-krav og kontroll av dokument-/LOB-tilgjengelighet krever separate, dokumenterte utviklingssteg.

## Utfyllende tekniske og historiske detaljer

De opprinnelige spesifikasjonene er samlet nedenfor for å bevare alle detaljer, eksempler og avgrensninger fra den lokale arbeidskopien. Dette er bakgrunnsreferanse; **dagens funksjonsbeskrivelse ovenfor** er styrende når eldre instruksjoner er erstattet av nyere praksis. De sammenfoldede delene er ikke selvstendige dokumenter.

<!-- BEGIN_INNHOLDSKONTROLL_KILDESAMLING -->
<!-- END_INNHOLDSKONTROLL_KILDESAMLING -->
'''

START = '<!-- BEGIN_INNHOLDSKONTROLL_KILDESAMLING -->'
END = '<!-- END_INNHOLDSKONTROLL_KILDESAMLING -->'
STAMP = '<!-- SIARD_INNHOLDSKONTROLL_KONSOLIDERT:1 -->'

TITLES = {
    4: 'Fagmodeller og eksterne adaptere',
    5: 'Noark 4 og ePhorte som fagspesifikk referanse',
    6: 'NULL-semantikk og kvalitet på kontrollresultater',
    7: 'Prosjektstatus, rapportering og gjenkjøring',
    8: 'Lokale ressursmapper og fagspesifikke modeller',
}


def _read(file: Path) -> str:
    # UTF-8 with optional BOM, preserve every non-BOM character from source.
    return file.read_text(encoding='utf-8-sig')


def _write_atomic(path: Path, data: str) -> None:
    with tempfile.NamedTemporaryFile('w', encoding='utf-8', newline='\n',
                                     dir=path.parent, prefix='.siard_docs_',
                                     suffix='.tmp', delete=False) as out:
        temp_name = out.name
        out.write(data)
    try:
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def _detail(title: str, text: str) -> str:
    # Markdown source is retained verbatim, including local unpublished A8.
    # "details" keeps the main document readable despite complete preservation.
    return ('<details>\n<summary>' + title + '</summary>\n\n'
            + text.rstrip('\n') + '\n\n</details>\n')


def main() -> int:
    root = Path(__file__).resolve().parent
    docs = root / 'docs'
    main_doc = docs / 'INNHOLDSKONTROLL.md'
    if not main_doc.is_file():
        print('[FEIL] Fant ikke docs/INNHOLDSKONTROLL.md. Ingen endringer gjort.')
        return 2
    original = _read(main_doc)
    if STAMP in original:
        print('[OK] Dokumentasjonen er allerede samlet. Ingen endringer gjort.')
        return 0

    sources = sorted(docs.glob('INNHOLDSKONTROLL-A*.md'),
                     key=lambda p: (int(re.search(r'-A(\d+)', p.name).group(1))
                                    if re.search(r'-A(\d+)', p.name) else 999,
                                    p.name))
    nums = set()
    for file in sources:
        match = re.match(r'INNHOLDSKONTROLL-A(\d+)(?:-|\.)', file.name)
        if match:
            nums.add(int(match.group(1)))
    missing = set(range(4, 9)) - nums
    if missing:
        print('[FEIL] Mangler lokalt A-dokument for: ' +
              ', '.join('A' + str(n) for n in sorted(missing)))
        print('Ingen filer er endret. Alle A4-A8 må være tilgjengelige før samling.')
        return 2

    if CANONICAL.count(START) != 1 or CANONICAL.count(END) != 1:
        print('[FEIL] Ugyldig dokumentmal. Ingen endringer gjort.')
        return 2
    sections = [
        _detail('Tidligere samlet grunnbeskrivelse (bevart fra lokal arbeidskopi)', original)
    ]
    for source in sources:
        content = _read(source)
        if not content.strip():
            print(f'[FEIL] Tom kildefil: {source.name}. Ingen endringer gjort.')
            return 2
        number = int(re.search(r'-A(\d+)', source.name).group(1))
        title = TITLES.get(number, 'Supplerende faglig og teknisk dokumentasjon')
        sections.append(_detail(title, content))

    # New canonical material first; old source texts are preserved in full.
    content = CANONICAL.replace(START + '\n' + END,
                                START + '\n\n' + '\n'.join(sections)
                                + '\n' + END)
    content = STAMP + '\n' + content

    # Repair one previously verified cross-reference outside docs/.
    model_readme = root / 'siard_workflow' / 'models' / 'README.md'
    updated_readme = None
    if model_readme.is_file():
        readme = _read(model_readme)
        updated_readme = readme.replace(
            'docs/INNHOLDSKONTROLL-A4-MODELLER-OG-ADAPTERE.md',
            'docs/INNHOLDSKONTROLL.md')

    # No file deletions. Write only the unified document and (if needed) link.
    _write_atomic(main_doc, content)
    if updated_readme is not None and updated_readme != _read(model_readme):
        _write_atomic(model_readme, updated_readme)
        print('[OK] Oppdatert henvisning i siard_workflow/models/README.md')

    digest = hashlib.sha256(content.encode('utf-8')).hexdigest()
    print('[OK] Samlet dokumentasjon i docs/INNHOLDSKONTROLL.md')
    print('[OK] ' + str(len(sources) + 1) + ' lokale Markdown-kilder bevart i dokumentet')
    print('[OK] SHA-256: ' + digest)
    print('\nDisse filene kan slettes ETTER at du har kontrollert dokumentet:')
    for source in sources:
        print('  docs/' + source.name)
    print('  fix-innholdskontroll-dokumentasjon.py  (engangsskript)')
    print('\nIngen av filene over er slettet automatisk.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
