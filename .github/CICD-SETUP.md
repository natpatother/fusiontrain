# CI/CD setup — Deploy to Azure App Service

The workflow [`deploy-azure.yml`](workflows/deploy-azure.yml) builds the React
frontend into the FastAPI backend and zip-deploys it to the existing App Service
on every push to `main` (or via **Run workflow**). It authenticates with the
App Service **publish profile** stored as a single GitHub secret.

You only need to do this **one-time setup** once.

## What the workflow targets

| Setting | Value |
|---------|-------|
| GitHub repo | `natpatother/fusiontrain` |
| App Service | `rag-demo-app-rd0617c74d82a8` |
| Resource group | `rag-demo-rg` |

> App settings (DATABASE_URL, AZURE_OPENAI_*, etc.) and the startup command are
> already configured on the App Service — the pipeline only ships code, so secrets
> never pass through GitHub. Manage runtime config with `az webapp config appsettings`.

## 1. Get the publish profile

**Option A — Azure CLI** (run locally after `az login`):

```bash
az webapp deployment list-publishing-profiles \
  -g rag-demo-rg -n rag-demo-app-rd0617c74d82a8 \
  --xml > publish-profile.xml
```

**Option B — Portal:** App Service → **Overview** → **Download publish profile**.

> If the download is blocked, enable basic auth first:
> `az resource update --resource-group rag-demo-rg --name scm \
> --namespace Microsoft.Web --resource-type basicPublishingCredentialsPolicies \
> --parent sites/rag-demo-app-rd0617c74d82a8 --set properties.allow=true`

## 2. Add it as a GitHub secret

Add the **entire XML contents** as a repository secret named
`AZURE_WEBAPP_PUBLISH_PROFILE`.

**With the `gh` CLI:**

```bash
gh secret set AZURE_WEBAPP_PUBLISH_PROFILE < publish-profile.xml
```

**Or in the UI:** Repo → **Settings → Secrets and variables → Actions →
New repository secret** → name `AZURE_WEBAPP_PUBLISH_PROFILE`, paste the XML.

Then delete the local `publish-profile.xml` — it's a long-lived credential.

## 3. Trigger a deploy

- Push any code change to `main`, **or**
- **Actions → Deploy to Azure App Service → Run workflow**.

Then verify:

```bash
curl https://rag-demo-app-rd0617c74d82a8.azurewebsites.net/api/health
# {"status":"ok","database":true}
```

## Rotating / troubleshooting the credential

- The publish profile is a standing secret. To rotate it, **Reset publish profile**
  in the portal (or `az webapp deployment list-publishing-profiles ... --xml` after a
  reset) and update the GitHub secret with the new XML.
- `Deployment Failed with Error: ... Basic authentication is disabled` → enable SCM
  basic auth (the command in step 1) or switch to OIDC auth.

## Notes

- **Seeding** the vector store (`scripts/seed.py`) is a one-time data step and is
  intentionally **not** in the pipeline — it doesn't run on every deploy.
- The package zip's root contains `app/main.py`, matching the App Service startup
  command `gunicorn app.main:app -k uvicorn.workers.UvicornWorker -w 2 --timeout 120`.
- `SCM_DO_BUILD_DURING_DEPLOYMENT=true` is already set on the App Service, so Oryx
  runs `pip install -r requirements.txt` on the server during each deploy.
- Doc-only changes (`**/*.md`, `.azure/**`, `.vscode/**`) don't trigger a deploy.
