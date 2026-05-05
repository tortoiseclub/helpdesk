import frappe


def sync_message_id_to_communication(doc, method=None):
    """
    Write the Email Queue's message_id back to the linked Communication record.

    Frappe generates the message_id when building the email content and stores it
    on the Email Queue, but never propagates it to the Communication. Without this,
    when an outbound email loops back through a group inbox (e.g. help@tortoise.pro
    re-delivering to support@tortoise.pro), Frappe's inbound deduplication cannot
    match the looped email to the existing Communication and creates a duplicate ticket.
    """
    if not doc.communication or not doc.message_id:
        return

    existing = frappe.db.get_value("Communication", doc.communication, "message_id")
    if existing:
        return

    frappe.db.set_value(
        "Communication",
        doc.communication,
        "message_id",
        doc.message_id,
        update_modified=False,
    )
