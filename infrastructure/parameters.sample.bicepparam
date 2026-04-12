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
param modelName = 'gpt-4o-mini'
param modelVersion = '2024-07-18'

// Deployment name — this becomes the azure.deployment value in config.json.
param deploymentName = 'gpt-4o-mini'

// Capacity in thousands of tokens per minute.
param deploymentCapacity = 10

// Your Entra user/principal object ID.
// Find it with: az ad signed-in-user show --query id -o tsv
param principalId = ''

// Principal type: 'User' for interactive, 'ServicePrincipal' for CI/CD.
param principalType = 'User'
