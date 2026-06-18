# RAG Chat Demo — Azure Landing Zone

Mini full-stack demo matching the **Cloud Infrastructure / Landing Zone (MS Team)** architecture.

- **Frontend** — React (Vite). Teams/iFrame-style UI with two tabs: **Chat** (search the vector store) and **Upload** (add knowledge by pasting text or uploading a file).
- **Backend** — Python (FastAPI). Embeds the question, retrieves the nearest documents from **Azure PostgreSQL Flexible Server** (`pgvector`), and answers with a chat model (RAG). It also ingests documents (chunk → embed → store). The LLM backend is pluggable: **Azure OpenAI** or **Azure AI Foundry**, chosen via `LLM_PROVIDER`.
- **Database** — `document_embeddings` table using `VECTOR(3072)` (matches `text-embedding-3-large`).

## Architecture

```mermaid
flowchart LR
    subgraph Client["Microsoft Teams"]
        UI["React UI<br/>Chat + Upload (iFrame)"]
    end

    subgraph vNet["Production vNet"]
        APP["App Service<br/>FastAPI + React build"]
        PG[("PostgreSQL Flexible Server<br/>pgvector · document_embeddings")]
    end

    subgraph AI["LLM provider (pluggable)"]
        AOAI["Azure OpenAI"]
        FND["Azure AI Foundry"]
    end

    UI -->|"HTTPS /api/chat"| APP
    APP -->|"embed + chat"| AOAI
    APP -.->|"or LLM_PROVIDER=foundry"| FND
    APP -->|"vector search (&lt;=&gt;)"| PG

    subgraph Common["Common / Access / Monitoring"]
        KV["Key Vault"]
        AI2["App Insights"]
        AAD["Entra ID"]
        BLOB["Blob Storage"]
    end
    APP -.-> KV
    APP -.-> AI2
    APP -.-> BLOB
    UI -.->|"SSO"| AAD
```

**RAG request flow**

```mermaid
sequenceDiagram
    actor U as Officer (Teams)
    participant R as React UI
    participant A as FastAPI (App Service)
    participant E as Azure OpenAI / Foundry
    participant D as PostgreSQL (pgvector)

    U->>R: type question
    R->>A: POST /api/chat { message }
    A->>E: embed(question)
    E-->>A: query vector (3072 / 1536)
    A->>D: ORDER BY embedding <=> $1 LIMIT k
    D-->>A: top-k documents + scores
    A->>E: chat(question, retrieved context)
    E-->>A: answer
    A-->>R: { answer, sources }
    R-->>U: show answer + sources
```

> **Conventions in this guide.** Every local command is given for **macOS/Linux** (bash/zsh)
> and **Windows** (PowerShell). On Windows, run PowerShell (not the old `cmd`) unless noted.

---

## 0. Prerequisites

You need **Python 3.11+**, **Node.js 18+**, the **Azure CLI**, and the **psql** client.

**macOS** (Homebrew):

```bash
brew install python node azure-cli libpq
brew link --force libpq          # puts psql on PATH
```

**Windows** (winget, in PowerShell):

```powershell
winget install -e --id Python.Python.3.12
winget install -e --id OpenJS.NodeJS.LTS
winget install -e --id Microsoft.AzureCLI
winget install -e --id PostgreSQL.psql   # or install full PostgreSQL for psql
```

> Close and reopen the terminal after installing so the new tools are on `PATH`.

---

## 1. Database

Run this on your Azure PostgreSQL Flexible Server (the extension must be allow-listed in the
server's `azure.extensions` parameter — see the deploy section). DDL is in
[backend/scripts/init_db.sql](backend/scripts/init_db.sql):

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE document_embeddings (
    id SERIAL PRIMARY KEY,
    content_text TEXT,
    embedding VECTOR(3072)        -- text-embedding-3-large = 3072 dims
);
```

### Searching 3072-dim vectors (keeping `VECTOR(3072)`)

The plain pgvector `vector` type stores **up to 16,000 dims**, and exact KNN works at any
dimension. The well-known **2000-dim limit applies only to building `hnsw`/`ivfflat`
indexes** — never to storage or queries. So the column stays exactly `VECTOR(3072)`; you
just choose how (or whether) to index it. Three verified options:

**Option 1 — No index, exact KNN** *(default; what this demo uses)*

```sql
-- No CREATE INDEX. pgvector does exact (sequential-scan) search = perfect recall.
SELECT id, content_text, 1 - (embedding <=> %s) AS score
FROM document_embeddings ORDER BY embedding <=> %s LIMIT %s;
```
Perfect recall, full fp32; O(n) per query — ideal for demo/small data.

**Option 2 — HNSW expression index on a `halfvec` cast** *(ANN at scale, vanilla pgvector)*

```sql
CREATE INDEX ON document_embeddings
    USING hnsw ((embedding::halfvec(3072)) halfvec_cosine_ops);
-- the query MUST cast both sides to match, or the planner ignores the index:
--   ORDER BY embedding::halfvec(3072) <=> %s::halfvec(3072)
```
Needs server-side **pgvector ≥ 0.7.0** (Azure Flexible Server ships **0.8.x** on PG 14–17).
`halfvec` indexes up to 4000 dims, so 3072 fits; index is fp16 (slightly lower recall — you
can over-fetch and re-rank on the exact fp32 column). `seed.py` builds this automatically
for `EMBEDDING_DIM > 2000`, and `rag.py` already emits the matching cast.

**Option 3 — Azure DiskANN (`pg_diskann`)** *(Azure-only, no query change)*

```sql
CREATE EXTENSION IF NOT EXISTS pg_diskann CASCADE;   -- allow-list pg_diskann first
CREATE INDEX ON document_embeddings USING diskann (embedding vector_cosine_ops)
    WITH (product_quantized = true, pq_param_num_chunks = 1024);  -- required for >2000 dims
```
Microsoft-documented ANN path that indexes the **plain `vector(3072)`** directly (up to
16,000 dims) — queries stay on `embedding <=> %s`, no `halfvec` cast.

> Verify the live extension version before relying on `halfvec`:
> `SELECT extversion FROM pg_extension WHERE extname = 'vector';`
> *(Verified against the pgvector README and Microsoft Learn, June 2026.)*

---

## 2. Backend

**macOS/Linux:**

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env             # then fill in your Azure values
python scripts/seed.py           # loads sample docs into the vector table
uvicorn app.main:app --reload --port 8000
```

**Windows (PowerShell):**

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env      # then fill in your Azure values
python scripts\seed.py           # loads sample docs into the vector table
uvicorn app.main:app --reload --port 8000
```

> If PowerShell blocks `Activate.ps1` with a script-execution error, run once per session:
> `Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned`
> (or use `cmd`: `.venv\Scripts\activate.bat`).

### API

| Method & path | Body | Purpose |
|---------------|------|---------|
| `POST /api/chat` | `{ "message": "..." }` | RAG answer → `{ answer, sources[] }` |
| `POST /api/documents` | `{ "content": "..." }` | Ingest pasted text (chunk → embed → store) |
| `POST /api/documents/upload` | multipart `file` | Ingest an uploaded `.txt`/`.md`/… file |
| `GET /api/documents` | — | List stored chunks `{ total, documents[] }` |
| `DELETE /api/documents/{id}` | — | Remove one chunk |
| `GET /api/health` | — | `{ status, database }` |

Ingestion splits text into ~800-char chunks (on paragraph boundaries) and stores **one row
per chunk** in `document_embeddings`, keeping the required schema exactly. `seed.py` is
still handy for loading the demo corpus; the **Upload tab** is for adding your own.

---

## 3. Frontend

Same on both OSes (npm):

```bash
cd frontend
npm install
npm run dev                      # http://localhost:5173
```

The dev server proxies `/api` to `http://localhost:8000`, so run the backend too.

---

## Environment variables (backend/.env)

Always-required, regardless of provider:

| Var | Description |
|-----|-------------|
| `DATABASE_URL` | `postgresql://user:pass@server.postgres.database.azure.com:5432/db?sslmode=require` |
| `LLM_PROVIDER` | `azure_openai` **or** `foundry` — picks the client at startup |
| `EMBEDDING_DIM` | vector size; **must match the model + DB column** (large → `3072`, small → `1536`) |

---

## Choosing the LLM provider: Azure OpenAI vs MS Foundry

The backend code is identical for both — [app/providers.py](backend/app/providers.py)
reads `LLM_PROVIDER` and exposes the same `embed()` / `chat()` interface to the RAG layer.
You only change `.env` (locally) or App Settings (on Azure). Pick **one** of the two
blocks below.

### Option A — Azure OpenAI Service

Set `LLM_PROVIDER=azure_openai` and use **deployment names** you created in Azure OpenAI Studio:

```dotenv
LLM_PROVIDER=azure_openai
EMBEDDING_DIM=3072

AZURE_OPENAI_ENDPOINT=https://<resource>.openai.azure.com/
AZURE_OPENAI_API_KEY=<key>
AZURE_OPENAI_API_VERSION=2024-10-21
EMBEDDING_DEPLOYMENT=text-embedding-3-large     # your deployment name
CHAT_DEPLOYMENT=gpt-4o-mini                      # your deployment name
```

| Var | Description |
|-----|-------------|
| `AZURE_OPENAI_ENDPOINT` | `https://<resource>.openai.azure.com/` |
| `AZURE_OPENAI_API_KEY` | Azure OpenAI key |
| `AZURE_OPENAI_API_VERSION` | e.g. `2024-10-21` |
| `EMBEDDING_DEPLOYMENT` | **deployment** name for `text-embedding-3-large` (or `-small`) |
| `CHAT_DEPLOYMENT` | **deployment** name for `gpt-4o` / `gpt-4o-mini` |

### Option B — Azure AI Foundry

Set `LLM_PROVIDER=foundry` and use the Foundry **model inference endpoint** + **model names**:

```dotenv
LLM_PROVIDER=foundry
EMBEDDING_DIM=3072

FOUNDRY_ENDPOINT=https://<resource>.services.ai.azure.com/models
FOUNDRY_API_KEY=<key>
FOUNDRY_API_VERSION=2024-05-01-preview
FOUNDRY_EMBEDDING_MODEL=text-embedding-3-large  # model name in your Foundry project
FOUNDRY_CHAT_MODEL=gpt-4o-mini                   # model name in your Foundry project
```

| Var | Description |
|-----|-------------|
| `FOUNDRY_ENDPOINT` | `https://<resource>.services.ai.azure.com/models` |
| `FOUNDRY_API_KEY` | Foundry key |
| `FOUNDRY_API_VERSION` | e.g. `2024-05-01-preview` |
| `FOUNDRY_EMBEDDING_MODEL` | model name, e.g. `text-embedding-3-large` |
| `FOUNDRY_CHAT_MODEL` | model name, e.g. `gpt-4o-mini` |

> **Switching the embedding model?** If you change to `text-embedding-3-small`, set
> `EMBEDDING_DIM=1536` and re-run `python scripts/seed.py` (it rebuilds the table + index
> to match). See [§ Switching the embedding model](#switching-the-embedding-model).

### Switching the embedding model

| Model | `EMBEDDING_DIM` | DB index built by seed.py |
|-------|-----------------|---------------------------|
| `text-embedding-3-large` | `3072` | HNSW on a `halfvec` cast (needs pgvector ≥ 0.7.0) |
| `text-embedding-3-small` | `1536` | native HNSW (`vector_cosine_ops`) |

After changing the model/`EMBEDDING_DIM`, re-seed so the column and index match:

```bash
python scripts/seed.py     # TRUNCATEs + recreates with the new dimension
```

---

# Deploy to Azure

This deploys the demo onto the landing zone in the diagram:

| Diagram component | Azure resource |
|-------------------|----------------|
| App Service | Linux App Service (Python 3.12) — serves FastAPI **and** the React build |
| Database / pgvector | Azure Database for PostgreSQL **Flexible Server** |
| OpenAI / Foundry | Azure OpenAI **or** Azure AI Foundry |
| Key Vault, App Insights, Blob, Entra ID | optional common services (see step 8) |

> Single App Service: we copy the built React app into `backend/app/static`, so the
> backend serves the UI at `/` and the API at `/api/*` — one origin, no CORS needed.

Prerequisites: Azure CLI (`az login`), an active subscription, and quota for Azure OpenAI.

> The `az` commands below are the same on both OSes. Only **shell variable syntax** and
> **line continuation** differ: macOS/Linux uses `VAR=value`, `$VAR`, and `\` at line ends;
> PowerShell uses `$VAR = "value"`, `$VAR`, and a backtick `` ` `` at line ends. Both
> variants are given for the steps where it matters.

## 0. Set variables

**macOS/Linux:**

```bash
RG=rag-demo-rg
LOC=southeastasia
PG=rag-demo-pg-$RANDOM           # globally-unique
PG_USER=pgadmin
PG_PASS='ChangeMe_$ecret123'
PG_DB=ragdb
AOAI=rag-demo-openai-$RANDOM     # globally-unique
APP=rag-demo-app-$RANDOM         # globally-unique -> https://$APP.azurewebsites.net
PLAN=rag-demo-plan

az group create -n $RG -l $LOC
```

**Windows (PowerShell):**

```powershell
$RG   = "rag-demo-rg"
$LOC  = "southeastasia"
$PG   = "rag-demo-pg-$(Get-Random)"      # globally-unique
$PG_USER = "pgadmin"
$PG_PASS = 'ChangeMe_$ecret123'
$PG_DB = "ragdb"
$AOAI = "rag-demo-openai-$(Get-Random)"  # globally-unique
$APP  = "rag-demo-app-$(Get-Random)"     # globally-unique -> https://$APP.azurewebsites.net
$PLAN = "rag-demo-plan"

az group create -n $RG -l $LOC
```

## 1. PostgreSQL Flexible Server + pgvector

Same `az` commands on both OSes (PowerShell users: replace the trailing `\` with `` ` ``):

```bash
az postgres flexible-server create \
  -g $RG -n $PG -l $LOC \
  --admin-user $PG_USER --admin-password "$PG_PASS" \
  --version 16 --tier Burstable --sku-name Standard_B1ms \
  --storage-size 32 --database-name $PG_DB \
  --public-access 0.0.0.0           # allow Azure services; tighten for prod

# Allow-list the vector extension, then restart so it takes effect.
az postgres flexible-server parameter set \
  -g $RG -s $PG --name azure.extensions --value vector
az postgres flexible-server restart -g $RG -n $PG
```

Then create the schema ([backend/scripts/init_db.sql](backend/scripts/init_db.sql)):

**macOS/Linux:**

```bash
PGPASSWORD="$PG_PASS" psql \
  "host=$PG.postgres.database.azure.com port=5432 dbname=$PG_DB user=$PG_USER sslmode=require" \
  -f backend/scripts/init_db.sql
```

**Windows (PowerShell):**

```powershell
$env:PGPASSWORD = $PG_PASS
psql "host=$PG.postgres.database.azure.com port=5432 dbname=$PG_DB user=$PG_USER sslmode=require" `
  -f backend\scripts\init_db.sql
```

## 2. Azure OpenAI + model deployments

Same `az` commands on both OSes (PowerShell: `\` → `` ` ``):

```bash
az cognitiveservices account create \
  -g $RG -n $AOAI -l $LOC --kind OpenAI --sku S0 --custom-domain $AOAI

az cognitiveservices account deployment create \
  -g $RG -n $AOAI --deployment-name text-embedding-3-large \
  --model-name text-embedding-3-large --model-version "1" \
  --model-format OpenAI --sku-capacity 1 --sku-name Standard

az cognitiveservices account deployment create \
  -g $RG -n $AOAI --deployment-name gpt-4o-mini \
  --model-name gpt-4o-mini --model-version "2024-07-18" \
  --model-format OpenAI --sku-capacity 1 --sku-name Standard
```

Capture the endpoint + key into variables:

**macOS/Linux:**

```bash
AOAI_ENDPOINT=$(az cognitiveservices account show -g $RG -n $AOAI --query properties.endpoint -o tsv)
AOAI_KEY=$(az cognitiveservices account keys list -g $RG -n $AOAI --query key1 -o tsv)
```

**Windows (PowerShell):**

```powershell
$AOAI_ENDPOINT = az cognitiveservices account show -g $RG -n $AOAI --query properties.endpoint -o tsv
$AOAI_KEY      = az cognitiveservices account keys list -g $RG -n $AOAI --query key1 -o tsv
```

> Using **Azure AI Foundry** instead? Skip this step, create your Foundry project +
> model deployments in the portal, and in step 5 set `LLM_PROVIDER=foundry` with the
> `FOUNDRY_*` settings instead of the `AZURE_OPENAI_*` ones.

## 3. Build the frontend into the backend

**macOS/Linux:**

```bash
cd frontend && npm ci && npm run build && cd ..
rm -rf backend/app/static && cp -r frontend/dist backend/app/static
```

**Windows (PowerShell):**

```powershell
cd frontend ; npm ci ; npm run build ; cd ..
if (Test-Path backend\app\static) { Remove-Item -Recurse -Force backend\app\static }
Copy-Item -Recurse frontend\dist backend\app\static
```

## 4. Create the App Service

Same on both OSes (PowerShell: `\` → `` ` ``):

```bash
az appservice plan create -g $RG -n $PLAN --is-linux --sku B1
az webapp create -g $RG -p $PLAN -n $APP --runtime "PYTHON:3.12"
az webapp config set -g $RG -n $APP \
  --startup-file "gunicorn app.main:app -k uvicorn.workers.UvicornWorker -w 2 --timeout 120"
```

## 5. App settings (environment variables)

Use **one** of the two provider blocks (matching step 2). See
[Choosing the LLM provider](#choosing-the-llm-provider-azure-openai-vs-ms-foundry).

### 5a. If using Azure OpenAI (`LLM_PROVIDER=azure_openai`)

**macOS/Linux:**

```bash
az webapp config appsettings set -g $RG -n $APP --settings \
  SCM_DO_BUILD_DURING_DEPLOYMENT=true \
  DATABASE_URL="postgresql://$PG_USER:$PG_PASS@$PG.postgres.database.azure.com:5432/$PG_DB?sslmode=require" \
  LLM_PROVIDER=azure_openai \
  EMBEDDING_DIM=3072 \
  AZURE_OPENAI_ENDPOINT="$AOAI_ENDPOINT" \
  AZURE_OPENAI_API_KEY="$AOAI_KEY" \
  AZURE_OPENAI_API_VERSION=2024-10-21 \
  EMBEDDING_DEPLOYMENT=text-embedding-3-large \
  CHAT_DEPLOYMENT=gpt-4o-mini \
  ALLOWED_ORIGINS="*"
```

**Windows (PowerShell):**

```powershell
az webapp config appsettings set -g $RG -n $APP --settings `
  SCM_DO_BUILD_DURING_DEPLOYMENT=true `
  DATABASE_URL="postgresql://$PG_USER:$PG_PASS@$PG.postgres.database.azure.com:5432/$PG_DB?sslmode=require" `
  LLM_PROVIDER=azure_openai `
  EMBEDDING_DIM=3072 `
  AZURE_OPENAI_ENDPOINT="$AOAI_ENDPOINT" `
  AZURE_OPENAI_API_KEY="$AOAI_KEY" `
  AZURE_OPENAI_API_VERSION=2024-10-21 `
  EMBEDDING_DEPLOYMENT=text-embedding-3-large `
  CHAT_DEPLOYMENT=gpt-4o-mini `
  ALLOWED_ORIGINS="*"
```

### 5b. If using MS Foundry (`LLM_PROVIDER=foundry`)

Replace `<...>` with your Foundry endpoint/key/model names.

**macOS/Linux:**

```bash
az webapp config appsettings set -g $RG -n $APP --settings \
  SCM_DO_BUILD_DURING_DEPLOYMENT=true \
  DATABASE_URL="postgresql://$PG_USER:$PG_PASS@$PG.postgres.database.azure.com:5432/$PG_DB?sslmode=require" \
  LLM_PROVIDER=foundry \
  EMBEDDING_DIM=3072 \
  FOUNDRY_ENDPOINT="https://<resource>.services.ai.azure.com/models" \
  FOUNDRY_API_KEY="<foundry-key>" \
  FOUNDRY_API_VERSION=2024-05-01-preview \
  FOUNDRY_EMBEDDING_MODEL=text-embedding-3-large \
  FOUNDRY_CHAT_MODEL=gpt-4o-mini \
  ALLOWED_ORIGINS="*"
```

**Windows (PowerShell):**

```powershell
az webapp config appsettings set -g $RG -n $APP --settings `
  SCM_DO_BUILD_DURING_DEPLOYMENT=true `
  DATABASE_URL="postgresql://$PG_USER:$PG_PASS@$PG.postgres.database.azure.com:5432/$PG_DB?sslmode=require" `
  LLM_PROVIDER=foundry `
  EMBEDDING_DIM=3072 `
  FOUNDRY_ENDPOINT="https://<resource>.services.ai.azure.com/models" `
  FOUNDRY_API_KEY="<foundry-key>" `
  FOUNDRY_API_VERSION=2024-05-01-preview `
  FOUNDRY_EMBEDDING_MODEL=text-embedding-3-large `
  FOUNDRY_CHAT_MODEL=gpt-4o-mini `
  ALLOWED_ORIGINS="*"
```

> Using `text-embedding-3-small`? Set `EMBEDDING_DIM=1536` here **and** in the `.env` you
> seed with, then re-run `scripts/seed.py`.

## 6. Deploy the code

**macOS/Linux:**

```bash
# Zip the backend folder (which now contains app/static) and push it.
cd backend && zip -r ../app.zip . -x "*.venv*" "*__pycache__*" ".env" && cd ..
az webapp deploy -g $RG -n $APP --src-path app.zip --type zip
```

**Windows (PowerShell):**

```powershell
# Include only what the app needs (avoids zipping .venv / __pycache__ / .env).
Compress-Archive -Path backend\app, backend\scripts, backend\requirements.txt, backend\startup.sh `
  -DestinationPath app.zip -Force
az webapp deploy -g $RG -n $APP --src-path app.zip --type zip
```

## 7. Seed the vector store

Point a local `.env` at the Azure resources (same values as step 5), then run the seed
script against the cloud database:

**macOS/Linux:**

```bash
cd backend && python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python scripts/seed.py
```

**Windows (PowerShell):**

```powershell
cd backend ; py -m venv .venv ; .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python scripts\seed.py
```

Browse **`https://<your-app-name>.azurewebsites.net`** — the chat UI loads and answers
from the vector store.

## 8. Hardening (optional, matches the diagram)

- **Key Vault** — store `DATABASE_URL` / keys as secrets; reference them from App Settings
  with `@Microsoft.KeyVault(...)` and enable the App Service **managed identity**.
- **Managed identity instead of keys** — grant the identity `Cognitive Services OpenAI User`
  and Postgres AAD auth; drop the key/password from settings.
- **VNet integration + Private Endpoints** — put Postgres and OpenAI on the Production vNet,
  restrict the App Service via NSG (as drawn).
- **Application Insights** — `az monitor app-insights component create` and set
  `APPLICATIONINSIGHTS_CONNECTION_STRING`.
- **Entra ID (AAD)** — enable App Service Authentication so only signed-in officers (incl.
  the Teams iFrame) can reach the app.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `extension "vector" is not allow-listed` | run the `azure.extensions` step + restart (step 1) |
| `psql: command not found` | macOS: `brew install libpq && brew link --force libpq`; Windows: install PostgreSQL / `winget install PostgreSQL.psql` |
| PowerShell won't run `Activate.ps1` | `Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned` |
| 500 on `/api/chat`, `/api/health` shows `database:false` | check `DATABASE_URL`, firewall, `sslmode=require` |
| UI loads but answers are empty | run `scripts/seed.py`; confirm model deployment names match settings |
| Want an ANN index but `type "halfvec" does not exist` | pgvector < 0.7.0 — upgrade (PG 16) or stay on exact KNN (no index) |
| App won't start | verify the startup command and that the zip root contains `app/main.py` |
