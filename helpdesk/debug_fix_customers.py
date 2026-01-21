"""
Script to fix tickets without linked customers.

Usage:
    # In bench console or REPL:
    from helpdesk.debug_fix_customers import fix_tickets_without_customer
    
    # Dry run (default) - see what would be updated
    fix_tickets_without_customer(dry_run=True, limit=10)
    
    # Actually update tickets
    fix_tickets_without_customer(dry_run=False, limit=10)
    
    # Process all tickets
    fix_tickets_without_customer(dry_run=False, limit=None)
"""

from email.utils import parseaddr

import frappe

from helpdesk.utils import get_customer, get_email_from_subject


def _extract_email_from_raised_by(raised_by: str) -> str | None:
    """
    Extract email from raised_by field, skipping tortoise.pro emails.
    
    :param raised_by: The raised_by field value
    :return: Email address if valid and not tortoise.pro, None otherwise
    """
    if not raised_by:
        return None
    
    _, email = parseaddr(raised_by)
    if email and "tortoise.pro" not in email.lower():
        return email
    
    return None


def _extract_email_from_contact(contact: str) -> str | None:
    """
    Extract email from contact, skipping tortoise.pro emails.
    
    :param contact: Contact document dict
    :return: Email address if valid and not tortoise.pro, None otherwise
    """
    if not contact:
        return None

    try:
        contact_doc = frappe.get_doc("Contact", contact)
        if contact_doc and contact_doc.email_id:
            return contact_doc.email_id
    except Exception as e:
        print(f"Error extracting email from contact {contact}: {str(e)}")
        return None
    
    return None


def _extract_email_from_participants(participant_emails: str) -> str | None:
    """
    Extract first valid email from participant_emails, skipping tortoise.pro emails.
    
    :param participant_emails: Comma-separated email addresses
    :return: First valid email address (not tortoise.pro), None if none found
    """
    if not participant_emails:
        return None
    
    emails = participant_emails.split(",")
    for email_str in emails:
        _, email = parseaddr(email_str.strip())
        if email and "tortoise.pro" not in email.lower():
            return email
    
    return None


def _resolve_email_for_ticket(ticket: dict) -> str | None:
    """
    Resolve a valid email address for the ticket using fallback logic.
    Priority: raised_by -> participant_emails -> subject
    
    :param ticket: Ticket document dict
    :return: Valid email address (not tortoise.pro), None if none found
    """

    # Fallback to participant_emails
    if ticket.get("participant_emails"):
        email = _extract_email_from_participants(ticket["participant_emails"])
        if email:
            return email
    
    # Last resort: try to extract from subject
    if ticket.get("subject"):
        email = get_email_from_subject(ticket["subject"])
        if email and "tortoise.pro" not in email.lower():
            return email
    
    return None


def fix_tickets_without_customer(dry_run: bool = True, limit: int | None = None):
    """
    Find tickets without customers and attempt to link them using get_customer().
    
    :param dry_run: If True, only print what would be updated (default: True)
    :param limit: Maximum number of tickets to process (default: None = all)
    :return: Summary dict with counts
    """
    # Fetch tickets without customers
    filters = {"customer": ["is", "not set"]}
    
    tickets = frappe.get_all(
        "HD Ticket",
        filters=filters,
        fields=[
            "name",
            "subject",
            "contact",
            "raised_by",
            "participant_emails",
            "customer",
        ],
        limit=limit,
        order_by="modified desc",
    )
    
    if not tickets:
        print("No tickets found without customers.")
        return {
            "total": 0,
            "updated": 0,
            "skipped_no_contact": 0,
            "skipped_no_email": 0,
            "skipped_multiple_customers": 0,
            "skipped_no_customers": 0,
        }
    
    print(f"\nFound {len(tickets)} ticket(s) without customers.")
    if dry_run:
        print("🔍 DRY RUN MODE - No changes will be made\n")
    else:
        print("⚠️  LIVE MODE - Tickets will be updated\n")
    
    stats = {
        "total": len(tickets),
        "updated": 0,
        "skipped_no_contact": 0,
        "skipped_no_email": 0,
        "skipped_multiple_customers": 0,
        "skipped_no_customers": 0,
    }
    
    for ticket in tickets:
        ticket_name = ticket["name"]
        
        # Skip if no contact
        if not ticket.get("contact"):
            print(f"⏭️  {ticket_name}: Skipped - no contact linked")
            stats["skipped_no_contact"] += 1
            continue

        # Try all non-tortoise.pro participant_emails as well as fallback to subject for email
        candidate_emails = set()

        # Collect participant_emails if present and not tortoise.pro
        participant_emails_str = ticket.get("participant_emails", "")
        if participant_emails_str:
            emails = [parseaddr(e.strip())[1] for e in participant_emails_str.split(",")]
            for email in emails:
                if email and "tortoise.pro" not in email.lower():
                    candidate_emails.add(email)

        # Fallback: If no valid participant_emails, try extracting from subject
        if not candidate_emails and ticket.get("subject"):
            fallback_email = get_email_from_subject(ticket["subject"])
            if fallback_email and "tortoise.pro" not in fallback_email.lower():
                candidate_emails.add(fallback_email)

        if not candidate_emails:
            print(f"⏭️  {ticket_name}: Skipped - no valid email found (avoiding tortoise.pro)")
            stats["skipped_no_email"] += 1
            continue

        found_customer = False
        for email_id in candidate_emails:
            try:
                customers = get_customer(ticket["contact"], email_id)
            except Exception as e:
                continue

            if not customers:
                continue
            if len(customers) == 1:
                found_customer = True
                break
            else:
                print(f"⏭️  {ticket_name}: Skipped - multiple customers found ({len(customers)}): {', '.join(customers)}")
                stats["skipped_multiple_customers"] += 1
                # If there are multiple customers for this email, try next email
                continue
        

        if not found_customer:
            print(f"⏭️  {ticket_name}: Skipped - no customers found for contact '{ticket['contact']}' and emails '{', '.join(candidate_emails)}'")
            stats["skipped_no_customers"] += 1
            continue

        # Exactly 1 customer - update ticket
        customer_name = customers[0]
        
        if dry_run:
            print(f"✅ {ticket_name}: Would update -> customer '{customer_name}' (email: {email_id})")
        else:
            try:
                frappe.db.set_value(
                    "HD Ticket",
                    ticket_name,
                    "customer",
                    customer_name,
                    update_modified=False,
                )
                print(f"✅ {ticket_name}: Updated -> customer '{customer_name}' (email: {email_id})")
                stats["updated"] += 1
            except Exception as e:
                print(f"❌ {ticket_name}: Error updating - {str(e)}")
    
    # Print summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total tickets processed: {stats['total']}")
    print(f"Successfully updated: {stats['updated']}")
    print(f"Skipped (no contact): {stats['skipped_no_contact']}")
    print(f"Skipped (no valid email): {stats['skipped_no_email']}")
    print(f"Skipped (multiple customers): {stats['skipped_multiple_customers']}")
    print(f"Skipped (no customers found): {stats['skipped_no_customers']}")
    
    if not dry_run:
        frappe.db.commit()
        print("\n✅ Changes committed to database")
    
    return stats


def execute():
    """
    Entry point for bench execute command.
    Usage: bench --site <site> execute helpdesk.debug_fix_customers.execute
    """
    # Default to dry-run with limit for safety
    fix_tickets_without_customer(dry_run=True, limit=10)
