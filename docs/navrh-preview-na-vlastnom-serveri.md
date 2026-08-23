# `test.potravinator.cz` — náhľad `/navrh` na vlastnom serveri

Alternatíva k Netlify, ktorá nemá žiadne limity na plán ani na počet commiterov.
Beží to na vašom stroji, za vaším existujúcim basic authom, ako **druhá pm2 app**
na inom porte. Produkčná appka ani `main` sa nedotknú.

Toto musí spustiť niekto s SSH prístupom na `159.65.124.249`.

---

## Čo z toho vyplýva

| | súčasná produkcia | tento náhľad |
| --- | --- | --- |
| pm2 app | `foodmania` | `foodmania-navrh` |
| port | 3000 (predvolený) | **3001** |
| cesta | `/home/foodmania/foodmania-frontend` | `/home/foodmania/foodmania-navrh` |
| branch | `origin/main` | `feat/navrh-porovnani` |
| domena | `www.potravinator.cz` | `test.potravinator.cz` |

Sú to dva nezávislé procesy z dvoch nezávislých checkoutov. Nič spoločné okrem stroja.

---

## 1. DNS

Pridať A záznam:

```
test.potravinator.cz.   A   159.65.124.249
```

## 2. Checkout a build (na serveri, ako user `foodmania`)

```bash
cd /home/foodmania
git clone https://gitlab.com/johnysarkozi/foodmania-frontend.git foodmania-navrh
cd foodmania-navrh
git checkout feat/navrh-porovnani
```

Env súbor — `.env.local` ani `.env.production.local` nie sú v repe:

```bash
cat > .env.production.local <<'EOF'
NEXT_PUBLIC_REST_ENDPOINT=https://backend.potravinator.cz
NEXT_PUBLIC_REST_API_ENDPOINT=https://backend.potravinator.cz
NEXT_PUBLIC_CDN_BASE_URL=https://images.potravinator.cz
NEXT_PUBLIC_WEBSITE_URL=https://test.potravinator.cz
NEXT_PUBLIC_BASE_AUTH=
NEXT_PUBLIC_THUMBOR_SECURITY_KEY=
NEXT_PUBLIC_GOOGLE_API_KEY=
NEXT_PUBLIC_STRIPE_PUBLIC_KEY=
EOF
```

Build:

```bash
npm install --legacy-peer-deps   # rovnako ako produkčný post-deploy
npm run build
```

## 3. pm2

`ecosystem.navrh.config.js` v `/home/foodmania/foodmania-navrh`:

```js
module.exports = {
  apps: [
    {
      name: 'foodmania-navrh',
      cwd: '/home/foodmania/foodmania-navrh',
      script: 'node_modules/next/dist/bin/next',
      args: 'start -p 3001',
      instances: 1,
      exec_mode: 'fork',
      env: { NODE_ENV: 'production', PORT: 3001 },
    },
  ],
};
```

```bash
pm2 start ecosystem.navrh.config.js
pm2 save
```

Overenie, že appka odpovedá lokálne:

```bash
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:3001/navrh   # ma byt 200
```

## 4. nginx vhost

`/etc/nginx/sites-available/test.potravinator.cz`:

```nginx
server {
    listen 80;
    server_name test.potravinator.cz;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name test.potravinator.cz;

    ssl_certificate     /etc/letsencrypt/live/test.potravinator.cz/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/test.potravinator.cz/privkey.pem;

    # rovnaky basic auth ako na www — over si cestu k htpasswd
    # v existujucom vhoste www.potravinator.cz
    auth_basic           "Restricted Access";
    auth_basic_user_file /etc/nginx/.htpasswd;

    location / {
        proxy_pass         http://127.0.0.1:3001;
        proxy_http_version 1.1;
        proxy_set_header   Upgrade $http_upgrade;
        proxy_set_header   Connection 'upgrade';
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
    }
}
```

```bash
ln -s /etc/nginx/sites-available/test.potravinator.cz /etc/nginx/sites-enabled/
certbot --nginx -d test.potravinator.cz      # ak certbot uz na stroji je
nginx -t && systemctl reload nginx
```

## 5. Hotovo

**https://test.potravinator.cz/navrh**

---

## Aktualizácia po zmene v kóde

```bash
cd /home/foodmania/foodmania-navrh
git pull
npm install --legacy-peer-deps
npm run build
pm2 reload foodmania-navrh
```

Toto sa dá zautomatizovať (GitLab CI s deploy keyom alebo `pm2 deploy`), ale
až keď bude základ bežať.

---

## Čo som nemohol overiť

Na ten stroj sa nedostanem, takže tieto veci treba na mieste potvrdiť:

- **cesta k `.htpasswd`** — vyššie je odhad; skutočnú nájdete v existujúcom
  vhoste pre `www.potravinator.cz` (`grep -r auth_basic_user_file /etc/nginx/`)
- **či je na stroji certbot** a ako sú certifikáty spravované
- **či je port 3001 voľný** (`ss -ltnp | grep 3001`)
- **skutočný port produkčnej appky** — `ecosystem.config.js` ho nenastavuje,
  takže beží na predvolenom 3000; ak nie, prispôsobte
- **verzia Node na serveri** — projekt potrebuje >= 18.17, odporúčam 22

## Známé limity a co by chtělo backend

Tyhle věci na `/navrh` nejdou dořešit jen na frontendu:

- **Historie cen se stahuje po produktech.** `GET /product_price_histories/{productId}`
  je custom route pro jeden produkt; kolekce `/product_price_histories` neexistuje
  (vrací 404), takže nejde načíst historii pro celý seznam jedním dotazem.
  Frontend historii tahá se seznamem (limit 40 položek) — potřebuje ji
  jak graf, tak odznak měsíční změny v řádku a datum platnosti cen.
  Pro seznam o 20 položkách to je 20 dotazů. Řešením by byl filtr na
  kolekci, např. `GET /product_price_histories?product.id[]=1&product.id[]=2`.

- **Odkazy na produkty se musí dotahovat po jedné.** Embedované varianty
  v `GET /shopping-lists/{id}/shopping-list-rows` neobsahují `url` — jen
  `/product_variants` ho vrací (a to u 100 % variantů, měřeno na 976
  variantech z 5 obchodů). Dotáhnout je hromadně nejde:
  `?id=46570` se ignoruje a vrátí celou kolekci, `?product.id[]=…` nevrátí nic
  a opakovaný `?product.id=A&product.id=B` si nechá jen poslední.
  Navíc to nelze vzít ani po produktu: nahrazený sloupec nese variantu
  *jiného* produktu, takže `?product.id=` ji nedohledá. Zbývá tedy
  `GET /product_variants/{variantId}`, jeden dotaz na odkaz. Řešením by bylo
  buď přidat `url` do embedovaných variantů v řádcích seznamu, nebo zapnout
  filtr na kolekci (`?id[]=` / `?product.id[]=`).

- **Účtenka / PDF → seznam.** Import z textu funguje na frontendu (uživatel
  vloží řádky, ty se párují proti katalogu). Fotka nebo PDF účtenky vyžaduje
  OCR, tedy serverovou službu — např. `POST /receipts` s obrázkem, která vrátí
  rozpoznané řádky, a ty už frontend umí spárovat stejnou logikou jako
  vložený text.

- **Katalogy si neshodnou názvy produktů.** Pro jednu vaničku Flory vrací
  Košík `name: "Light"` s značkou jen v `manufacturer`, Rohlík
  `"Flora Light"`, Tesco `"Flora Light 400g"`. Někde je v `manufacturer`
  doslova `unknown` nebo prázdno, a někde si `name` a `unitValue`
  protiřečí (`"...405g"` na variantě s `unitValue: 400`). Frontend to
  skládá do jednoho titulku sám (`productTitle()` v `navrh-shared.tsx`),
  ale správně by to patřilo do dat.

- **Backend radši nabídne náhradu, než by nechal prázdno.** I u nepotraviny
  (kabel Lightning) vrátí `to-replace` sloupec pro všech 5 obchodů. Vetev
  „tento obchod položku nemá“ se tím prakticky nedá vyvolat.

- **`GET /countries/{id}/categories` vrací 500** při hlavičce
  `Accept: application/json`. Funguje jen `application/ld+json`. Frontend to
  obchází explicitním přepsáním hlavičky u tohohle jednoho dotazu, ale je to
  chyba na backendu.
