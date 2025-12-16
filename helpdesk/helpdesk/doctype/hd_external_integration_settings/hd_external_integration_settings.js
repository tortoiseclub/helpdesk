// Copyright (c) 2025, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("HD External Integration Settings", {
  refresh: function (frm) {
    if (frm.doc.enabled && frm.doc.apps && frm.doc.apps.length > 0) {
      frm.add_custom_button(__("Test Connection"), function () {
        frappe.call({
          method: "helpdesk.api.external_integration.test_connection",
          args: {
            app_name: frm.doc.apps[0].app_name,
          },
          callback: function (r) {
            if (r.message && r.message.success) {
              frappe.msgprint({
                title: __("Success"),
                indicator: "green",
                message: __("Successfully connected to {0}", [
                  frm.doc.apps[0].app_name,
                ]),
              });
            } else {
              frappe.msgprint({
                title: __("Connection Failed"),
                indicator: "red",
                message: r.message.error || __("Failed to connect to the API"),
              });
            }
          },
          error: function (r) {
            frappe.msgprint({
              title: __("Error"),
              indicator: "red",
              message: __("An error occurred while testing the connection"),
            });
          },
        });
      });
    }
  },
});
