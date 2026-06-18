# RAG Demo Azure Deployment Plan

Status: Completed and verified (2026-06-17)

## Azure context
- Subscription: c74d82a8-495b-4804-94a0-35f7cabd9d4f
- Tenant: ceeb9806-b9ea-44c8-8fe1-4eba76cfad9a
- Location: southeastasia for App Service/PostgreSQL; eastus for Azure OpenAI model availability

## Resources to create
- Resource group: `rag-demo-rg`
- Azure Database for PostgreSQL Flexible Server with pgvector allow-list
- Azure OpenAI resource with `text-embedding-3-large` and `gpt-4.1-mini` deployments
- Linux App Service plan and Python 3.12 Web App

## Deployment steps
1. Provision resource group, PostgreSQL Flexible Server, and pgvector setting.
2. Provision Azure OpenAI and model deployments.
3. Build React frontend and copy `frontend/dist` to `backend/app/static`.
4. Create App Service and configure app settings.
5. Zip-deploy backend package.
6. Seed vector database with sample documents.
7. Verify Azure website `/`, `/api/health`, and `/api/chat`.

## Final resources
- App URL: `https://rag-demo-app-rd0617c74d82a8.azurewebsites.net`
- Resource group: `rag-demo-rg`
- PostgreSQL Flexible Server: `rag-demo-pg-rd0617c74d82a8`
- Azure OpenAI: `rag-demo-openai-eastus-rd0617c74d82a8`
- Chat deployment: `gpt-4.1-mini`
- Embedding deployment: `text-embedding-3-large`

## Verification results
- `/`: HTTP 200, React `index.html` served.
- `/api/health`: HTTP 200, `{"status":"ok","database":true}`.
- `/api/chat`: HTTP 200, returned an answer with 4 sources after seeding 12 documents.

## Notes
- This follows the repository README CLI workflow rather than generating new IaC.
- Passwords and service keys are not written to this plan file.
- `gpt-4o-mini` version `2024-07-18` is deprecated in the tested Azure OpenAI flow, so `gpt-4.1-mini` is used instead.
- App Service startup uses a fallback command that installs `requirements.txt` at container start because Kudu/Oryx did not create `antenv` for this zip deploy.
