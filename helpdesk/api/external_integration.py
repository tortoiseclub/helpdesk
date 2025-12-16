# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

import json

import frappe
import requests
from frappe import _


@frappe.whitelist()
def call_external_api(app_name: str, action_name: str, params: dict = None):
    """
    Generic method to call external APIs configured in HD External Integration Settings.

    Args:
        app_name: Name of the external app (e.g., 'proconut', 'tortoise')
        action_name: Action identifier (e.g., 'get_employee_data')
        params: Dictionary of parameters to pass to the API

    Returns:
        dict: Response from the external API or error message
    """
    if isinstance(params, str):
        params = json.loads(params)

    params = params or {}

    # Check if integrations are enabled
    if not frappe.get_single("HD External Integration Settings").enabled:
        return {"error": "External integrations are not enabled", "enabled": False}

    # Get app configuration
    from helpdesk.helpdesk.doctype.hd_external_integration_settings.hd_external_integration_settings import (
        HDExternalIntegrationSettings,
    )

    app_config = HDExternalIntegrationSettings.get_app_config(app_name)
    if not app_config:
        return {"error": f"App '{app_name}' not found or not enabled"}

    # Get endpoint configuration
    endpoint_config = HDExternalIntegrationSettings.get_endpoint_config(
        app_name, action_name
    )
    if not endpoint_config:
        return {
            "error": f"Endpoint '{action_name}' not found or not enabled for app '{app_name}'"
        }

    # Make the API call
    try:
        response_data = _make_http_request(app_config, endpoint_config, params)
        return {"data": response_data, "success": True}
    except requests.exceptions.RequestException as e:
        frappe.log_error(
            message=f"External API Error ({app_name}.{action_name}): {str(e)}",
            title=f"External API Request Failed: {app_name}",
        )
        return {"error": f"Failed to fetch data from {app_name}: {str(e)}"}
    except Exception as e:
        frappe.log_error(
            message=f"External Integration Error ({app_name}.{action_name}): {str(e)}",
            title=f"External Integration Error: {app_name}",
        )
        return {"error": f"An error occurred: {str(e)}"}


@frappe.whitelist()
def get_employee_data(ticket_id: str, app_name: str = "proconut"):
    """
    Fetch employee data for a ticket from an external system.
    This is a convenience wrapper around call_external_api specifically for employee data.

    Args:
        ticket_id: The HD Ticket ID
        app_name: Name of the external app (default: 'proconut')

    Returns:
        dict: Employee data from external API or error message
    """
    # Get ticket and contact email
    ticket = frappe.get_doc("HD Ticket", ticket_id)
    if not ticket:
        return {"error": f"Ticket {ticket_id} not found"}

    contact_email = _get_contact_email(ticket)
    if not contact_email:
        return {"error": "No contact email found for this ticket"}

    # Check if email is a configured email account
    if _is_email_account(contact_email):
        return {
            "error": "Contact email is a system email account",
            "is_system_email": True,
        }

    # Call the external API with app_name and action_name
    return call_external_api(
        app_name=app_name,
        action_name="get_employee_data",
        params={"search_text": contact_email},
    )


@frappe.whitelist()
def check_integration_status(app_name: str = None):
    """
    Check if external integrations are enabled and optionally check a specific app.

    Args:
        app_name: Optional - Name of specific app to check

    Returns:
        dict: Status information
    """
    settings = frappe.get_single("HD External Integration Settings")

    if not settings.enabled:
        return {"enabled": False, "configured": False}

    if app_name:
        from helpdesk.helpdesk.doctype.hd_external_integration_settings.hd_external_integration_settings import (
            HDExternalIntegrationSettings,
        )

        app_config = HDExternalIntegrationSettings.get_app_config(app_name)
        return {
            "enabled": settings.enabled,
            "configured": bool(app_config),
            "app_name": app_name,
        }

    # Return general status
    return {
        "enabled": settings.enabled,
        "configured": bool(settings.apps),
        "app_count": len(settings.apps) if settings.apps else 0,
        "endpoint_count": len(settings.endpoints) if settings.endpoints else 0,
    }


@frappe.whitelist()
def test_connection(app_name: str):
    """
    Test connection to an external app (for admin use).

    Args:
        app_name: Name of the app to test

    Returns:
        dict: Connection test result
    """
    from helpdesk.helpdesk.doctype.hd_external_integration_settings.hd_external_integration_settings import (
        HDExternalIntegrationSettings,
    )

    app_config = HDExternalIntegrationSettings.get_app_config(app_name)
    if not app_config:
        return {"success": False, "error": f"App '{app_name}' not found or not enabled"}

    # Try to make a simple request to test connectivity
    try:
        # Just test if we can reach the base URL
        response = requests.get(app_config["base_url"], timeout=10)
        return {"success": True, "status_code": response.status_code}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _make_http_request(app_config: dict, endpoint_config: dict, params: dict) -> dict:
    """
    Make HTTP request to external API.

    Args:
        app_config: App configuration with base_url, auth_type, api_key
        endpoint_config: Endpoint configuration with path, method, headers, param_mappings
        params: Parameters to pass to the API

    Returns:
        dict: Response from the API
    """
    base_url = app_config["base_url"].rstrip("/")
    endpoint_path = endpoint_config["endpoint_path"]

    # Ensure endpoint starts with /
    if not endpoint_path.startswith("/"):
        endpoint_path = "/" + endpoint_path

    url = f"{base_url}{endpoint_path}"

    # Build headers
    headers = {"Content-Type": "application/json"}

    # Add authentication headers based on auth_type
    if app_config["auth_type"] == "API Key":
        headers["X-Proconut-Secret-Key"] = app_config["api_key"]
    elif app_config["auth_type"] == "Bearer Token":
        headers["Authorization"] = f"Bearer {app_config['api_key']}"
    elif app_config["auth_type"] == "Basic Auth":
        headers["Authorization"] = f"Basic {app_config['api_key']}"
    elif app_config["auth_type"] == "Auth header":
        headers["Authorization"] = f"{app_config['api_key']}"

    # Add additional headers from endpoint config
    if endpoint_config.get("additional_headers"):
        headers.update(endpoint_config["additional_headers"])

    # Apply parameter mappings
    mapped_params = {}
    param_mappings = endpoint_config.get("query_param_mappings", {})

    for key, value in params.items():
        # Use mapping if available, otherwise use original key
        mapped_key = param_mappings.get(key, key)
        mapped_params[mapped_key] = value

    # Make the request based on HTTP method
    http_method = endpoint_config["http_method"].upper()

    if http_method == "GET":
        response = requests.get(url, headers=headers, params=mapped_params, timeout=30)
    elif http_method == "POST":
        response = requests.post(url, headers=headers, json=mapped_params, timeout=30)
    elif http_method == "PUT":
        response = requests.put(url, headers=headers, json=mapped_params, timeout=30)
    elif http_method == "PATCH":
        response = requests.patch(url, headers=headers, json=mapped_params, timeout=30)
    elif http_method == "DELETE":
        response = requests.delete(url, headers=headers, params=mapped_params, timeout=30)
    else:
        raise ValueError(f"Unsupported HTTP method: {http_method}")

    response.raise_for_status()
    return response.json()


def _get_contact_email(ticket):
    """Get the contact email from the ticket"""
    # First try to get from contact linked to ticket
    if ticket.contact:
        contact = frappe.get_doc("Contact", ticket.contact)
        if contact and contact.email_id:
            return contact.email_id.lower()

    # Fallback to raised_by field
    if ticket.raised_by:
        return ticket.raised_by.lower()

    return None


def _is_email_account(email: str) -> bool:
    """
    Check if the given email is one of the configured Email Accounts.
    We don't want to query external APIs for system email addresses.
    """
    if not email:
        return False

    email_lower = email.lower()
    # Check if this email belongs to any configured email account
    email_accounts = frappe.get_all(
        "Email Account",
        filters={"enable_incoming": 1},
        fields=["email_id"],
    )

    for account in email_accounts:
        if account.email_id and account.email_id.lower() == email_lower:
            return True

    return False
