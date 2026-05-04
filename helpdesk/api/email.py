import re
from typing import List

import frappe
from frappe import _

from helpdesk.helpdesk.doctype.hd_ticket.hd_ticket import get_always_cc, merge_cc
from helpdesk.helpdesk.utils.email import (
    default_outgoing_email_account,
    default_ticket_outgoing_email_account,
)
from helpdesk.utils import agent_only


_EMAIL_RE = re.compile(
    r"^(([^<>()\[\]\\.,;:\s@\"]+(\.[^<>()\[\]\\.,;:\s@\"]+)*)"
    r'|(".+"))@((\[[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}])'
    r"|([a-zA-Z\-0-9]+\.)+[a-zA-Z]{2,})$"
)


def _validate_email(address: str) -> bool:
    return bool(_EMAIL_RE.match(address.strip()))


def _resolve_sender_email(ticket_doc):
    """
    Walk the same fallback chain as HDTicket.sender_email() but for a
    freshly-created ticket that has no prior communications.
    """
    if ea := default_ticket_outgoing_email_account():
        return frappe.get_doc("Email Account", ea["name"])
    if ea := default_outgoing_email_account():
        return frappe.get_doc("Email Account", ea["name"])
    return None


@frappe.whitelist()
@agent_only
def compose_new_email(
    to: str,
    subject: str,
    message: str,
    cc: str = None,
    bcc: str = None,
    attachments: List[str] = [],
):
    """
    Compose and send a brand-new outbound email from Helpdesk.

    Creates a new HD Ticket (with the composed subject) and sends the first
    outbound Communication without the forced ``Re [#ticket]:`` prefix that
    ``reply_via_agent`` applies on subsequent replies.

    Returns a dict with ``ticket_id`` and ``communication_id``.
    """
    # ── Validation ────────────────────────────────────────────────────────────
    if not to or not to.strip():
        frappe.throw(_("At least one recipient is required"), frappe.ValidationError)

    if not subject or not subject.strip():
        frappe.throw(_("Subject is required"), frappe.ValidationError)

    if not message or not message.strip():
        frappe.throw(_("Message body is required"), frappe.ValidationError)

    recipient_list = [r.strip() for r in to.split(",") if r.strip()]
    for addr in recipient_list:
        if not _validate_email(addr):
            frappe.throw(
                _("{0} is not a valid email address").format(addr),
                frappe.ValidationError,
            )

    # ── Create HD Ticket ──────────────────────────────────────────────────────
    ticket = frappe.get_doc(
        {
            "doctype": "HD Ticket",
            "subject": subject.strip(),
            "raised_by": recipient_list[0],
            "via_customer_portal": False,
        }
    ).insert(ignore_permissions=True)

    # ── Resolve sender email account ──────────────────────────────────────────
    skip_email_workflow: bool = bool(
        int(frappe.get_value("HD Settings", None, "skip_email_workflow") or "0")
    )
    sender_email = None if skip_email_workflow else _resolve_sender_email(ticket)

    if not skip_email_workflow and not sender_email:
        frappe.throw(_("Cannot send email. No outgoing email account configured."))

    medium = "" if skip_email_workflow else "Email"
    sender = frappe.session.user

    # ── Merge always-CC ───────────────────────────────────────────────────────
    always_cc = get_always_cc()
    merged_cc = merge_cc(cc, always_cc)

    # ── Create Communication record ───────────────────────────────────────────
    communication = frappe.get_doc(
        {
            "doctype": "Communication",
            "communication_type": "Communication",
            "communication_medium": medium,
            "sent_or_received": "Sent",
            "status": "Linked",
            "email_status": "Open",
            "subject": subject.strip(),
            "content": message,
            "sender": sender,
            "recipients": to,
            "cc": merged_cc,
            "bcc": bcc,
            "reference_doctype": "HD Ticket",
            "reference_name": ticket.name,
            "email_account": sender_email.name if sender_email else None,
        }
    ).insert(ignore_permissions=True)

    # ── Re-attach uploaded files to the Communication ─────────────────────────
    _attachments = []
    for attachment in attachments:
        file_doc = frappe.get_doc("File", attachment)
        file_doc.attached_to_name = communication.name
        file_doc.attached_to_doctype = "Communication"
        file_doc.save(ignore_permissions=True)
        ticket.attach_file_with_doc("HD Ticket", ticket.name, file_doc.file_url)
        _attachments.append({"file_url": file_doc.file_url})

    if skip_email_workflow or not frappe.db.get_single_value(
        "HD Settings", "enable_reply_email_via_agent"
    ):
        return {"ticket_id": ticket.name, "communication_id": communication.name}

    # ── Parse inline media (img/video src → embed) ────────────────────────────
    parsed_message = ticket.parse_content(message)

    if hasattr(sender_email, "signature") and sender_email.signature:
        parsed_message = parsed_message + "\n\n" + sender_email.signature

    reply_to_email = sender_email.email_id

    instantly_send: bool = bool(
        int(frappe.get_value("HD Settings", None, "instantly_send_email") or "0")
    )
    send_delayed = not instantly_send
    send_now = instantly_send

    try:
        frappe.sendmail(
            attachments=_attachments,
            bcc=bcc,
            cc=merged_cc,
            communication=communication.name,
            delayed=send_delayed,
            expose_recipients="header",
            message=parsed_message,
            as_markdown=True,
            now=send_now,
            recipients=to,
            reference_doctype="HD Ticket",
            reference_name=ticket.name,
            reply_to=reply_to_email,
            sender=reply_to_email,
            subject=subject.strip(),
            with_container=False,
            email_headers={"X-Auto-Generated": "hd-compose"},
        )
    except Exception as e:
        frappe.throw(_(str(e)))

    return {"ticket_id": ticket.name, "communication_id": communication.name}
