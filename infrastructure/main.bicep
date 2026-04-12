// Main deployment — Azure infrastructure for finance-os.
//
// Deploys:
//   1. Azure OpenAI (Cognitive Services) with Entra-only auth (API keys disabled)
//   2. Model deployment (e.g. gpt-4o-mini)
//   3. RBAC role assignment for the specified principal
//
// Usage:
//   az deployment group create \
//     --resource-group <rg-name> \
//     --template-file infrastructure/main.bicep \
//     --parameters infrastructure/parameters.sample.bicepparam

targetScope = 'resourceGroup'

// ── Parameters ──────────────────────────────────────────────────────────────

@description('Azure region for all resources.')
param location string = resourceGroup().location

@description('Name of the Azure OpenAI resource.')
param openAiAccountName string

@description('SKU for the Azure OpenAI resource.')
@allowed(['S0'])
param openAiSku string = 'S0'

@description('Model to deploy (e.g. gpt-4o, gpt-4o-mini).')
param modelName string = 'gpt-4o-mini'

@description('Model version to deploy.')
param modelVersion string = '2024-07-18'

@description('Deployment name — this is the value for azure.deployment in config.json.')
param deploymentName string = 'gpt-4o-mini'

@description('Deployment capacity in thousands of tokens per minute.')
param deploymentCapacity int = 10

@description('Object ID of the Entra principal (user or service principal) to grant access.')
param principalId string

@description('Type of principal being granted access.')
@allowed(['User', 'ServicePrincipal', 'Group'])
param principalType string = 'User'

// ── Modules ─────────────────────────────────────────────────────────────────

module openAi 'modules/cognitive-services.bicep' = {
  name: 'openai-${uniqueString(resourceGroup().id)}'
  params: {
    location: location
    accountName: openAiAccountName
    sku: openAiSku
    modelName: modelName
    modelVersion: modelVersion
    deploymentName: deploymentName
    deploymentCapacity: deploymentCapacity
  }
}

module rbac 'modules/role-assignment.bicep' = {
  name: 'rbac-${uniqueString(resourceGroup().id, principalId)}'
  params: {
    openAiAccountName: openAi.outputs.accountName
    principalId: principalId
    principalType: principalType
  }
}

// ── Outputs ─────────────────────────────────────────────────────────────────

@description('Azure OpenAI resource endpoint — use as azure.endpoint in config.json.')
output endpoint string = openAi.outputs.endpoint

@description('Model deployment name — use as azure.deployment in config.json.')
output deploymentName string = openAi.outputs.deploymentName
