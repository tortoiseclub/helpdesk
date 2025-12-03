# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

import json

import frappe
from frappe import _
from bs4 import BeautifulSoup

from helpdesk.utils import agent_only


# =============================================================================
# SETTINGS & CONFIGURATION
# =============================================================================

def _get_ai_settings():
    """Get AI settings from HD Settings."""
    settings = frappe.get_cached_doc("HD Settings")
    
    if not settings.enable_ai_summary:
        return None
    
    return {
        "enabled": settings.enable_ai_summary,
        "enable_tag_annotation": getattr(settings, 'enable_ai_tag_annotation', False),
        "provider": settings.ai_provider,
        "model": settings.ai_model or "gpt-4o",
        "openai_api_key": settings.get_password("openai_api_key") if settings.ai_provider == "OpenAI" else None,
        "azure_endpoint": settings.azure_openai_endpoint,
        "azure_api_key": settings.get_password("azure_openai_api_key") if settings.ai_provider == "Azure OpenAI" else None,
        "azure_deployment": settings.azure_openai_deployment,
        "azure_api_version": settings.azure_openai_api_version or "2024-06-01",
        "prompt_template": settings.summary_prompt_template or _get_default_summary_prompt(),
    }


def _get_default_summary_prompt():
    """Return the default system prompt for ticket summarization."""
    return """You are a helpful assistant that summarizes support tickets. Based on the ticket information provided, create a concise summary that captures:
1. The main issue or request
2. Key details and context
3. Current status and any important updates

Keep the summary clear, professional, and under 200 words."""


def _get_tag_annotation_prompt():
    """Return the system prompt for tag annotation."""
    return """You are a helpful assistant that categorizes support tickets with relevant tags.
Based on the ticket information provided, analyze the content and suggest the most relevant tags from the available list.

Rules:
1. ONLY suggest tags from the provided available tags list
2. Suggest 1-5 tags that best describe the ticket's topic, issue type, or category
3. Return ONLY a JSON array of tag names, nothing else
4. If no tags are relevant, return an empty array: []

Example response: ["billing", "refund", "urgent"]"""


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def _strip_html(html_content):
    """Remove HTML tags and return plain text."""
    if not html_content:
        return ""
    soup = BeautifulSoup(html_content, "html.parser")
    return soup.get_text(separator=" ", strip=True)


def _get_ticket_context(ticket_id: str, prefer_summary: bool = False) -> dict:
    """
    Gather full ticket context including description, communications, and comments.
    
    Args:
        ticket_id: The HD Ticket name/ID
        prefer_summary: If True, return the summary if it exists, otherwise return the full context
        
    Returns:
        Dictionary containing ticket details, communications, and comments
    """
    from frappe.query_builder import Order
    
    ticket = frappe.get_doc("HD Ticket", ticket_id)
    
    if prefer_summary and ticket.summary:
        return {
            "ticket": {
                "id": ticket.name,
                "subject": ticket.subject,
                "summary": ticket.summary,
            }
        }
    
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
    
    # Handle summary-only context
    if "summary" in ticket:
        return f"Ticket #{ticket['id']}: {ticket['subject']}\n\nSummary:\n{ticket['summary']}"
    
    prompt_parts = [
        f"Ticket #{ticket['id']}: {ticket['subject']}",
        f"Status: {ticket.get('status', 'N/A')} | Priority: {ticket.get('priority', 'N/A')} | Type: {ticket.get('ticket_type') or 'N/A'}",
        f"Raised by: {ticket.get('raised_by', 'N/A')} on {ticket.get('creation', 'N/A')}",
        "",
        "--- Original Description ---",
        ticket.get("description") or "(No description provided)",
    ]
    
    if context.get("communications"):
        prompt_parts.extend(["", "--- Communications ---"])
        for i, comm in enumerate(context["communications"], 1):
            direction = "Customer" if comm["type"] == "Received" else "Agent"
            prompt_parts.append(f"\n[{i}] {direction} ({comm['sender']}) - {comm['date']}:")
            prompt_parts.append(comm["content"][:2000])
    
    if context.get("comments"):
        prompt_parts.extend(["", "--- Internal Comments ---"])
        for i, comment in enumerate(context["comments"], 1):
            prompt_parts.append(f"\n[{i}] {comment['author']} - {comment['date']}:")
            prompt_parts.append(comment["content"][:1000])
    
    return "\n".join(prompt_parts)


def _get_ai_client(settings: dict):
    """Get the appropriate AI client based on provider settings."""
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
    else:
        if not settings["openai_api_key"]:
            frappe.throw(_("OpenAI API key is required"))
        
        return OpenAI(api_key=settings["openai_api_key"])


def _call_llm(settings: dict, system_prompt: str, user_content: str) -> str:
    """Call the LLM API to generate content."""
    client = _get_ai_client(settings)
    model = settings["azure_deployment"] if settings["provider"] == "Azure OpenAI" else settings["model"]
    
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        max_tokens=500,
        temperature=0.3,
    )
    
    return response.choices[0].message.content.strip()


def _parse_json_response(response: str) -> list:
    """Parse JSON array from LLM response, handling markdown code blocks."""
    cleaned = response.strip()
    
    # Remove markdown code blocks if present
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        # Remove first line (```json or ```) and last line (```)
        cleaned = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    
    return json.loads(cleaned)


def _get_available_tags() -> list[str]:
    """Get all available tags for HD Ticket doctype."""
    from frappe.desk.doctype.tag.tag import get_tags
    return get_tags("HD Ticket", "") or []


def _get_ticket_tags(ticket_id: str) -> list[str]:
    """Get current tags for a ticket."""
    QBTag = frappe.qb.DocType("Tag Link")
    rows = (
        frappe.qb.from_(QBTag)
        .select(QBTag.tag)
        .where(QBTag.document_type == "HD Ticket")
        .where(QBTag.document_name == ticket_id)
        .run(as_dict=True)
    )
    return [row.tag for row in rows]


def _add_tag_to_ticket(ticket_id: str, tag: str):
    """Add a tag to a ticket using Frappe's tag system."""
    from frappe.desk.doctype.tag.tag import add_tag
    add_tag(tag=tag, dt="HD Ticket", dn=ticket_id)


# =============================================================================
# CORE FUNCTIONS (Single source of truth for AI operations)
# =============================================================================

def _generate_summary_for_ticket(ticket_id: str, settings: dict) -> str:
    """
    Core function to generate summary for a ticket.
    
    Args:
        ticket_id: The HD Ticket name/ID
        settings: AI settings dictionary
        
    Returns:
        Generated summary text
        
    Raises:
        Exception on failure
    """
    context = _get_ticket_context(ticket_id)
    user_content = _build_prompt_content(context)
    return _call_llm(settings, settings["prompt_template"], user_content)


def _annotate_tags_for_ticket(ticket_id: str, settings: dict) -> dict:
    """
    Core function to annotate tags for a ticket.
    
    Args:
        ticket_id: The HD Ticket name/ID
        settings: AI settings dictionary
        
    Returns:
        Dictionary with tags_added, tags_already_present, and all_suggested
        
    Raises:
        Exception on failure
    """
    available_tags = _get_available_tags()
    
    if not available_tags:
        return {"tags_added": [], "tags_already_present": [], "all_suggested": [], "no_tags_available": True}
    
    # Get ticket context (prefer summary if available for efficiency)
    context = _get_ticket_context(ticket_id, prefer_summary=True)
    
    # Build prompt
    user_content = f"""Available tags: {json.dumps(available_tags)}

Ticket Information:
{_build_prompt_content(context)}

Based on the ticket information above, select the most relevant tags from the available tags list.
Return ONLY a JSON array of tag names."""
    
    # Call LLM
    response = _call_llm(settings, _get_tag_annotation_prompt(), user_content)
    
    # Parse response
    suggested_tags = _parse_json_response(response)
    
    if not isinstance(suggested_tags, list):
        suggested_tags = []
    
    # Filter to valid tags only
    valid_tags = [tag for tag in suggested_tags if tag in available_tags]
    
    # Get existing tags
    existing_tags = _get_ticket_tags(ticket_id)
    
    # Add new tags
    tags_added = []
    for tag in valid_tags:
        if tag not in existing_tags:
            _add_tag_to_ticket(ticket_id, tag)
            tags_added.append(tag)
    
    return {
        "tags_added": tags_added,
        "tags_already_present": [t for t in valid_tags if t in existing_tags],
        "all_suggested": valid_tags,
    }


# =============================================================================
# API ENDPOINTS (Whitelisted functions for frontend)
# =============================================================================

@frappe.whitelist()
def is_ai_enabled() -> bool:
    """Check if AI summary feature is enabled."""
    return bool(frappe.db.get_single_value("HD Settings", "enable_ai_summary"))


@frappe.whitelist()
def is_ai_tag_annotation_enabled() -> bool:
    """Check if AI tag annotation feature is enabled."""
    ai_enabled = frappe.db.get_single_value("HD Settings", "enable_ai_summary")
    tag_enabled = frappe.db.get_single_value("HD Settings", "enable_ai_tag_annotation")
    return bool(ai_enabled and tag_enabled)


@frappe.whitelist()
@agent_only
def generate_ticket_summary(ticket_id: str, force: bool = False) -> dict:
    """
    Generate an AI-powered summary for a ticket.
    
    Args:
        ticket_id: The HD Ticket name/ID
        force: If True, regenerate even if summary exists
        
    Returns:
        Dictionary with success status and generated summary
    """
    settings = _get_ai_settings()
    if not settings:
        return {"success": False, "message": _("AI Summary is not enabled in settings")}
    
    if not frappe.db.exists("HD Ticket", ticket_id):
        frappe.throw(_("Ticket not found"), frappe.DoesNotExistError)
    
    # Check cache
    if not force:
        existing_summary = frappe.db.get_value("HD Ticket", ticket_id, "summary")
        if existing_summary:
            return {"success": True, "summary": existing_summary, "cached": True}
    
    try:
        summary = _generate_summary_for_ticket(ticket_id, settings)
        
        # Save to database
        frappe.db.set_value("HD Ticket", ticket_id, "summary", summary, update_modified=False)
        frappe.db.commit()
        
        return {"success": True, "summary": summary, "cached": False}
    
    except Exception as e:
        frappe.log_error(
            message=f"Failed to generate summary for ticket {ticket_id}: {str(e)}",
            title="AI Summary Generation Failed"
        )
        return {"success": False, "message": str(e)}


@frappe.whitelist()
@agent_only
def annotate_tags(ticket_id: str) -> dict:
    """
    Use AI to analyze a ticket and automatically assign relevant tags.
    
    Args:
        ticket_id: The HD Ticket name/ID
        
    Returns:
        Dictionary with success status and assigned tags
    """
    settings = _get_ai_settings()
    if not settings:
        return {"success": False, "message": _("AI is not enabled in settings")}
    
    if not frappe.db.exists("HD Ticket", ticket_id):
        frappe.throw(_("Ticket not found"), frappe.DoesNotExistError)
    
    try:
        result = _annotate_tags_for_ticket(ticket_id, settings)
        
        if result.get("no_tags_available"):
            return {"success": False, "message": _("No tags available. Please create some tags first.")}
        
        if not result["tags_added"] and not result["tags_already_present"]:
            return {
                "success": True,
                "message": _("No relevant tags found"),
                "tags_added": [],
                "all_suggested": result["all_suggested"],
            }
        
        return {
            "success": True,
            "tags_added": result["tags_added"],
            "tags_already_present": result["tags_already_present"],
            "all_suggested": result["all_suggested"],
        }
    
    except json.JSONDecodeError:
        frappe.log_error(title="AI Tag Annotation Parse Error")
        return {"success": False, "message": _("Failed to parse AI response")}
    
    except Exception as e:
        frappe.log_error(
            message=f"Failed to annotate tags for ticket {ticket_id}: {str(e)}",
            title="AI Tag Annotation Failed"
        )
        return {"success": False, "message": str(e)}


# =============================================================================
# HOOK-READY FUNCTIONS (Background jobs / Hooks entry points)
# These can be moved to hooks.py or called from background jobs
# =============================================================================

def on_ticket_update_generate_summary(ticket_id: str):
    """
    Hook-ready function to generate summary on ticket update.
    Silently fails on error (logs to error log).
    """
    settings = _get_ai_settings()
    if not settings or not settings.get("enabled"):
        return
    
    try:
        summary = _generate_summary_for_ticket(ticket_id, settings)
        frappe.db.set_value("HD Ticket", ticket_id, "summary", summary, update_modified=False)
        frappe.db.commit()
    except Exception as e:
        frappe.log_error(
            message=f"Hook: Summary generation failed for ticket {ticket_id}: {str(e)}",
            title="AI Summary Generation Failed"
        )


def on_ticket_update_annotate_tags(ticket_id: str):
    """
    Hook-ready function to annotate tags on ticket update.
    Silently fails on error (logs to error log).
    """
    settings = _get_ai_settings()
    if not settings or not settings.get("enable_tag_annotation"):
        return
    
    try:
        _annotate_tags_for_ticket(ticket_id, settings)
    except Exception as e:
        frappe.log_error(
            message=f"Hook: Tag annotation failed for ticket {ticket_id}: {str(e)}",
            title="AI Tag Annotation Failed"
        )


def process_ticket_with_ai(ticket_id: str):
    """
    Main entry point for AI processing on ticket updates.
    Runs both summary generation and tag annotation.
    Designed to be called from hooks or background jobs.
    """
    on_ticket_update_generate_summary(ticket_id)
    on_ticket_update_annotate_tags(ticket_id)


# Background job aliases (for clarity in enqueue calls)
generate_summary_on_communication = on_ticket_update_generate_summary
annotate_tags_on_communication = on_ticket_update_annotate_tags
