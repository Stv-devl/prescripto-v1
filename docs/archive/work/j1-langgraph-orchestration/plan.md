# Plan: J1 — orchestration du chat portée en LangGraph   (entry: docs/specs/j1-langgraph-orchestration.md · research: docs/work/j1-langgraph-orchestration/research.md · design: n/a)
Token profile: economy

## Skips
- INTERFACE : SKIP — aucune surface utilisateur, portage backend pur (annoncé en Phase 0).
- Front : SKIP — le contrat SSE consommé par `client/src/features/chat/` ne change pas (spec §OUT).
- DB : SKIP — checkpointer retenu = `InMemorySaver` (voir Decisions ci-dessous), aucune table nouvelle, aucune migration Alembic.
- Parallélisation EXECUTE : SKIP — `CLAUDE.md` §Workflows : « EXECUTE reste
  séquentiel — une exception, la jambe RED, un `test-writer` par couche
  test-first. » Rien dans ce plan n'est une jambe RED de couche test-first hors
  `graph.py` lui-même (déjà traité comme tel) : le cutover API et l'adapter
  harnais sont test-after/câblage, donc strictement séquentiels comme le reste
  (révision post plan-critic : la version précédente de ce plan proposait deux
  « lots parallèles » à tort — corrigé).

## Decisions clarifiant les Open questions de research.md
- **Checkpointer : `InMemorySaver`, pas `langgraph-checkpoint-postgres`.** Ce
  portage est un aller-retour requête-réponse sans étape d'interruption humaine
  (pas de pause-for-input dans le scope) ; le bénéfice marginal d'un
  checkpointer durable (reprise après crash mi-exécution, replay) ne justifie
  pas un second driver Postgres (`psycopg` v3) ni une migration pour ce
  portage. La persistance de l'historique affiché reste entièrement
  `messages`/`conversations`, inchangée. Réversible : si `J2`/`J3` a besoin de
  résumabilité, `langgraph-checkpoint-postgres` s'ajoute alors sans toucher au
  reste du graphe.
  **Conséquence explicite sur la spec, §Business logic to cover** (« le
  checkpointer persiste et restitue l'état d'exécution attendu entre deux
  appels ») : **aucun cas de test ne couvre ce point, volontairement.**
  `build_graph()` compile un graphe neuf par requête (voir ci-dessous), donc
  il n'existe structurellement **aucune persistance inter-appels** à prouver
  — le seul comportement observable d'`InMemorySaver` dans ce scope est
  intra-run (survie à un crash mi-exécution de la même requête), qui ne
  s'exerce pas sans point de reprise câblé côté API, explicitement hors
  scope. Ce n'est pas un oubli : la ligne de la spec est satisfaite en tant
  que question de recherche répondue (research.md, checkpointer), pas en tant
  que cas de test — corrigé après le second plan-critic du 2026-09-18, qui
  avait relevé le silence.
- **Le graphe ne porte QUE les étapes 2 à 6** (réécriture → recherche →
  enrichissement → extraction structurée → génération). Les étapes 1
  (résolution de conversation + persistance du message utilisateur) et 7
  (persistance du message assistant + événements finaux) restent dans la
  fonction orchestratrice `chat_stream()` qui enveloppe l'exécution du graphe
  — exactement la même forme qu'aujourd'hui dans `stream.py`. Ce choix évite
  toute question de sérialisation d'un objet `AsyncSession` dans un état de
  graphe checkpointé : les nœuds sont des closures liées à `db`/`tenant_id`/
  `project_id`/`user_id` pour cette requête, jamais des champs d'état.
  `build_graph()` compile un graphe **par requête** (les closures capturent
  `db`/`tenant_id`/`project_id`/`user_id` de cet appel précis) — jamais un
  graphe module-level partagé entre requêtes.
- **`extract_table_node` et `extract_schema_node` s'exécutent en parallèle de
  `generate_node`, pas en séquence.** Dans `stream.py:270-283`, les deux
  tâches d'extraction sont lancées via `asyncio.create_task` **avant** la
  boucle de streaming Mistral et seulement attendues après (:303-324) — donc
  concurrentes avec la génération aujourd'hui. Un plan qui les listerait comme
  des nœuds séquentiels ordinaires sérialiserait ce qui est concurrent et
  degraderait la latence (AC4). Topologie retenue : le graphe est statique
  (tous les nœuds existent à la compilation) ; après `enrich_node`, une
  fonction de routage conditionnelle (`add_conditional_edges`, évaluée à
  l'exécution sur l'état déjà connu — `structured`/`schema_flag`/
  `context_block` sont posés par `rewrite_node`/`enrich_node` avant que cette
  arête ne soit évaluée) active toujours `generate_node`, et active
  `extract_table_node`/`extract_schema_node` seulement quand leur drapeau est
  actif ET `context_block` non vide — reproduisant `if structured == "table"
  and context_block:` / `if schema_flag == "schema" and context_block:`. Un
  nœud `join_node`
  ne s'exécute qu'une fois **tous** ses prédécesseurs actifs terminés (jointure
  standard LangGraph — un superstep attend toutes les branches actives avant
  le suivant). Les trois nœuds écrivent des clés d'état disjointes
  (`full_response`/`generation_usage`, `table`, `schema`) : aucun reducer
  personnalisé n'est nécessaire. Le verrou `mistral_large_limiter` continue de
  sérialiser les appels réseau réels quel que soit le parallélisme de
  soumission — comportement inchangé.
- **Streaming : `stream_mode="custom"` + `get_stream_writer()`**, pas
  `"messages"` (qui ne capte rien pour un appel SDK brut — research.md, External
  surface Q3). Le nœud de génération boucle sur
  `mistral_client.chat.stream_async(...)` et appelle `writer({"text": token})`
  par token ; l'orchestrateur convertit chaque item de
  `graph.astream(state, stream_mode="custom")` en ligne SSE, à l'identique du
  format actuel.
- **`@traceable` posé sur chaque nœud** (rewrite, search, enrich, extract_table,
  extract_schema, generate) — sinon LangSmith ne montre que le run englobant.
- **Pin des versions dans `.claude/rules/01-stack.md` et promotion au ledger
  `settled.md`** dans le même commit que `uv add langgraph langsmith` — geste
  explicite du write chain ci-dessous, pas laissé à une session future.
- **`LANGSMITH_TRACING` actif partout y compris AWS** (décision utilisateur,
  cadrage) — `Settings` porte donc `langsmith_tracing: bool = True` par défaut
  hors tests, activable/désactivable via env comme tout le reste.
  **Affiné en EXECUTE (2026-09-18)** : `configure_langsmith()` n'active
  réellement le tracing que si une clé est présente (`langsmith_tracing and
  langsmith_api_key`), pas sur le seul booléen — mesuré empiriquement qu'une
  clé vide déclenche un vrai appel réseau (toujours 401, non bloquant mais
  réel) par appel tracé, ce qui aurait ajouté une dépendance réseau non
  souhaitée à la suite de tests. `_deployed_is_locked_down` exige déjà une clé
  hors `local` quand le tracing est actif, donc ce garde-fou ne change rien en
  production/AWS — seulement en local/tests, où une clé est légitimement
  absente.
- **La latence induite par le tracing LangSmith** (research.md : non réglé
  côté SDK Python) se mesure empiriquement pendant la validation harnais, pas
  en amont — si le p95 de la colonne `v0` dérive significativement de
  `baseline`/`baseline-aws` alors que le tracing est actif, désactiver le
  tracing pour un second run isolerait la cause avant d'accuser autre chose.

## Write chain (sequential)
1. **DB — SKIP** (voir ci-dessus).
2. **Backend** :
   a. `uv add langgraph langsmith` (`backend/pyproject.toml`, `backend/uv.lock`).
   b. Pin des versions installées dans `.claude/rules/01-stack.md` (table
      Backend) + promotion des 4 faits version-pinnés de
      `docs/research-cache/langgraph-langsmith.md` vers
      `docs/research-cache/settled.md` (geste du main thread, pas d'un agent).
   c. `backend/app/core/config.py` — 3 champs `Settings` (`langsmith_api_key`,
      `langsmith_tracing`, `langsmith_project`), extension de
      `_deployed_is_locked_down` (exige `langsmith_api_key` si
      `langsmith_tracing` est vrai hors `local`). Test-after :
      `backend/tests/core/test_config.py`.
   d. `backend/app/core/langsmith.py` (nouveau) : une fonction
      `configure_langsmith(settings)` qui pose les variables d'environnement
      `LANGSMITH_TRACING`, `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT` à partir
      de `Settings` — appelée une fois au niveau module de `graph.py` (voir
      2.e-bis), pas dans `main.py`. Test-after :
      `backend/tests/core/test_langsmith.py`.
   e. **Corrigé en review (2026-09-18)** : ce paragraphe disait initialement
      que `graph.py` n'importerait jamais `app.core.langsmith`, donc qu'ajouter
      une entrée `EXTERNAL_CLIENTS` était inutile. **Faux** — l'étape 2.e-bis,
      écrite juste après dans la même session, décide justement que
      `configure_langsmith(settings)` s'appelle au niveau module de `graph.py`,
      ce qui exige `from app.core.langsmith import configure_langsmith` dans
      ce fichier (confirmé sur disque : `graph.py:28`). Le raisonnement de 2.e
      a été invalidé par 2.e-bis sans être revu — trouvé par la review
      correctness, pas en amont. `EXTERNAL_CLIENTS`
      (`.claude/hooks/enforce-backend-layers.py`) porte désormais
      `"app.core.langsmith": ["core/", "services/chat/graph.py"]`, même
      patron que `qdrant`/`mistral`.
   e-bis. **Écart décidé en EXECUTE (2026-09-18), pas d'édition de `main.py`** :
      l'adapter harnais (`sprint/eval/adapter/*.py`) appelle `chat_stream()`
      **in-process, sans jamais importer `app.main`**
      (`sprint/eval/adapter/service.py:19-20` — confirmé en relisant le
      fichier) — câbler `configure_langsmith()` uniquement dans le lifespan de
      `main.py` laisserait le tracing inactif pendant tout run harnais, ce qui
      viole directement l'AC6 (« une trace LangSmith d'un appel réel »,
      l'appel réel étant précisément un run harnais). Le seul point d'import
      partagé par les deux chemins (API et harnais) est `graph.py` lui-même :
      `configure_langsmith(settings)` s'appelle donc **au niveau module de
      `graph.py`**, une fois, comme le fait déjà `core/mistral.py` pour
      `mistral_client = Mistral(api_key=settings.mistral_api_key)` au même
      niveau. `main.py` n'est pas touché.
   f. **[`backend/app/services/chat/graph.py` RED→GREEN]** — le module
      test-first. Contenu : `ChatState(TypedDict)`, les nœuds — `rewrite_node`,
      `search_node`, `enrich_node`, `generate_node`, `extract_table_node`,
      `extract_schema_node` (chacun `@traceable`), plus `error_node` (nœud
      terminal du chemin d'erreur recherche) et `join_node` (structurel, voir
      ci-dessous) — **huit nœuds au total**. Les arêtes (échec de recherche →
      `error_node` ; sinon →
      `enrich_node` → éventail vers `generate_node` et, conditionnellement,
      `extract_table_node`/`extract_schema_node` → **un nœud `join_node`,
      purement structurel (ne touche ni `db` ni Qdrant/Mistral), qui ne fait
      que matérialiser le point où le graphe a attendu toutes les branches
      actives** avant de rendre l'état final — voir Decisions ci-dessus pour
      la préservation du parallélisme actuel ; la persistance Postgres réelle
      (étape 7) reste hors graphe, dans l'orchestrateur, pour la raison déjà
      donnée (pas d'`AsyncSession` dans l'état checkpointé)),
      `build_graph()` qui compile avec `InMemorySaver` **par requête**
      (closures sur `db`/`tenant_id`/`project_id`/`user_id` — `join_node`
      n'en a besoin d'aucun), et la fonction publique
      `async def chat_stream(db, *, tenant_id, project_id, user_id, question,
      conversation_id=None) -> AsyncGenerator[str, None]` — **même signature
      qu'aujourd'hui**, qui enveloppe l'exécution du graphe entre la
      résolution de conversation (étape 1, réutilise `conversation_mod`) et la
      persistance finale (étape 7). Les helpers purs actuellement privés dans
      `stream.py` (`_usage_leg`, `_usage_event`, `_normalize_for_dedup`,
      `_filter_bilan_thermique`, `_build_context_and_sources`,
      `_build_mistral_messages`, `_run_search`) migrent tels quels dans ce
      fichier (ou un sous-module s'il dépasse 500 lignes — décision de
      REFACTOR, mesurée, pas devinée maintenant).
   g. `backend/app/api/chat.py` — cutover : importe `chat_stream` depuis
      `app.services.chat.graph` au lieu de `app.services.chat.stream`. Aucun
      autre changement (signature identique).
   h. `backend/app/services/chat/__init__.py` — mise à jour du ré-export si
      applicable.
3. **Front — SKIP.**
4. **Wiring** — couvert par 2g (aucun changement de routeur, l'endpoint existe déjà).
5. **Tests** :
   a. `backend/tests/api/test_chat.py` (nouveau, test-after — aucun test API
      chat n'existe aujourd'hui) : intégration bout-en-bout sur l'endpoint
      réel, `mistral_client`/`qdrant_client` patchés comme le fait déjà
      `tests/services/chat/test_chunk_enrichment.py`, prouve la séquence SSE
      identique à l'ancien comportement.
   b. `sprint/eval/adapter/langgraph_v0.py` (nouveau) — même contrat que
      `sprint/eval/adapter/service.py`/`bourrage_contexte.py` :
      `async def repondre(question) -> (texte, sources, usage)`, appelle le
      nouveau `chat_stream()` in-process et draine ses événements SSE.
   c. Harnais réel : `python sprint/eval/adapter/langgraph_v0.py` (ou
      équivalent) produit `sprint/eval/result/v0.csv` — label `v0`, jamais
      `baseline` (le harnais refuse déjà l'écrasement).
6. **Refactor — tenté, abandonné pour une raison outillage, pas une décision
   arbitraire.** `graph.py` fait 698 lignes (> 500). Le split en package
   (`services/chat/graph/{helpers,state,build}.py` + `__init__.py`) a été
   essayé : `tdd-require-red-py.py` refuse la **création** de chacun de ces
   nouveaux fichiers tant que son miroir (`tests/services/chat/graph/test_*.py`)
   n'a pas prouvé un RED — un mécanisme pensé pour un nouveau comportement, pas
   pour la réorganisation interne d'un fichier déjà vert et déjà couvert par
   `test_graph.py` (dont la surface publique, `chat_stream`/`_usage_leg`/
   `_usage_event`, ne change pas de chemin d'import quel que soit le découpage
   interne). Fabriquer de faux tests RED pour satisfaire le hook aurait été
   une entorse plus grave à la discipline TDD que de laisser le fichier en un
   seul morceau. **Décision : `graph.py` reste un seul fichier.** Écart de
   seuil accepté comme Minor en review — même traitement que `admin.py`
   (1742 l.), `summary.py` (1174 l.), `search.py` (710 l.), déjà documentés au
   backlog comme candidats `/refactor:split` non traités, pas des exceptions
   nouvelles inventées pour ce chantier.
   **Suppression annulée — correction post-run harnais (2026-09-18).** Le
   plan prévoyait de supprimer `backend/app/services/chat/stream.py` et son
   test gelé une fois l'équivalence confirmée. Faux départ : relecture de
   `sprint/eval/adapter/service.py:19-20` (l'adapter harnais `baseline`)
   montre qu'il importe `stream.py` **directement**, pas via
   `app.services.chat` ni via le graphe. Le supprimer casserait pour
   toujours la capacité de rejouer la baseline — exactement ce que
   `sprint/PLAN-SPRINT.md` §2 interdit (« ta baseline doit rester
   rejouable, pas seulement mesurée une fois ») et ce que `CLAUDE.md` dit
   déjà pour `RETRIEVAL_MODE=baseline` (« on ne touche jamais »). `stream.py`
   **reste en place indéfiniment**, gelé, comme référence baseline — seul
   `api/chat.py` (via `app/services/chat/__init__.py`) bascule vers
   `graph.py` en production. Le blast radius de research.md avait bien
   listé les 3 sites, mais pas cette tension avec le principe de
   reproductibilité — trouvé en exécutant cette étape, pas en amont.
7. **Trace LangSmith** — étape séquentielle propre, pas seulement une note en
   marge des acceptance criteria (corrigé après le second plan-critic) :
   consulter la trace d'au moins un appel réel `v0` dans LangSmith, documenter
   coût/latence par nœud dans `sprint/JOURNAL.md`. Détail complet en
   Acceptance criteria ci-dessous (AC6). Dernière étape avant `/loop:review`/`/loop:ship`.

## Parallel lots (inside this track, same tree)
none — fully sequential. Le cutover API (2g) et l'adapter harnais (5b) ne
partagent aucun fichier et dépendent tous deux uniquement de 2f terminé, mais
aucun des deux n'est la jambe RED d'une couche test-first : `CLAUDE.md`
§Workflows réserve le parallélisme d'EXECUTE à ce seul cas (« EXECUTE reste
séquentiel — une exception, la jambe RED »). Corrigé après le plan-critic du
2026-09-18, qui avait relevé que la version précédente violait cette règle.
Écrits l'un après l'autre, dans l'ordre du write chain.

## Track isolation
- Worktree : none — single track, un seul chantier en vol (Phase 0.5).
- Shared foundations touched : `backend/pyproject.toml`/`uv.lock` (lockfile),
  `.claude/rules/01-stack.md`, `.claude/hooks/enforce-backend-layers.py`. Aucun
  autre chantier ne doit tourner en parallèle sur ce dépôt tant que ce plan
  n'est pas mergé.

## Files
| Path | Create/Edit | Role |
| --- | --- | --- |
| `backend/pyproject.toml` | Edit | ajoute `langgraph`, `langsmith` |
| `backend/uv.lock` | Edit (généré) | résolution `uv add` |
| `.claude/rules/01-stack.md` | Edit | pin versions backend |
| `docs/research-cache/settled.md` | Edit | promotion des faits version-pinnés |
| `backend/app/core/config.py` | Edit | 3 champs `Settings` + validateur |
| `backend/tests/core/test_config.py` | Edit (test-after) | cas des 3 champs + validateur |
| `backend/app/core/langsmith.py` | Create | `configure_langsmith()`, client confiné |
| `backend/tests/core/test_langsmith.py` | Create (test-after) | cas de `configure_langsmith()` |
| `.claude/hooks/enforce-backend-layers.py` | Edit | `EXTERNAL_CLIENTS["app.core.langsmith"]` (corrigé en review, voir 2.e) |
| `backend/app/main.py` | SKIP (voir 2.e-bis) | — |
| `backend/app/services/chat/graph.py` | Create (test-first) | état, nœuds, graphe, `chat_stream()` |
| `backend/tests/services/chat/test_graph.py` | Create (test-first, gelé après gate) | comportement complet du pipeline |
| `backend/app/api/chat.py` | Edit | cutover import |
| `backend/app/services/chat/__init__.py` | Edit | ré-export si applicable |
| `backend/tests/api/test_chat.py` | Create (test-after) | intégration SSE bout-en-bout |
| `sprint/eval/adapter/langgraph_v0.py` | Create | adapter harnais `v0` |
| `sprint/eval/langgraph_v0.py` | Create (non prévu au plan initial) | point d'entrée CLI, même patron que `bourrage_contexte.py` |
| `backend/tests/conftest.py` | Edit (non prévu au plan initial) | 2 fixtures autouse : neutralise le vrai débit du limiteur Mistral (sinon la suite prend des minutes) et purge la pollution d'env `LANGSMITH_*` que `configure_langsmith()` laisse derrière lui (sinon des `Settings()` nues plus loin dans la suite héritent d'une valeur au lieu du défaut du champ) |
| `backend/app/services/chat/stream.py` | **SKIP — reste en place** (voir Refactor, correction du 2026-09-18) | référence baseline, importée directement par l'adapter harnais |
| `backend/tests/services/chat/test_stream.py` | SKIP — reste gelé, inchangé | couvre `stream.py`, toujours vivant |

## Contracts
- `async def chat_stream(db: AsyncSession, *, tenant_id: uuid.UUID, project_id:
  uuid.UUID, user_id: uuid.UUID, question: str, conversation_id: uuid.UUID |
  None = None) -> AsyncGenerator[str, None]` — **signature inchangée**, seule
  l'implémentation interne devient un graphe LangGraph compilé.
- Séquence SSE inchangée, dans cet ordre exact : `{"conversation_id": str}` →
  `{"text": token}` × N → `{"structured": {...}}`? (seulement si
  `structured == "table"` **et** `context_block` non vide **et** extraction
  réussie) → `{"schema": {...}}`? (seulement si `schema_flag == "schema"` **et**
  `context_block` non vide **et** extraction réussie ; `enrich_schema_with_search`
  appelé quand `schema.schema_type == "semelle_filante"` **et** (des
  paramètres manquent **OU** `"fond_fouille"` est présent dans
  `schema.params`) — condition exacte de `stream.py:315-322`, plus large
  qu'un simple « paramètres manquants ») → `{"sources": [...]}`? (**seulement
  si `sources` non vide** — garde `if sources:`, pas inconditionnel) →
  `{"usage": {"rewrite": {...}, "generation": {...}, "total": {...}}}` →
  `[DONE]`.
- Chemin d'erreur recherche : `{"conversation_id": str}` est **déjà émis**
  avant que la recherche ne s'exécute (`stream.py:180` précède `:225`). Une
  exception dans `_run_search` produit donc la séquence à **3 événements**
  `{"conversation_id": str}` → `{"error": "Le service de recherche est
  temporairement indisponible. Veuillez réessayer dans quelques instants."}`
  → `[DONE]`, **jamais** `text`/`structured`/`schema`/`sources`/`usage`, et
  **aucune** persistance du message assistant (le message utilisateur, lui,
  est déjà commité avant l'émission de `conversation_id`).
- `ChatState(TypedDict)` (nom indicatif, ajustable en EXECUTE) porte
  uniquement des données sérialisables métier — jamais `db`/`tenant_id`/
  `project_id`/`user_id` (passés par closure de nœud, pas par l'état) :
  `question`, `search_query`, `related_queries`, `scope`, `structured`,
  `schema_flag`, `search_results`, `context_block`, `sources`, `full_response`,
  `rewrite_usage`, `generation_usage`, `table`, `schema`, `error`.
- `_usage_leg(usage: UsageInfo | None) -> dict[str, int | float]` et
  `_usage_event(rewrite, generation) -> dict[str, object]` migrent identiques
  (mêmes calculs, mêmes clés) depuis `stream.py`.
- `repondre(question: str) -> tuple[str, list[dict], dict]` (contrat harnais,
  inchangé) pour `sprint/eval/adapter/langgraph_v0.py`.

## Test plan (gate — validated by the user before EXECUTE)

**Open questions de research.md — toutes réglées ci-dessus** (checkpointer,
frontière graphe/orchestrateur, mode de streaming, blocage LangSmith reporté à
une mesure empirique en EXECUTE plutôt qu'à une hypothèse figée en test).
Aucune n'est reportée à l'implémentation sans réponse.

Ce plan ne corrige pas un défaut — c'est un portage. Pas de bloc
**Reproduction**.

### Test-first — backend : `backend/tests/services/chat/test_graph.py`
↔ `backend/app/services/chat/graph.py`

**Core behaviour**
- [ ] un run complet (scope "specific", pas de table/schema, recherche non
      vide) émet exactement la séquence `conversation_id` → `text` × N →
      `sources` → `usage` → `[DONE]`, dans cet ordre.
- [ ] le texte accumulé sur l'ensemble des événements `text` est identique à
      la concaténation des tokens produits par le flux Mistral simulé.
- [ ] à la fin du run, un message assistant est commité en base avec
      `content` égal au texte accumulé et `sources_json` reflétant les
      sources émises.
- [ ] `_usage_leg(None)` rend des zéros partout.
- [ ] `_usage_leg` avec 1 000 000 tokens d'entrée et 500 000 de sortie rend un
      coût de 1.25 USD (prix $0.5/$1.5 par million de tokens — fixture
      chiffrée à la main, reprise identique de l'ancien test).
- [ ] `_usage_leg` sur un usage dont `prompt_tokens` est absent compte 0 token
      d'entrée.
- [ ] `_usage_event(None, None)` rend `rewrite`, `generation` et `total` tous
      à zéro.
- [ ] `_usage_event` avec seulement `generation` renseigné laisse `rewrite` à
      zéro et `total` égal à `generation`.
- [ ] `_usage_event` avec les deux legs renseignés somme chaque champ dans
      `total`.

**Business rules**
- [ ] un échec de la recherche (exception) émet, dans cet ordre exact,
      `{"conversation_id": ...}` → `{"error": "Le service de recherche est
      temporairement indisponible. Veuillez réessayer dans quelques
      instants."}` → `[DONE]` — **trois** événements, jamais deux —, sans
      aucun `text`/`sources`/`usage`, et sans commit du message assistant
      (le message utilisateur reste commité).
- [ ] avec `scope == "broad"`, le contexte assemblé inclut le résultat de
      `build_db_context` avant le contexte des chunks ; avec `scope ==
      "specific"`, `build_db_context` n'est pas appelé.
- [ ] avec `scope == "broad"`, `structured` et `schema_flag` sont forcés à
      `"none"` quel que soit ce que `rewrite_query` a renvoyé — sauf si la
      question ou la requête réécrite matche `FORCED_SCHEMA_RE`, auquel cas
      `schema_flag` repasse à `"schema"` **même en scope broad** (le forçage
      par mot-clé s'applique après la réinitialisation broad, jamais avant —
      ordre exact de `stream.py:201-219`).
- [ ] une question dont le texte original ne contient aucun mot-clé
      thermique (`_THERMAL_KEYWORDS_RE`) voit ses chunks de type/nom de
      fichier « bilan thermique » retirés du contexte assemblé
      (`_filter_bilan_thermique`) ; une question qui matche ces mots-clés les
      conserve tous.
- [ ] avec `structured == "table"` et un contexte non vide, un événement
      `{"structured": ...}` est émis, construit à partir du résultat de
      `extract_table`.
- [ ] avec `schema_flag == "schema"` et un contexte non vide, un événement
      `{"schema": ...}` est émis, construit à partir du résultat de
      `extract_schema` (y compris l'enrichissement `enrich_schema_with_search`,
      déclenché quand `schema_type == "semelle_filante"` et que des
      paramètres manquent **ou** que `"fond_fouille"` est présent dans
      `schema.params`).
- [ ] quand la recherche ne rend aucun résultat exploitable (contexte vide),
      aucun événement `sources` n'est émis (garde `if sources:`), les tâches
      d'extraction table/schema ne sont pas lancées, et la génération se
      poursuit malgré tout sur le message système/contexte vide.
- [ ] `mistral_large_limiter.wait()` (le verrou partagé, pas une instance
      locale) est attendu avant chaque appel Mistral effectué pendant le run
      (réécriture, génération, et extraction table/schema quand déclenchées).
- [ ] des chunks d'un autre tenant, présents dans le magasin Qdrant simulé
      pour la même requête, n'apparaissent jamais dans le contexte assemblé ni
      dans les sources d'un run scopé à un tenant donné (cas cross-tenant
      obligatoire, `07-backend.md`).

**Edge cases**
- [ ] une exception dans `extract_schema` dégrade silencieusement (aucun
      événement `schema`, le run continue).
- [ ] une exception dans `extract_table` dégrade silencieusement (aucun
      événement `structured`, le run continue).
- [ ] un contexte non vide mais dont l'ensemble des sources est filtré
      (`_build_context_and_sources` ne retient rien) rend `sources = []` et
      aucun événement `sources`.

### Test-after — core, api, harnais
- `backend/tests/core/test_config.py` — les 3 nouveaux champs se chargent
  depuis l'environnement ; `_deployed_is_locked_down` lève si
  `langsmith_tracing` est vrai, l'environnement n'est pas `local`, et
  `langsmith_api_key` est vide.
- `backend/tests/core/test_langsmith.py` — `configure_langsmith(settings)`
  pose les 3 variables d'environnement attendues à partir de `Settings`.
- `backend/tests/api/test_chat.py` — intégration sur l'endpoint réel :
  la séquence SSE observée à travers `POST /projects/{id}/chat` correspond au
  contrat ci-dessus (au moins le chemin heureux et le chemin d'erreur
  recherche).
- Harnais : `sprint/eval/result/v0.csv` produit et comparé à `baseline`/
  `baseline-aws` sur les 4 axes (coût, rappel, p95, taux de réponse sans
  source) — c'est la preuve d'équivalence, pas un test pytest.

Business logic sans test = FAIL (`.claude/rules/05-testing.md`).

## Vigilance (carried from research)
- Le verrou Mistral doit rester un verrou global unique — vérifié par le cas
  business-rule dédié ci-dessus, à re-vérifier en review si un nœud crée un
  `_RateLimiter` local par erreur.
- Le shim `_search_compat` reste l'unique point d'entrée Qdrant — la review
  vérifie qu'aucun nœud n'appelle `.query_points()` directement.
- Le filtre `tenant_id` traverse chaque sous-appel (`expand_heading_chunks`,
  `enrich_with_dpgf_quantities`, `build_db_context`) — couvert par le cas
  cross-tenant, la review vérifie qu'aucun refactor ne l'a fait sauter.
- La séquence et la forme exacte des événements SSE (y compris les gardes
  `if sources:` et les conditions table/schema) sont un contrat gelé par les
  tests ci-dessus. **La review ne se contente PAS de `Contracts`** — ce
  document a déjà eu une erreur (l'omission de `conversation_id` dans le
  chemin d'erreur, corrigée par le plan-critic du 2026-09-18) : la review
  relit le dernier `stream.py` via `git show HEAD:backend/app/services/chat/stream.py`
  (ou l'historique, une fois le fichier supprimé du disque) et compare
  événement par événement, pas seulement contre ce plan.
- `stream_mode="custom"` + `get_stream_writer()` est le mécanisme correct pour
  un nœud SDK brut ; la review signale un usage de `stream_mode="messages"`
  comme un défaut, pas une variante.
- La dépendance transitive `langchain-core` (via `uv add langgraph`) n'est pas
  un écart de scope — ce n'est ni `langchain` complet ni
  `langchain-mistralai`. La review ne doit pas la lever comme telle.
- `@traceable` doit être présent sur chaque nœud appelant `mistralai`
  directement, sinon LangSmith ne montre que le run englobant sans détail.
- Seuls 3 sites référençaient `chat_stream`/`stream.py`
  (`api/chat.py`, `sprint/eval/adapter/service.py`, le test gelé) — la review
  vérifie qu'aucun quatrième site n'est apparu depuis (grep avant suppression).
- Le harnais refuse d'écraser un résultat existant — la review vérifie que le
  run `v0` utilise son propre label et n'a jamais écrit sur `baseline*.csv`.
- Le pin de version dans `01-stack.md` + la promotion à `settled.md` doivent
  être dans le même commit que `uv add` — la review vérifie que ces deux
  fichiers bougent dans le diff.

## Acceptance criteria (carried from the entry artifact)
- [x] Le harnais produit un tableau à trois colonnes (`baseline` ·
      `bourrage_contexte` · `v0`) sur les mêmes 20 questions. **Fait** —
      `baseline.csv` local a été écrasé avant ce chantier (journal du
      2026-09-18) ; la colonne de référence est `baseline-aws.csv`, déjà la
      référence retenue par ce plan pour la marge chiffrée.
- [x] `v0` : coût moyen par question dans la même fourchette que `baseline`.
      **Fait** — 0,004098 $/question vs 0,0041 $ (`baseline-aws`), quasi
      identique.
- [x] `v0` : rappel (qualité) au moins égal à `baseline` (18/20 mesuré à `J0`/`J0b`).
      **Fait** — 18/20, mêmes deux échecs exacts que `baseline-aws` (Q5
      piège-exact, Q20 raté de récupération pré-existant), zéro régression,
      noté à la main sur les 20 réponses.
- [x] `v0` : p95 latence dans la même fourchette que `baseline`. **Fait** —
      18,46 s vs 15,73 s (`baseline-aws`), +17,4 %, dans la marge ±20 %
      décidée ci-dessous.
- [x] Le flux SSE produit par le nouveau chemin est fonctionnellement
      identique côté client — **Fait**, `backend/tests/api/test_chat.py`
      (2 cas : chemin heureux, chemin d'erreur recherche).
- [x] Une trace LangSmith d'un appel réel est consultée et son coût/latence par
      nœud est expliqué. **Fait** — après plusieurs obstacles côté compte
      (voir Decisions/Traps) : trace lue via `client.list_runs()` sur un run
      réel. Détail dans `sprint/JOURNAL.md`.
- [x] Chaque nœud qui touche Qdrant ou Postgres continue de filtrer par
      `tenant_id` — **Fait**,
      `test_cross_tenant_chunks_never_leak_into_context_or_sources`.
- [x] Suite complète backend verte après cutover (`python -m pytest`),
      couverture inchangée ou meilleure sur `app/services/chat/`. **Fait** —
      438 passed, `graph.py` à 92 % (vs 16 % sur le corps du générateur de
      l'ancien `stream.py`).

**Marge chiffrée pour "même fourchette"** (précisée ici, absente de la spec
d'origine, décidée par `/loop:plan` comme la spec le prévoyait) : coût moyen et
p95 latence de `v0` dans **± 20 %** de `baseline-aws` (la référence de
production, `sprint/JOURNAL.md` 2026-09-18). **Ce seuil est bloquant comme les
autres critères d'acceptation** — le gabarit de `/loop:plan` lui-même est
explicite : « Copy the acceptance criteria verbatim; do not rephrase them
softer » (`.claude/commands/loop/plan.md`, §Rules). La spec n'a délégué à ce
plan que le choix de la marge chiffrée, pas la nature bloquante du critère
(corrigé après le premier plan-critic du 2026-09-18, qui avait raison de
relever que la version précédente le dégradait en simple avis — et la
citation initialement donnée ici pour le justifier, attribuée à
`.claude/rules/05-testing.md`, était fabriquée : cette chaîne n'existe pas
dans ce fichier, corrigé par le second plan-critic du même jour). Un
dépassement bloque `/loop:ship` au même titre qu'un test rouge ; il ne se lève
que si l'utilisateur l'accepte explicitement à ce gate précis, après lecture
de la cause (ex. surcharge de tracing LangSmith mesurée isolément — voir
Decisions ci-dessus).

L'AC « trace LangSmith consultée » (ci-dessus) est portée par l'étape 7 du
write chain — pas une note séparée : voir plus haut, « Trace LangSmith ».

## Plan critic
Trois passes le 2026-09-18. Passe 1 : completeness 58, quality 35 (1 Critical
+ 7 Major) — tous corrigés. Passe 2 (ciblée sur les corrections) : completeness
92, quality 82, 1 Major restant (duplication rédactionnelle entre une note et
la nouvelle étape 7 du write chain, aucun contenu technique affecté) — corrigé
directement (paragraphe dupliqué supprimé, relu pour confirmer).
- completeness: 92
- quality: 82 (dernier Major, purement rédactionnel, résolu par suppression du doublon)
- surviving blockers: none
