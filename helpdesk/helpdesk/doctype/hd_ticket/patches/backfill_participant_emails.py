"""
Backfill participant_emails for existing HD Tickets.
Extracts all email addresses from communications linked to each ticket.

Run with: bench --site <site> execute helpdesk.helpdesk.doctype.hd_ticket.patches.backfill_participant_emails.execute
"""

from email.utils import parseaddr

import frappe


def extract_emails_from_string(email_string: str) -> set:
    """
    Extract email addresses from a string that may contain:
    - Simple emails: user@example.com
    - Named emails: "John Doe" <john@example.com>
    - Comma-separated list of the above
    """
    if not email_string:
        return set()

    emails = set()
    parts = email_string.split(",")

    for part in parts:
        part = part.strip()
        if not part:
            continue

        _, email = parseaddr(part)
        if email:
            emails.add(email)

    return emails


def get_participant_emails_for_ticket(ticket_name: str) -> str | None:
    """
    Get all unique participant emails from communications linked to a ticket.
    """
    communications = frappe.get_all(
        "Communication",
        filters={
            "reference_doctype": "HD Ticket",
            "reference_name": ticket_name,
        },
        fields=["sender", "recipients", "cc", "bcc"],
    )

    all_emails = set()

    for comm in communications:
        for field in ["sender", "recipients", "cc", "bcc"]:
            field_value = comm.get(field)
            if field_value:
                extracted = extract_emails_from_string(field_value)
                all_emails.update(extracted)

    if not all_emails:
        return None

    # Deduplicate case-insensitively while preserving original case
    seen_lower = set()
    final_emails = []
    for email in all_emails:
        if email.lower() not in seen_lower:
            final_emails.append(email)
            seen_lower.add(email.lower())

    return ",".join(final_emails) if final_emails else None


def execute(batch_size=100):
    """
    Backfill participant_emails for all HD Tickets.
    Uses direct SQL update to avoid triggering hooks.
    Processes in batches to avoid high CPU usage.
    """
    # Get all ticket names that don't have participant_emails set yet
    tickets = frappe.get_all(
        "HD Ticket",
        filters={"participant_emails": ["in", [None, ""]]},
        pluck="name",
        order_by="name asc",
    )

    total = len(tickets)
    updated = 0
    skipped = 0

    print(f"Processing {total} tickets in batches of {batch_size}...")

    for i, ticket_name in enumerate(tickets):
        participant_emails = get_participant_emails_for_ticket(ticket_name)

        if participant_emails:
            # Direct SQL update to avoid hooks and preserve all other fields
            frappe.db.sql(
                """
                UPDATE `tabHD Ticket`
                SET participant_emails = %s
                WHERE name = %s
                """,
                (participant_emails, ticket_name),
            )
            updated += 1
        else:
            skipped += 1

        # Commit and show progress every batch_size tickets
        if (i + 1) % batch_size == 0:
            frappe.db.commit()
            print(f"Processed {i + 1}/{total} tickets...")

    # Final commit for remaining records
    frappe.db.commit()

    print(f"\nBackfill complete!")
    print(f"  Total tickets: {total}")
    print(f"  Updated: {updated}")
    print(f"  Skipped (no communications): {skipped}")
