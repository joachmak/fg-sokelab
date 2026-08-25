# Workshop-oppgaver: Introduksjon til søk med OpenSearch

## Før du starter

1. Start applikasjonen med `docker compose up --build`
2. Åpne OpenSearch Dashboards på http://localhost:5601
3. Ha [OpenSearch-dokumentasjonen](https://docs.opensearch.org/latest/about/) klar!

---

## Del 1: Utforsk datasettet

### Oppgave 1.1: Hva er i datasettet?

Trykk på burger-menyen, bla ned til "Index Management", og velg "Indexes" i menyen til venstre. Finn så "bekk-articles"-indeksen. Her kan du se litt informasjon om indeksen, altså strukturen som holder på informasjonen om alle bekk-artiklene som vi har gjort søkbare.

Du kan også bruke **Dev Tools** til å finne mye av den samme informasjonen. Med Dev Tools kan du kjøre søkeforespørsler, inspisere indekser, undersøke hvordan tekst blir pre-prosessert av såkalte "analyzere", og mye mer.

Gjennom hele fagåret skal vi bruke Dev Tools veldig aktivt til å forstå hvordan en søkemotor som OpenSearch fungerer under panseret.

**Spørsmål:**

1. Hvor mange artikler finnes i indeksen? Bruk Count-APIet!
2. Bruk Search-APIet til å søke etter forskjellige artikler.

📚 **Relevant dokumentasjon:**

- [Search API](https://opensearch.org/docs/latest/api-reference/search/)
- [Count API](https://opensearch.org/docs/latest/api-reference/count/)

<details>
<summary>💡 Hint 1</summary>

For å telle dokumenter, se på `_count` endepunktet i dokumentasjonen.

For å se dokumenter, bruk `_search` API-et med `size` parameteren.

</details>

<details>
<summary>💡 Hint 2</summary>

```
GET indeks-navn/_count
GET indeks-navn/_search
```

</details>

<details>
<summary>✅ Løsning</summary>

```json
# Tell dokumenter
GET bekk-articles/_count

# Se ett dokument
GET bekk-articles/_search
{
  "size": 1
}
```

Forklaring: `_count` returnerer antall dokumenter. `_search` med `size: 1` viser ett dokument slik at du kan se strukturen.

</details>

---

### Oppgave 1.2: Hvordan er indeksen konfigurert?

**Mappings** i OpenSearch definerer strukturen til indeksen - hvilke felter som finnes, hvilke datatyper de har, og hvordan de skal prosesseres. Det er som et skjema for dataene dine.

**Analyzers** er prosesser som transformerer tekst til søkbare tokens. For eksempel vil Norwegian analyzer gjøre "applikasjonene" om til "applikasjon" (stemming) og fjerne stoppord som "og", "i", "på". Dette gjør søket vårt fleksibelt og robust mot skrivefeil, bøyninger osv.

**Spørsmål:**

1. Hvilke datatyper har de ulike feltene?
2. Hvilken analyzer brukes for `title` og `content` feltene? Kunne vi ha brukt noen andre analyzers?
3. Hva er forskjellen mellom felttypene `text` og `keyword`?
4. Hvorfor har `title` et ekstra `raw`-subfelt? I hvilke situasjoner kan dette være nyttig?

📚 **Relevant dokumentasjon:**

- [Mapping API](https://opensearch.org/docs/latest/field-types/)
- [Text vs Keyword](https://opensearch.org/docs/latest/field-types/supported-field-types/text/)

<details>
<summary>💡 Hint</summary>

Bruk `_mapping` endepunktet for å se hvordan indeksen er konfigurert.

```
GET indeks-navn/_mapping
```

</details>

<details>
<summary>✅ Løsning</summary>

```json
GET bekk-articles/_mapping
```

**Svar:**

**1. Datatyper:**

- `text`: title, content, previewText, summary (søkbare tekstfelter)
- `keyword`: id, authors, tags, series, url, language (eksakte verdier)
- `date`: publishedAt, createdAt, updatedAt

**2. Analyzers:**

- `title` og `content` bruker **Norwegian analyzer**
- Alternativer kunne vært: `standard` (generell), `simple` (kun lowercase), `whitespace` (splitter på mellomrom), eller custom analyzers

**3. Text vs Keyword:**

- `text`: Analysert (stemming, lowercase, stoppord). Brukes for søk med fleksibel matching
- `keyword`: Uanalysert, lagret som eksakt verdi. Ofte nyttig for filtrering, sortering og aggregeringer

**4. title.raw (keyword-subfelt):**
Nyttig for eksakt søk, altså dersom man vil finne artikler med nøyaktig tittel, inkludert spesifikke spesialtegn osv.

**Kobling til teori:** Analyzere transformerer tekst til tokens som lagres i den inverterte indeksen. Norwegian analyzer med stemming gjør at "applikasjoner" og "applikasjon" matcher. Keyword-felter beholder original verdi og er nødvendige for operasjoner som krever eksakte verdier.

</details>

### Oppgave 1.3: Filtrering

**Filtrering** lar deg begrense søkeresultater basert på spesifikke kriterier. De vanligste filtreringstypene er:

- **Term**: Eksakt match på keyword-felter (f.eks. forfatter, språk, tags)
- **Range**: Dato- eller tallintervaller (f.eks. publisert mellom 2024-01-01 og 2024-12-31)
- **Bool**: Kombinere flere filtre med AND/OR/NOT logikk

Filtrering påvirker ikke relevans-scoringen, men er et steg som OpenSearch gjør enten før eller etter at søkeresultatene er rangert.

**Spørsmål:**

1. Hvor mange artikler ble publisert i 2024?
2. Hvor mange artikler er skrevet på norsk?
3. Gjør et søk avgrenset til "Bekk Christmas"-artikler skrevet av en spesifikk forfatter!

📚 **Relevant dokumentasjon:**

- [Range query](https://opensearch.org/docs/latest/query-dsl/term/range/)
- [Term query](https://opensearch.org/docs/latest/query-dsl/term/term/)
- [Bool query](https://opensearch.org/docs/latest/query-dsl/compound/bool/)
- [Match query](https://opensearch.org/docs/latest/query-dsl/full-text/match/)

<details>
<summary>💡 Hint 1</summary>

**Spørsmål 1:** Bruk **range query** på `publishedAt` feltet med `_count` API-et.

**Spørsmål 2:** Bruk **term query** på `language` feltet. Hva er språkkoden for norsk?

**Spørsmål 3:** Du trenger en **bool query** som kombinerer:

- `must`: **match** query for "Bekk Christmas" i title/content
- `filter`: **term** query for spesifikk forfatter i `authors` feltet

</details>

<details>
<summary>✅ Løsning</summary>

```json
# Spørsmål 1: Hvor mange artikler publisert i 2024?
GET bekk-articles/_count
{
  "query": {
    "range": {
      "publishedAt": {
        "gte": "2024-01-01",
        "lt": "2025-01-01"
      }
    }
  }
}

# Spørsmål 2: Hvor mange artikler på norsk?
GET bekk-articles/_count
{
  "query": {
    "term": {
      "language": "nb"
    }
  }
}

# Spørsmål 3: "Bekk Christmas" artikler av spesifikk forfatter
# (Erstatt "Anders Fagereng" med forfatter du finner i datasettet)
GET bekk-articles/_search
{
  "query": {
    "bool": {
      "must": [
        {
          "match": {
            "title": "Bekk Christmas"
          }
        }
      ],
      "filter": [
        {
          "term": {
            "authors": "Anders Fagereng"
          }
        }
      ]
    }
  }
}
```

**Forklaring:**

- **Range query:** Filtrerer på dato-intervall. Effektivt fordi OpenSearch indekserer datoer som tall.
- **Term query:** Eksakt match på keyword-felt (`language`). Brukes for filtrering uten scoring.
- **Bool query:** Kombinerer `must` (scoring) og `filter` (binær ja/nei). `filter` er raskere fordi den kan caches.

**Kobling til teori:** Filters bruker ikke BM25-scoring, bare ja/nei matching. Dette er raskere og kan caches av OpenSearch.

</details>

---

### Oppgave 1.4: Hvordan analyseres norsk tekst?

**Eksperiment:**

Bruk `_analyze` endepunktet:

```json
GET bekk-articles/_analyze
{
  "analyzer": "norwegian",
  "text": "din tekst her"
}
```

1. Test hvordan Norwegian analyzer behandler teksten: "Datamaskiner kjører applikasjonene våre"
2. Sammenlign med Standard analyzer på samme tekst
3. Test også: "Dette er en test av stoppord i norsk"

**Spørsmål:**

1. Hvilke tokens produseres?
2. Hva skjer med ord som "Datamaskiner" og "applikasjonene"?
3. Hvilke ord fjernes som stoppord?
4. Hvorfor er stemming og stoppord-fjerning nyttig for søk? Forklar med konsepter fra presentasjonen (inverterte indekser, BM25).

📚 **Relevant dokumentasjon:**

- [Analyze API](https://opensearch.org/docs/latest/api-reference/analyze-apis/)
- [Norwegian analyzer](https://opensearch.org/docs/latest/analyzers/language-analyzers/#norwegian-analyzer)

<details>
<summary>✅ Løsning</summary>

```json
# Norsk analyzer
GET bekk-articles/_analyze
{
  "analyzer": "norwegian",
  "text": "Datamaskinene kjører applikasjonene våre"
}

# Standard analyzer
GET bekk-articles/_analyze
{
  "analyzer": "standard",
  "text": "Datamaskinene kjører applikasjonene våre"
}

# Stoppord test
GET bekk-articles/_analyze
{
  "analyzer": "norwegian",
  "text": "Dette er en test av stoppord i norsk"
}
```

**Observasjoner:**

- **Stemming:** "Datamaskinene" → "datamaskin", "applikasjonene" → "applikasjon"
- **Stoppord:** "er", "en", "av", "i" fjernes
- **Lowercase:** "Dette" → "dette"

**Kobling til teori (fra presentasjonen):**

- **Inverted index** mapper tokens til dokumenter. Uten stemming måtte vi ha separate entries for "applikasjon" og "applikasjonene"
- **Stemming** gjør at søk etter "applikasjon" også matcher "applikasjoner", "applikasjonens", etc.
- **Stoppord** fjernes fordi de forekommer i nesten alle dokumenter og gir liten informasjon (lav IDF i BM25)
- Norwegian analyzer er (i dette tilfellet) bedre enn Standard fordi den forstår norsk grammatikk
</details>

### Oppgave 1.5: Hvordan beregnes relevans?

**Eksperiment:**

1. Søk etter "kubernetes" i content-feltet
2. Se på `_score` for topp 3 resultater
3. Bruk `explain: true` for å se hvordan scoren beregnes

**Spørsmål:**

1. Hvilke faktorer påvirker scoren?
2. Kan du identifisere **BM25-komponenter** fra presentasjonen? (TF, IDF, dokumentlengde)
3. Hvilke tf- og idf-varianter bruker OpenSearch? https://en.wikipedia.org/wiki/Tf%E2%80%93idf#Definition
   - Hvorfor er disse variantene "bedre" enn de vi brukte i presentasjonen?
   - Kunne / burde OpenSearch ha brukt andre varianter?

📚 **Relevant dokumentasjon:**

- [Explain API](https://opensearch.org/docs/latest/api-reference/explain/)
- [BM25 scoring](https://opensearch.org/docs/latest/query-dsl/query-dsl-index/#scoring)

<details>
<summary>💡 Hint 1</summary>

```json
GET indeks/_search
{
  "explain": true,
  "query": {
    "match": {
      "felt": "søketerm"
    }
  }
}
```

Se etter:

- `idf` (inverse document frequency)
- `tf` (term frequency)
- `fieldNorm` (lengde-normalisering)
</details>

<details>
<summary>💡 Hint 2</summary>

I explain-output, se spesielt på:

- "weight(...) in XXX" - viser BM25 beregning
- "tf, computed as..." - term frequency
- "idf, computed as..." - inverse document frequency
- "fieldNorm" - dokument-lengde
</details>

<details>
<summary>✅ Løsning</summary>

```json
GET bekk-articles/_search
{
  "explain": true,
  "query": {
    "match": {
      "content": "kubernetes"
    }
  },
  "size": 3
}
```

**Analyse av explain output:**

Se etter linjer som:

```
"weight(content:kubernetes in XXX) [BM25], result of:"
  - "idf, computed as..." → hvor sjeldent er ordet?
  - "tf, computed as..." → hvor ofte i dette dokumentet?
  - "fieldNorm" → hvor langt er dokumentet?
```

**Kobling til BM25-teori (fra presentasjonen):**

1. **IDF (Inverse Document Frequency):**
   - Hvis "kubernetes" finnes i 50/1543 dokumenter → høy IDF → viktig term
   - Hvis ordet var i alle dokumenter → lav IDF → lite informativt

2. **TF (Term Frequency):**
   - Dokument som nevner "kubernetes" 10 ganger scores høyere enn et som nevner det 1 gang
   - Men: diminishing returns (saturering) - 10 vs 11 ganger har mindre effekt enn 1 vs 2

3. **Field Length Normalization:**
   - Kort dokument med "kubernetes" 2 ganger er mer relevant enn langt dokument med det 2 ganger
   - Forhindrer at lange dokumenter alltid vinner

**Hvorfor er dette viktig?**
BM25 balanserer:

- Sjeldenhet (IDF): sjeldne ord gir mer poeng
- Frekvens (TF): flere forekomster = mer relevant
- Lengde (norm): normaliser for dokumentstørrelse
</details>

## Del 2: Når fungerer søk IKKE?

### Oppgave 2.1: Finn et dårlig søk

Prøv søke på:

- Veldig vanlige ord (lav IDF)
- Ord som har flere betydninger
- Spesialord (kode-snippets, versjonsnummer, etc.)

Bruk `explain: true` for å forstå hvorfor scoringen blir som den blir.

<details>
<summary>✅ Eksempler på problematiske søk</summary>

**Eksempel 1: Vanlige ord**

```json
GET bekk-articles/_search
{
  "explain": true,
  "query": {
    "match": {
      "content": "utvikling"
    }
  }
}
```

Problem: "utvikling" finnes i veldig mange artikler → lav IDF → alle dokumenter scorer likt → rekkefølgen virker tilfeldig

**Eksempel 2: Versjonsnummer**

```json
GET bekk-articles/_search
{
  "query": {
    "match": {
      "content": "2.0"
    }
  }
}
```

Problem: Analyzeren kan splitte "2.0" til ["2", "0"] eller fjerne det helt. Her må vi være litt OBS på hvilken analyzer vi bruker.

**Eksempel 3: Polysemi (ord med flere betydninger)**

```json
GET bekk-articles/_search
{
  "query": {
    "match": {
      "content": "form"
    }
  }
}
```

Problem: "form" kan bety mange ting:

- HTML-form (teknisk kontekst)
- Form/kondisjon ("i god form")
- Form/skjema/dokument
- Form/design/utforming

Søkemotoren forstår ikke **hvilken betydning** du er ute etter. Alle artikler som nevner "form" i hvilken som helst kontekst matcher. Dette kalles **polysemi** - ett ord, flere betydninger.

</details>

---

### Oppgave 2.2: Flerspråklig søk

Datasettet vårt inneholder både norske og engelske artikler. La oss utforske hvordan dette kan påvirke søkekvaliteten.

**Eksperiment:**

1. Søk etter et norsk ord, f.eks. "utvikling"
2. Søk etter et engelsk ord, f.eks. "development"
3. Sammenlign antall treff og relevans
4. Bruk `_analyze` til å se hva som skjer med engelske ord:

Test "Norwegian analyzer" på engelsk tekst:

```json
GET bekk-articles/_analyze
{
  "analyzer": "norwegian",
  "text": "testing of a fancy search application"
}
```

Sammenlign med "English analyzer":

```json
GET bekk-articles/_analyze
{
  "analyzer": "english",
  "text": "testing of a fancy search application"
}
```

**Spørsmål:**

1. Hva skjer når Norwegian analyzer behandler engelske ord som "testing", "application", "search", eller "a"?
2. Hvorfor kan dette ha en negativ innvirkning på søkekvaliteten? Tenk på hvordan indeksen er strukturert.
3. Hvordan kunne vi ha indeksert dataene våre for å støtte flerspråklig søk?

📚 **Relevant dokumentasjon:**

- [Language analyzers](https://opensearch.org/docs/latest/analyzers/language-analyzers/)
- [Aggregations](https://opensearch.org/docs/latest/aggregations/)

<details>
<summary>✅ Løsning og diskusjon</summary>

**Problem:**
Norwegian analyzer forstår ikke engelsk grammatikk:

- "applications" stemmes ikke ordentlig, fordi Norwegian stemmer ikke kjenner engelsk morfologi
- Engelske stoppord ("the", "a", "is") fjernes ikke
- Norske stoppord ("i", "på", "og") er ikke relevante for engelske artikler

Resultat: **dårlig søkekvalitet for engelske artikler** når vi bruker Norwegian analyzer.

**Løsninger:**

**1. Language detection + separate indexes:**

- Lag separate indekser for hver språk: `bekk-articles-no`, `bekk-articles-en`
- Bruk riktig analyzer for hvert språk
- Søk i begge indekser og flett sammen resultater

**2. Multi-field med forskjellige analyzers:**

```json
"content": {
  "type": "text",
  "analyzer": "norwegian",
  "fields": {
    "en": {
      "type": "text",
      "analyzer": "english"
    }
  }
}
```

- Indekser samme tekst med begge analyzers
- Bruk `multi_match` på både `content` og `content.en`

**3. Standard analyzer (kompromiss):**

- Bruk `standard` analyzer (ingen stemming, kun lowercase + tokenization)
- Fungerer "OK" for begge språk, men ikke optimalt. Mister fordelene med språk-spesifikk stemming

</details>

---

## Del 3: Design en søkeopplevelse - Åpen oppgave

Vi skal designe en splitter ny søkefunksjonalitet for [skjer.bekk.no](https://skjer.bekk.no/).

Først må vi tenke litt på søkesystemet som helhet.

- Hvilke informasjonsbehov har en typisk bruker på skjer.bekk.no?
- Hvordan forventer vi at en bruker skal måtte uttrykke sine informasjonsbehov?
  - Hvordan kan vi hjelpe brukeren med å formidle informasjonsbehovet sitt?
- Hva vet vi om brukeren som kan hjelpe oss med å gi mer relevante treff?
  - Er dette informasjon vi har tilgjengelig på skjer.bekk.no?
  - Hvilke antagelser kan vi gjøre om brukeren, som kan brukes til å gi mer relevante søketreff? Hva kjennetegner en typisk Bekk-ansatt?
- Finnes det forskjellige brukergrupper? Har de isåfall ulike behov?
  - Det er ikke alltid vi klarer å dekke alle brukergruppers behov med ett søkefelt. Får vi det til her, eller bør vi tilby flere søk? Klarer vi evt. å tilfredsstille brukerbehovene på andre måter, som filtrering / sortering / aggregering?

Nå som vi har en idé om brukerens informasjonsbehov, kan vi begynne å tenke på selve søkemotoren.

- Hvilke felter bør vi gjøre søkbare?
- Hvilken informasjon gir mest verdi for å finne relevante treff?
- Hvilke datatyper bær vi bruke for de ulike feltene?
- Hvilke preprosesseringssteg / analysesteg er lure å bruke på dokumentene og søkestrengen? Hvorfor?
  - Hvilke preprosesseringssteg burde vi unngå? Er det noen som kan forverre søkekvaliteten?
  - Burde forskjellige felter analyseres på forskjellige måter? Hvorfor / hvorfor ikke?
