# Annona — a cosa serve, per chi, e come si verifica

> Pagina in italiano, per il mercato italiano. Il resto della documentazione è in
> inglese; questa è la sintesi che si gira a chi deve decidere, non a chi deve
> implementare. La versione impaginata:
> [annona — casi d'uso](https://claude.ai/code/artifact/21348fae-0d01-4931-bbbf-9269d151dafe).

## Il problema, in tre righe

Ogni agente AI che installi manda il tuo materiale da qualche parte. Quel «da
qualche parte» oggi è deciso da una riga di configurazione scritta diciotto mesi
fa da uno sviluppatore, e nessuno se ne accorge finché non c'è un audit.

Ti hanno detto di scegliere fra tre architetture: modelli **on-prem** (privati,
limitati dall'hardware), **API di frontiera** (bravissime, e i tuoi dati escono),
o **pesi tuoi nel tuo cloud** (compromesso onesto, costa un team MLOps).

> **La colonna giusta è una proprietà della singola richiesta, non dell'azienda.**

Riassumere un bando pubblico non è lo stesso problema di ragionare sulla cartella
clinica di un paziente — e il secondo non diventa sicuro perché l'ufficio
acquisti ha firmato un DPA.

## Il vantaggio, in brevissimo

| | |
|---|---|
| **Non scegli più una volta sola** | La stessa installazione manda il lavoro pubblico al modello migliore e tiene quello sensibile in casa. Non paghi la sovranità su tutto per proteggere il 5%. |
| **Il fallback non ti tradisce** | Se la GPU locale cade, il lavoro riservato **si ferma**. Non viene dirottato sull'API che è ancora su. È l'unica differenza che conta rispetto a un gateway. |
| **Hai una prova, non una promessa** | Ogni decisione finisce in un registro a catena di hash che verifichi offline, con un comando che non contatta nessuno. |
| **Nessuno deve ricordarsi le regole** | La policy è un file YAML che un DPO legge in una seduta. Chi sviluppa dichiara l'intento; dove gira lo decide il kernel. |

```
$ annona why step_7f3a
step_7f3a  inference  HELD
  class        restricted  (il working set ha toccato /mnt/pratiche/2026/BG-114.pdf)
  rule         R-clienti  restricted → [local-gpu], on_unavailable: hold
  candidates   local-gpu (non raggiungibile dalle 14:02:11)
  not chosen   frontier — max_class public < restricted
  outcome      held alle 14:03:07
  ledger       #418  sha256:9c1f…a7  (catena verificata)
```

Quel rifiuto *è* il prodotto. Un gateway, nella stessa situazione, avrebbe fatto
failover silenzioso sull'API di frontiera e restituito un'ottima risposta.

## Sei casi d'uso, e il test che li dimostra

Non sono scenari da slide: sono sei test in
[`tests/test_use_cases.py`](https://github.com/akaion-ai/annona/blob/main/tests/test_use_cases.py) che girano a ogni push
contro il vero loop agentico, la vera policy e il vero registro. Se una di queste
frasi smette di essere vera, la build diventa rossa.

| # | Situazione | Verdetto | Test |
|---|---|---|---|
| 1 | **Studio legale** — un collaboratore chiede una scadenza su un fascicolo cliente | tutto on-prem; il modello di frontiera è su e non viene chiamato | `test_a_client_matter_is_answered_without_the_matter_leaving` |
| 2 | **Lo stesso studio** — una domanda di diritto pubblico, senza dati cliente | va al modello migliore: la sovranità non è una tassa su tutto | `test_a_question_with_no_client_data_goes_to_the_best_model` |
| 3 | **Sanità / HR** — qualcuno incolla un codice fiscale nel prompt, nessun file aperto | bloccato al primo turno: si classificano i byte che stanno per partire | `test_an_identifier_typed_into_the_prompt_never_reaches_a_frontier_model` |
| 4 | **L'audit** — la GPU cade di martedì alle 14:02 | held, non dirottato; il registro spiega cosa e perché | `test_when_the_gpu_dies_the_work_stops_instead_of_moving_abroad` |
| 5 | **Commercialista** — stessa avaria, una riga di policy diversa | identificativi sostituiti in locale, risposta ri-identificata qui | `test_with_a_redactor_the_frontier_model_answers_and_never_sees_a_name` |
| 6 | **L'agente che eccede** — «e già che ci sei pulisci il disco» | lo strumento non parte e il rifiuto va a registro | `test_the_toolbox_still_works_and_the_policy_decides_which_part_of_it` |

Il caso 5 usa [rizzo-pii](https://github.com/Rizzo-AI-Academy/rizzo-pii) (Simone
Rizzo, MIT): lui riconosce gli identificativi italiani meglio di qualunque regex,
Annona decide se il testo redatto può attraversare e lo registra. Un redattore
non può concedere permessi.

## Come è verificato

| Cosa | Come | Stato |
|---|---|---|
| Suite completa, offline | `make check` — lint, tipi, 10 contratti di layering, test | **523 verdi** |
| Matrice di conformance del placement | 3 classi × 5 stati di disponibilità | 15 casi |
| Leak rate | canary piantato nei file, substrato di frontiera intercettato | **0** |
| Manomissione del registro | voce riscritta, cancellata, riordinata, riga corrotta | 4/4 rilevate |
| Modello locale vero | `make test-live` — Ollama, qwen2.5 3B e 14B | 6 verdi |
| Container come si deploya | `make test-container` — utente non privilegiato, volumi, policy | 12 verdi |
| Collaudo di una macchina nuova | `make verify` — 9 controlli in 25 secondi | 9/9 |

```
$ make verify
  pass  il runtime locale risponde
  pass  il modello ha chiamato lo strumento
  pass  leggere un file cliente ha reso il run riservato
  pass  nessun payload è arrivato al substrato di frontiera
  pass  leak rate a zero
  pass  ogni inferenza è stata piazzata on-prem
  pass  la catena del registro verifica
  pass  il run ha prodotto una risposta
  pass  con la GPU giù, il lavoro riservato è held (non dirottato)
```

L'ultimo controllo è quello commerciale: tutto il resto del mercato passa gli
altri otto.

## Provarlo

```bash
git clone git@github.com:akaion-ai/annona.git && cd annona
make setup && make demo         # run agentico vero, senza credenziali e senza rete

docker compose up -d            # kernel + modello locale, arm64 o amd64
make verify                     # i 9 controlli sopra, sulla tua macchina
```

Sul DGX Spark cambia una cosa sola: il profilo `vllm` del compose. Stessa
immagine, stesso schema di policy — e le immagini sono costruite e testate anche
per `linux/arm64`, perché un'immagine solo x86 su un GB10 non parte e lo scopri
in sede dal cliente.

## Cosa non fa, detto prima

- **Pseudonimo non è anonimo.** La mappa di re-identificazione esiste: la
  redazione riduce l'esposizione, non toglie la base giuridica.
- **Sul GB10 non c'è confidential computing.** Memoria cifrata e attestazione
  remota della GPU sono reali su hardware classe HGX B200, non su un DGX Spark.
  Un amministratore privilegiato può leggere la memoria — on-prem
  quell'amministratore è il cliente, ed è il punto, ma va detto in riunione e non
  scoperto in audit.
- **Il registro non ha ancora un'ancora esterna.** È a prova di modifica,
  cancellazione e riordino; una catena ricostruita da zero da chi ha accesso in
  scrittura non è rilevabile, e c'è un test che lo dichiara.
- **I modelli piccoli sbagliano ancora gli argomenti degli strumenti.** Il
  decoding vincolato da grammatica è la prossima cosa, ed è la claim di ricerca
  del progetto.

Il repository pubblica i propri buchi in tabella accanto alle proprie garanzie, e
ogni garanzia ha un test con il suo nome. È l'unico modo in cui un fornitore può
chiedere di essere creduto su una cosa che, per definizione, il cliente non può
vedere mentre accade.
