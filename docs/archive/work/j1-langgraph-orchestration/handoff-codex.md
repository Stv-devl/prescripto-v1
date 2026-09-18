---
phase: execute
execute_status: in-progress
review_status: n/a
token_profile: economy
---

# Codex handoff: J1 — orchestration du chat portée en LangGraph
Token profile: economy
Entry: docs/specs/j1-langgraph-orchestration.md
Current phase: execute — 8/8 acceptance criteria faites (AC6 débloquée :
Service Key → Personal Access Token + endpoint EU + carte bancaire). Prêt
pour REVIEW.
Worktree/branch: main tree (no worktree, single track)

## Objective and acceptance criteria
Voir `docs/specs/j1-langgraph-orchestration.md` (Objective, Acceptance
criteria) et `docs/work/j1-langgraph-orchestration/plan.md` (§Acceptance
criteria, coché critère par critère avec les chiffres réels).

## Completed
- Spec, research, plan écrits et critiqués (plan-critic : 3 passes,
  completeness 92 / quality 82, zéro blocker survivant).
- `uv add langgraph langsmith` (1.2.11 / 0.13.0), versions pinnées dans
  `.claude/rules/01-stack.md` + `docs/research-cache/settled.md`.
- `backend/app/core/config.py` — 3 champs `Settings` (`langsmith_tracing`,
  `langsmith_api_key`, `langsmith_project`) + validateur.
- `backend/app/core/langsmith.py` — `configure_langsmith()`, gate sur clé
  présente (pas seulement le flag) pour éviter un vrai appel réseau 401 par
  appel tracé sans clé.
- `backend/app/services/chat/graph.py` (698 l., test-first, RED→GREEN,
  21/21 cas verts, 92 % couverture) — le graphe LangGraph complet.
  Split en package tenté puis abandonné : `tdd-require-red-py.py` refuse la
  création de nouveaux fichiers `services/` sans RED individuel, y compris
  pour une réorganisation pure sans changement de comportement (voir
  plan.md §Write chain, étape 6).
- Cutover : `backend/app/services/chat/__init__.py` importe désormais
  `chat_stream` depuis `graph.py` (une ligne). `api/chat.py` inchangé.
- `backend/tests/api/test_chat.py` (2 cas, intégration SSE bout-en-bout réelle).
- `sprint/eval/adapter/langgraph_v0.py` + `sprint/eval/langgraph_v0.py`
  (adapter + CLI harnais, même patron que `bourrage_contexte`).
- Run harnais réel exécuté (`sprint/eval/result/v0.csv`) contre le corpus
  local : coût 0,004098 $/question, p95 18,46 s, rappel **18/20 — identique
  à `baseline-aws`, mêmes deux échecs exacts (Q5, Q20), zéro régression**.
- **Correction majeure trouvée en exécutant l'étape de suppression** :
  `stream.py` NE DOIT PAS être supprimé — `sprint/eval/adapter/service.py`
  (l'adapter `baseline`) l'importe directement, et le supprimer casserait la
  reproductibilité de la baseline (`sprint/PLAN-SPRINT.md` §2). `stream.py`
  et son test gelé restent en place indéfiniment. Plan et spec corrigés.
- Bug pré-existant découvert (hors scope J1, `.tdd-unfrozen` refermé, ligne
  backlog ouverte) : `_NON_PRECISE_RE` (`schema_extraction.py`) traite un
  tiret de signe négatif comme « non précisé », supprime `fond_fouille`.
- Bug de fuite d'état découvert et corrigé : `configure_langsmith()` écrit
  dans `os.environ` sous les mêmes noms que `Settings` lit par défaut —
  polluait les `Settings()` nues construites plus loin dans la suite.
  Fixture autouse ajoutée dans `tests/conftest.py`.
- Suite complète backend verte : 438 passed, 5 xfailed.

## In progress
- REVIEW en cours (`/loop:review`) : Stage 1 FIND terminé, 2 Major +
  1 Major trouvés (tous corrigés), Stage 3 synthèse à produire.

## Remaining
1. REVIEW (`/loop:review`).
2. SHIP (`/loop:ship`).

## Changed files
Voir `docs/work/j1-langgraph-orchestration/plan.md`, §Files (table à jour,
inclut les écarts trouvés en EXECUTE : pas d'édition d'`EXTERNAL_CLIENTS` ni
de `main.py`, `stream.py` non supprimé, `conftest.py` et
`sprint/eval/langgraph_v0.py` ajoutés hors plan initial).

## Decisions and traps
- Pas de flag runtime permanent type `RETRIEVAL_MODE` pour l'orchestration —
  cutover unique, mais `stream.py` reste néanmoins sur disque (voir
  Completed) : deux raisons différentes de garder l'ancien code, pas une
  contradiction.
- LangSmith actif partout y compris AWS, mais gate local sur présence de clé
  réelle (`core/langsmith.py`) — sinon bruit réseau non désiré en tests/dev.
- `uv add langgraph` tire `langchain-core` en dépendance transitive
  obligatoire — pas un écart de scope.
- Nœuds = fonctions Python simples ; `stream_mode="custom"` +
  `get_stream_writer()` pour le streaming ; `@traceable` par nœud.
- Checkpointer : `InMemorySaver`, compilé par requête (closures sur
  db/tenant_id/project_id) — pas de Postgres, décision tranchée en plan.
- `extract_table_node`/`extract_schema_node` tournent en éventail parallèle à
  `generate_node`, joints par un `join_node` structurel — préserve le
  parallélisme du pipeline original (latence).
- Verrou Mistral et shim Qdrant réutilisés tels quels par chaque nœud.
- `langsmith_endpoint` ajouté à `Settings` (défaut EU — ce workspace est
  hébergé en EU, l'endpoint US par défaut du SDK 403 silencieusement).
- Trace réelle lue via `client.list_runs()` : le graphe fonctionne comme
  conçu — `extract_table_node`/`extract_schema_node`/`generate_node`
  démarrent à la même seconde (parallélisme prouvé, pas seulement supposé).

## Verification
- `cd backend && python -m pytest -q` → 438 passed, 5 xfailed, couverture
  69,84 % (`graph.py` seul : 92 %).
- `cd backend && uv run python ../sprint/eval/langgraph_v0.py` → 20/20
  questions traitées sans erreur, résultats dans
  `sprint/eval/result/v0.csv`.

## Resume rules
- Read `CLAUDE.md`, this handoff, then only relevant rules
  (`02-architecture.md` §Backend, `05-testing.md`, `07-backend.md`).
- Preserve the token profile (`economy`) and existing artifacts.
- Never read `.env*`, credentials, keys, or secrets.
- Do not redo completed phases. Update this handoff when the phase changes.
