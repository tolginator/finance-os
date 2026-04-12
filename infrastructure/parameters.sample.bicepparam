// Sample parameters for finance-os Azure infrastructure.
//
// Copy this file, fill in your values, and deploy:
//
//   az deployment group create \
//     --resource-group <your-rg> \
//     --template-file infrastructure/main.bicep \
//     --parameters infrastructure/parameters.bicepparam

using 'main.bicep'

// Name for the Azure OpenAI resource (must be globally unique).
param openAiAccountName = ''

// Model to deploy and its version.
param modelName = 'gpt-4.1-mini'
param modelVersion = '2025-04-14'

// Deployment name — this becomes the azure.deployment value in config.json.
param deploymentName = 'gpt-4.1-mini'

// Capacity in thousands of tokens per minute.
param deploymentCapacity = 10

// Deployment SKU — newer models (gpt-4.1+) require 'Standard'.
param deploymentSkuName = 'Standard'

// Your Entra user/principal object ID.
// Find it with: az ad signed-in-user show --query id -o tsv
param principalId = ''

// Principal type: 'User' for interactive, 'ServicePrincipal' for CI/CD.
param principalType = 'User'

// CI managed identity name and GitHub repository for OIDC federation.
param ciIdentityName = 'finance-os-ci'
param gitHubRepo = 'tolginator/finance-os'
