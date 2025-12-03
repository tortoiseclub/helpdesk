# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

import frappe
from frappe import _
from bs4 import BeautifulSoup

from helpdesk.utils import agent_only


def _get_ai_settings():
    """Get AI settings from HD Settings."""
    settings = frappe.get_cached_doc("HD Settings")
    
    if not settings.enable_ai_summary:
        return None
    
    return {
        "enabled": settings.enable_ai_summary,
        "provider": settings.ai_provider,
        "model": settings.ai_model or "gpt-4o",
        "openai_api_key": settings.get_password("openai_api_key") if settings.ai_provider == "OpenAI" else None,
        "azure_endpoint": settings.azure_openai_endpoint,
        "azure_api_key": settings.get_password("azure_openai_api_key") if settings.ai_provider == "Azure OpenAI" else None,
        "azure_deployment": settings.azure_openai_deployment,
        "azure_api_version": settings.azure_openai_api_version or "2024-06-01",
        "prompt_template": settings.summary_prompt_template or _get_default_prompt(),
    }


def _get_default_prompt():
    """Return the default system prompt for ticket summarization."""
    return """You are a helpful assistant that summarizes support tickets. Based on the ticket information provided, create a concise summary that captures:
1. The main issue or request
2. Key details and context
3. Current status and any important updates

Keep the summary clear, professional, and under 200 words."""


def _strip_html(html_content):
    """Remove HTML tags and return plain text."""
    if not html_content:
        return ""
    soup = BeautifulSoup(html_content, "html.parser")
    return soup.get_text(separator=" ", strip=True)


def _get_ticket_context(ticket_id: str) -> dict:
    """
    Gather full ticket context including description, communications, and comments.
    
    Args:
        ticket_id: The HD Ticket name/ID
        
    Returns:
        Dictionary containing ticket details, communications, and comments
    """
    from frappe.query_builder import Order
    
    # Get ticket document
    ticket = frappe.get_doc("HD Ticket", ticket_id)
    
    # Get communications
    QBCommunication = frappe.qb.DocType("Communication")
    communications = (
        frappe.qb.from_(QBCommunication)
        .select(
            QBCommunication.content,
            QBCommunication.creation,
            QBCommunication.sender,
            QBCommunication.sent_or_received,
            QBCommunication.subject,
        )
        .where(QBCommunication.reference_doctype == "HD Ticket")
        .where(QBCommunication.reference_name == ticket_id)
        .orderby(QBCommunication.creation, order=Order.asc)
        .run(as_dict=True)
    )
    
    # Get comments (internal notes)
    QBComment = frappe.qb.DocType("HD Ticket Comment")
    comments = (
        frappe.qb.from_(QBComment)
        .select(
            QBComment.content,
            QBComment.creation,
            QBComment.commented_by,
        )
        .where(QBComment.reference_ticket == ticket_id)
        .orderby(QBComment.creation, order=Order.asc)
        .run(as_dict=True)
    )
    
    return {
        "ticket": {
            "id": ticket.name,
            "subject": ticket.subject,
            "description": _strip_html(ticket.description),
            "status": ticket.status,
            "priority": ticket.priority,
            "ticket_type": ticket.ticket_type,
            "raised_by": ticket.raised_by,
            "creation": str(ticket.creation),
        },
        "communications": [
            {
                "content": _strip_html(c.content),
                "sender": c.sender,
                "type": c.sent_or_received,
                "date": str(c.creation),
            }
            for c in communications
        ],
        "comments": [
            {
                "content": _strip_html(c.content),
                "author": c.commented_by,
                "date": str(c.creation),
            }
            for c in comments
        ],
    }


def _build_prompt_content(context: dict) -> str:
    """Build the user prompt content from ticket context."""
    ticket = context["ticket"]
    
    prompt_parts = [
        f"Ticket #{ticket['id']}: {ticket['subject']}",
        f"Status: {ticket['status']} | Priority: {ticket['priority']} | Type: {ticket['ticket_type'] or 'N/A'}",
        f"Raised by: {ticket['raised_by']} on {ticket['creation']}",
        "",
        "--- Original Description ---",
        ticket["description"] or "(No description provided)",
    ]
    
    if context["communications"]:
        prompt_parts.extend(["", "--- Communications ---"])
        for i, comm in enumerate(context["communications"], 1):
            direction = "Customer" if comm["type"] == "Received" else "Agent"
            prompt_parts.append(f"\n[{i}] {direction} ({comm['sender']}) - {comm['date']}:")
            prompt_parts.append(comm["content"][:2000])  # Limit content length
    
    if context["comments"]:
        prompt_parts.extend(["", "--- Internal Comments ---"])
        for i, comment in enumerate(context["comments"], 1):
            prompt_parts.append(f"\n[{i}] {comment['author']} - {comment['date']}:")
            prompt_parts.append(comment["content"][:1000])  # Limit content length
    
    return "\n".join(prompt_parts)


def _get_ai_client(settings: dict):
    """
    Get the appropriate AI client based on provider settings.
    
    Args:
        settings: AI settings dictionary
        
    Returns:
        OpenAI or AzureOpenAI client instance
    """
    try:
        from openai import OpenAI, AzureOpenAI
    except ImportError:
        frappe.throw(
            _("OpenAI package is not installed. Please install it using: pip install openai>=1.0.0")
        )
    
    if settings["provider"] == "Azure OpenAI":
        if not settings["azure_endpoint"] or not settings["azure_api_key"]:
            frappe.throw(_("Azure OpenAI endpoint and API key are required"))
        
        return AzureOpenAI(
            azure_endpoint=settings["azure_endpoint"],
            api_key=settings["azure_api_key"],
            api_version=settings["azure_api_version"],
        )
    else:  # OpenAI
        if not settings["openai_api_key"]:
            frappe.throw(_("OpenAI API key is required"))
        
        return OpenAI(api_key=settings["openai_api_key"])


def _call_llm(settings: dict, system_prompt: str, user_content: str) -> str:
    """
    Call the LLM API to generate content.
    
    Args:
        settings: AI settings dictionary
        system_prompt: The system prompt
        user_content: The user message content
        
    Returns:
        Generated text from the LLM
    """
    client = _get_ai_client(settings)
    
    # For Azure OpenAI, use deployment name as model
    model = settings["azure_deployment"] if settings["provider"] == "Azure OpenAI" else settings["model"]
    
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            max_tokens=500,
            temperature=0.3,  # Lower temperature for more consistent summaries
        )
        
        return response.choices[0].message.content.strip()
    except Exception as e:
        frappe.log_error(
            message=f"LLM API Error: {str(e)}",
            title="AI Summary Generation Failed"
        )
        raise


@frappe.whitelist()
@agent_only
def generate_ticket_summary(ticket_id: str, force: bool = False) -> dict:
    """
    Generate an AI-powered summary for a ticket.
    
    Args:
        ticket_id: The HD Ticket name/ID
        force: If True, regenerate even if summary exists
        
    Returns:
        Dictionary with the generated summary
    """
    # Check if AI summary is enabled
    settings = _get_ai_settings()
    if not settings:
        return {"success": False, "message": _("AI Summary is not enabled in settings")}
    
    # Check if ticket exists and user has permission
    if not frappe.db.exists("HD Ticket", ticket_id):
        frappe.throw(_("Ticket not found"), frappe.DoesNotExistError)
    
    ticket = frappe.get_doc("HD Ticket", ticket_id)
    
    # Check if summary already exists and force is not set
    if ticket.summary and not force:
        return {"success": True, "summary": ticket.summary, "cached": True}
    
    try:
        # Get ticket context
        context = _get_ticket_context(ticket_id)
        
        # Build prompt content
        user_content = _build_prompt_content(context)
        
        # Call LLM
        summary = _call_llm(settings, settings["prompt_template"], user_content)
        
        # Save summary to ticket
        frappe.db.set_value("HD Ticket", ticket_id, "summary", summary, update_modified=False)
        frappe.db.commit()
        
        return {"success": True, "summary": summary, "cached": False}
    
    except Exception as e:
        frappe.log_error(
            message=f"Failed to generate summary for ticket {ticket_id}: {str(e)}",
            title="AI Summary Generation Failed"
        )
        return {"success": False, "message": str(e)}


def generate_summary_on_communication(ticket_id: str):
    """
    Background job to generate summary when a communication is added.
    This is called from the HD Ticket doctype hooks.
    
    Args:
        ticket_id: The HD Ticket name/ID
    """
    settings = _get_ai_settings()
    if not settings:
        return
    
    try:
        context = _get_ticket_context(ticket_id)
        user_content = _build_prompt_content(context)
        summary = _call_llm(settings, settings["prompt_template"], user_content)
        
        frappe.db.set_value("HD Ticket", ticket_id, "summary", summary, update_modified=False)
        frappe.db.commit()
        
    except Exception as e:
        frappe.log_error(
            message=f"Background summary generation failed for ticket {ticket_id}: {str(e)}",
            title="AI Summary Generation Failed"
        )


@frappe.whitelist()
def is_ai_enabled() -> bool:
    """Check if AI summary feature is enabled."""
    return bool(frappe.db.get_single_value("HD Settings", "enable_ai_summary"))

