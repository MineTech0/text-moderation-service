
# Tekstipohjainen moderointiservice – määrittelydokumentti

## 1. Tavoite

Toteuttaa kevyt, tuotantokelpoinen **tekstimoderointipalvelu**, joka:

- vastaanottaa viestin ja sen id:n sekä callback-URL:n
- käsittelee viestin taustalla (jono + worker)
- tekee päätöksen `allow | flag | block`
- kutsuu annetun webhook-endpointin moderointituloksella
- tukee **suomea ja englantia**
- yhdistää:
  - kovatasoisen **sanalistapohjaisen filtterin**
  - **pienen monikielisen toksisuusmallin** (CPU-only)
- mahdollistaa **mallin helpon vaihtamisen konfiguraatiolla**
- lataa **sanalistat ensimmäisellä käynnistyksellä** (ja käyttää niitä muistista jatkossa).

---

## 2. Toiminnalliset vaatimukset

1. **Viestin moderointi**
   - Palvelu vastaanottaa viestitekstin (string), viestin id:n (string) ja `callback_url`:n.
   - Palvelu palauttaa heti HTTP 200 -vastauksen, jossa kerrotaan että pyyntö on jonossa.
   - Varsinainen moderointipäätös tehdään asynkronisesti jonosta.
   - Moderoinnin tulos lähetetään **POST-kutsuna** `callback_url`:iin.

2. **Moderointipäätös**
   - Päätösvaihtoehdot:
     - `allow` – hyväksytty
     - `flag` – epäilyttävä, esim. näytetään käyttäjälle varoitus tai lähetetään kevyempään moderointijonoon
     - `block` – sisältö estetään tai ohjataan manuaaliseen tarkistukseen
   - Päätöksen perusteet:
     - kovatasoinen sanalista (suomi + englanti)
     - toksisuusmallin antama pistemäärä (0–1)
   - Palvelu palauttaa myös perustiedot syystä:
     - `badword` (bool)
     - `toxicity_score` (float)
     - `model_label` (esim. `toxic` / `non-toxic` / mallikohtainen label)

3. **Mallin vaihdettavuus**
   - Moderointimalli (Hugging Face tms.) on **pluggable**:
     - konfiguroitava mallin nimi (ympäristömuuttuja)
     - mallin lataa ja kapseloi erillinen **ModelAdapter**-kerros
   - Uusi malli pystytään ottamaan käyttöön:
     - muuttamalla configia
     - käynnistämällä palvelu uudelleen
   - Rajapinta ModelAdapterille pysyy samana (esim. `score_toxicity(text: str) -> (score: float, label: str)`).

4. **Sanalistojen lataaminen**
   - Palvelu lataa **ensimmäisellä käynnistyksellä** suomen- ja englanninkieliset sanalistat:
     - lähde-URL:t määritellään konfiguraatiossa (esim. LDNOOBW / LDNOOBWV2)
     - listat tallennetaan paikallisesti (esim. `data/badwords_fi.txt`, `data/badwords_en.txt`)
   - Seuraavilla käynnistyksillä:
     - jos tiedostot löytyvät levyllä, niitä käytetään suoraan
     - haluttaessa voidaan määritellä TTL tai “päivitä lista jos X päivää vanha” (nice-to-have).

5. **Tekstin normalisointi ja kiertoyritysten käsittely**
   - Palvelu normalisoi tekstiä ennen sanalistatarkistusta:
     - lowercasetus
     - leet-mapping (0→o, 1→i, 3→e, 4→a, 5→s, 7→t, @→a, $→s)
     - turhien symbolien poisto
     - pitkien toistojen typistys (esim. `viiiittu` → `viittu`)
     - mahdollisuus etsiä sanoja myös **tiivistetystä muodosta** (poistetaan välilyönnit/symbolit → `v i t t u` → `vittu`)
   - Palvelu tunnistaa ja estää tyypillisiä kirosanojen kiertotapoja.

6. **Triviaalien viestien käsittely**
   - Jos viesti on “triviaali” (esim. tyhjä, vain whitespacea, yksi merkki), moderointi voi:
     - palauttaa `allow`, syyllä `model_label="trivial"`, `toxicity_score=0.0`, `badword=False`
   - Triviaalisuuden raja-arvo on konfiguroitavissa (esim. `len(stripped) < 2`).

---

## 3. Ei-toiminnalliset vaatimukset

1. **Suorituskyky**
   - Palvelu toimii CPU-only ympäristössä (Hetzner VPS, ei GPU).
   - Tavoite: vähintään kymmeniä viestejä sekunnissa pienellä/matalalla latenssilla (mallista riippuen).
   - Mallin koko: tyypillisesti ≤ ~500 MB (mieluiten 50–200 MB). Liian suuret mallit eivät sovellu.

2. **Saatavuus**
   - Palvelu pyörii jatkuvasti; käynnistyy automaattisesti uudelleen (esim. systemd, Docker, orkestrointi).
   - Sanalistojen lataus/käynnistys ei saa estää appia liian pitkäksi aikaa (timeoutit, virheenkäsittely).

3. **Skalautuvuus**
   - Alkuvaiheessa riittää yksinkertainen **in-memory jono + yksi worker-thread**.
   - Jatkossa voidaan:
     - siirtyä Redis/RabbitMQ-jonoon
     - ajaa useita worker-prosesseja skaalautumisen tarpeen mukaan
     - erottaa API-palvelu ja worker-palvelu eri prosesseihin/podeihin.

4. **Luotettavuus**
   - Jos `callback_url`-kutsu epäonnistuu:
     - tehdään konfiguroitava määrä retry-yrityksiä (esim. 3 kertaa backoffilla)
     - epäonnistuneet pyynnöt logitetaan ja mahdollisesti siirretään dead-letter-järjestelmään (tiedosto / Redis-lista tms.).
   - Palvelu ei saa kaatua yksittäisen viestin virheestä.

5. **Observability**
   - **Lokitus:**
     - sisääntulevat pyynnöt (id, ei koko tekstiä, ellei debug-tila)
     - päätös (id, decision, syyt)
     - callback-onnistumiset ja virheet
   - **Metriikat (Prometheus tms.):**
     - pyyntöjen määrä / sekunti
     - jonon pituus
     - päätösten jakauma (allow/flag/block)
     - mallin inferenssin latenssi
     - callback-onnistumisprosentti / -latenssi

---

## 4. Arkkitehtuuri

### 4.1 Komponentit

1. **FastAPI-sovellus**
   - Vastaanottaa HTTP-pyynnöt.
   - Tarjoaa:
     - `POST /moderate` (päärajapinta)
     - `GET /healthz` (elossa)
     - `GET /readyz` (valmis, malli ladattu, sanalistat ladattu)
   - Lisää moderointipyynnön sisäiseen jonoon.

2. **Jono**
   - Pythonin `queue.Queue` tai vastaava abstraktio.
   - Pyyntötyyppi sisältää:
     - `id: str`
     - `text: str`
     - `callback_url: str`

3. **Worker**
   - Erillinen taustalla pyörivä säie tai prosessi.
   - Loopeaa jonon yli:
     - hakee pyynnön
     - ajaa moderointilogiikan
     - kutsuu `callback_url`:ia tuloksella.

4. **Moderointimoottori (ModerationEngine)**
   - Vastaa:
     - trivial voiko skipata
     - sanalistatarkistus
     - mallin kutsuminen ModelAdapterin kautta
     - heuristiikat (thresholdit → decision)
   - Rajapinta esim.:
     - `def moderate(request: ModerateRequest) -> ModerationResult`

5. **ModelAdapter-kerros**
   - Abstraktio mallista; mahdollistaa mallinvaihdon ilman että muu koodi muuttuu.
   - Esim. protokolla:

     ```python
     class BaseModelAdapter(Protocol):
         def score(self, text: str) -> tuple[float, str]:
             """Palauttaa (score, label). Score 0–1, label mallin labelina."""
     ```

   - Toteutuksia:
     - `HuggingFacePipelineAdapter(model_name: str, device: int = -1)`
     - mahdollisesti eri mallit, esim. `SimpleKeywordAdapter` (testausta varten).

6. **WordlistLoader**
   - Vastaa sanalistojen lataamisesta:
     - tarkistaa, löytyvätkö paikalliset tiedostot
     - jos eivät löydy:
       - lataa ne konfiguroiduista URL-osoitteista
       - tallentaa levylle
     - lukee tiedostot muistiin `set[str]`-rakenteiksi.
   - Varmistaa että tämä tehdään vain kerran käynnistystä kohden (singleton/once).

---

## 5. API-määrittely

### 5.1 `POST /moderate`

**Kuvaus:**  
Lisää moderointipyyntö jonoon ja palauttaa heti “queued”-tilan.

**Request body (JSON):**

```json
{
  "id": "string",
  "text": "string",
  "callback_url": "https://example.com/moderation-callback"
}
```

- `id`: viestin uniikki tunniste (string, max esim. 255 merkkiä)
- `text`: käyttäjän viesti (string)
- `callback_url`: validi HTTPS-URL (suositus) johon tulos POSTataan

**Response 200 (application/json):**

```json
{
  "status": "queued",
  "id": "string"
}
```

Virhetilanteet (esim. validointivirheet):

- 400 Bad Request – virheellinen JSON / validointi
- 422 Unprocessable Entity – esim. epäkelpo `callback_url`

---

### 5.2 Callback payload

Worker lähettää moderoinnin tuloksen **POST**-pyyntönä `callback_url`:iin.

**Request (palvelulta asiakkaan callbackiin):**

`POST {callback_url}`  
`Content-Type: application/json`

Body (JSON):

```json
{
  "id": "string",
  "text": "string",
  "decision": "allow",
  "reason": {
    "badword": false,
    "toxicity_score": 0.12,
    "model_label": "non-toxic"
  }
}
```

- `id`: sama kuin alkuperäisessä pyynnössä
- `text`: alkuperäinen viesti (tai halutessa voi jättää pois konfiguraatiolla; privacy)
- `decision`: `"allow" | "flag" | "block"`
- `reason`:
  - `badword`: `true` jos osuma kovaan sanalistaan
  - `toxicity_score`: `0.0–1.0` mallin antama pistemäärä
  - `model_label`: mallin tuottama label (vapaa teksti)

**Asiakkaan palvelun vastauksen odotukset:**

- 2xx (esim. 200 / 204) = ok
- 4xx/5xx = virhe → moderointiservice yrittää `N` uudelleenyritystä backoffilla

---

### 5.3 Healthcheckit

#### `GET /healthz`

- Tarkistaa että sovellus on elossa (prosessi pyörii).
- Ei välttämättä vaadi mallin tai sanalistojen olevan ladattuja.
- Vastaa esim.:

```json
{
  "status": "ok"
}
```

#### `GET /readyz`

- Tarkistaa, että:
  - sanalistat ovat ladattuna muistiin
  - malli on alustettu
  - worker on käynnissä
- Jos jokin näistä puuttuu → palauttaa esim. 503.

---

## 6. Moderointilogiikka

### 6.1 Triviaalit viestit

- `is_trivial(text: str) -> bool`  
  - esim. `len(text.strip()) < TRIVIAL_LENGTH_THRESHOLD`  
  - default: 2 merkkiä

Jos triviaalinen:

- `decision = "allow"`
- `reason.badword = False`
- `reason.toxicity_score = 0.0`
- `reason.model_label = "trivial"`

### 6.2 Sanalistatarkistus

1. Teksti normalisoidaan:

   - lowercasetus
   - leet-mapping: `0→o, 1→i, 3→e, 4→a, 5→s, 7→t, @→a, $→s`
   - zero-width-merkkien poisto
   - toistojen typistys (`(.){2,} → `)

2. Luodaan kaksi näkymää:

   - token-pohjainen:
     - regex: `[a-zA-ZåäöÅÄÖ]+`
     - tarkistetaan, onko kukin token `BADWORDS`-setissä
   - “squashed”:
     - poistetaan kaikki mitä ei ole kirjaimia (`[^a-zA-ZåäöÅÄÖ]+ → ""`)
     - tarkistetaan, sisältääkö tämä string **minkä tahansa** `BADWORDS`-sanan substringinä

3. Jos osuma:

   - `badword = True`

### 6.3 Mallin score

- `ModelAdapter.score(text)` → `(score: float, label: str)`

Esimerkki heuristiikasta (konfiguroitavat thresholdit):

- `BLOCK_THRESHOLD` (esim. 0.9)
- `FLAG_THRESHOLD` (esim. 0.7)

Päätöslogiikka:

1. Jos `badword == True`  
   → `decision = "block"`

2. Muuten:
   - jos `score > BLOCK_THRESHOLD` → `block`
   - elif `score > FLAG_THRESHOLD` → `flag`
   - else → `allow`

---

## 7. Mallin vaihdettavuus

### 7.1 Konfigurointi

Ympäristömuuttujat (esimerkki):

- `MODEL_BACKEND` – esim. `huggingface_pipeline`
- `MODEL_NAME` – esim. `"textdetox/xlmr-large-toxicity-classifier"`
- `MODEL_DEVICE` – oletus `-1` (CPU)

### 7.2 ModelAdapter

Abstrakti rajapinta:

```python
class BaseModelAdapter(Protocol):
    def score(self, text: str) -> tuple[float, str]:
        """Palauttaa (score, label).
        Score 0–1, label mallikohtainen merkkijono."""
```

Hugging Face -implementaatio:

```python
class HuggingFacePipelineAdapter(BaseModelAdapter):
    def __init__(self, model_name: str, device: int = -1):
        self._pipe = pipeline("text-classification", model=model_name, device=device)

    def score(self, text: str) -> tuple[float, str]:
        out = self._pipe(text)[0]
        label = out["label"]
        score = float(out["score"])
        # Normalisoi score 0–1 välille jos mallin output on “toxic/non-toxic”
        # (esim. jos label == 'toxic' → score, muussa tapauksessa 1-score)
        return score, label
```

Moderointimoottori käyttää vain `BaseModelAdapter`-rajapintaa → mallin vaihto = config + restart.

---

## 8. Sanalistojen lataus ensimmäisellä käynnistyksellä

### 8.1 Konfiguraatio

Ympäristömuuttujat:

- `WORDLIST_FI_URL`
- `WORDLIST_EN_URL`
- `WORDLIST_DIR` (esim. `./data/`)
- `WORDLIST_REFRESH_DAYS` (optional, esim. 7; 0 = ei automaattipäivitystä)

### 8.2 Latauslogiikka

1. Sovellus käynnistyy:
   - tarkistaa, onko `WORDLIST_DIR/badwords_fi.txt` ja `badwords_en.txt` olemassa
2. Jos **ei ole**:
   - lataa URL:sta HTTP:llä
   - tallentaa tiedostoon
3. Jos **on**:
   - tarkistaa `WORDLIST_REFRESH_DAYS` (jos > 0):
     - jos tiedoston mtime > N päivää vanha → lataa uudelleen
4. Lukee tiedostot `set[str]`-rakenteeseen ja säilyttää ne muistissa sovelluksen eliniän ajan.

Virhetilanteet:

- Jos lataus epäonnistuu:
  - logitetaan virhe
  - voidaan:
    - joko estää sovelluksen käynnistyminen (fail-fast)
    - tai käynnistyä “degraded mode” ilman sanalistaa (ei suositella tuotannossa)

---

## 9. Turvallisuus

1. **Palvelun suojaus**
   - `POST /moderate` -endpoint vaatii autentikaation:
     - esim. `Authorization: Bearer <token>` (shared secret / JWT)
   - IP-allowlist (esim. vain tietyt backendi(t) saavat kutsua)

2. **Callback-turvallisuus**
   - Moderointipalvelu voi lähettää callbackin vain HTTPS:lle (suositus).
   - Mahdollisuus allekirjoittaa payload HMAC:lla:
     - HTTP-header esim. `X-Moderation-Signature: sha256=<hexdigest>`
     - asiakas tarkistaa allekirjoituksen ja varmistaa, että kutsu on aidosti moderointiserviceltä.

3. **Tietosuoja**
   - Mahdollisuus konfiguroida, lähetetäänkö `text` takaisin callbackiin:
     - tuotannossa voi riittää pelkkä `id` + `decision` + `reason`.
   - Tekstien lokitus:
     - oletuksena **ei lokiteta täysiä tekstejä** info-lokitasolla
     - mahdollisuus debug-tilaan (dev-ympäristö), jossa tekstejä logitetaan.

---

## 10. Deploy ja ympäristö (Hetzner VPS)

1. **Käyttöympäristö**
   - Python 3.11+
   - FastAPI + Uvicorn
   - transformers (+ tarvittavat mallit)
   - requests tms. callbackeihin

2. **Käynnistys**
   - `uvicorn app.main:app --host 0.0.0.0 --port 8000`
   - edessä voi olla reverse proxy (nginx/traefik) TLS:ää varten.

3. **Resurssit**
   - Suositus: vähintään esim. 2 vCPU, 4 GB RAM (mallista riippuen).
   - Malli ladatun jälkeen pysyy muistissa → ei jatkuvaa levy/verkko I/O:ta.

4. **Containerointi (optional)**
   - Dockerfile, jossa:
     - perus Python image
     - asennetaan riippuvuudet
     - kopioidaan koodi
     - asetetaan `WORDLIST_DIR` volume- tai datadiriksi, jotta listat säilyvät konttien välillä.
