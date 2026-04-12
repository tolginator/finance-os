# Infrastructure

Bicep templates for provisioning Azure resources used by finance-os.

## What gets created

| Resource | Purpose |
|----------|---------|
| Azure OpenAI (Cognitive Services) | LLM inference with Entra-only auth (API keys disabled) |
| Model deployment (e.g. gpt-4.1-mini) | The deployment your config points to |
| RBAC role assignment | `Cognitive Services OpenAI User` for your principal |

## Prerequisites

- Azure CLI (`az`) installed and logged in
- A resource group already created
- Your Entra principal object ID (`az ad signed-in-user show --query id -o tsv`)

## Deploy

```bash
# 1. Copy the sample parameters and fill in your values
cp infrastructure/parameters.sample.bicepparam infrastructure/parameters.bicepparam

# 2. Deploy
az deployment group create \
  --resource-group <your-rg> \
  --template-file infrastructure/main.bicep \
  --parameters infrastructure/parameters.bicepparam
```

The deployment outputs `endpoint` and `deploymentName` — use these in your `~/.config/finance-os/config.json`:

```json
{
  "llm_provider": "azure_openai",
  "azure": {
    "endpoint": "<endpoint from output>",
    "deployment": "<deploymentName from output>"
  }
}
```

## Security

- **No API keys** — `disableLocalAuth: true` ensures only Entra ID tokens are accepted
- **RBAC-scoped** — the role assignment grants inference-only access (`Cognitive Services OpenAI User`), not management access
- **No secrets in repo** — `parameters.bicepparam` is gitignored; only the sample is checked in
