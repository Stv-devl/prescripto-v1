# Spec: J1 — porter l'orchestration du chat en LangGraph
Token profile: economy

## Objective
Porter `chat_stream()` (`backend/app/services/chat/stream.py`) en LangGraph — même
comportement observable, même coût, même latence — pour préparer les boucles
(recommencer/enchaîner) dont `J2` a besoin, avec tracing LangSmith actif dès le
premier appel.

## Scope
- IN :
  - Un nouveau module test-first (`backend/app/services/chat/graph.py` + fichiers
    de support si nécessaire) qui reconstruit le pipeline en LangGraph : state
    typé (`TypedDict`/`Annotated`/reducer), un nœud par étape (reformulation,
    recherche, enrichissement, génération), arête conditionnelle où le flux
    actuel en a une, checkpointer branché (comparé explicitement à la
    persistance Postgres déjà en place — pas un remplacement aveugle).
  - Réutilisation des fonctions existantes (`query_rewrite.py`,
    `chunk_enrichment.py`, `context_enrichment.py`, `search_service`, etc.)
    comme corps de nœuds — pas de récriture de leur logique.
  - Streaming SSE inchangé au premier passage : le nœud de génération produit
    le même flux de tokens que `stream.py` aujourd'hui, câblé tel quel.
  - Tracing LangSmith branché dès le premier appel (`LANGSMITH_TRACING`,
    `LANGSMITH_API_KEY`, projet dédié) — actif partout, y compris AWS
    (décision explicite : du contenu CCTP transite par LangSmith Cloud).
  - `LANGSMITH_API_KEY` ajouté à `Settings` (validé au démarrage comme
    `mistral_api_key`/`qdrant_api_key`) et à Secrets Manager, même famille que
    les 3 secrets déjà en place (`J0b`).
  - Validation d'équivalence via le harnais (`sprint/eval/harnais.py`) : un
    nouvel adapter `v0` (même pattern que l'adapter `bourrage_contexte`
    existant) appelle le nouveau module et produit la colonne `v0` face à
    `baseline` et `bourrage_contexte`.
  - **Cutover, dans le même diff, une fois l'équivalence prouvée** : l'endpoint
    `api/chat.py` appelle le nouveau module. Pas de flag runtime permanent —
    le mécanisme d'interrupteur `RETRIEVAL_MODE` est spécifique à la
    récupération (`J2`), rien dans le plan ne prescrit un équivalent pour
    l'orchestration.
    **Correction du 2026-09-18 (`/loop:plan`, EXECUTE)** : cette ligne
    prévoyait aussi de retirer `stream.py` et ses tests gelés — annulé.
    `sprint/eval/adapter/service.py` (l'adapter harnais `baseline`) importe
    `stream.py` directement, et le supprimer casserait pour toujours la
    reproductibilité de la baseline (`sprint/PLAN-SPRINT.md` §2 : « ta
    baseline doit rester rejouable »). `stream.py` reste en place
    indéfiniment, gelé, comme référence baseline.
  - Lecture d'une trace LangSmith réelle, expliquée (où part le temps, où part
    l'argent) — restituée dans `sprint/JOURNAL.md`, pas dans ce dépôt de specs.
- OUT :
  - Tout changement de qualité de récupération (chunking, reranking, hybride)
    — c'est `J2`.
  - Tout changement du contrat SSE côté client (`chat.py:33`, format des
    événements) — le streaming reste celui d'aujourd'hui, seul son producteur
    change de forme interne.
  - Tout nouvel outil MCP ou garde anti-injection — `J4`.
  - Toute UI nouvelle — aucune surface front ne change.
  - Le remplacement du checkpointer par la persistance Postgres des
    conversations (`conversations`/`messages`) — les deux coexistent, le
    checkpointer sert l'état d'exécution du graphe, pas l'historique
    utilisateur.

## Data model
Aucune migration Alembic. Aucun schéma Postgres ne change. Si le checkpointer
LangGraph choisi a besoin de tables propres (ex. `langgraph-checkpoint-postgres`),
elles passent par `/database:migration` comme toute autre table — décision prise
en `/loop:research`/`/loop:plan`, pas ici.

## Custom backend
- `backend/app/services/chat/graph.py` (nouveau, test-first) : construction du
  graphe, state, nœuds, arêtes.
- `backend/app/core/langsmith.py` (nouveau, ou config dans `core/config.py`) :
  configuration du tracing, même famille que `core/mistral.py`/`core/qdrant.py`
  (`EXTERNAL_CLIENTS`).
- `backend/app/core/config.py` : `LANGSMITH_API_KEY`, `LANGSMITH_TRACING`,
  `LANGSMITH_PROJECT` ajoutés à `Settings`.
- `backend/app/api/chat.py` : bascule l'appel vers le nouveau module (cutover).
- `backend/pyproject.toml` : `langgraph`, `langsmith` ajoutés via `uv add`.
- `sprint/eval/adapter/langgraph_v0.py` (ou équivalent) : adapter harnais pour
  la colonne `v0`.
- Suppression : `backend/app/services/chat/stream.py` et
  `backend/tests/services/chat/test_stream.py` (ou déplacement en frozen
  archive si `/loop:plan` juge la suppression prématurée avant confirmation
  finale du cutover).

## Front surface
NONE — aucune feature front ne change. Le contrat SSE consommé par
`client/src/features/chat/` reste identique.

## Acceptance criteria
- [ ] Le harnais produit un tableau à trois colonnes (`baseline` ·
      `bourrage_contexte` · `v0`) sur les mêmes 20 questions.
- [ ] `v0` : coût moyen par question dans la même fourchette que `baseline`
      (± marge raisonnable définie en `/loop:plan`, pas de dérive type "×7"
      comme le bourrage).
- [ ] `v0` : rappel (qualité) au moins égal à `baseline` (18/20 mesuré à `J0`/`J0b`) —
      un portage ne doit pas régresser, et n'a pas à améliorer (c'est `J2`).
- [ ] `v0` : p95 latence dans la même fourchette que `baseline` (pas de
      dégradation attribuable à l'orchestration elle-même).
- [ ] Le flux SSE produit par le nouveau chemin est fonctionnellement
      identique côté client (mêmes types d'événements, même contenu de
      `Source`/`StructuredSchema`/`StructuredTable`) — vérifié par un test
      d'intégration `api/` sur `chat.py`.
- [ ] Une trace LangSmith d'un appel réel est consultée et son coût/latence par
      nœud est expliqué (documenté dans `sprint/JOURNAL.md`, pas ici).
- [ ] Chaque nœud qui touche Qdrant ou Postgres continue de filtrer par
      `tenant_id` (invariant non-négociable, `06-database.md`) — testé par un
      cas cross-tenant sur le nouveau module, comme l'exige `07-backend.md`.
- [ ] Suite complète backend verte après cutover (`python -m pytest`), couverture
      inchangée ou meilleure sur `app/services/chat/`.

## Business logic to cover
- Construction et exécution du graphe : l'enchaînement reformulation →
  recherche → enrichissement → génération produit le même résultat observable
  qu'aujourd'hui pour une entrée donnée (comparaison de sortie, pas de mock
  d'étape interne).
- L'arête conditionnelle (le point où le flux actuel bifurque — ex. absence de
  résultat de recherche, erreur d'extraction de schéma/tableau) se déclenche
  sur les mêmes conditions qu'aujourd'hui.
- Le filtrage `tenant_id` traverse chaque nœud qui interroge Qdrant ou
  Postgres : cas cross-tenant obligatoire.
- Le checkpointer persiste et restitue l'état d'exécution attendu entre deux
  appels (ce qu'il ajoute par rapport à la persistance Postgres existante, pas
  un doublon).
- Le tracing LangSmith s'active sans faire échouer un appel si la clé est
  absente en environnement de test (comportement dégradé explicite, pas une
  exception qui remonte au client).
