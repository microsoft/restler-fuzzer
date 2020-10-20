{
  "swagger": "2.0",
  "info": {
    "title": "Test sample from Azure Networking API.",
    "description": "Testing.",
    "version": "2018-12-01"
  },
  "schemes": [
    "https"
  ],
  "consumes": [
    "application/json"
  ],
  "produces": [
    "application/json"
  ],
  "paths": {
    "/subscriptions/{subscriptionId}/resourceGroups/{resourceGroupName}/providers/Microsoft.Network/applicationSecurityGroups/{applicationSecurityGroupName}": {

      "put": {
        "tags": [
          "ApplicationSecurityGroups"
        ],
        "operationId": "ApplicationSecurityGroups_CreateOrUpdate",
        "description": "Creates or updates an application security group.",
        "parameters": [
          {
            "name": "resourceGroupName",
            "in": "path",
            "required": true,
            "type": "string",
            "description": "The name of the resource group."
          },
          {
            "name": "applicationSecurityGroupName",
            "in": "path",
            "required": true,
            "type": "string",
            "description": "The name of the application security group."
          },
          {
            "name": "parameters",
            "in": "body",
            "required": true,
            "schema": {
              "$ref": "#/definitions/ApplicationSecurityGroup"
            },
            "description": "Parameters supplied to the create or update ApplicationSecurityGroup operation."
          }
        ],
        "responses": {
          "201": {
            "description": "Create successful. The operation returns the resulting application security group resource.",
            "schema": {
              "$ref": "#/definitions/ApplicationSecurityGroup"
            }
          },
          "200": {
            "description": "Update successful. The operation returns the resulting application security group resource.",
            "schema": {
              "$ref": "#/definitions/ApplicationSecurityGroup"
            }
          }
        },
        "x-ms-long-running-operation": true,
        "x-ms-examples": {
          "Create application security group": { "$ref": "./examples/ApplicationSecurityGroupCreate.json" }
        }
      }
    }
  },
  "definitions": {
    "Resource": {
      "properties": {
        "id": {
          "type": "string",
          "description": "Resource ID."
        },
        "name": {
          "readOnly": true,
          "type": "string",
          "description": "Resource name."
        },
        "type": {
          "readOnly": true,
          "type": "string",
          "description": "Resource type."
        },
        "location": {
          "type": "string",
          "description": "Resource location."
        },
        "tags": {
          "type": "object",
          "additionalProperties": {
            "type": "string"
          },
          "description": "Resource tags."
        }
      },
      "description": "Common resource representation.",
      "x-ms-azure-resource": true
    },

    "ApplicationSecurityGroup": {
      "properties": {
        "properties": {
          "x-ms-client-flatten": true,
          "$ref": "#/definitions/ApplicationSecurityGroupPropertiesFormat",
          "description": "Properties of the application security group."
        },
        "etag": {
          "readOnly": true,
          "type": "string",
          "description": "A unique read-only string that changes whenever the resource is updated."
        }
      },
      "allOf": [
        {
          "$ref": "#/definitions/Resource"
        }
      ],
      "description": "An application security group in a resource group."
    },
    "ApplicationSecurityGroupPropertiesFormat": {
      "properties": {
        "resourceGuid": {
          "readOnly": true,
          "type": "string",
          "description": "The resource GUID property of the application security group resource. It uniquely identifies a resource, even if the user changes its name or migrate the resource across subscriptions or resource groups."
        },
        "provisioningState": {
          "readOnly": true,
          "type": "string",
          "description": "The provisioning state of the application security group resource. Possible values are: 'Succeeded', 'Updating', 'Deleting', and 'Failed'."
        }
      },
      "description": "Application security group properties."
    },
    "ApplicationSecurityGroupListResult": {
      "properties": {
        "value": {
          "type": "array",
          "items": {
            "$ref": "#/definitions/ApplicationSecurityGroup"
          },
          "description": "A list of application security groups."
        },
        "nextLink": {
          "readOnly": true,
          "type": "string",
          "description": "The URL to get the next set of results."
        }
      },
      "description": "A list of application security groups."
    }
  }
}
