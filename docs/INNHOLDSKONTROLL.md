# Innholdskontroll (QA) av SIARD

Innholdskontroll er et **generisk, skrivebeskyttet** rammeverk for kartlegging og kontroll av databasetabeller og faglige informasjonsbærere i SIARD. De faglige modellene er arbeidsutkast; kontrollresultater må ikke forveksles med fullstendig arkivfaglig godkjenning.

Dette er den **samlede funksjonsdokumentasjonen** for innholdskontroll. Bruksmåte, modeller, adaptere, ressursmapper, rapportering og fagsystemreferanser dokumenteres her, uten separate dokumenter for hvert utviklingstrinn.

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

En valgfri **Utpakket SIARD-mappe** må ha `header/metadata.xml` (eller `metadata.xml` i valgt rot, der denne kildestrukturen brukes). Den brukes ved automatisk eller eksplisitt utpakket-kildevalg, men overstyrer ikke **SIARD-fil**. Kildevalget lagres med operasjonsparametrene i prosjektet.

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
- `common/*.json`: 12 fellesmoduler for blant annet person, kontaktopplysninger, klientregister, sak, registrering/journalpost, hendelseslogg, dokumentkjede, filreferanse, tilgang, tjenester/tiltak og sosialfaglig saksbehandling (`social_register`).
- `domains/*.json`: foreløpige domener for `saksarkiv`, `barnevern`, `skole`, `ppt`, `helsetjeneste`, `pleie_omsorg` og `sosialtjeneste`.
- `taxonomies/kommunale_systemkategorier.json`: historisk kategorigrunnlag fra IKAMRs `0000-kommune-elarkiv.xlsx` (15.05.2020) med 9 ASTA/KAISA-hovedkategorier og 20 kommunale kategorier. Dette er klassifikasjon, ikke bevis for at alle kategorier har en modell.
- `standards/noark4_saksarkiv_reference.json`: konseptuelle Noark 4-kryssreferanser, **ikke** verifisert databaseskjema.

Alle domenemodellene kan ha status `draft` eller `pilot`, og de foreliggende modellene er arbeidsutkast. En systemkategori betyr ikke at programmet har en fullstendig modell, bestemte tabeller eller dokumenterte fagkrav. Manglende fagområder skal ikke fylles med ubegrunnede antakelser.

### Systemadaptere og eksplisitt godkjenning

En adapter er en separat JSON-fil med versjonert struktur. Den velger `domain_id` og kan angi `category_code`, `standard_id`, konkrete `source`-tabeller, `key`-kolonner, andre felt og relasjoner. System- og leverandørspesifikke adaptere **skal ligge utenfor SWM-repositoryet**, i en eksplisitt valgt ekstern katalog. Programmet avviser adapterfiler inne i repository-treet.

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

Adapterens `domain_id` må stemme med valgt fagmodell, og en oppgitt `category_code` må stemme med fagmodellens kategori (for eksempel `6-18`). Uten eksplisitt domenevalg kan adapterens `domain_id` brukes som valg. Ukjente felter, ugyldige verdier, stier utenfor valgt systemadaptermappe og adaptere inne i repoet avvises. Det kjøres ikke SQL eller Python-uttrykk fra adapterfilen. Eldre QA-mal/profil er ikke lenger et eget valg i den generiske GUI-dialogen eller CLI-en.

### Tre uavhengige ressursmapper

I **Innhold → Innholdskontroll → konfigurer operasjon** finnes knappen **Ressursmapper…** nederst i dialogen. Velg eksisterende kataloger med **Bla…** og klikk **Lagre mapper**. Katalogene kan ligge på forskjellige disker; tomt felt er tillatt, men en oppgitt mappe må eksistere. De opprettes ikke av programmet og gjennomsøkes ikke automatisk.

| Ressurs | Bruk og lagring | Virkning i innholdskontroll |
| --- | --- | --- |
| **Decom / SIARDMapper-maler** | Eksisterende `json_template_dir` i lokal `config.json`. Stien videreføres, ikke flyttes. | Maler er referanse-/verktøyressurser, ikke automatisk QA-mapping. |
| **KDRS Søk & Vis-maler** | `kdrs_sok_vis_dir` i lokal `resource_folders.json`. | Bare valgt katalog; ingen automatisk import eller KDRS-basert fagkontroll. |
| **Systemadaptere til fagmodeller** | `system_adapter_dir` i lokal `resource_folders.json`. | Filvelgeren for **Ekstern systemadapter (JSON)** starter her; kun eksplisitt valgte adaptere leses. |

`resource_folders.json` ligger i programmets lokale dataområde og er utelatt fra Git. Dette er felles maskininnstillinger, **ikke** innstillinger for plassering av prosjektfiler, SIARD-kilder eller rapporter. En ugyldig JSON eller en ikke-eksisterende mappe meldes som feil ved lesing/lagring. Ingen proprietære ressurser kopieres automatisk.

Eldre `.siardwf`-prosjekter kan inneholde `resources_root`. Denne brukes som kompatibilitetsfallback når en ny `system_adapter_dir` ikke er satt. Når en dedikert systemadaptermappe er valgt, har den forrang: absolutte eller relative adapterstier som peker utenfor denne katalogen avvises. Velg da adapterfilen på nytt i den konfigurerte mappen.

En ekstern systeminformasjonskatalog kan for eksempel organiseres slik (plassering og navnevalg er lokale):

```text
<ekstern-systeminformasjon>/
  6-18-sosialtjeneste/
    <fagsystem>/
      <adapter-id>_sosialtjeneste_proposed.json
      systemdokumentasjon/
```

Systemspesifikke mappinger og dokumentasjon må lagres utenfor dette offentlige kode-repositoriet. `docs/examples/synthetic_saksarkiv_adapter.json` er derimot et **syntetisk** eksempel uten produksjonsdata. En ekstern ressursmappe er ikke identisk med kildemappe, arbeidsområde eller rapportmappe.

### Sosialtjeneste og leverandøruavhengige begreper

Fagmodellen `sosialtjeneste` er et **utkast** med systemkategori **`6-18 Sosialtjeneste`**. Modulen `social_register` supplerer delte moduler med faglige konsepter, blant annet:

- søknad (`social_application`), vedtak (`social_decision`) og saksbehandlingsforløp;
- sosialfaglig journaloppføring og planer/oppfølgingsplaner;
- inntekts-/utgiftsopplysninger og økonomiske transaksjoner;
- historikk for vedtaks- og tiltaksstatus.

**Klient/person må skilles fra systembruker; vedtak må skilles fra tiltak.** CLOB/NCLOB-felt kan inneholde faglige tekstverdier og er ikke automatisk dokumentfiler. Leverandørspesifikke tabell-/kolonnenavn (for eksempel `inntutg` og `trans`) skal ikke være aliaser i generiske moduler. Slike navn hører hjemme i ekstern, eksplisitt gjennomgått systemmapping. En modell beskriver ikke fysisk databaseskjema, og ingen mapping blir godkjent automatisk.

### Kontroll av valgt adapter mot SIARD-metadata

Når en ekstern adapter er eksplisitt valgt, lages en **separat metadatagjennomgang**. Denne kontrollerer om angitte tabeller, kolonner og deklarerte primærnøkler finnes i akkurat dette SIARD-uttrekket. For relasjoner kontrolleres kolonnepar og datatypenes hovedfamilier. Mulige statusmeldinger omfatter:

- `METADATA_TREFF`, `TABELL_MANGLER`, `KOLONNER_MANGLER` eller `NOKKEL_KREVER_GJENNOMGANG` for bindinger;
- `KOLONNER_FUNNET`, `TYPE_GJENNOMGANG` eller manglende nøkkel-/kolonnepar for relasjoner.

**Ingen av disse er faglig godkjenning.** Datatypeavvik, som `INT` mot `FLOAT`, krever menneskelig gjennomgang. Kontroll av tabell-/feltnavn beviser verken korrekt faglig semantikk eller referanseintegritet i radinnhold. `review_status: proposed` forblir inaktiv etter en metadatamatch; godkjenning skjer eksplisitt i ekstern adapter. Resultatene skilles fra generelle navnebaserte forslag og fra faktisk utførte datakontroller. De eksporteres til `_adapter_bindinger.csv` og `_adapter_relasjoner.csv` ved siden av øvrige QA-filer.

## Noark 4- og ePhorte-referanse (fagspesifikt tillegg)

Generisk innholdskontroll skal ikke være avhengig av ePhorte. Historisk ble en separat Noark 4-orientert pilot brukt til å prøve arkivfaglige begreper, SQL-katalogreferanser og en **privat** adaptergenerator. `siard_workflow/core/content_qa/ephorte_noark4.py` eksisterer fortsatt som fagsystemspesifikk kode, men den generiske QA-dialogen tilbyr **ikke** automatisk generering av ePhorte-adaptere. Gammel prosjektparameter `propose_ephorte_noark4_adapter=true` skal kun gi migreringsadvarsel, og skal ikke skrive adapterfil.

Noark 4-referansen omfatter blant annet arkiv, arkivdel, arkivperiode, ordningsprinsipp/-verdi, sak, journalpost, avsender/mottaker, dokumentkjede og merknad. `siard_workflow/models/standards/noark4_saksarkiv_reference.json` bruker offentlige Noark 4 DTD-navn og historiske kontroll-ID-er som **forslag**, ikke en verifisert ePhorte-databasemodell.

| Konsept | Referansenavn i Noark 4 | Historisk kontroll-ID |
| --- | --- | --- |
| Arkiv | `ARKIV` | `N4.01.01` |
| Arkivdel | `ARKIVDEL` | `N4.02.01` |
| Sak | `NOARKSAK` | `N4.03.01a` (tidligere `N4.03.01`) |
| Journalpost | `JOURNPST` / `JOURNPOST` | `N4.04.01` |
| Avsender/mottaker | `AVSMOT` | `N4.05.01` |
| Dokumenttilknytning | `DOKLINK` | `N4.06.01` |
| Dokumentbeskrivelse | `DOKBESK` / `DOKBESKRIV` | `N4.06.11` |
| Dokumentrepresentasjon | `DOKVERS` / `DOKVERSJON` | `N4.06.21` |
| Merknad | `MERKNAD` | `N4.07.01` |

Kildene har ulike roller: offentlige Noark 4 DTD-er og historiske standardkrav beskriver navn/krav; arbeidsreferanser og eldre SQL-kontrollkataloger kan støtte manuell vurdering; **bare det konkrete uttrekkets `metadata.xml`** viser hvilke tabeller, nøkler og datatyper som faktisk er deklarert der. Ingen private SQL-kataloger eller leverandørmappinger er inkludert i kodepakken.

I dokumentkjeden må disse observerte målene holdes adskilt:

| Mål | Betydning |
| --- | --- |
| `document_link.count` | Antall koblingsrader mellom journalposter og dokumentbeskrivelser. |
| `document_description.count` | Antall dokumentbeskrivelser. |
| `document_representation.count` | Antall representasjoner (versjon × variant), ikke nødvendigvis unike dokumenter. |
| `document_version.count` | Unike dokument-/versjonskombinasjoner, **bare** når eksplisitt DISTINCT-kartlegging er godkjent. |

Spesielle faglige metrikker produseres bare når en valgt, godkjent adapter oppgir `standard_id: "noark4"`. `semantic_results` kan da inneholde `concept_id`, `metric_id`, `scope`, `method`, `value`, `state`, `source_table`, modell-/adapterhash og historisk SQL-ID. `not_measured` representeres med `value: null`, ikke tallet null. SQL-ID betyr referanse, **ikke** at historisk SQL er kjørt. Resultatet er et foreløpig faglig analysegrunnlag, ikke en komplett Noark 4.1-validering eller endelig DWM-importkontrakt.

En separat, historisk kommandolinjemodul kan fremdeles lage **private, ubekreftede** forslag fra en eksisterende QA-JSON uten ny radskanning:

```bat
py -3 -m siard_workflow.core.content_qa.ephorte_noark4 ^
  --qa-json "D:\rapporter\eksempel_innholdskontroll.json" ^
  --output-dir "D:\systeminformasjon\adapters\ephorte\noark4" ^
  --adapter-id ephorte_noark4_forslag_01
```

Dette er **ikke** et valg i den generiske GUI-dialogen. Forslagene er `proposed`, overskriver ikke eksisterende adaptere og gir ingen faglig verifikasjon. Historiske Noark 4-metrikker produseres når en eksplisitt adapter har `standard_id: "noark4"`; observerte tall forutsetter at nødvendige bindinger faktisk er godkjent og radkontrollert. Uten grunnlag skal `value` være `null` og `state` `not_measured`. Relasjonsforslag krever eksplisitte FK-er mot riktig foreldrenøkkel; tvetydige FK-er kan ikke automatisk velges. `required: true` må avgjøres faglig.

Ingen komplett Noark 4.1-kravmatrise, SQL-motor, kontroll mot produksjonssystem eller endelig DWM-evidensimport er etablert. Resultatet er pilot-/referansegrunnlag og krever fortsatt vurdering mot systemversjon og arkivskapers dokumentasjon.

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

QA leverer **PDF og JSON**, samt CSV for tabeller (`_tabeller.csv`), informasjonsbærere (`_informasjonsbaerere.csv`) og funn/avvik (`_avvik.csv`). Kartlegging gir også `_kartleggingsforslag.json`, `_kartleggingsforslag.csv`, `_fremmednokler.csv` og `_relasjonsforslag.csv`. Når en adapter er valgt, kommer `_adapter_bindinger.csv` og `_adapter_relasjoner.csv`. Tilgjengelige standardmetrikker kan gi `_faglige_metrikker.csv`. Alle filene får prefiks med SIARD-navn og kjøretidsstempel, og en kollisjon overskriver ikke tidligere rapporter.

Tabellenes faktiske schema-/tabellnavn og rapportenes referanser er teknisk evidens; private adapterfiler, rå nøkkelverdier og personidentifikatorer skal ikke pakkes inn i rapporten. JSON-resultatet inneholder modell-/adapter-ID og SHA-256, antall `approved`/`proposed`-bindinger og relevante kontrollstatusfelt, men ikke innholdet i den private adapterfilen.

Rapporten skal vise profil-ID, SHA-256 for modell/adapter der tilgjengelig, valgt kildetype, relevante kontrollvalg, antall og status. Fremdriften må ikke fremstille uverifiserte forslag som utførte kontrollresultater.

## Prosjektfiler, fullføringsstatus og ny kjøring

En fullført operasjon lagrer et øyeblikksbilde av innstillingene som faktisk ble kjørt (`completed_params`). Endrede innstillinger gjør at tidligere resultat ikke skal gjenbrukes som om de fortsatt gjaldt. Ferdigmarkeringen fjernes når parametre endres i den ordinære dialogen. Eldre `.siardwf`-prosjekter skal fortsatt kunne leses.

**Lagre prosjekt med nytt filnavn** skal gi en ny, frisk prosjektstatus med samme arbeidsflyt og innstillinger, uten å endre den gamle prosjektfilen eller slette eksisterende rapporter. Ved ny kjøring kan arbeidsflyten nullstilles eksplisitt med sirkelpilen ved «Kjør workflow». En eksisterende fullført operasjon skal ikke automatisk hoppes over når relevante parametre er endret.

Utdata for rapporter/logg/prosjekt følger appens etablerte plassering. Ingen dokumentasjonsopprydding skal endre disse stiene eller føre til ny vedvarende analysedatabase, BaseX-integrasjon eller ekstra automatisk radskanning.

## Bruk i GUI

1. Velg en SIARD-fil og legg til **Innhold → Innholdskontroll** som vanlig arbeidsflytoperasjon.
2. Velg **Kilde for innholdskontroll**: automatisk, utpakket mappe eller SIARD-fil.
3. Velg **Fagmodell** (standard: `saksarkiv`). Bruk eventuelt **Ressursmapper…** for å velge Decom-, KDRS- og systemadapterkataloger. Velg deretter en ekstern, gjennomgått **Systemadapter (JSON)** dersom faglige bindinger skal aktiveres.
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

CLI støtter `--domain`, `--adapter`, `--resources-root`, `--metadata-only`, `--skip-metadata-pk` og `--list-domains`, men ikke et generisk `--profile`-valg. For CLI-bruk med relativ adaptersti må `--resources-root` peke til ekstern systemadaptermappe. Dokumenterte returkoder er `0` godkjent, `1` program-/filfeil, `2` delvis kontrollert og `3` avvik.

## Test og regresjon

Kjør `test-innholdskontroll.bat` fra repositoryroten. Den skal kontrollere registrering av QA-operasjonen, relevante avhengigheter, enhetstester for innholdskontroll og Python-syntaks. Ved GUI-endringer testes dessuten praktisk via `start.bat` på Windows. Rapporter og adaptertolkning bør verifiseres mot syntetiske data før de brukes på reelle SIARD-er.

Viktige regresjonsområder:

- Skillet mellom teknisk fullføring og faglig vurdering.
- At tom streng, utelatt celle og `xsi:nil` ikke blandes.
- At `NULL`/duplikat i nøkkel ikke maskeres; statusfordeling og DISTINCT måles korrekt.
- At bare eksplisitt godkjente adapterbindinger brukes; foreslåtte bindinger er inaktive.
- At generiske fagbegreper **ikke** får leverandørspesifikke tabell-/feltnavn som aliaser (`inntutg`, `trans`), og at den sosiale domenemodellen har kategori `6-18`.
- At kildedata ikke endres, og at ingen person-/nøkkelverdier lekker til logg/CSV/PDF.
- At nye prosjektfiler, endrede parametre og gjenkjøring ikke feilaktig gjenbruker ferdigstatus.
- At de tre uavhengige ressursmappene bevarer tidligere Decom-innstilling og aldri importerer eller godkjenner adaptere automatisk.
- At valgte adaptere gjennomgås mot metadata uten at forslag blir aktivert.

## Begrensninger og videre arbeid

Det er ikke dokumentert at alle fagsystemer, Noark-versjoner, datafelter, statuser, kodeverk eller referanser er fullstendig kartlagt. Decom-/KDRS-maler er foreløpig referanser, ikke generell automatisk import. Ekte SIARD-eksport kan avvike fra produksjonsdatabasen. Bruk faglige kontrollkilder og eksplisitt mapping før konklusjoner trekkes.

En framtidig DWM-integrasjon må importere QA-resultat som **ekstern evidens** uten å overskrive egne autoritative målinger. Fysisk systemmapping, formelle Noark-krav og kontroll av dokument-/LOB-tilgjengelighet krever separate, dokumenterte utviklingssteg.
