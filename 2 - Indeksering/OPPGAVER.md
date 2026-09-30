# Workshop-oppgaver: Indeksering med OpenSearch

I forrige økt fikk dere en ferdig indeks å utforske. Denne gangen skal dere selv planlegge, opprette og fylle en indeks med data, basert på et sett med rå restaurant-dokumenter og noen konkrete brukerhistorier.

## Før dere starter (5 min)

1. Start OpenSearch og Dashboards: `docker compose up --build`. Dette
   starter `opensearch` (søkerammeverket) og `dashboards` (et grensesnitt).
2. Åpne **Dev Tools** i OpenSearch Dashboards på http://localhost:5601.
3. Åpne `data/restauranter.json` i en editor - dette er de rå dataene
   dere skal jobbe med.
4. Ha [OpenSearch-dokumentasjonen](https://docs.opensearch.org/latest/about/) klar 🤝

---

## Del 0: Brukerhistorier (10 min)

Se gjennom `data/restauranter.json`. Det er 30 restauranter med felt som
`navn`, `beskrivelse`, `kategori`, `by`, `prisniva`, `rating`,
`antall_vurderinger`, `tags` (en liste) og `orgnummer`.

`data/restauranter.json` inneholder all informasjonen dere har tilgjengelig om
et sett med restauranter. Nå skal dere designe en søketjeneste hvor det skal være mulig
å søke på denne informasjonen.

Nedenfor finner dere et par brukerhistorier.

Som bruker ønsker jeg å...

1. Kun forholde meg til ett søkefelt, men ha litt enkel filtreringsfunksjonalitet på siden
2. Kunne få forslag om restauranter som er i nærheten av meg
3. Få forslag om restauranter som har mange fornøyde gjester
4. Kunne skrive inn enkelte ord feil, og forstatt få relevante treff
5. Kunne filtrere bort de dyreste og dårligste restaurantene

Som en skattemyndighet ønsker jeg å...

1. Finne en spesifikk restaurant basert på organisasjonsnummeret deres 🫴💰

---

## Del 1: Planlegging (25-30 min)

Nå skal vi designe en indeks-struktur! Indeksen bør designes slik at søkesystemet kan oppfylle brukerhistoriene så godt som mulig.

### Oppgave 1.1: Forstå brukeren (10-15 min)

Et søkesystem som Google har bare ett tekstfelt hvor man kan skrive inn informasjon. Likevel er det utrolig avansert, og gir relevante treff som er tilpasset til hver enkelt bruker. Hvordan er det mulig at Google ikke har tonnevis av filtre på siden?

Det ville vært belastende for oss å fortelle Google hvor vi bor hver gang vi ønsker å finne en restaurant i nærheten. Derfor samler Google inn denne informasjonen for oss. Utover å selge dataene, kan de bruke dem til å gi oss en bedre søkeopplevelse❤️

Det er lov (og lurt) å samle inn litt informasjon om brukerne våre, og bruke den til å lage seg noen antagelser om deres behov. Antagelsene kan vise seg å være feil, og da må man justere de, men det er en del av prosessen. Her er et eksempel på hvordan man kan utforme en antagelse:

> Ved å sjekke klokken kan vi gjette om brukeren ser etter frokost, lunsj eller middag. Bakerier er mer relevante til frokost. Til lunsj ønsker man gjerne noe som er raskt og billig. Til middag ønsker man å dra på restaurant.

Senere kunne vi ha implementert en slik antagelse i OpenSearch ved hjelp av [boosting](https://docs.opensearch.org/latest/mappings/mapping-parameters/boost/#query-time-boosting-recommended). Applikasjonskoden vår (som inneholder søkespørringen) kan...

- sjekke klokken, og finne ut om det er frokost, lunsj eller middag
- hvis det er lunsj, kan den legge til en mini-query (som en liten del av hele søkespørringen) som booster `"prisniva": "Billig"`:

```JSON
  {
    "term": {
      "prisniva": {
        "value": "Billig",
        "boost": 2.0
      }
    }
  }
```

**Tenk og noter:**

1. Hvem er brukerne av systemet vårt?
2. Hvilken informasjon kan vi få tak i om brukerne våre automatisk, slik at de slipper å legge den inn manuelt? Hvordan kan vi samle inn denne informasjonen?
3. Bruk datasettet vårt, og formuler et par antagelser om brukerne. Tenk på hvordan de kan forbedre søkeopplevelsen. Med utgangspunkt i restaurant-datasettet vårt: hvordan kan vi skreddersy søkeresultatene til brukerne våre?
4. Hvordan påvirker antagelsene hvilke søketreff som er relevante?

Her kan vi bli kreative! For eksempel: "Vi kan bruke AI, og kjøre en sentimentanalyse på søkestrengen for å lære noe om behovene til brukeren." Søkespørringer skrives typisk i applikasjonskode, hvor mulighetene er grenseløse!

Usikker på hva som er mulig, eller hvilken funksjonalitet i OpenSearch du kan bruke til å implementere antagelsene dine senere? Spør AI!

### Oppgave 1.2: Design en indeks (10 min)

I forrige deloppgave ble vi litt bedre kjent med datasettet, og ikke minst med brukerne våre. Vi har notert ned noen antagelser om brukerne, og planlagt hvilken informasjon vi har lyst til å samle inn. Vi klarer nå å se for oss hvordan brukere ønsker å søke etter restauranter i søkesystemet vårt.

Dermed kan vi begynne å tenke på hvordan vi ønsker å utforme restaurant-indeksen vår!

**Tenk og noter:**

1. Hvilke felter ønsker vi å ha i indeksen?
2. Se gjennom [OpenSearch sin oversikt over felt-typer](https://docs.opensearch.org/latest/mappings/supported-field-types/index/). Hvilken felt-type bør hvert felt få, og hvorfor?
3. Hvordan bør feltene preprosesseres? Hvilke [analyzers](https://docs.opensearch.org/latest/analyzers/supported-analyzers/index/) eller [tokenizers](https://docs.opensearch.org/latest/analyzers/tokenizers/index/) bør vi bruke? Trenger vi [stemming](https://docs.opensearch.org/latest/analyzers/stemming/)? OBS:

Her må vi huske at en spørring (query) består av mange mini-spørringer som kun sjekker søkestrengen opp mot ett enkelt felt. I mini-spørringene vil søkestrengen preprosesseres på samme vis som feltet den sammenlignes med.

Hvis `beskrivelse` er et `text`-felt og `navn` et `keyword`-felt, vil søkestrengen "Fersk City Wok" analyseres med en `standard`-analyzer når det sammenlignes med beskrivelsen til dokumentet, og med en `keyword`-analyzer når det sammenlignes med navnet:

```jsonc
GET restauranter-v1/_search
{
  "query": {
    "bool": {
      "must": {
        "match": {
          // preprosesseres med analyzeren til "beskrivelse"-feltet
          "beskrivelse": "Fersk City Wok"
        }
      },
      "should": {
        "match": {
          // preprosesseres med analyzeren til "navn"-feltet
          "navn": "Fersk City Wok"
        }
      }
    }
  }
}
```

### Oppgave 1.3: Lag en index template! (5 min)

1. Basert på det vi har funnet, få AI til å generere opp en index template i `./index-template.jsonc`-filen.
2. Bruk [OpenSearch Dev Tools](http://localhost:5601/app/dev_tools#/console) (se [hvordan man oppretter index templates i Dev Tools](https://docs.opensearch.org/latest/im-plugin/index-templates/)), eller gå til Index Management > Templates i OpenSearch Dashboards for å opprette en index template

### Oppgave 1.4: Dobbeltsjekk brukerhistoriene (5 min)

Gå gjennom brukerhistoriene i Del 0. For hver brukerhistorie, sjekk om vi er i stand til å oppfylle de basert på hvordan vi har definert indeksen vår. Hvis noen brukerhistorier ikke kan oppfylles, vurder å justere index templaten. Hvis dere mener at en brukerhistorie ikke er så viktig, er det lov å se bort ifra den. Kunden har ikke _alltid_ rett.

---

## Del 2: Lag indeksen i OpenSearch og last inn dataene (10 min)

### Oppgave 2.1: Lag indeksen (5 min)

Lag en indeks som matcher index-patternet definert i index templaten. For eksempel: kall indeksen `restauranter-v1` hvis index-patternet er `restauranter-*`.

```
PUT restauranter-v1
GET restauranter-v1
```

### Oppgave 2.2: Last inn dataene (5 min)

`data/generate-bulk-request.py` er et enkelt python-script som generer en bulk-request ut ifra `data/restauranter.json`.

> Hvis dere i planleggingen bestemte at dokumentene bør se annerledes ut enn i `restauranter.json` (f.eks. andre feltnavn, eller at felter bør legges til / fjernes), må `generate-bulk-request.py` oppdateres til å matche den strukturen. Bruk AI til justere scriptet så det passer til index-templaten!

Kjør scriptet for å få en bulk-request dere kan putte inn i OpenSearch Dev Tools.

Sjekk at alle dokumentene faktisk kom inn:

```json
GET restauranter-v1/_count
GET restauranter-v1/_search
{
  "query": {
    "match_all": {}
  }
}
```

#### Hvis noe går galt

... så er det alltid mulig å rydde opp. Bruk Dev Tools eller Dashboards-grensesnittet (Index Management > Indexes) til å slette en indeks.

```json
DELETE restauranter-v1
```

---

## Del 3: Skriv spørringer! (25 min)

Skriv én spørring (bestående av flere mini-spørringer) som dekker brukerhistoriene i Del 0. Spørringen kan skrives i Dev Tools.

Prøv å utvide spørringen med noen av antagelsene våre ifra del 1.

Gjerne bruk AI til å skrive en spørring for dere! Det er mye læring i å analysere strukturen til en spørring, og diskutere spørringen sammen med Copilot. Her kan det være lurt å jobbe iterativt, og begynne med en liten spørring som dekker de enkleste brukerhistoriene, og utvide spørringen litt og litt.

📚 **Relevant dokumentasjon:**

- [Search API](https://docs.opensearch.org/latest/api-reference/search-apis/search/)
- [Bool query](https://docs.opensearch.org/latest/query-dsl/compound/bool/)
- [Multi-match queries](https://docs.opensearch.org/latest/query-dsl/full-text/multi-match/)
- [Boosting](https://docs.opensearch.org/latest/query-dsl/compound/boosting/)
