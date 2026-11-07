# Generiske fag- og modulmodeller (a4, arbeidsutkast)

Denne katalogen inneholder **ingen kundedata, ePhorte- eller Familia-mapping**.
Den er skrivebeskyttet og brukes av innholdskontroll for aa bygge en
konseptuell QA-profil. Selve SIARD-databasen analyseres foerst med manuelt
verifisert ekstern adapter.

- `index.json`: eneste inngang for registrerte moduler, domener og taksonomi.
- `common/*.json`: gjenbrukbare faglige moduler og informasjonsbaerere.
- `domains/*.json`: sammensetning av moduler for et fagomraade.
- `taxonomies/kommunale_systemkategorier.json`: 9 ASTA/KAISA-hovedkategorier
  og 20 kommunale kategorier fra `0000-kommune-elarkiv.xlsx` (2020).

Alle domener har `status=draft` og er IKKE godkjente, fullstendige
fagspesifikasjoner. Kategori er ikke det samme som systemprodukt,
uttaksformat eller lov-/standardversjon.

Mer dokumentasjon: `docs/INNHOLDSKONTROLL-A4-MODELLER-OG-ADAPTERE.md`.
