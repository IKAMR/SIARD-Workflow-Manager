# Generiske fag- og modulmodeller

Dette modellbiblioteket er en **versjonert, skrivebeskyttet samling av konseptuelle fagmodeller** for SIARD innholdskontroll. Det inneholder ingen kundedata, leverandørspesifikke tabell-/kolonnemappinger eller private Decom-/KDRS-maler. Fagmodellene er arbeidsutkast, ikke normative kravlister eller beskrivelser av fysiske databaser.

- `index.json`: eksplisitt indeks over moduler, domener og taksonomi.
- `common/*.json`: 12 generiske moduler, inkludert `social_register` for sosialfaglige begreper.
- `domains/*.json`: syv domenemodeller: saksarkiv, barnevern, skole, PPT, helsetjeneste, pleie/omsorg og sosialtjeneste.
- `taxonomies/kommunale_systemkategorier.json`: ni ASTA/KAISA-hovedkategorier og 20 kommunale kategorier (historisk klassifikasjonsgrunnlag fra 2020).
- `standards/noark4_saksarkiv_reference.json`: offentlig Noark 4-navnereferanse; ingen automatisk eller verifisert ePhorte-mapping.

En kategori er ikke det samme som et systemprodukt, en godkjent fagmodell eller en bestemt standardversjon. For faktisk faglig kontroll kreves en separat, eksplisitt valgt og gjennomgått JSON-systemadapter **utenfor repositoryet**. Bindinger med `review_status: proposed` aktiveres aldri automatisk. Metadata-treff mot en adapter gir heller ikke faglig godkjenning.

Tre uavhengige lokale ressursmapper kan velges for Decom/SIARDMapper, KDRS Søk & Vis og systemadaptere. De legges ikke under `siard_workflow/models/` og importeres ikke automatisk.

Full beskrivelse av modellene, adapterkontrakten, ressursmapper, kontrollstatuser og rapporter: [`docs/INNHOLDSKONTROLL.md`](../../docs/INNHOLDSKONTROLL.md).
