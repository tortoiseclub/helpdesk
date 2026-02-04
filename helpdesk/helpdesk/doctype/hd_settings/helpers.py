def is_email_content_empty(content: str | None) -> bool:
    return content is None or content.strip() == ""


def get_default_email_content(type: str) -> str:
    if type == "share_feedback":
        return """\
<p>Hello,</p>
<p>Thanks for reaching out to us. We’d love your feedback on your recent support experience with ticket #{{ doc.name }}.</p>
<a href="{{ url }}" class="btn btn-primary">Share Feedback</a>

<p>Thank you!<br>Support Team</p>"""

    if type == "acknowledgement":
        return """\
<p>Hi,</p>
<br />
<p>Thank you for reaching out to us. We've received your request and created a support ticket.</p>
<p>
    <strong>Ticket ID:</strong> {{ doc.name }}<br />
    <strong>Subject:</strong> {{ doc.subject }}<br />
</p>
<p>Our team is reviewing it and will get back to you shortly.</p>
<br />
<p>Best,<br />Support Team</p>
"""

    if type == "reply_to_agents":
        return """\
<div>
  <p>Hello,</p>
  <p>You have a new reply on the ticket <strong>#{{ doc.name }}</strong>.</p>
  <p><strong>Subject:</strong> {{ doc.subject }}</p>
  <p><strong>Raised By:</strong> {{ doc.raised_by }}</p>
  <p><strong>Priority:</strong> {{ doc.priority }}</p>

  <br />
  <p>
    You can view and respond to this ticket by
    <a href="{{ ticket_url }}">clicking here</a>.
  </p>
  <p>Regards,<br />Support Team</p>
</div>
"""

    if type == "reply_via_agent":
        return """\
<div>
  <h2><strong>Ticket #{{ doc.name }}</strong></h2>
  <h3>You have a new reply on this ticket</h3>
  <br />
  <div style="margin-bottom: 10px">
    <h3 style="margin-bottom: 20px">Message</h3>
    <div
      style="
        background: #f3f5f8;
        padding: 10px;
        border-radius: 4px;
        border: 1px solid #e5e9ee;
      "
    >
      {{ message }}
    </div>
  </div>
  <p>Please visit the customer portal to reply to this message</p>
  <a
    class="btn btn-primary"
    href="{{ ticket_url }}"
    rel="noopener noreferrer"
    target="_blank"
  >View in Portal</a>
  <br />
</div>
"""

    if type == "non_work_email_reply":
        return """\
<p>Hello,</p>
<p>Thank you for reaching out to us. We've received your email from <strong>{{ sender_email }}</strong>.</p>
<p>We notice you're contacting us from a personal email account. For security and verification purposes, we kindly request that you reach out to us using your official work/company email address.</p>
<p>This helps us:</p>
<ul>
  <li>Verify your identity and organization</li>
  <li>Ensure proper routing to the right support team</li>
  <li>Maintain our service level agreements</li>
</ul>
<p>Please resend your request from your work email address, and we'll be happy to assist you promptly.</p>
<br />
<p>Best regards,<br />Support Team</p>
"""
