// Azure Cognitive Services (OpenAI) — Entra-only authentication.
//
// API key access is disabled. All callers must authenticate via
// Entra ID (OAuth2/OIDC) using DefaultAzureCredential or equivalent.

@description('Azure region.')
param location string

@description('Name of the Cognitive Services account.')
param accountName string

@description('SKU tier.')
param sku string = 'S0'

@description('Model to deploy.')
param modelName string

@description('Model version.')
param modelVersion string

@description('Deployment name (maps to azure.deployment in config).')
param deploymentName string

@description('Capacity in thousands of tokens per minute.')
param deploymentCapacity int

resource account 'Microsoft.CognitiveServices/accounts@2024-10-01' = {
  name: accountName
  location: location
  kind: 'OpenAI'
  sku: {
    name: sku
  }
  properties: {
    // Entra-only: disable all API key / local auth paths
    disableLocalAuth: true

    customSubDomainName: accountName

    publicNetworkAccess: 'Enabled'

    networkAcls: {
      defaultAction: 'Allow'
    }
  }
}

resource deployment 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = {
  parent: account
  name: deploymentName
  sku: {
    name: 'Standard'
    capacity: deploymentCapacity
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: modelName
      version: modelVersion
    }
  }
}

@description('The endpoint URL for the Azure OpenAI resource.')
output endpoint string = account.properties.endpoint

@description('The deployment name.')
output deploymentName string = deployment.name

@description('The resource name.')
output accountName string = account.name
