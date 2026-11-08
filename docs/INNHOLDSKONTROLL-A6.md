# Innholdskontroll – a6

**Utviklingsversjon:** `v1.4.23-ikamr-04-a6`  
**Utgangspunkt:** `v1.4.23-ikamr-04-a5`, Git-commit `de23714ada08af08f3b854e09ab3e63ff21aed67` i `feature/innholdskontroll`.

## Formål

a6 retter feil funnet ved pilotkjøring av `1547_004 ephorte SIARD`: tabellen `dbo.LAGRFORMAT` har én tom streng i `LF_KODE` som feilaktig ble klassifisert som SQL `NULL` av a5. a6 rydder samtidig opp i fagmodellvelgeren og skiller status for vellykket kjøring fra faglig godkjenning.

## Endringer

- **Korrekt NULL-semantikk:** Et eksisterende, tomt XML-element (`<c1/>` eller `<c1></c1>`) leses som tom streng. En utelatt celle eller `xsi:nil="true"` leses som `NULL`. Dette gir ikke automatisk faglig godkjenning.
- **Primærnøkkelkontroll:** Tom streng på deklarert primærnøkkel rapporteres som `MERKNAD` (`metadata_pk_empty`) og får egen teller `pk_empty`. Faktisk `NULL` og dupliserte nøkler rapporteres fortsatt som `AVVIK`. Den nye telleren er med i tabell-CSV og JSON-oppsummeringen.
- **Fagmodell:** Standardmodellen er `saksarkiv`. Gammel Legacy/QA-mal kan ikke lenger velges i GUI eller CLI. Ingen faglige tabellkoblinger godkjennes automatisk.
- **GUI:** Parameterdialogen for innholdskontroll er bredere, med forbedret tekstbryting. De øvrige operasjonsdialogene beholder sin vanlige størrelse.
- **Status:** `DELVIS_KONTROLLERT` gir et vellykket *kjøringssteg* når selve kontrollen er gjennomført, men QA-status forblir `DELVIS_KONTROLLERT` og resultatet merkes `IKKE FAGLIG GODKJENT`. Faktiske avvik (`AVVIK`) eller tekniske feil gir fortsatt mislykket kjøringssteg.
- **Tester:** Eksisterende syntetiske testdata representerer nå `NULL` med `xsi:nil="true"`. Nye regresjonstester dekker tom streng, NULL, primærnøkkelmerknad og delvis kontroll.

## Installasjon og test

1. Pakk a6-delta-ZIP-en ut **direkte i roten av lokal a5-arbeidskopi** og overskriv filene.
2. Kjør eksisterende `test-innholdskontroll.bat` (enhetstester og syntakskontroll, **ikke installasjon**).
3. Kontroller at avslutningen viser `SLUTTSTATUS: OK` før commit.

**Ingen installasjons- eller patchskript er nødvendige.** Deltaen inneholder ferdig endrede filer og oppdaterte tester. Ingen sikkerhetskopi opprettes, og ingen filer i GitHub endres av ZIP-en.

## Ny pilotkontroll

Når lokale tester er OK, kjør én ny full innholdskontroll av `1547_004` med `saksarkiv`, radskanning og metadata-PK slått på. Forvent at `LAGRFORMAT` ikke lenger gir et `metadata_pk_null`-avvik for den tomme strengen. Uten godkjent systemadapter skal faglig status fortsatt være `DELVIS_KONTROLLERT`.

**Avgrensning:** Adapterforslag og tabellnavn gir ikke faglig godkjenning; verifisering av fremmednøkkeldata og ePhorte/Noark 4-relasjoner videreutvikles i a7.
