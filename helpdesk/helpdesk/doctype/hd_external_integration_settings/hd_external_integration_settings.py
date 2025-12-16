# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class HDExternalIntegrationSettings(Document):
    def validate(self):
        if self.enabled:
            self.validate_apps()
            self.validate_endpoints()

    def validate_apps(self):
        """Validate app configurations"""
        if not self.apps:
            frappe.throw(_("At least one app must be configured when integration is enabled"))

        app_names = [app.app_name for app in self.apps]
        if len(app_names) != len(set(app_names)):
            frappe.throw(_("Duplicate app names found. Each app name must be unique"))

        for app in self.apps:
            if not app.base_url:
                frappe.throw(_("Base URL is required for app: {0}").format(app.app_name))

    def validate_endpoints(self):
        """Validate endpoint configurations"""
        if not self.endpoints:
            return

        # Check for duplicate app_name + action_name combinations
        endpoint_keys = [(e.app_name, e.action_name) for e in self.endpoints]
        if len(endpoint_keys) != len(set(endpoint_keys)):
            frappe.throw(
                _("Duplicate app_name + action_name combinations found. Each combination must be unique")
            )

        # Validate that each endpoint's app_name exists in apps table
        app_names = [app.app_name for app in self.apps]
        for endpoint in self.endpoints:
            if endpoint.app_name not in app_names:
                frappe.throw(
                    _("App '{0}' not found for endpoint '{1}'. Please add the app first").format(
                        endpoint.app_name, endpoint.action_name
                    )
                )

    @staticmethod
    def get_app_config(app_name: str):
        """Get configuration for a specific app"""
        settings = frappe.get_single("HD External Integration Settings")

        if not settings.enabled:
            return None

        for app in settings.apps:
            if app.app_name == app_name and app.enabled:
                return {
                    "app_name": app.app_name,
                    "base_url": app.base_url,
                    "auth_type": app.auth_type,
                    "api_key": app.get_password("api_key") if app.api_key else None,
                }

        return None

    @staticmethod
    def get_endpoint_config(app_name: str, action_name: str):
        """Get configuration for a specific endpoint"""
        settings = frappe.get_single("HD External Integration Settings")

        if not settings.enabled:
            return None

        for endpoint in settings.endpoints:
            if (
                endpoint.app_name == app_name
                and endpoint.action_name == action_name
                and endpoint.enabled
            ):
                # Parse JSON fields
                additional_headers = {}
                query_param_mappings = {}

                if endpoint.additional_headers:
                    try:
                        import json
                        additional_headers = json.loads(endpoint.additional_headers)
                    except Exception:
                        pass

                if endpoint.query_param_mappings:
                    try:
                        import json
                        query_param_mappings = json.loads(endpoint.query_param_mappings)
                    except Exception:
                        pass

                return {
                    "endpoint_path": endpoint.endpoint_path,
                    "http_method": endpoint.http_method,
                    "additional_headers": additional_headers,
                    "query_param_mappings": query_param_mappings,
                }

        return None

    @staticmethod
    def is_enabled():
        """Check if external integrations are enabled"""
        settings = frappe.get_single("HD External Integration Settings")
        return settings.enabled
