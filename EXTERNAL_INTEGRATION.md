# External API Integration for Helpdesk

This document describes the generic external API integration system for the Helpdesk app. This system allows you to integrate with any external service (Proconut, Tortoise, or others) through a flexible configuration interface.

## Architecture Overview

The integration system consists of three main components:

### 1. **HD External Integration Settings** (Single DocType)
Main configuration doctype that enables/disables all external integrations.

### 2. **HD Integration App** (Child Table)
Stores configuration for each external application:
- **app_name**: Unique identifier (e.g., 'proconut', 'tortoise')
- **base_url**: Base URL of the external API
- **auth_type**: Authentication method (API Key, Bearer Token, Basic Auth, None)
- **api_key**: Authentication credential (stored as password)
- **enabled**: Toggle to enable/disable this app

### 3. **HD Integration Endpoint** (Child Table)
Stores configuration for specific API endpoints:
- **app_name**: Links to the app (must match an app_name from HD Integration App)
- **action_name**: Unique identifier for this action (e.g., 'get_employee_data')
- **endpoint_path**: Relative path for the endpoint (e.g., '/api/v1/employee/')
- **http_method**: GET, POST, PUT, PATCH, DELETE
- **additional_headers**: Optional JSON for custom headers
- **query_param_mappings**: Optional JSON for parameter name mapping
- **enabled**: Toggle to enable/disable this endpoint

## Configuration Example

### Example: Configuring Proconut/Tortoise Integration

1. **Enable Integration**
   - Go to HD External Integration Settings
   - Check "Enable External Integrations"

2. **Add App Configuration**
   In the "Apps" table, add:
   ```
   App Name: proconut
   Base URL: https://api.proconut.com
   Auth Type: API Key
   API Key: your_secret_key_here
   Enabled: ✓
   ```

3. **Add Endpoint Configuration**
   In the "Endpoints" table, add:
   ```
   App Name: proconut
   Action Name: get_employee_data
   Endpoint Path: /api/v1/employee/
   HTTP Method: GET
   Enabled: ✓
   ```

4. **Advanced Configuration** (Optional)
   
   **Additional Headers** (JSON):
   ```json
   {
     "X-Custom-Header": "value",
     "X-Another-Header": "another-value"
   }
   ```

   **Query Parameter Mappings** (JSON):
   ```json
   {
     "email": "user_email",
     "id": "employee_id"
   }
   ```
   This maps `email` parameter to `user_email` in the API request.

## API Usage

### Python API

#### 1. Generic API Call
```python
import frappe
from helpdesk.api.external_integration import call_external_api

# Call any configured endpoint
result = call_external_api(
    app_name="proconut",
    action_name="get_employee_data",
    params={"email": "user@example.com"}
)

if result.get("success"):
    data = result.get("data")
    # Process data
else:
    error = result.get("error")
    # Handle error
```

#### 2. Convenience Method for Employee Data
```python
from helpdesk.api.external_integration import get_employee_data

# Fetch employee data for a ticket
result = get_employee_data(
    ticket_id="HD-TICKET-00001",
    app_name="proconut"
)
```

#### 3. Check Integration Status
```python
from helpdesk.api.external_integration import check_integration_status

# Check general status
status = check_integration_status()
# Returns: {"enabled": True, "configured": True, "app_count": 1, "endpoint_count": 2}

# Check specific app
status = check_integration_status(app_name="proconut")
# Returns: {"enabled": True, "configured": True, "app_name": "proconut"}
```

### JavaScript API (Frontend)

#### Using frappe-ui's createResource

```javascript
import { createResource } from "frappe-ui";

const employeeData = createResource({
  url: "helpdesk.api.external_integration.get_employee_data",
  makeParams: () => ({
    ticket_id: ticketId,
    app_name: "proconut",
  }),
  auto: true,
});

// Access data
if (employeeData.data?.success) {
  const data = employeeData.data.data;
  // Use data
}
```

#### Generic API Call from Frontend

```javascript
const apiCall = createResource({
  url: "helpdesk.api.external_integration.call_external_api",
  makeParams: () => ({
    app_name: "proconut",
    action_name: "get_employee_data",
    params: JSON.stringify({ email: "user@example.com" }),
  }),
});

apiCall.reload();
```

## Frontend Integration

### Tortoise Tab in Ticket View

The "Tortoise" tab appears in the ticket sidebar when:
1. External Integration is enabled
2. The 'proconut' app is configured and enabled
3. At least one endpoint is configured for the app

The tab displays:
- Employee information (name, designation, employee ID)
- Device allowance and consumed limits
- Employee band
- List of orders/claimed benefits

## Adding New External Services

To add a new external service (e.g., "myservice"):

1. **Configure the App**
   - Add to HD External Integration Settings
   - Set app_name = "myservice"
   - Configure base_url, auth_type, and credentials

2. **Configure Endpoints**
   - Add endpoints with action_name (e.g., "get_user_data")
   - Configure HTTP method and paths

3. **Use in Code**
   ```python
   result = call_external_api(
       app_name="myservice",
       action_name="get_user_data",
       params={"user_id": "123"}
   )
   ```

4. **Frontend Integration** (Optional)
   - Create a new tab or component
   - Use `check_integration_status(app_name="myservice")` to check availability
   - Call the API using `call_external_api`

## Authentication Types

### API Key
Adds header: `X-Proconut-Secret-Key: <api_key>`

### Bearer Token
Adds header: `Authorization: Bearer <api_key>`

### Basic Auth
Adds header: `Authorization: Basic <api_key>`

### None
No authentication headers added

## Security Considerations

1. **Credentials Storage**: API keys are stored as passwords in the database (encrypted)
2. **System Email Filter**: The system automatically filters out configured email accounts to prevent querying external APIs for system emails
3. **Error Logging**: Failed API calls are logged to Error Log with full context
4. **Timeouts**: All API requests have a 30-second timeout
5. **Permissions**: Only System Managers and Agent Managers can configure integrations

## File Structure

```
helpdesk/
├── helpdesk/
│   ├── doctype/
│   │   ├── hd_external_integration_settings/
│   │   │   ├── hd_external_integration_settings.json
│   │   │   ├── hd_external_integration_settings.py
│   │   │   └── hd_external_integration_settings.js
│   │   ├── hd_integration_app/
│   │   │   ├── hd_integration_app.json
│   │   │   └── hd_integration_app.py
│   │   └── hd_integration_endpoint/
│   │       ├── hd_integration_endpoint.json
│   │       └── hd_integration_endpoint.py
│   └── api/
│       └── external_integration.py
└── desk/
    └── src/
        └── components/
            └── ticket-agent/
                ├── TicketSidebar.vue
                ├── TortoiseTab.vue
                └── OrderCard.vue
```

## Extensibility

The system is designed to be highly extensible:

- **Multiple Apps**: Configure as many external services as needed
- **Multiple Endpoints**: Each app can have unlimited endpoints
- **Flexible Parameters**: Use query_param_mappings to adapt to different API requirements
- **Custom Headers**: Add any custom headers needed per endpoint
- **HTTP Methods**: Supports GET, POST, PUT, PATCH, DELETE
- **Generic API**: Use `call_external_api()` for any integration need

## Troubleshooting

### Integration Not Working

1. Check if integration is enabled: Go to HD External Integration Settings
2. Verify app is enabled and configured correctly
3. Verify endpoint is enabled for the action_name
4. Check Error Log for detailed error messages
5. Use "Test Connection" button in HD External Integration Settings

### Tab Not Appearing

1. Ensure integration is enabled and configured
2. Check browser console for errors
3. Verify app_name matches in frontend code and backend config

### API Errors

- Check Error Log for detailed error messages
- Verify base_url is correct (no trailing slash issues)
- Verify endpoint_path starts with `/`
- Check authentication credentials
- Ensure external API is accessible from server
