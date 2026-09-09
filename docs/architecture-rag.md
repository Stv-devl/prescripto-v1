# Architecture RAG - Prescripto

## Vue d'ensemble

Prescripto utilise une **collection Qdrant unique** pour stocker l'ensemble des documents de tous les projets de chaque tenant. Le routage entre recherche par projet et recherche globale se fait par **filtres sur les metadonnees**, pas par collections separees.

## Pourquoi une seule collection

### Option ecartee : 1 collection par projet

```
rag_projet_1  →  collection Qdrant 1
rag_projet_2  →  collection Qdrant 2
...
rag_projet_50 →  collection Qdrant 50
```

Problemes :

- Recherche globale = interroger N collections, fusionner les scores, re-ranker
- Complexite O(N) par requete globale
- Gestion de N collections (creation, suppression, maintenance)
- Pas de comparaison de similarite cross-projet native

### Option retenue : 1 collection unique avec metadonnees

```
collection "documents"
  └─ chunk: { text, embedding, tenant_id, project_id, lot, phase, document_type, date, ... }
```

Avantages :

- Recherche globale = 1 seule requete, Qdrant gere le scoring
- Recherche projet = meme requete + filtre `project_id`
- Isolation multi-tenant = filtre `tenant_id` (toujours applique)
- Scaling lineaire, Qdrant gere des dizaines de millions de vecteurs

## Modes de recherche

### Mode projet (par defaut)

L'utilisateur travaille dans un projet. Toutes les requetes sont scopees a ce projet.

```
filtre: tenant_id = "cabinet_xyz" AND project_id = "projet_10"
```

Exemple :
> "Quelle est la prescription d'etancheite du lot 08 ?"
> → Resultats uniquement du projet courant

### Mode global (cross-projet)

L'utilisateur interroge l'ensemble de sa base documentaire.

```
filtre: tenant_id = "cabinet_xyz"
(pas de filtre project_id)
```

Exemple :
> "On a deja fait une toiture terrasse vegetalisee ?"
> → Projet 10, CCTP lot etancheite, p.34
> → Projet 27, CR phase APD, validation du principe

L'utilisateur n'a pas besoin de savoir dans quel projet se trouve l'information. Le score de similarite semantique fait le tri.

### Mode global avec filtres optionnels

Pour affiner la recherche globale, l'utilisateur peut combiner des filtres :

```
filtre: tenant_id = "cabinet_xyz"
        AND lot = "etancheite"
        AND phase IN ["PRO", "DCE"]
        AND date >= "2024-01-01"
```

Exemple :
> "Comment on a prescrit l'etancheite sur nos projets de logements depuis 2024 ?"

## Metadonnees par chunk

Chaque chunk indexe dans Qdrant porte les metadonnees suivantes :

| Champ            | Type     | Obligatoire | Description                              |
| ---------------- | -------- | ----------- | ---------------------------------------- |
| `tenant_id`      | string   | oui         | Isolation multi-tenant                   |
| `project_id`     | string   | oui         | Identifiant du projet                    |
| `document_id`    | string   | oui         | Identifiant du document source           |
| `document_type`  | string   | oui         | CCTP, CR, fiche_technique, plan, email   |
| `lot`            | string   | non         | Lot concerne (gros-oeuvre, CVC, etc.)    |
| `phase`          | string   | non         | Phase du projet (ESQ, APS, APD, PRO, DCE)|
| `page`           | integer  | non         | Numero de page dans le document source   |
| `date`           | datetime | non         | Date du document                         |
| `source_filename`| string   | oui         | Nom du fichier original                  |

## Dimensionnement

### Ordres de grandeur pour un cabinet type

| Metrique                | Valeur           |
| ----------------------- | ---------------- |
| Projets (actifs + archives) | 50 - 200     |
| Documents par projet    | 50 - 500         |
| Documents total         | 10 000 - 100 000 |
| Chunks total            | 500K - 2M        |
| Taille embeddings (1024d, float32) | ~2 - 8 Go |

Qdrant gere des dizaines de millions de vecteurs sur un VPS modeste (4-8 Go RAM). Le volume n'est pas un facteur limitant.

### Performance attendue

| Operation                          | Latence cible |
| ---------------------------------- | ------------- |
| Recherche projet (filtre project_id) | < 100ms     |
| Recherche globale (filtre tenant_id) | < 200ms     |
| Recherche globale + filtres metadonnees | < 200ms  |

## Qualite des resultats

Le facteur critique n'est pas le volume mais la **qualite du chunking et des metadonnees**.

### Chunking

- Decoupage semantique (par section/article pour les CCTP, par paragraphe pour les CR)
- Overlap de ~10-20% entre chunks pour conserver le contexte
- Taille cible : 500-1000 tokens par chunk

### Extraction de metadonnees

- Classification automatique du type de document (CCTP, CR, fiche technique...)
- Detection du lot concerne via LLM ou regles
- Extraction de la phase depuis le nom de fichier ou le contenu
- Date : metadonnee du fichier ou extraction depuis le contenu

### Re-ranking

Pour les recherches globales, un re-ranker (cross-encoder) ameliore la pertinence :

1. Qdrant retourne les top 20-50 chunks par similarite cosinus
2. Le re-ranker re-score chaque chunk avec la question complete
3. Les top 5-10 sont presentes a l'utilisateur avec source, page et passage

## Stack technique

| Composant        | Technologie                    |
| ---------------- | ------------------------------ |
| Vector DB        | Qdrant (self-hosted, VPS FR)   |
| Embeddings       | Mistral Embed (souverain FR)   |
| LLM              | Mistral Large (souverain FR)   |
| Backend          | FastAPI (Python)               |
| BDD relationnelle| PostgreSQL (projets, users)    |
| Frontend         | React + TypeScript             |
