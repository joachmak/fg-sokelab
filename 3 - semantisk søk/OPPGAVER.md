# Workshop-oppgaver: Semantisk søk med OpenSearch

## Før du starter

1. Start applikasjonen med `docker compose up --build`
2. Åpne OpenSearch Dashboards på http://localhost:5601
3. Ha [OpenSearch-dokumentasjonen](https://docs.opensearch.org/latest/about/) klar!

Datasettet er 10 000 tilfeldig utvalgte bokmål-artikler fra norsk Wikipedia (2019).

---

## Del 1: Utforsk indeksen

### Oppgave 1.1: Hva er i indeksen?

**Spørsmål:**

1. Hvor mange artikler finnes i indeksen?
2. Hent ett dokument og se på strukturen. Hvilke felter finnes?
3. Hva inneholder `embed_text`-feltet? Hvorfor er det annerledes enn `text`?

📚 **Relevant dokumentasjon:**

- [Count API](https://opensearch.org/docs/latest/api-reference/count/)
- [Search API](https://opensearch.org/docs/latest/api-reference/search/)

<details>
<summary>✅ Løsning</summary>

```json
GET norsk-wikipedia/_count

GET norsk-wikipedia/_search
{
  "size": 1
}
```

`embed_text` inneholder tittel + første avsnitt av artikkelen. Det er dette feltet modellen har generert vektorer fra — ikke hele artikkelteksten. Dette er et bevisst valg: lange tekster er vanskelige å representere i én enkelt vektor, og introduksjonen oppsummerer gjerne innholdet godt.

</details>

---

### Oppgave 1.2: Hvordan er indeksen satt opp for semantisk søk?

Semantisk søk i OpenSearch bygger på tre komponenter:

- **`knn_vector`-felt**: Lagrer embeddingen (en liste med tall) for hvert dokument
- **Ingest pipeline**: Kjøres automatisk når dokumenter indekseres — leser `embed_text` og skriver vektoren til `content_vector`
- **Søkepipeline**: Kjøres automatisk på søk — gjør at `neural`-spørringen finner riktig modell uten at du trenger å oppgi modell-ID

**Spørsmål:**

1. Hva er dimensjonen på vektorene i `content_vector`-feltet? Hva betyr det i praksis?
2. Hvilken algoritme brukes for å finne nærmeste naboer? Hva er alternativene?
3. Hva er `space_type: cosinesimil`? Hva måler cosinus-likhet?
4. Se på ingest-pipelinen og søkepipelinen. Hva gjør hver av dem?

📚 **Relevant dokumentasjon:**

- [k-NN index](https://opensearch.org/docs/latest/search-plugins/knn/knn-index/)
- [Text embedding processor](https://opensearch.org/docs/latest/ingest-pipelines/processors/text-embedding/)
- [Neural query enricher](https://opensearch.org/docs/latest/search-plugins/search-pipelines/neural-query-enricher/)

<details>
<summary>💡 Hint</summary>

```json
GET norsk-wikipedia/_mapping

GET _ingest/pipeline/wikipedia-embeddings

GET _search/pipeline/wikipedia-neural-search
```

</details>

<details>
<summary>✅ Løsning</summary>

```json
GET norsk-wikipedia/_mapping
GET _ingest/pipeline/wikipedia-embeddings
GET _search/pipeline/wikipedia-neural-search
```

**Dimensjon:** 384. Det betyr at hvert dokument er representert som et punkt i et 384-dimensjonalt rom. Semantisk like dokumenter havner nær hverandre i dette rommet.

**Algoritme:** HNSW (Hierarchical Navigable Small World) — en grafbasert algoritme for tilnærmet nærmeste-nabo-søk. Alternativet er eksakt k-NN, men det skalerer ikke. HNSW gir svært god treff med langt lavere kostnad.

**Cosinus-likhet** måler vinkelen mellom to vektorer, ikke avstanden. To tekster med lik *mening* vil peke i samme retning i vektorrommet uavhengig av lengde. Verdier mellom −1 (motsatte) og 1 (identiske).

**Ingest pipeline:** Leser `embed_text`, kaller modellen, skriver 384-tall til `content_vector`.

**Søkepipeline:** `neural_query_enricher` injiserer modell-ID i `neural`-spørringen automatisk, så du slipper å oppgi den manuelt i hvert søk.

</details>

---

## Del 2: Semantisk søk i praksis

### Oppgave 2.1: Ditt første semantiske søk

**Semantisk søk** med `neural`-spørringen fungerer slik: OpenSearch embedder søkestrengen din med samme modell som ble brukt ved indeksering, og finner så dokumentene med nærmeste vektorer.

Prøv et søk:

```json
GET norsk-wikipedia/_search
{
  "size": 5,
  "_source": ["title", "text"],
  "query": {
    "neural": {
      "content_vector": {
        "query_text": "norske fjell og natur",
        "k": 5
      }
    }
  }
}
```

**Spørsmål:**

1. Hva slags artikler får du opp? Er de relevante?
2. Prøv å endre `k` til 1, 10, og 100. Hva skjer med resultatene?
3. Prøv noen egne søkestrenger. Hva fungerer godt?

📚 **Relevant dokumentasjon:**

- [Neural query](https://opensearch.org/docs/latest/query-dsl/specialized/neural/)

---

### Oppgave 2.2: Semantisk vs. nøkkelord-søk

La oss sammenligne semantisk søk med tradisjonelt BM25-søk på de samme spørringene.

**Eksperiment:** Kjør begge spørringene og sammenlign topp 5 resultater.

```json
# Semantisk søk
GET norsk-wikipedia/_search
{
  "size": 5,
  "_source": ["title"],
  "query": {
    "neural": {
      "content_vector": {
        "query_text": "SØKESTRENG HER",
        "k": 5
      }
    }
  }
}

# Nøkkelord-søk (BM25)
GET norsk-wikipedia/_search
{
  "size": 5,
  "_source": ["title"],
  "query": {
    "match": {
      "text": "SØKESTRENG HER"
    }
  }
}
```

Prøv disse søkestrengene og noter forskjellene:

1. `"konge"` — prøv også synonymer som `"monark"` og `"hersker"`
2. `"hav og sjø"` — prøv også `"oseanografi"`
3. `"andre verdenskrig"` — prøv også `"nazi-Tyskland"`
4. `"1814"` — hva skjer med nøkkelord vs. semantisk?
5. En setning: `"den nordiske velferdsstaten og dens utvikling"`

**Spørsmål:**

1. I hvilke tilfeller gir semantisk søk klart bedre resultater enn BM25?
2. I hvilke tilfeller gjør BM25 det bedre?
3. Hva er det semantisk søk egentlig «forstår» som BM25 ikke gjør?

<details>
<summary>✅ Diskusjon</summary>

**Semantisk søk vinner når:**
- Søkeordet og innholdet bruker forskjellige ord for samme konsept (synonymer, omskrivninger)
- Spørringen er en hel setning eller et konsept, ikke ett enkelt ord
- Du søker etter tema, ikke eksakt terminologi

**BM25 vinner når:**
- Du søker på eksakte egennavn, steder, årstall eller fagtermer
- Det er viktig at et spesifikt ord faktisk forekommer i teksten
- Dokumentet er langt og inneholder mange relevante nøkkelord

**Hva modellen «forstår»:**
Modellen har lært at «monark», «konge», «hersker» og «statsoverhode» brukes i lignende kontekster og representerer dem nær hverandre i vektorrommet. BM25 ser bare på om eksakt streng finnes i dokumentet.

</details>

---

### Oppgave 2.3: Når svikter semantisk søk?

Semantisk søk er ikke alltid bedre. La oss finne svakhetene.

**Eksperimenter:**

1. Søk på et veldig vanlig, generelt begrep som `"Norge"` eller `"folk"`. Hva skjer med scorene?
2. Søk på en teknisk fagterm eller et smalt konsept med lite treningsdata, f.eks. `"Grunnloven § 112"`.
3. Søk på noe som avhenger av eksakt ordform, f.eks. `"NRK"` eller `"UEFA"`.
4. Prøv en lang, spesifikk søkestreng med mange detaljer. Klarer modellen å holde på alle?

**Spørsmål:**

1. Hvorfor gir semantisk søk dårlige resultater for svært generelle begreper?
2. Hva er begrensningen til å embedde bare tittel + første avsnitt?
3. Hva skjer med scorene når alle dokumenter er «litt relevante»?

<details>
<summary>✅ Diskusjon</summary>

**Generelle begreper:** Mange artikler er semantisk nær «Norge» — resultatet blir tilfeldig og scorene er tette. Ingen meningsfull rangering.

**Smale fagtermer:** Modellen kan mangle kontekst for svært spesifikke uttrykk som ikke dukker opp mye i treningsdataene. Den kan ikke lese §-tegn som juridisk kontekst.

**Forkortelser og egennavn:** «NRK» og «UEFA» er semantisk tvetydige for modellen — den vet ikke om du mener organisasjonen, en hendelse, eller noe annet.

**Kun tittel + første avsnitt:** Semantikken til lange artikler fanges ikke opp. En artikkel om «Fjord» som hovedsakelig handler om bilindustri vil matche dårlig på natursøk selv om bilen er nevnt i innledningen.

</details>

---

## Del 3: Co-occurrence-matrise

En **co-occurrence-matrise** er en klassisk metode fra distribusjonsbasert semantikk. Ideen: ord som opptrer i samme kontekst betyr noe likt. Dette er det matematiske grunnlaget bak word2vec og GloVe — nevrale embeddings er i praksis komprimerte co-occurrence-matriser.

### Oppgave 3.1: Bygg co-occurrence-matrisen

Bygg en co-occurrence-matrise fra f.eks. norsk wikipedia (https://www.nb.no/sprakbanken/ressurskatalog/oai-nb-no-sbr-50/) eller et annet datasett. Python/JuPyterLab er passende verktøy for dette.

**Spørsmål:**

1. Hva er størrelsen på matrisen (rader × kolonner)?
2. Finn de 10 ordene som co-occurrerer mest med `"kongen"`. Er de meningsfulle?
3. Sammenlign co-occurrence-naboene til `"kongen"` med naboene til `"president"`. Hva forteller det om semantikk?
4. GloVe og word2vec er i bunn og grunn co-occurrence-matriser med et ekstra steg. Hva er det nevrale nettet i disse modellene egentlig gjør?

---

## Del 4: Hybrid søk

### Oppgave 4.1: Kombiner semantisk og nøkkelord-søk

**Hybrid søk** kombinerer BM25 og semantisk søk i én spørring. OpenSearch normaliserer og vekter de to scorene slik at de kan sammenlignes.

Først må vi sette opp en søkepipeline med en normaliseringsprosessor:

```json
PUT _search/pipeline/wikipedia-hybrid-pipeline
{
  "phase_results_processors": [
    {
      "normalization-processor": {
        "normalization": {
          "technique": "min_max"
        },
        "combination": {
          "technique": "arithmetic_mean",
          "parameters": {
            "weights": [0.3, 0.7]
          }
        }
      }
    }
  ]
}
```

Søk med hybrid-spørringen:

```json
GET norsk-wikipedia/_search?search_pipeline=wikipedia-hybrid-pipeline
{
  "size": 5,
  "_source": ["title"],
  "query": {
    "hybrid": {
      "queries": [
        {
          "match": {
            "text": "SØKESTRENG HER"
          }
        },
        {
          "neural": {
            "content_vector": {
              "query_text": "SØKESTRENG HER",
              "k": 5
            }
          }
        }
      ]
    }
  }
}
```

**Spørsmål:**

1. Prøv de samme søkestrengene fra oppgave 2.2. Er hybrid søk bedre enn begge alene?
2. Vektene i pipelinen er `[0.3, 0.7]` (BM25 vs. semantisk). Prøv `[0.5, 0.5]` og `[0.7, 0.3]`. Hva endrer seg?
3. Når gir hybrid søk størst gevinst?

📚 **Relevant dokumentasjon:**

- [Hybrid query](https://opensearch.org/docs/latest/query-dsl/compound/hybrid/)
- [Normalization processor](https://opensearch.org/docs/latest/search-plugins/search-pipelines/normalization-processor/)

<details>
<summary>✅ Diskusjon</summary>

Hybrid søk er generelt mer robust enn begge metodene alene:
- BM25 sikrer at eksakte treff ikke mistes
- Semantisk søk fanger opp relaterte konsepter og synonymer
- Normaliseringsprocessoren gjør scorene sammenlignbare

Vektingen avhenger av bruksområdet. For et encyklopedisk søk (Wikipedia) er semantisk vekting gjerne høyere fordi brukere søker etter konsepter, ikke eksakte fraser.

</details>
