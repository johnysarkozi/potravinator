# Netlify náhľad `/navrh` a napojenie na backend

**Náhľad:** https://potravinator-navrh.netlify.app/navrh
**Admin:** https://app.netlify.com/projects/potravinator-navrh
**Zdroj:** `gitlab.com/johnysarkozi/foodmania-frontend`, vetva `feat/navrh-porovnani`.
Každý push na túto vetvu Netlify nasadí sám (~2 minúty).

## Ako sa náhľad dostane k backendu

Frontend nevolá backend priamo, ale cez proxy na tej istej doméne:

```
prehliadač → potravinator-navrh.netlify.app/api-proxy/…
           → (server Netlify) → https://backend.potravinator.cz/…
```

Nastavené v `netlify.toml` na vetve `feat/navrh-porovnani`:

- `NEXT_PUBLIC_REST_ENDPOINT = "/api-proxy"` (a to isté pre `NEXT_PUBLIC_REST_API_ENDPOINT`)
- presmerovanie `/api-proxy/*` → `https://backend.potravinator.cz/:splat`, status 200 (rewrite)

Proxy je tam kvôli CORS: backend posiela `access-control-allow-origin` len pre
`www.potravinator.cz` a `localhost:3000`, takže priame volanie z `*.netlify.app`
by prehliadač zablokoval.

**Dôsledok:** frontend nie je „napojený" na konkrétny backend, ale na adresu.
Keď sa na `backend.potravinator.cz` nasadí nový backend s rovnakým API, náhľad
s ním komunikuje hneď, bez zmeny kódu. Ak nový backend beží na inej adrese,
stačí zmeniť cieľ presmerovania v `netlify.toml`.

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

Overené proti mocku v prehliadači, nie proti novému backendu — vývojové
prostredie Claude Code sa na `*.potravinator.cz` nedostane (sieťová politika
prostredia). Ak má nový backend iné API (iné endpointy alebo tvar dát), treba
jeho OpenAPI špecifikáciu (`/docs.jsonopenapi`) alebo prístup k repu.

## Čo ešte ostáva natvrdo (mimo `/navrh`)

Pôvodný kód živej appky:

- `src/components/shopping-list/header-shopping-list.tsx` — päť obchodov natvrdo
- `src/components/ui/exportPdf/shopping-list/template-pdf-header.tsx` — päť
  obchodov natvrdo a **iné priradenie ID** (1 = Rohlík, všade inde 1 = Billa),
  takže PDF export mohol mať obchody poprehadzované už predtým
