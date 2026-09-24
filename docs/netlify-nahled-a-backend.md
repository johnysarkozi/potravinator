# Netlify náhľad `/navrh` a napojenie na backend

> **Aktuálne (od 22. 9. 2026):** produkčné API je **`https://foodmania.inovent.sk`**,
> obrázky (Thumbor, bez podpisového kľúča, `/unsafe/…`) na
> **`https://foodmania-img.inovent.sk`**. Podľa autora backendu je kontrakt 1:1
> so starým; ako schéma stále platí starý OpenAPI
> `https://backend.potravinator.cz/docs.jsonopenapi` (s `Accept: */*` alebo
> `application/vnd.openapi+json` — na `application/json` vracia 406).
> `backend.potravinator.cz` a `images.potravinator.cz` ešte bežia, ale so
> **starými dátami** — nemiešať. Staré nákupné zoznamy sa nepreniesli.
> Nová verzia nie je API Platform, `/docs.jsonopenapi` na novom API nie je.
>
> Zlú náhradu alebo zle spárované produkty hlásiť autorovi backendu s **ID
> nákupného zoznamu** — zapracuje ich do učenia párovania.

**Náhľad:** https://potravinator-navrh.netlify.app/navrh
**Admin:** https://app.netlify.com/projects/potravinator-navrh
**Zdroj:** `gitlab.com/johnysarkozi/foodmania-frontend`, vetva `feat/navrh-porovnani`.
Každý push na túto vetvu Netlify nasadí sám (~2 minúty).

## Ako sa náhľad dostane k backendu

Frontend nevolá backend priamo, ale cez proxy na tej istej doméne:

```
prehliadač → potravinator-navrh.netlify.app/api-proxy/…
           → (server Netlify) → https://foodmania.inovent.sk/…
```

Nastavené v `netlify.toml` na vetve `feat/navrh-porovnani`:

- `NEXT_PUBLIC_REST_ENDPOINT = "/api-proxy"` (a to isté pre `NEXT_PUBLIC_REST_API_ENDPOINT`)
- presmerovanie `/api-proxy/*` → `https://foodmania.inovent.sk/:splat`, status 200 (rewrite)
- `NEXT_PUBLIC_CDN_BASE_URL = "https://foodmania-img.inovent.sk"` (to isté aj v Netlify → Environment variables)

Proxy vznikla kvôli CORS (starý backend povoľoval len `www.potravinator.cz` a
`localhost:3000`). Nový backend má CORS doplnené, ale proxy ostáva: presun API
je potom zmena jedného riadku a náhľad nezávisí od nastavenia CORS.

**Dôsledok:** frontend nie je „napojený" na konkrétny backend, ale na adresu.
Presun API = zmeniť cieľ presmerovania v `netlify.toml` (a CDN premennú), push.
`NEXT_PUBLIC_*` sa zapekajú pri builde, samotná zmena premennej bez nového
buildu nestačí.

## Nový backend (september 2026)

Kolega nasadil úplne nový backend s novou databázou a iným zoznamom obchodov.
Frontend na to bol pripravený zle na troch miestach — opravené v commite
`e513ad8`:

| Problém | Príčina | Oprava |
| --- | --- | --- |
| Zoznam obchodov sa nezmenil | `/navrh` bral názvy a farby podľa ID (1 = Billa…), a tie prebili API | Tabuľka značiek podľa **názvu** reťazca; ktoré obchody existujú, určuje API |
| Živá časť appky ukazovala staré obchody | `AvailableShopsProvider` veril localStorage cache 24 h bez opýtania servera | Cache len pre prvé vykreslenie, server sa pýta vždy |
| „Treba premazať localStorage" | Uložené `userId` a `navrhShoppingListId` patria starej databáze | `ensureList()` overí zoznam, pri 400/401/403/404/410/422 založí nový; odmietnutého používateľa nahradí |
| Ukážkový nákup nič nepridal | ID produktov zo starej databázy | Keď ID nesedí (overené podľa názvu), hľadá sa podľa názvu |

Overené proti mocku v prehliadači, nie proti živému API — vývojové prostredie
Claude Code sa na `*.inovent.sk` ani `*.potravinator.cz` nedostane (sieťová
politika prostredia; povoliť v nastaveniach prostredia → Network access).
Prepnutie na `foodmania.inovent.sk` je v commite `d9bf518`.

## Čo ešte ostáva natvrdo (mimo `/navrh`)

Pôvodný kód živej appky:

- `src/components/shopping-list/header-shopping-list.tsx` — päť obchodov natvrdo
- `src/components/ui/exportPdf/shopping-list/template-pdf-header.tsx` — päť
  obchodov natvrdo a **iné priradenie ID** (1 = Rohlík, všade inde 1 = Billa),
  takže PDF export mohol mať obchody poprehadzované už predtým
