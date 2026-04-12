// Main deployment — Azure infrastructure for finance-os.
//
// Deploys:
//   1. Azure OpenAI (Cognitive Services) with Entra-only auth (API keys disabled)
//   2. Model deployment (e.g. gpt-4.1-mini)
//   3. RBAC role assignments for the operator and CI identity
//   4. User Assigned Managed Identity with GitHub Actions OIDC federation
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

@description('Model to deploy (e.g. gpt-4.1-mini, gpt-4.1-mini).')
param modelName string = 'gpt-4.1-mini'

@description('Model version to deploy.')
param modelVersion string = '2025-04-14'

@description('Deployment name — this is the value for azure.deployment in config.json.')
param deploymentName string = 'gpt-4.1-mini'

@description('Deployment capacity in thousands of tokens per minute.')
param deploymentCapacity int = 10

@description('Deployment SKU name (e.g. Standard, GlobalStandard). Newer models require GlobalStandard.')
param deploymentSkuName string = 'Standard'

@description('Object ID of the Entra principal (user or service principal) to grant access.')
param principalId string

@description('Type of principal being granted access.')
@allowed(['User', 'ServicePrincipal', 'Group'])
param principalType string = 'User'

@description('Name of the managed identity for CI/CD.')
param ciIdentityName string = 'finance-os-ci'

@description('GitHub repository in owner/repo format for OIDC federation.')
param gitHubRepo string = 'tolginator/finance-os'

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
    deploymentSkuName: deploymentSkuName
  }
}

module ciIdentity 'modules/managed-identity.bicep' = {
  name: 'ci-identity-${uniqueString(resourceGroup().id)}'
  params: {
    location: location
    identityName: ciIdentityName
    gitHubRepo: gitHubRepo
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

module ciRbac 'modules/role-assignment.bicep' = {
  name: 'rbac-ci-${uniqueString(resourceGroup().id, ciIdentity.outputs.principalId)}'
  params: {
    openAiAccountName: openAi.outputs.accountName
    principalId: ciIdentity.outputs.principalId
    principalType: 'ServicePrincipal'
  }
}

// ── Outputs ─────────────────────────────────────────────────────────────────

@description('Azure OpenAI resource endpoint — use as azure.endpoint in config.json.')
output endpoint string = openAi.outputs.endpoint

@description('Model deployment name — use as azure.deployment in config.json.')
output deploymentName string = openAi.outputs.deploymentName

@description('CI managed identity client ID — set as AZURE_CLIENT_ID in GitHub.')
output ciClientId string = ciIdentity.outputs.clientId
