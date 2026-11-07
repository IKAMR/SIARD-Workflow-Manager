# Innholdskontroll a4: felles fagmodeller og eksterne systemadaptere

**Versjon:** v1.4.23-ikamr-04-a4  
**Gren:** feature/innholdskontroll  
**Status:** Pilot; ikke komplett ePhorte-/Noark- eller fagsystemvalidering.

## Maal

Separere (a) fagomraade, (b) delte fagmoduler, (c) leverandor-/systemmapping
og (d) faktisk SIARD-uttrekk. Kjernefunksjonene fra a1-a3 er uendret og kan
fortsatt brukes med gammel `profile_file` eller standard ePhorte-kartleggingsmal.

Den nye modellen ER IKKE en databasestruktur eller normativ Noark-modell.
Verifisering av felt, koder, krav og relasjoner skjer i senere utviklingssteg.

## Innebygd modellbibliotek

- `siard_workflow/models/index.json`: manuell, versjonert indeks.
- `siard_workflow/models/taxonomies/kommunale_systemkategorier.json`:
  9 ASTA/KAISA-kategorier, 20 kommunale kategorier fra regnearket
  `0000-kommune-elarkiv.xlsx` (Kategorier, 15.05.2020).
- `siard_workflow/models/common/`: 10 generiske moduler, inkludert person,
  kontaktinformasjon, klientregister, sak, registrering/journalpost,
  hendelseslogg, dokumentkjede, filreferanse, tilgang og tjenester/tiltak.
- `siard_workflow/models/domains/`: 7 forelopige sammensetninger:
  `saksarkiv`, `barnevern`, `skole`, `ppt`, `helsetjeneste`, `pleie_omsorg`,
  `sosialtjeneste`.

De ovrige 13 kommunale kategoriene er registrert i taksonomien, men har
IKKE en domenemodell ennaa. Ikke-forankrede fagregler skal ikke opprettes
for aa fylle ut antallet. Hvert fagbegrep er en observasjonskategori, og
ikke alle slike begreper har egen fysisk tabell.

## Eksternt, privat fagressursbibliotek

Velg selv rotmappe under `Innhold -> Innholdskontroll -> Fagressursbibliotek`.
Mappen maa eksistere. Programmet oppretter eller endrer ingenting der.
Eksempel (valgfri sti, ikke hardkodet):

```text
F:/arkiv-fagressurser/
  templates/
    decom/
    kdrs-sok-og-vis/
  adapters/
    ephorte/
    familia/
  vendor-documentation/
```

Decom- og KDRS-maler registreres her som originalt referansemateriale.
**A4 leser ikke eller tolker ikke disse malfilene automatisk.** En egen
importer kan utvikles senere etter at filformatene er analysert.

## Adapterkontrakt

En adapter er en separat, eksplisitt valgt JSON-fil under `adapters/` (eller
valgt med full sti). Den inneholder produktspesifikke tabell- og feltbindinger.
Adaptere kan vaere interne eller offentlige og skal IKKE automatisk kopieres
inn i GitHub eller rapporten. Et syntetisk eksempel ligger i
`docs/examples/synthetic_saksarkiv_adapter.json`.

```json
{
  "format_version": 1,
  "id": "example_only",
  "label": "Syntetisk eksempel",
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

`approved`: Operatorkontrollert binding er eksplisitt aktivert.
`proposed`: Forslag, aldri automatisk aktivert. En godkjent binding krever
fysisk `source` og minst ett `key`-felt. Adaptere har ingen SQL/Python-
uttrykk eller dynamisk kjoring; JSON-feltene blir validert strengt.
Det aa skrive `approved` er en erklaering i adapteren, ikke et kryptografisk
bevis eller en automatisk depotgodkjenning.

A4 bygger en midlertidig a1-QA-profil fra godkjente bindinger; den leser
uttrekket med den eksisterende skrivebeskyttede QA-motoren. Alle ubundne
fagbegreper blir staaende som `IKKE_KONTROLLERT`, ikke som null eller OK.

## Valg i GUI

1. Under `Innholdskontroll`: Velg `Fagmodell` (eller behold
   `Eksisterende QA-mal` for 100 % kompatibel a3-kjoring).
2. Velg eventuelt en eksisterende `Fagressursbibliotek`-mappe.
3. Velg eventuelt en privat `Ekstern systemadapter (JSON)`.
4. Velg `Kilde for innholdskontroll` (automatisk/utpakket/fil) slik som a3.
5. For bare modellforslag: sett `Tell og kontroller alle tabellrader = Nei`.
6. `Gammel QA-mal` og fagmodell/adapter kan ikke kombineres (klar feil).

Adapter med `domain_id` kan velges uten at fagmodell er valgt; domenet
bestemmes da fra adapteren. Valgt fagmodell som ikke stemmer med adapterens
`domain_id` gir feil, aldri stille omkobling.

## CLI

```bat
py -3 -m siard_workflow.core.content_qa --list-domains
py -3 -m siard_workflow.core.content_qa "D:\\uttrekk\\eksempel.siard" --domain saksarkiv --metadata-only
py -3 -m siard_workflow.core.content_qa "D:\\uttrekk\\eksempel.siard" --domain saksarkiv --adapter "F:\\arkiv-fagressurser\\adapters\\ephorte\\mapping.json"
```

A4 beholder den eldre `--profile`-parameteren til gamle malfiler. Et ferdig
adapteroppsett maa verifiseres mot en konkret SIARD-versjon og tilhorende
systemdokumentasjon foer bruk. Datoer/statuskolonner kan inneholde sensitive
opplysninger; ikke velg person- eller fritekstfelt som statusfelt.

## Rapporter/proveniens

Eksisterende JSON-, CSV- og PDF-filer produseres som i a3. Ny `model_context`
i JSON inneholder `domain_id`, `category_code`, `module_ids`, SHA-256 for
modellen og valgt adapter, adapter-ID, antall godkjente/ubekreftede bindinger.
Resultatet inneholder **ikke** den private adapterfilen eller lokal full sti,
men de eldre QA-rapportene viser fortsatt SIARDs faktiske schema-/tabellnavn.
Dette er IKKE en ferdig portabel DWM-evidenskontrakt: separat integrasjonssteg
maa definere scope, identiteter og semantisk maaleekvivalens.

## Pakking/test

`packaging/siard_manager.spec` inkluderer naa `siard_workflow/models/` for
PyInstaller. Kjor `test-innholdskontroll.bat` fra repositoryroten. Den nye
`test_content_qa_models.py` dekker kategori-, modul-, adapter- og kildelogikk
med kun syntetiske SIARD-data. Ekte Windows GUI og EXE-bygg maa valideres
paa utviklingsmaskin. Ingen endringer foretas i uttrekk eller private maler.
