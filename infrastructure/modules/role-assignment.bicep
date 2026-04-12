// RBAC role assignment — Cognitive Services OpenAI User.
//
// Grants the specified principal permission to call the Azure OpenAI
// inference APIs via Entra ID tokens. No API key access is available.

@description('Name of the Azure OpenAI account to assign the role on.')
param openAiAccountName string

@description('Object ID of the Entra principal.')
param principalId string

@description('Type of principal.')
@allowed(['User', 'ServicePrincipal', 'Group'])
param principalType string = 'User'

// Cognitive Services OpenAI User — allows inference calls
var cognitiveServicesOpenAIUser = '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'

resource openAiAccount 'Microsoft.CognitiveServices/accounts@2024-10-01' existing = {
  name: openAiAccountName
}

resource roleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(openAiAccount.id, principalId, cognitiveServicesOpenAIUser)
  scope: openAiAccount
  properties: {
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      cognitiveServicesOpenAIUser
    )
    principalId: principalId
    principalType: principalType
  }
}
