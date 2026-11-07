# A5 – ePhorte/Noark 4 som første saksarkivadapter

**Utviklingsversjon:** `v1.4.23-ikamr-04-a5`  
**Gren:** `feature/innholdskontroll`  
**Status:** PILOT / uverifisert fagmapping. Ingen automatisk leverandørgodkjenning.

## Formål

A5 utvider a4 med en Noark 4-orientert saksarkivreferanse, en kontrollert generator
for *private* ePhorte-adapterforslag og egne observerte faglige resultatmål. Den
bruker allerede generert SIARD-katalog og deklarerte fremmednøkler som kilder.

Dette er **ikke** en implementering av alle Noark 4.1-krav, en kjøring av MySQL-SQL,
eller en verifisering mot original databasedrift. DWM-import er en senere oppgave;
CSV/JSON er et foreløpig maskinlesbart resultatgrunnlag.

## Kilder og roller

| Kilde | Hva den kan begrunne | Hva den IKKE beviser |
| --- | --- | --- |
| `IKAMR/schemas/N4/v1.0` | Offentlige Noark 4 DTD-entiteter og navn | ePhortes private kolonnemapping |
| Noark 4.1 del 1/2, rettelser og kravtabeller | Normative/historiske krav per spesifisert utgave | Hvordan én SQL-database faktisk er installert |
| `noark4-fields-working-reference.xlsx` | Arbeidshypoteser om Noark 4 og leverandørvarianter | At alle varianter har identiske tabellnavn |
| ePhorte SQL-kataloger fra 2023 og 2025 | Eldre kontrollformål og sporbarhet til kontroll-ID | At SQL blir kjørt i a5 |
| SIARD `header/metadata.xml` | Faktiske navn, deklarerte PK/FK og radantall i **dette** uttrekket | At dataverdier eller faglige relasjoner er korrekt |

Public kode inneholder **ikke** de to SQL-katalogene, en komplett leverandørmapping
eller private Decom-/KDRS-maler. Standardoppslaget i
`siard_workflow/models/standards/noark4_saksarkiv_reference.json` inneholder
Noark 4-tabellnavn (DTD) og konseptuelle fagbegreper, men ingen SQL/kolonneverdier.

## Konseptuelle enheter

Generisk domenemodell `saksarkiv` bruker fra a5 også `archive_structure`:
arkiv, arkivdel, arkivperiode, ordningsprinsipp og ordningsverdi.

Første Noark 4-kryssreferanse inneholder blant annet:

| Fagobjekt | Noark 4 navn / vanlige ekstraktnavn | Katalogkontroll-ID |
| --- | --- | --- |
| Arkiv | ARKIV | N4.01.01 |
| Arkivdel | ARKIVDEL | N4.02.01 |
| Sak | NOARKSAK | N4.03.01a (2025), N4.03.01 (2023) |
| Journalpost | JOURNPST / JOURNPOST | N4.04.01 |
| Avsender/mottaker | AVSMOT | N4.05.01 |
| Dokumenttilknytning | DOKLINK | N4.06.01 |
| Dokumentbeskrivelse | DOKBESK / DOKBESKRIV | N4.06.11 |
| Dokumentrepresentasjon | DOKVERS / DOKVERSJON | N4.06.21 |
| Merknad | MERKNAD | N4.07.01 |

Tabellnavn er *forslag* fra offentlige Noark 4-navn, ikke en erklæring om at alle
faktiske ePhorte-installasjoner bruker samme navn. Andre begreper og relasjoner
står i referansefilen.

### Viktig: dokumentkjeden

`DOKLINK` representerer et koblingsforhold mellom journalpost og dokumentbeskrivelse.
En dokumentbeskrivelse kan knyttes til flere journalposter. I en del ePhorte-
uttrekk har `DOKVERSJON` en **sammensatt PK** for dokument, versjon og variant.

Derfor må følgende skilles:

- `document_link.count` – antall koblingsrader, ikke unike dokumenter.
- `document_description.count` – antall dokumentbeskrivelser.
- `document_representation.count` – rader (versjon × variant) i kildetabellen.
- `document_version.count` – antall **unike dokument-/versjonsnøkler**,
  bare når særskilt DISTINCT-projeksjon er gjennomgått og godkjent.

Den generiske QA-motoren støtter fra a5 `distinct_metrics` med eksplisitt oppgitte
kolonner. Den beregner kardinalitet på samme radskann som QA, med nøklede
fingeravtrykk i midlertidig SQLite. Ingen dokumentinnhold, rå primærnøkler eller
persondata skrives til rapportene. NULL-nøkler holdes utenfor DISTINCT-tellingen
og registreres separat som `distinct_missing`.

## Bruksmåte A – direkte fra GUI

1. Velg `Innhold → Innholdskontroll`.
2. Velg fagmodell **`saksarkiv`**.
3. Velg en **eksisterende** ekstern mappe i `Fagressursbibliotek`, utenfor repoet.
4. Velg **`Lag ePhorte/Noark 4-adapterforslag` = Ja**.
5. Start gjerne med `Tell og kontroller alle tabellrader = Nei`:
   metadata-kartlegging krever ikke skann av alle SIARD-radene.
6. Forslaget lagres under
   `Fagressursbibliotek/adapters/ephorte/noark4/` som JSON, review-CSV og
   review-JSON. **Alle bindinger/relasjoner får `review_status: proposed`.**
7. Sammenlign med dine ePhorte-/Noark 4-kilder før du **manuelt** endrer
   *individuelle* verifiserte bindinger til `approved`.
8. Velg den gjennomgåtte adapteren i `Ekstern systemadapter (JSON)` og
   slå på radskann for faktisk nøkkel- og referansekontroll.

**Programmet godkjenner aldri forslag automatisk.** En ukartlagt fagmodell
skal fortsatt gi `DELVIS_KONTROLLERT` selv om tekniske tabellopptellinger er OK.
Hvis du har aktivert en uverifisert binding, kan resultatet bli misvisende;
operatøren har ansvar for godkjenningen.

## Bruksmåte B – gjenbruk allerede lagret QA-resultat

Det er ikke nødvendig å skanne flere millioner rader på nytt bare for å lage
et privat forslag. Bruk en eksisterende `_innholdskontroll.json` fra a3/a4:

```bat
py -3 -m siard_workflow.core.content_qa.ephorte_noark4 ^
  --qa-json "D:\rapporter\ephorte_innholdskontroll.json" ^
  --output-dir "D:\arkiv-fagressurser\adapters\ephorte\noark4" ^
  --adapter-id ephorte_noark4_forslag_01
```

Programmet nekter å overskrive et eksisterende forslag, og tillater ikke at
private adapterfiler genereres inne i applikasjonens eget repo.

Etter manuell kontroll: velg JSON-filen som vanlig a4 systemadapter, gjerne med
`resources_root` angitt. Dersom navn eller nøkler varierer i et nytt uttrekk,
laget en egen adaptervariant og dokumenter den – ikke gjenbruk en feil mapping.

## Om avsender og mottaker, arkivdel og relasjoner

Fremmednøkkelparene må finnes eksplisitt i `metadata.xml` for at generatoren
foreslår dem. Den krever at FKen viser til **foreldrens primærnøkkel**.
Når flere FKer passer samme par, blir det `FLERTYDIG` og ingen relasjon foreslås.
`required` settes aldri automatisk til `true`; det krever egen vurdering av
NULL-semantikk, historiske statusverdier og Noark-versjon.

Aktiverte relasjoner kontrolleres mot faktiske datarader av den eksisterende
QA-motoren; uaktiverte forslag er ikke kontrollresultater.

## Rapport og sporbarhet

Med en eksplisitt valgt adapter merket `standard_id: "noark4"` får rapporten
en særskilt Noark 4-metrikkseksjon og CSV-fil
`*_innholdskontroll_faglige_metrikker.csv`. JSON-resultatet har
`semantic_results`, inkludert `concept_id`, `metric_id`, `scope`, `method`,
`value`, `state`, `source_table`, modell-/adapterhash og historisk SQL-ID.
**SQL-ID betyr historisk referanse, ikke at spørringen er kjørt.**

Manglende eller ikke-kjørte kontroller gir `value: null` og `state: not_measured`
– aldri null som et observert antall. Rapporten inneholder ikke private adapterfiler.

## Begrensninger og neste steg

- Ikke implementert i a5: full Noark 4.1-kravmatrise, SQL-motor, alle
  statusfordelinger, unike `DOKLINK`-dokumenter eller fil-/LOB-tilgjengelighet.
- Det finnes ennå ingen direkte DWM-importkontrakt; resultatfeltene er
  foreløpige. DWM skal senere importere som **ekstern evidens**, ikke
  overskrive egne masterresultater.
- SIARD-eksport kan avvike fra opprinnelig produksjonsbase. Vurdering av
  innholdet krever fortsatt arkivskapers kontrollgrunnlag.
- Windows GUI, PyInstaller og lange reelle ePhorte-kjøringer må verifiseres
  på brukerens Windows-maskin. Testene bruker syntetisk SIARD.
