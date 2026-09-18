# Research: J1 — orchestration du chat portée en LangGraph   (entry: docs/specs/j1-langgraph-orchestration.md)
Token profile: economy

## Pattern to follow
Aucun analogue LangGraph dans ce dépôt — première introduction. Le pipeline
actuel (`backend/app/services/chat/stream.py:151-345`) est la référence
comportementale : 7 étapes séquentielles.

1. **Résolution de conversation** (:151-180) — `conversation_mod.get_conversation()`
   / `create_conversation()`, commit du message utilisateur, premier événement
   SSE `{"conversation_id": ...}`.
2. **Réécriture de requête** (:184-216) — `query_rewrite.rewrite_query(question,
   history, usage_sink)` → `(search_query, related_queries, scope, structured,
   schema_flag)`. `scope` bifurque les paramètres de recherche (broad : 21
   chunks / 48k contexte / seuil 0.30 ; specific : 20 / 20k / 0.40).
3. **Recherche** (:225-242) — `search_service.search_merged()` →
   `expand_heading_chunks()` → `enrich_with_dpgf_quantities()`. **Branche
   d'erreur** (:235-239) : exception → `{"error": ...}` et retour anticipé.
4. **Enrichissement de contexte** (:241-255) — si `scope == "broad"`,
   `build_db_context()` préfixe des métadonnées lot/type ; `_filter_bilan_thermique()`
   retire les documents thermiques hors sujet ; `_build_context_and_sources()`
   (pure) déduplique et groupe par lot. Retour anticipé si contexte vide
   (`sources = []`).
5. **Extraction structurée parallèle** (:270-324) — deux tâches asyncio créées
   mais pas attendues tout de suite : `extract_table()` si `structured ==
   "table"`, `extract_schema()` si `schema_flag == "schema"`. Chacune dégrade
   silencieusement (log + `None`) sur exception (`schema_extraction.py:137-140`,
   `table_extraction.py:156-157`).
6. **Génération streamée** (:285-301) — `mistral_large_limiter.wait()` puis
   `mistral_client.chat.stream_async()`. Chaque token → SSE `{"text": token}`,
   accumulé dans `full_response`, dernier `usage` capturé.
7. **Persistance et clôture** (:303-345) — attend `table_task`/`schema_task`,
   SSE `{"structured": ...}` / `{"schema": ...}` / `{"sources": [...]}` /
   `{"usage": ...}` / `[DONE]`. **Commit** du message assistant
   (`content`, `sources_json`, `structured_json`, `schema_json`).

Séquence SSE complète, dans l'ordre : `conversation_id` → `text` × N →
`structured`? → `schema`? → `sources` → `usage` → `[DONE]`.

## Wiring points
- `backend/app/api/chat.py:15-35` — `POST /projects/{project_id}/chat`,
  `Depends(CurrentUser)`, appelle `chat_service.chat_stream(db, tenant_id=,
  project_id=, user_id=, question=, conversation_id=)`, retourne
  `StreamingResponse(stream, media_type="text/event-stream",
  headers={"X-Accel-Buffering": "no"})`. Aucune gestion d'exception à cette
  couche — une panne du générateur part en SSE partiel.
- `.claude/hooks/enforce-backend-layers.py:73-78` — `EXTERNAL_CLIENTS` déclare
  déjà `app.core.qdrant` et `app.core.mistral` comme propriétaires possibles
  dans `services/chat/`. Un nouveau `core/langsmith.py` (ou équivalent) devra y
  être ajouté avec `services/chat/graph.py` comme propriétaire, sinon le hook
  refuse l'import.
- `.claude/hooks/tdd_py_lib.py:45` — `TEST_FIRST_DIRS = ("services/",)` : un
  nouveau `backend/app/services/chat/graph.py` est **test-first par construction**
  (miroir `backend/tests/services/chat/test_graph.py`), gelé une fois RED prouvé.
- `backend/app/core/config.py:59,44-47` — pattern des secrets (`mistral_api_key`
  sans défaut = requis au boot, `qdrant_api_key` avec défaut `""` +
  description) et validateur `_deployed_is_locked_down` (:137-151, refuse un
  déploiement non-local sans `qdrant_api_key`). Ajouter `langsmith_api_key`,
  `langsmith_tracing`, `langsmith_project` sur le même modèle, et étendre le
  validateur pour exiger `langsmith_api_key` si `langsmith_tracing` est vrai
  hors `local` (cohérent avec la décision « LangSmith actif partout, y compris
  AWS »).
- `sprint/eval/harnais.py:72-119` — contrat `repondre(question) -> (texte,
  sources, usage)` : `run(label, repondre)` boucle sur les 20 questions et
  écrit `label.csv`/`label.md`. **Refuse d'écraser un fichier existant**
  (corrigé le 2026-09-18, journal) — donc le run `v0` prendra son propre label,
  jamais `baseline`.
- `sprint/eval/adapter/service.py:28-57` — l'adapter baseline draine les
  événements SSE de `chat_stream()` in-process pour reconstituer
  `(answer_text, sources_list, usage_dict)`. `sprint/eval/adapter/bourrage_contexte.py:60-78`
  est le second exemple du même contrat, sans passer par `chat_stream()` du
  tout. Le futur adapter `v0` suit exactement ce patron : instancier le graphe
  compilé, l'invoquer avec les mêmes paramètres, extraire l'état final dans le
  même tuple.

## Reusable
Tous les sous-modules de `backend/app/services/chat/` sont réutilisables
**sans modification** comme corps de nœuds — signatures relevées par
l'exploration :

| Module | Fonction | Signature |
| --- | --- | --- |
| `query_rewrite.py` | `rewrite_query()` | `async (question, history: list[Message], usage_sink?) -> (str\|None, list[str], str, str, str)` |
| `chunk_enrichment.py` | `expand_heading_chunks()` | `async (tenant_id, project_id, search_results) -> list[SearchResult]` |
| `chunk_enrichment.py` | `enrich_with_dpgf_quantities()` | `async (tenant_id, project_id, search_query, question, search_results) -> list[SearchResult]` |
| `context_enrichment.py` | `build_db_context()` | `async (db, tenant_id, project_id) -> str` |
| `schema_extraction.py` | `extract_schema()` | `async (context_block, question) -> StructuredSchema\|None` |
| `table_extraction.py` | `extract_table()` | `async (context_block, question) -> StructuredTable\|None` |
| `conversation.py` | CRUD (`create/get/list/delete_conversation`, `get_messages`) | — |
| `prompts.py` | constantes + `classify_scope()`, `get_forced_related()`, `get_ouvrage_instruction()` | pures |

Clients à préserver tels quels :
- `core/mistral.py:14` — singleton `mistral_client` ; `:16` pricing
  `{"input": 0.5, "output": 1.5}` USD/M tokens ; `:19-36` `mistral_large_limiter`
  (0.25 req/s, **verrou global sérialisé, pas par utilisateur** — un nœud
  LangGraph doit `await mistral_large_limiter.wait()` avant chaque appel, le
  scheduler du graphe ne doit pas paralléliser les appels Mistral entre
  utilisateurs concurrents).
- `core/qdrant.py:16` — singleton `qdrant_client` ; `:19-46` shim
  `_search_compat()` qui traduit `.search(query_vector=...)` vers
  `.query_points(query=...)` — tout code appelant doit continuer d'utiliser
  `.search()`, jamais `.query_points()` directement.
- Isolation : chaque appel Qdrant pose `Filter(must=[FieldCondition(key="tenant_id",
  match=MatchValue(value=str(tenant_id))), ...])` — non-négociable, à
  reproduire dans chaque nœud qui touche Qdrant.
- `models/message.py` / `models/conversation.py` — schéma inchangé ; le
  checkpointer LangGraph s'ajoute **au-dessus**, il ne remplace rien (voir
  External surface, Q4).
- `backend/tests/fakes.py:36-143` — `FakeQdrant` (store en mémoire,
  `._matches()` applique chaque `FieldCondition` en égalité de chaîne sur le
  payload, méthodes `.search()/.delete()/.upsert()/.batch_update_points()/.scroll()`)
  — patron à réutiliser pour tester le nouveau module sans réseau réel.

## Blast radius
Seuls 3 sites référencent `chat_stream`/`stream.py` :
1. `backend/app/api/chat.py:23` — endpoint de production.
2. `sprint/eval/adapter/service.py:35` — adapter harnais baseline (in-process).
3. `backend/tests/services/chat/test_stream.py` — test gelé, mais **n'importe
   que `_usage_leg`/`_usage_event`**, pas le générateur complet (voir Traps).

Aucun autre appelant interne (`services/summary.py`, `services/admin.py`,
`services/search.py` n'importent pas `chat/stream`). Le cutover décidé en
cadrage (spec, §Scope) est donc borné à ces 3 sites plus l'ajout du module
`graph.py` et de son test miroir.

`backend/pyproject.toml` — versions actuelles : `mistralai>=1.0,<2`,
`qdrant-client>=1.19,<1.21`, `sqlalchemy[asyncio]>=2.0`, `asyncpg>=0.30`,
`fastapi[standard]>=0.115`, Python 3.12, `uv`. `langgraph`/`langsmith`
n'apparaissent nulle part (ni `pyproject.toml`, ni `uv.lock`) — première
installation.

## Live DB state
n/a — aucune ligne existante à interroger. Le port ne touche aucune table
métier ; la seule question ouverte est le choix du checkpointer (voir Open
questions), qui déciderait ou non d'une nouvelle table Postgres via
`/database:migration` — pas d'état à mesurer avant que cette décision soit
prise.

## External surface
Recherche complète : `docs/research-cache/langgraph-langsmith.md` (nouveau,
`stability: volatile`, non encore promue au ledger — rien n'est pinné dans
`01-stack.md` tant que `uv add` n'a pas eu lieu, voir Traps).

- **Version/paquet** `[fetched]` : `uv add langgraph` — dernière stable PyPI
  **1.2.11**, `requires-python >=3.10`. Dépendance transitive dure sur
  `langchain-core<2,>=1.4.7` (inévitable dès `uv add langgraph`, même sans le
  paquet `langchain` complet ni `langchain-mistralai`).
- **État du graphe** `[fetched]` : `StateGraph(State)` avec `State` en
  `TypedDict` (idiome documenté principal) ; reducer par défaut = overwrite,
  `Annotated[T, fn]` pour un reducer personnalisé ; `MessagesState` est un
  prébuilt optionnel, pas adapté ici (l'état du pipeline n'est pas
  principalement une liste de messages).
- **Nœud = fonction Python simple** `[fetched]`, confirmé texto dans la doc
  officielle : « Nodes and Edges are nothing more than functions — they can
  contain an LLM or just good ol' code. » Un nœud appelant `mistralai`
  directement est idiomatique, `langchain-mistralai` n'est **pas requis**.
  Coût réel : on perd la capture automatique de tokens
  (`stream_mode="messages"`) et le traçage LangSmith automatique par nœud —
  tous deux branchés sur le système de callbacks LangChain, qui ne se
  déclenche que pour un appel passant par un `Runnable`/chat-model LangChain.
- **Streaming SSE** `[fetched]` : pour un nœud SDK brut, le mécanisme
  documenté est `stream_mode="custom"` + `get_stream_writer()` (ou paramètre
  `writer` injecté en async/Py<3.11) — le nœud boucle sur
  `mistral_client.chat.stream_async(...)` et appelle `writer(chunk)` par
  token ; côté FastAPI, `async for chunk in graph.astream(input,
  stream_mode="custom")` produit les lignes SSE. `stream_mode="messages"` ne
  capte **rien** pour un appel SDK brut — confirmé explicitement. `"values"`/
  `"updates"` servent à observer les étapes du graphe, pas le texte token par
  token.
- **Checkpointer** `[fetched]` : cœur `langgraph` fournit `InMemorySaver`
  (renommage de l'ancien `MemorySaver`, non durable, perdu au restart).
  Production Postgres → paquet séparé `langgraph-checkpoint-postgres` (3.1.2),
  qui apporte **`psycopg` v3** — un second driver Postgres en plus de
  `asyncpg`/SQLAlchemy déjà en place. Un checkpoint est un instantané complet
  de **tout l'état du graphe** par super-step (requête reformulée, hits de
  recherche, contexte enrichi, réponse partielle/finale — pas seulement le
  message final), indexé par `thread_id`, avec pointeur parent pour replay.
  **N'ajoute rien à la table `messages` existante** — sert la reprise après
  crash mi-exécution et le replay/debug, pas la persistance de l'historique
  affiché à l'utilisateur, qui reste `messages`/`conversations`.
- **LangSmith — env vars** `[fetched]` : `LANGSMITH_TRACING=true`,
  `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT` — plus de nommage `LANGCHAIN_*`
  pour ces trois-là.
- **LangSmith — auto-trace vs `@traceable`** `[fetched]`, confirmé
  explicitement : seuls les appels passant par un `Runnable`/chat-model
  LangChain sont tracés automatiquement. Un nœud fonction simple appelant le
  SDK brut (la forme retenue ici) **n'est pas tracé automatiquement** — il
  faut un `@traceable` explicite par nœud pour qu'il apparaisse dans l'arbre
  de trace. Le run du graphe lui-même (`graph.invoke`/`.astream`) est tracé
  comme run englobant dans tous les cas ; le manque concerne le détail
  interne par nœud.
- **LangSmith — blocage de la requête** — **non réglé.** Seul un réglage
  spécifique JS (`LANGCHAIN_CALLBACKS_BACKGROUND`) a été trouvé dans la doc
  officielle ; aucune confirmation pour le SDK Python. Reporté en Open
  questions.
- **LangSmith — tarif/plafond gratuit** `[fetched]` : palier Developer
  (gratuit, 1 siège) — jusqu'à 5000 traces de base/mois puis facturation à
  l'usage (unités LCU 1,50 $ / LSU 1,00 $, sans taux $/1000 traces publié en
  clair), rétention 14 jours. Une affirmation secondaire non confirmée
  officiellement dit que le plafond serait un mur dur avant ajout d'une carte
  bancaire — signalé non vérifié.

## Traps (points of vigilance for the review)
- **Le verrou Mistral doit rester un verrou global, pas par run de graphe.**
  `mistral_large_limiter` est un singleton process-wide (0.25 req/s). Chaque
  nœud du graphe qui appelle Mistral (génération, extraction table, extraction
  schéma) doit `await` le même verrou — un import qui recréerait un limiteur
  local casserait silencieusement le débit maximal négocié avec Mistral.
- **Le shim `_search_compat` est la seule interface Qdrant valide.** Un nœud
  qui importerait `qdrant_client.query_points` directement contournerait le
  shim et la garantie de forme d'appel testée dans `tests/core/test_qdrant.py`.
- **Le filtre `tenant_id` doit traverser chaque nœud, pas seulement le nœud de
  recherche.** `expand_heading_chunks`, `enrich_with_dpgf_quantities` et
  `build_db_context` font chacun leur propre appel Qdrant/SQL scopé — un
  refactor qui centraliserait la recherche sans repasser `tenant_id` à ces
  trois-là ouvrirait une fuite cross-tenant.
- **Ordre strict des événements SSE.** La séquence `conversation_id` → `text`
  × N → `structured`? → `schema`? → `sources` → `usage` → `[DONE]` est ce que
  le client front consomme aujourd'hui (contrat hors périmètre, spec §OUT). Le
  nouveau graphe doit produire exactement cette séquence, dans cet ordre, y
  compris l'absence de `structured`/`schema` quand ils ne s'appliquent pas.
- **`stream_mode="messages"` ne fonctionnera pas tel quel** avec des nœuds
  appelant `mistralai` directement (voir External surface, Q3) — c'est
  `stream_mode="custom"` + `get_stream_writer()` qu'il faut câbler, une
  décision d'implémentation à figer au plan, pas à découvrir en exécution.
- **`langchain-core` entre dans les dépendances dès `uv add langgraph`**,
  contredisant la formulation initiale de la spec (« pas de récriture avec
  LangChain complet ») — ce n'est PAS `langchain` ni `langchain-mistralai`,
  seulement le socle transitif obligatoire. À documenter dans le plan pour que
  la review ne le lève pas comme un écart de scope.
- **`@traceable` est requis nœud par nœud**, sinon LangSmith ne montre que le
  run englobant sans détail interne — contredit une lecture naïve de « tracing
  actif dès le premier appel » (spec) si on omet ce décorateur.
- **`admin.py`/`search.py`/`summary.py` n'importent jamais `chat/stream`** —
  confirmé, donc le cutover ne les touche pas. Mais `search_service.search_merged`
  (appelé par le pipeline actuel) reste partagé : ne pas dupliquer sa logique
  dans un nœud, l'appeler tel quel.
- **Le harnais refuse d'écraser un résultat existant** (`sprint/eval/harnais.py`,
  corrigé le 2026-09-18) — le futur run `v0` doit passer son propre label,
  jamais `baseline`, sous peine d'échec immédiat plutôt que d'écrasement
  silencieux (régression déjà vécue une fois sur `baseline-aws`).
- **Le test gelé actuel (`test_stream.py`) ne couvre que `_usage_leg`/
  `_usage_event`**, pas le générateur complet — la spec avait supposé un test
  comportemental plus large à réécrire ; en réalité il n'y a presque rien à
  migrer de ce fichier précis, la vraie couverture comportementale
  (recherche, enrichissement, streaming, persistance) n'existe **nulle part**
  aujourd'hui en test automatisé. Le plan doit donc écrire ces cas pour la
  première fois sur `graph.py`, pas les "porter".

## Open questions
- **Le checkpointer : `InMemorySaver` (dev, non durable) ou
  `langgraph-checkpoint-postgres` (durable, nouveau driver `psycopg` v3) ?**
  Ce que le port apporte réellement sans étape d'interruption humaine
  (pause-for-input) se limite à « reprendre un run après crash sans
  recalculer » et au replay de debug — pas à la persistance de l'historique
  affiché, qui reste `messages`/`conversations`. `/loop:plan` doit trancher : soit
  `InMemorySaver` suffit pour ce portage (le run est un aller-retour
  requête-réponse, pas un flux interruptible), soit `langgraph-checkpoint-postgres`
  est justifié — et dans ce cas une migration Alembic entre dans le plan.
- **Le traçage LangSmith bloque-t-il le chemin de la requête ?** Aucune source
  officielle Python trouvée (seul un réglage JS existe). À vérifier
  empiriquement pendant l'implémentation (mesurer la latence avec/sans
  `LANGSMITH_TRACING=true`) plutôt qu'à supposer — le seuil p95 de la spec
  (≤ baseline) est ce qui tranchera si c'est un problème.
- **Le taux de dépassement LangSmith au-delà de 5000 traces/mois** est publié
  en unités LCU/LSU, sans conversion $/trace claire. À estimer une fois le
  volume réel de traces/mois connu (20 questions × runs de dev + trafic AWS),
  pour savoir si le palier gratuit suffit pendant le sprint.
- **Faut-il pin `langgraph`/`langsmith` dans `.claude/rules/01-stack.md`
  immédiatement, ou seulement une fois installés ?** Le research a été fait
  avant tout `uv add` : `/loop:plan` doit prévoir cette ligne (stack + ledger
  `settled.md`) comme geste du plan, dans le même commit que l'installation.
