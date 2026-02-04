# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class HDNonWorkEmailLog(Document):
	"""
	Log to track when auto-replies were sent to non-work email addresses.
	This helps prevent spam by throttling auto-reply frequency.
	"""
	pass
