// User Assigned Managed Identity with GitHub Actions OIDC federation.
//
// Creates a UAMI for CI/CD and adds a federated identity credential
// so GitHub Actions can authenticate via OIDC (no secrets needed).

@description('Azure region.')
param location string

@description('Name of the managed identity.')
param identityName string

@description('GitHub repository in owner/repo format.')
param gitHubRepo string

@description('Git ref for the federated credential subject (e.g. refs/heads/main).')
param gitHubRef string = 'refs/heads/main'

resource identity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: identityName
  location: location
}

resource federatedCredential 'Microsoft.ManagedIdentity/userAssignedIdentities/federatedIdentityCredentials@2023-01-31' = {
  parent: identity
  name: 'github-actions'
  properties: {
    issuer: 'https://token.actions.githubusercontent.com'
    subject: 'repo:${gitHubRepo}:ref:${gitHubRef}'
    audiences: ['api://AzureADTokenExchange']
  }
}

@description('Client ID of the managed identity — use for azure/login.')
output clientId string = identity.properties.clientId

@description('Principal ID of the managed identity — use for RBAC.')
output principalId string = identity.properties.principalId
