# Prescripto — Lancer le projet

## 1. Services Docker

```bash
docker compose -f docker-compose.dev.yml up -d
```

## 2. Backend

```bash
cd backend
[ -f .env ] || cp .env.example .env   # ne copie que si absent — puis renseigner MISTRAL_API_KEY et JWT_SECRET_KEY
uv sync --extra dev       # installe les dépendances dans .venv/ (uv, jamais pip)
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

`ENVIRONMENT=local` dans `backend/.env` est ce qui active le bypass d'auth — le
défaut sans variable est `production` (aucun bypass). `.env.example` le
positionne déjà à `local`.

## 3. Frontend

```bash
cd client
pnpm dev
```

## Auth

Pas de compte requis en dev : `ENVIRONMENT=local` bypass l'authentification avec
un user/tenant dev cree automatiquement au demarrage.

## URLs

| Service  | URL                          |
| -------- | ---------------------------- |
| Frontend | `http://localhost:5173`      |
| API docs | `http://localhost:8000/docs` |
| pgAdmin  | `http://localhost:5050`      |

## Visualiser la base de données (pgAdmin)

1. Ouvrir `http://localhost:5050`
2. Se connecter avec :
   - **Email** : `admin@prescripto.fr`
   - **Mot de passe** : `prescripto_dev_admin`
3. Ajouter un serveur :
   - **Host** : `postgres` (nom du service Docker)
   - **Port** : `5432`
   - **Database** : voir ta config `.env`
   - **Username / Password** : voir ta config `.env`

### Commandes psql (alternative)

```bash
# Se connecter au conteneur PostgreSQL
docker exec -it prescripto-postgres psql -U <user> -d <database>

# Lister les tables
\dt

# Décrire une table
\d users

# Requête rapide
SELECT * FROM users LIMIT 10;

# Quitter
\q
```

## Arrêter

```bash
docker compose -f docker-compose.dev.yml down
```
