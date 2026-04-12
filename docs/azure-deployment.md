# Azure Deployment Guide

End-to-end instructions for deploying and connecting finance-os to Azure OpenAI with Entra ID (OAuth2/OIDC) authentication. No API keys — everything uses token-based auth.

## Prerequisites

| Tool | Install |
|------|---------|
| Azure CLI | `curl -sL https://aka.ms/InstallAzureCLIDeb \| sudo bash` |
| Bicep CLI | Bundled with Azure CLI ≥ 2.20 |
| Python 3.12+ | Required for finance-os agents |

## Step 1 — Log in to Azure

```bash
az login
```

Verify your account:

```bash
az account show --query '{subscription: name, id: id, tenant: tenantId}' -o table
```

If you have multiple subscriptions, set the correct one:

```bash
az account set --subscription "<your-subscription-id>"
```

## Step 2 — Create a resource group

```bash
az group create \
  --name rg-finance-os \
  --location eastus2
```

> **Tip**: Use a region that supports Azure OpenAI. Check availability at [Azure OpenAI model availability](https://learn.microsoft.com/en-us/azure/ai-services/openai/concepts/models).

## Step 3 — Get your Entra principal ID

```bash
az ad signed-in-user show --query id -o tsv
```

Copy the output — you'll need it in the next step.

## Step 4 — Configure deployment parameters

```bash
cp infrastructure/parameters.sample.bicepparam infrastructure/parameters.bicepparam
```

Edit `infrastructure/parameters.bicepparam` and fill in:

```
param openAiAccountName = 'finance-os-openai'   // must be globally unique
param principalId = '<your-principal-id>'         // from step 3
```

The defaults work for everything else, but you can customize:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `openAiAccountName` | *(required)* | Globally unique name for the Azure OpenAI resource |
| `modelName` | `gpt-4o` | OpenAI model to deploy |
| `modelVersion` | `2024-11-20` | Model version |
| `deploymentName` | `gpt-4o` | Deployment name (becomes `azure.deployment` in config) |
| `deploymentCapacity` | `10` | Capacity in thousands of tokens per minute |
| `principalId` | *(required)* | Your Entra object ID |
| `principalType` | `User` | `User`, `ServicePrincipal`, or `Group` |

## Step 5 — Deploy the infrastructure

```bash
az deployment group create \
  --resource-group rg-finance-os \
  --template-file infrastructure/main.bicep \
  --parameters infrastructure/parameters.bicepparam \
  --query 'properties.outputs' \
  -o json
```

Expected output:

```json
{
  "deploymentName": { "value": "gpt-4o" },
  "endpoint": { "value": "https://finance-os-openai.openai.azure.com/" }
}
```

Save the `endpoint` and `deploymentName` values — you need them next.

## Step 6 — Configure finance-os

Update `~/.config/finance-os/config.json`:

```json
{
  "llm_provider": "azure_openai",
  "azure": {
    "endpoint": "https://finance-os-openai.openai.azure.com/",
    "deployment": "gpt-4o",
    "api_version": "2024-10-21"
  }
}
```

Or use environment variables:

```bash
export FINANCE_OS_LLM_PROVIDER=azure_openai
export FINANCE_OS_AZURE__ENDPOINT=https://finance-os-openai.openai.azure.com/
export FINANCE_OS_AZURE__DEPLOYMENT=gpt-4o
```

## Step 7 — Verify it works

```bash
# Check config is loaded
finance-os config

# Run an agent with LLM synthesis
finance-os run filing-analyst --ticker AAPL --synthesize
```

## Troubleshooting

### "DefaultAzureCredential failed to retrieve a token"

You're not logged in or your token expired:

```bash
az login
```

### "AuthorizationFailed" or 403

Your principal doesn't have the right role. Verify the role assignment:

```bash
az role assignment list \
  --assignee "$(az ad signed-in-user show --query id -o tsv)" \
  --scope "/subscriptions/$(az account show --query id -o tsv)/resourceGroups/rg-finance-os" \
  --query "[?roleDefinitionName=='Cognitive Services OpenAI User']" \
  -o table
```

If empty, assign it manually:

```bash
az role assignment create \
  --assignee "$(az ad signed-in-user show --query id -o tsv)" \
  --role "Cognitive Services OpenAI User" \
  --scope "$(az cognitiveservices account show \
    --name finance-os-openai \
    --resource-group rg-finance-os \
    --query id -o tsv)"
```

### "Resource not found" or deployment errors

Verify the resource exists:

```bash
az cognitiveservices account show \
  --name finance-os-openai \
  --resource-group rg-finance-os \
  --query '{name: name, endpoint: properties.endpoint, localAuth: properties.disableLocalAuth}' \
  -o table
```

List deployments:

```bash
az cognitiveservices account deployment list \
  --name finance-os-openai \
  --resource-group rg-finance-os \
  --query "[].{name: name, model: properties.model.name, version: properties.model.version}" \
  -o table
```

## Cleanup

To tear down all resources:

```bash
az group delete --name rg-finance-os --yes --no-wait
```

## Security notes

- **`disableLocalAuth: true`** — API keys are completely disabled on the Azure OpenAI resource
- **RBAC-scoped** — `Cognitive Services OpenAI User` grants inference-only access, not management
- **No secrets in repo** — `parameters.bicepparam` is gitignored; credentials live in Entra ID
- **Token-based** — `DefaultAzureCredential` handles token acquisition and refresh automatically
