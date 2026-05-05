import operator
from functools import reduce

import frappe
from frappe import _
from frappe.query_builder import DocType
from frappe.query_builder.functions import Avg, Count, Function
from pypika import Case, Order

from helpdesk.utils import agent_only, is_frappe_version

HD_TICKET = "HD Ticket"

COUNT_NAME = (
    {"COUNT": "name", "as": "count"}
    if is_frappe_version("16", above=True)
    else "count(name) as count"
)

COUNT_DESC = "count desc"


@frappe.whitelist()
@agent_only
def get_dashboard_data(
    dashboard_type: str, filters: dict[str, any] = None
) -> list[dict[str, any]] | None:
    """
    Get dashboard data based on the type and date range.
    """
    filters = filters or {}

    user = frappe.session.user
    is_manager = "Agent Manager" in frappe.get_roles(user)

    if not is_manager and (filters.get("agent") != user or filters.get("team")):
        frappe.throw(
            _("You can only view your own dashboard data and cannot filter by team."),
            frappe.PermissionError,
        )
        return

    from_date = filters.get("from_date") if filters else None
    to_date = filters.get("to_date") if filters else None
    team = filters.get("team") if filters else None
    agent = filters.get("agent") if filters else None
    customer = filters.get("customer") if filters else None

    if agent == "@me":
        agent = frappe.session.user

    if not from_date:
        from_date = frappe.utils.add_days(frappe.utils.nowdate(), -30)
    if not to_date:
        to_date = frappe.utils.nowdate()

    _filters = frappe._dict(
        from_date=from_date,
        to_date=to_date,
        team=team,
        agent=agent,
        customer=customer,
    )

    dashboard = HelpdeskDashboard(_filters)

    if dashboard_type == "number_card":
        return dashboard.get_number_card_data()
    elif dashboard_type == "master":
        return get_master_dashboard_data(
            from_date, to_date, _filters.team, _filters.agent, _filters.customer
        )
    elif dashboard_type == "trend":
        return dashboard.get_trend_data()


class HelpdeskDashboard:
    def __init__(self, filters):
        self.filters = filters
        self.from_date = filters.get("from_date")
        self.to_date = filters.get("to_date")
        self.team = filters.get("team")
        self.agent = filters.get("agent")
        self.customer = filters.get("customer")

        self.ticket = DocType("HD Ticket")
        self.qb_conds = self._get_conditions()
        self.combined_cond = (
            reduce(operator.and_, self.qb_conds) if self.qb_conds else None
        )

        self.diff = frappe.utils.date_diff(self.to_date, self.from_date)
        if self.diff == 0:
            self.diff = 1
        self.prev_from_date = frappe.utils.add_days(self.from_date, -self.diff)
        self.to_date_next = frappe.utils.add_days(self.to_date, 1)

        self.open_statuses = frappe.get_all(
            "HD Ticket Status",
            filters={"category": "Open"},
            pluck="name",
        )
        self.resolved_statuses = frappe.get_all(
            "HD Ticket Status",
            filters={"category": "Resolved"},
            pluck="name",
        )

    def _get_conditions(self):
        # Exclude Outreach tickets from all dashboard metrics
        conds = [self.ticket.ticket_type != "Outreach"]
        if self.team:
            conds.append(self.ticket.agent_group == self.team)
        if self.agent:
            # Pass args to Function(...) directly. ParameterizedFunction is not callable.
            conds.append(
                Function(
                    "JSON_SEARCH", self.ticket._assign, "one", self.agent
                ).isnotnull()
            )
        if self.customer:
            conds.append(self.ticket.customer == self.customer)
        return conds

    def _get_case(self, start, end, value, func, extra_cond=None):
        cond = (self.ticket.creation >= start) & (self.ticket.creation < end)
        if extra_cond:
            cond = cond & extra_cond
        if self.combined_cond:
            cond = cond & self.combined_cond

        return func(Case().when(cond, value).else_(None))

    def get_metric_data(self, value, func, extra_cond=None):
        current_expr = self._get_case(
            self.from_date, self.to_date_next, value, func, extra_cond
        )
        prev_expr = self._get_case(
            self.prev_from_date, self.from_date, value, func, extra_cond
        )

        query = frappe.qb.from_(self.ticket).select(
            current_expr.as_("current"), prev_expr.as_("prev")
        )
        result = query.run(as_dict=True)
        return result[0].current or 0, result[0].prev or 0

    def get_number_card_data(self):
        return [
            self.get_ticket_count(),
            self.get_sla_fulfilled_count(),
            self.get_avg_first_response_time(),
            self.get_avg_resolution_time(),
            self.get_avg_feedback_score(),
        ]

    def get_ticket_count(self):
        current, prev = self.get_metric_data(self.ticket.name, Count)
        delta = ((current - prev) / prev * 100) if prev else 0

        return {
            "title": _("Tickets"),
            "value": current,
            "delta": delta,
            "deltaSuffix": "%",
            "negativeIsBetter": True,
            "tooltip": _("Total number of tickets created"),
        }

    def get_sla_fulfilled_count(self):
        extra_cond = self.ticket.agreement_status == "Fulfilled"
        current_fulfilled, prev_fulfilled = self.get_metric_data(
            self.ticket.name, Count, extra_cond
        )

        status_cond = (
            self.ticket.status.isin(self.resolved_statuses)
            if self.resolved_statuses
            else None
        )
        current_total, prev_total = self.get_metric_data(
            self.ticket.name, Count, status_cond
        )

        current_pct = (current_fulfilled / current_total * 100) if current_total else 0
        prev_pct = (prev_fulfilled / prev_total * 100) if prev_total else 0

        return {
            "title": _("% SLA Fulfilled"),
            "value": current_pct,
            "suffix": "%",
            "delta": current_pct - prev_pct,
            "deltaSuffix": "%",
            "tooltip": _("% of tickets created that were resolved within SLA"),
        }

    def get_avg_first_response_time(self):
        extra_cond = self.ticket.first_responded_on.isnotnull()
        current, prev = self.get_metric_data(
            self.ticket.first_response_time / 3600, Avg, extra_cond
        )

        return {
            "title": _("Avg. First Response"),
            "value": current,
            "suffix": " " + _("hrs"),
            "delta": current - prev,
            "deltaSuffix": " " + _("hrs"),
            "negativeIsBetter": True,
            "tooltip": _("Avg. time taken to first respond to a ticket"),
        }

    def get_avg_resolution_time(self):
        extra_cond = (
            self.ticket.status.isin(self.resolved_statuses)
            if self.resolved_statuses
            else None
        )
        value_expr = Function("CEIL", self.ticket.resolution_time / 86400)
        current, prev = self.get_metric_data(value_expr, Avg, extra_cond)

        return {
            "title": _("Avg. Resolution"),
            "value": current,
            "suffix": " " + _("days"),
            "delta": current - prev,
            "deltaSuffix": " " + _("days"),
            "negativeIsBetter": True,
            "tooltip": _("Avg. time taken to resolve a ticket"),
        }

    def get_avg_feedback_score(self):
        extra_cond = self.ticket.feedback_rating > 0
        current, prev = self.get_metric_data(
            self.ticket.feedback_rating, Avg, extra_cond
        )

        return {
            "title": _("Avg. Feedback Rating"),
            "value": current * 5,
            "suffix": "/5",
            "delta": (current - prev) * 5,
            "deltaSuffix": " " + _("stars"),
            "tooltip": _("Avg. feedback rating for the tickets resolved"),
        }

    def get_trend_data(self):
        return [
            self.get_ticket_trend_data(),
            self.get_feedback_trend_data(),
        ]

    def get_ticket_trend_data(self):
        open_status = "Open"
        closed_status = "Closed"
        sla_fulfilled_status = "SLA Fulfilled"
        emails_sent_key = "Emails Sent"
        emails_received_key = "Emails Received"

        base_cond = (self.ticket.creation > self.from_date) & (
            self.ticket.creation < self.to_date_next
        )
        if self.combined_cond:
            base_cond = base_cond & self.combined_cond

        query = (
            frappe.qb.from_(self.ticket)
            .select(
                Function("DATE", self.ticket.creation).as_("date"),
                Count(
                    Case()
                    .when(self.ticket.status.isin(self.open_statuses), self.ticket.name)
                    .else_(None)
                ).as_(open_status),
                Count(
                    Case()
                    .when(
                        self.ticket.status.isin(self.resolved_statuses),
                        self.ticket.name,
                    )
                    .else_(None)
                ).as_(closed_status),
                Count(
                    Case()
                    .when(self.ticket.agreement_status == "Fulfilled", self.ticket.name)
                    .else_(None)
                ).as_(sla_fulfilled_status),
            )
            .where(base_cond)
            .groupby(Function("DATE", self.ticket.creation))
            .orderby(Function("DATE", self.ticket.creation))
        )

        result = query.run(as_dict=True)

        # Fetch per-day email counts and merge into the result rows
        email_by_date = self._get_email_counts_by_date()
        result_by_date = {str(row["date"]): row for row in result}
        for date_str, email_row in email_by_date.items():
            if date_str in result_by_date:
                result_by_date[date_str][emails_sent_key] = email_row[emails_sent_key]
                result_by_date[date_str][emails_received_key] = email_row[emails_received_key]
            else:
                result_by_date[date_str] = {
                    "date": date_str,
                    open_status: 0,
                    closed_status: 0,
                    sla_fulfilled_status: 0,
                    emails_sent_key: email_row[emails_sent_key],
                    emails_received_key: email_row[emails_received_key],
                }
        # Ensure all ticket rows have the email keys (default 0 for days with no emails)
        for row in result:
            row.setdefault(emails_sent_key, 0)
            row.setdefault(emails_received_key, 0)

        # Re-sort by date after merge
        result = sorted(result_by_date.values(), key=lambda r: str(r["date"]))

        avg_tickets = self.get_avg_tickets_per_day()
        total_sent = sum(r.get(emails_sent_key, 0) or 0 for r in result)
        total_received = sum(r.get(emails_received_key, 0) or 0 for r in result)
        subtitle = _(
            "Avg tickets/day: {0} · Emails sent: {1} · Emails received: {2}"
        ).format(
            "{:.0f}".format(avg_tickets),
            total_sent,
            total_received,
        )

        return get_bar_chart_config(
            result,
            _("Ticket Trend"),
            subtitle,
            {"key": "date", "type": "time", "title": "Date", "timeGrain": "day"},
            _("Tickets"),
            [
                {"name": closed_status, "type": "bar"},
                {"name": open_status, "type": "bar"},
                {
                    "name": sla_fulfilled_status,
                    "type": "line",
                    "showDataPoints": True,
                    "axis": "y2",
                },
                {
                    "name": emails_sent_key,
                    "type": "line",
                    "showDataPoints": True,
                    "color": "#15CCEF",
                },
                {
                    "name": emails_received_key,
                    "type": "line",
                    "showDataPoints": True,
                    "color": "#F8814F",
                },
            ],
            stacked=True,
            y2Axis={"title": "% SLA", "yMin": 0, "yMax": 100},
        )

    def _get_email_counts_by_date(self) -> dict[str, dict]:
        """
        Returns a dict keyed by date string with Emails Sent and Emails Received counts,
        scoped to Communications linked to HD Tickets within the current filter window.
        """
        comm = DocType("Communication")

        base_cond = (
            (comm.communication_medium == "Email")
            & (comm.reference_doctype == "HD Ticket")
            & (comm.creation >= self.from_date)
            & (comm.creation < self.to_date_next)
        )

        # Apply team/agent/customer filters by joining to HD Ticket
        if self.combined_cond:
            ticket = self.ticket
            query = (
                frappe.qb.from_(comm)
                .join(ticket)
                .on(ticket.name == comm.reference_name)
                .select(
                    Function("DATE", comm.creation).as_("date"),
                    Count(
                        Case()
                        .when(comm.sent_or_received == "Sent", comm.name)
                        .else_(None)
                    ).as_("Emails Sent"),
                    Count(
                        Case()
                        .when(comm.sent_or_received == "Received", comm.name)
                        .else_(None)
                    ).as_("Emails Received"),
                )
                .where(base_cond & self.combined_cond)
                .groupby(Function("DATE", comm.creation))
                .orderby(Function("DATE", comm.creation))
            )
        else:
            query = (
                frappe.qb.from_(comm)
                .select(
                    Function("DATE", comm.creation).as_("date"),
                    Count(
                        Case()
                        .when(comm.sent_or_received == "Sent", comm.name)
                        .else_(None)
                    ).as_("Emails Sent"),
                    Count(
                        Case()
                        .when(comm.sent_or_received == "Received", comm.name)
                        .else_(None)
                    ).as_("Emails Received"),
                )
                .where(base_cond)
                .groupby(Function("DATE", comm.creation))
                .orderby(Function("DATE", comm.creation))
            )

        rows = query.run(as_dict=True) or []
        return {str(row["date"]): row for row in rows}

    def get_feedback_trend_data(self):
        rating = "Rating"
        rated_tickets = "Rated Tickets"

        base_cond = (self.ticket.creation > self.from_date) & (
            self.ticket.creation < self.to_date_next
        )
        if self.combined_cond:
            base_cond = base_cond & self.combined_cond

        query = (
            frappe.qb.from_(self.ticket)
            .select(
                Function("DATE", self.ticket.creation).as_("date"),
                (
                    Avg(
                        Case()
                        .when(
                            self.ticket.feedback_rating > 0, self.ticket.feedback_rating
                        )
                        .else_(None)
                    )
                    * 5
                ).as_(rating),
                Count(
                    Case()
                    .when(self.ticket.feedback_rating > 0, self.ticket.name)
                    .else_(None)
                ).as_(rated_tickets),
            )
            .where(base_cond)
            .groupby(Function("DATE", self.ticket.creation))
            .orderby(Function("DATE", self.ticket.creation))
        )

        result = query.run(as_dict=True)

        # Avg rating query
        avg_query = (
            frappe.qb.from_(self.ticket)
            .select((Avg(self.ticket.feedback_rating) * 5).as_("avg_rating"))
            .where(
                (self.ticket.creation.between(self.from_date, self.to_date_next))
                & (self.ticket.feedback_rating > 0)
            )
        )
        if self.combined_cond:
            avg_query = avg_query.where(self.combined_cond)

        avg_rating_result = avg_query.run(pluck=True)
        avg_rating = (
            avg_rating_result[0] if avg_rating_result and avg_rating_result[0] else 0
        )

        subtitle = _("Average feedback rating per day is around {0} stars").format(
            "{:.1f}".format(avg_rating)
        )

        return get_bar_chart_config(
            result,
            _("Feedback Trend"),
            subtitle,
            {"key": "date", "type": "time", "title": "Date", "timeGrain": "day"},
            _("Rated Tickets"),
            [
                {"name": rated_tickets, "type": "bar"},
                {
                    "name": rating,
                    "type": "line",
                    "showDataPoints": True,
                    "axis": "y2",
                    "color": "#48BB74",
                },
            ],
            y2Axis={"title": _("Rating"), "yMin": 0, "yMax": 5},
        )

    def get_avg_tickets_per_day(self):
        base_cond = (self.ticket.creation > self.from_date) & (
            self.ticket.creation < self.to_date_next
        )
        if self.combined_cond:
            base_cond = base_cond & self.combined_cond

        query = (
            frappe.qb.from_(self.ticket)
            .select(
                Count(self.ticket.name).as_("total_tickets"),
                Function("DATEDIFF", self.to_date_next, self.from_date).as_("days"),
            )
            .where(base_cond)
        )

        result = query.run(as_dict=True)
        total_tickets = result[0].total_tickets or 0
        days = result[0].days or 1
        return total_tickets / days


def get_master_dashboard_data(
    from_date: str,
    to_date: str,
    team: str = None,
    agent: str = None,
    customer: str = None,
) -> list[dict[str, any]]:
    filters = {
        "creation": ["between", [from_date, to_date]],
    }
    # Exclude Outreach tickets from all master dashboard metrics
    filters["ticket_type"] = ["!=", "Outreach"]
    if team:
        filters["agent_group"] = team
    if agent:
        filters["_assign"] = ["like", f"%{agent}%"]
    if customer:
        filters["customer"] = customer
    team_data = get_team_chart_data(from_date, to_date, filters)
    ticket_type_data = get_ticket_type_chart_data(from_date, to_date, filters)
    ticket_priority_data = get_ticket_priority_chart_data(from_date, to_date, filters)
    ticket_channel_data = get_ticket_channel_chart_data(from_date, to_date, filters)
    ticket_customer_data = get_ticket_customer_chart_data(from_date, to_date, filters)
    ticket_tag_data = get_ticket_tag_chart_data(from_date, to_date, filters)

    return [
        ticket_customer_data,
        ticket_tag_data,
        team_data,
        ticket_type_data,
        ticket_priority_data,
        ticket_channel_data,
    ]


# ---------------------------------------------------------------------------
# Chart config helpers
# ---------------------------------------------------------------------------

# ECharts colorBy:'data' makes each bar in a single-series chart get its own
# color from the palette, and the legend shows one entry per data point.
# colorBy is injected via the series-level echartOptions (merged per-series),
# while the legend override is injected via the top-level echartOptions.
_COLOR_BY_DATA_SERIES_ECHART = {"colorBy": "data"}
_LEGEND_SHOW_ECHART = {
    "legend": {
        "show": True,
        "type": "scroll",
        "bottom": 10,
        "orient": "horizontal",
        "itemGap": 12,
        "padding": [0, 25],
    },
}


def get_ticket_tag_chart_data(
    from_date: str, to_date: str, filters: dict[str, any] | None = None
) -> dict[str, any]:
    """
    Get ticket tag chart data for the dashboard using Tag Link as a through table.
    """
    filters = filters or {}

    ticket = DocType(HD_TICKET)
    tag_link = DocType("Tag Link")

    # Mirror the inclusive upper-bound behavior used elsewhere by extending to_date by one day
    to_date_next = frappe.utils.add_days(to_date, 1)

    conds = [
        tag_link.document_type == HD_TICKET,
        tag_link.document_name == ticket.name,
        ticket.creation >= from_date,
        ticket.creation < to_date_next,
        # Exclude Outreach tickets from tag-based metrics
        ticket.ticket_type != "Outreach",
    ]

    team = filters.get("agent_group")
    if team:
        conds.append(ticket.agent_group == team)

    assign_filter = filters.get("_assign")
    if (
        isinstance(assign_filter, (list, tuple))
        and len(assign_filter) == 2
        and isinstance(assign_filter[0], str)
        and assign_filter[0].lower() == "like"
    ):
        assign_like = assign_filter[1]
        conds.append(ticket._assign.like(assign_like))

    customer = filters.get("customer")
    if customer:
        conds.append(ticket.customer == customer)

    combined_cond = reduce(operator.and_, conds)

    query = (
        frappe.qb.from_(tag_link)
        .join(ticket)
        .on(
            (tag_link.document_type == HD_TICKET)
            & (tag_link.document_name == ticket.name)
        )
        .select(tag_link.tag.as_("tag"), Count(ticket.name).as_("count"))
        .where(combined_cond)
        .groupby(tag_link.tag)
        .orderby(Count(ticket.name), order=Order.desc)
        .limit(10)
    )

    result = query.run(as_dict=True) or []

    # Fetch the "Others" remainder count (tags beyond top 10)
    others_query = (
        frappe.qb.from_(tag_link)
        .join(ticket)
        .on(
            (tag_link.document_type == HD_TICKET)
            & (tag_link.document_name == ticket.name)
        )
        .select(Count(ticket.name).as_("count"))
        .where(combined_cond)
    )
    total_result = others_query.run(as_dict=True)
    total_count = total_result[0].count if total_result else 0
    top10_count = sum(r.count for r in result)
    others_count = total_count - top10_count
    if others_count > 0:
        result.append({"tag": _("Others"), "count": others_count})

    title = _("Tickets by Tag")

    if not result:
        # Return an empty but valid config so the UI can render gracefully
        return get_pie_chart_config(
            [],
            title,
            _("Percentage of Total Tickets by Tag"),
            "tag",
            "count",
        )

    if len(result) < 7:
        return get_pie_chart_config(
            result,
            title,
            _("Percentage of Total Tickets by Tag"),
            "tag",
            "count",
        )
    else:
        return get_horizontal_bar_chart_config(
            result,
            title,
            _("Top tags by ticket volume"),
            "tag",
            "count",
            _("Tag"),
        )


def get_team_chart_data(
    from_date: str, to_date: str, filters: dict[str, any] = None
) -> dict[str, any]:
    """
    Get team chart data for the dashboard.
    """
    result = frappe.get_all(
        HD_TICKET,
        fields=["agent_group as team", COUNT_NAME],
        filters=filters,
        group_by="agent_group",
        order_by=COUNT_DESC,
        limit_page_length=10,
    )
    for r in result:
        if not r.team:
            r.team = _("No Team")

    # Aggregate remaining teams beyond top 10 into "Others"
    total_result = frappe.get_all(
        HD_TICKET,
        fields=[COUNT_NAME],
        filters=filters,
    )
    total_count = total_result[0].count if total_result else 0
    top10_count = sum(r.count for r in result)
    others_count = total_count - top10_count
    if others_count > 0:
        result.append({"team": _("Others"), "count": others_count})

    if len(result) < 7:
        return get_pie_chart_config(
            result,
            _("Tickets by Team"),
            _("Percentage of Total Tickets by Team"),
            "team",
            "count",
        )
    else:
        return get_horizontal_bar_chart_config(
            result,
            _("Tickets by Team"),
            _("Top teams by ticket volume"),
            "team",
            "count",
            _("Team"),
        )


def get_ticket_type_chart_data(
    from_date: str, to_date: str, filters: dict[str, any] = None
) -> dict[str, any]:
    """
    Get ticket type chart data for the dashboard.
    """
    result = frappe.get_all(
        HD_TICKET,
        fields=["ticket_type as type", COUNT_NAME],
        filters=filters,
        group_by="ticket_type",
        order_by=COUNT_DESC,
    )
    # based on length show different chart, if len greater than 5 then show pie chart else bar chart
    if len(result) < 7:
        return get_pie_chart_config(
            result,
            _("Tickets by Type"),
            _("Percentage of Total Tickets by Type"),
            "type",
            "count",
        )
    else:
        return get_bar_chart_config(
            result,
            _("Tickets by Type"),
            _("Total Tickets by Type"),
            {"key": "type", "type": "category", "title": "Type", "timeGrain": "day"},
            "Tickets",
            [{"name": "count", "type": "bar"}],
            color_by_category=True,
        )


def get_ticket_priority_chart_data(
    from_date: str, to_date: str, filters: dict[str, any] = None
) -> dict[str, any]:
    """
    Get ticket priority chart data for the dashboard.
    """
    result = frappe.get_all(
        HD_TICKET,
        fields=["priority as priority", COUNT_NAME],
        filters=filters,
        group_by="priority",
        order_by=COUNT_DESC,
    )
    # based on length show different chart, if len greater than 5 then show pie chart else bar chart
    if len(result) < 7:
        return get_pie_chart_config(
            result,
            _("Tickets by Priority"),
            _("Percentage of Total Tickets by Priority"),
            "priority",
            "count",
        )
    else:
        return get_bar_chart_config(
            result,
            _("Tickets by Priority"),
            _("Total Tickets by Priority"),
            {
                "key": "priority",
                "type": "category",
                "title": "Priority",
                "timeGrain": "day",
            },
            "Tickets",
            [{"name": "count", "type": "bar"}],
            color_by_category=True,
        )


def get_ticket_channel_chart_data(
    from_date: str, to_date: str, filters: dict[str, any] = None
) -> dict[str, any]:
    """
    Get ticket channel chart data for the dashboard.
    """
    result = frappe.get_all(
        HD_TICKET,
        fields=["via_customer_portal as channel ", COUNT_NAME],
        filters=filters,
        group_by="via_customer_portal",
        order_by="via_customer_portal desc",
    )

    for row in result:
        row.channel = "Portal" if row.channel == 1 else "Email"

    return get_pie_chart_config(
        result,
        _("Tickets by Channel"),
        _("Percentage of Total Tickets by Channel"),
        "channel",
        "count",
    )


def get_ticket_customer_chart_data(
    from_date: str, to_date: str, filters: dict[str, any] = None
) -> dict[str, any]:
    """
    Get ticket customer chart data for the dashboard.
    """
    result = frappe.get_all(
        HD_TICKET,
        fields=["customer as customer", COUNT_NAME],
        filters=filters,
        group_by="customer",
        order_by=COUNT_DESC,
        limit_page_length=10,
    )

    for r in result:
        if not r.customer:
            r.customer = _("No Customer")

    # Aggregate remaining customers beyond top 10 into "Others"
    total_result = frappe.get_all(
        HD_TICKET,
        fields=[COUNT_NAME],
        filters=filters,
    )
    total_count = total_result[0].count if total_result else 0
    top10_count = sum(r.count for r in result)
    others_count = total_count - top10_count
    if others_count > 0:
        result.append({"customer": _("Others"), "count": others_count})

    if len(result) < 7:
        return get_pie_chart_config(
            result,
            _("Tickets by Customer"),
            _("Percentage of Total Tickets by Customer"),
            "customer",
            "count",
        )
    else:
        return get_horizontal_bar_chart_config(
            result,
            _("Tickets by Customer"),
            _("Top customers by ticket volume"),
            "customer",
            "count",
            _("Customer"),
        )


def get_pie_chart_config(
    data: list[dict[str, any]],
    title: str,
    subtitle: str,
    category_column: str,
    value_column: str,
) -> dict[str, any]:
    return {
        "type": "pie",
        "data": data,
        "title": title,
        "subtitle": subtitle,
        "categoryColumn": category_column,
        "valueColumn": value_column,
    }


def get_bar_chart_config(
    data: list[dict[str, any]],
    title: str,
    subtitle: str,
    x_axis_config: dict[str, any],
    y_axis_title: str,
    series: list,
    color_by_category: bool = False,
    **kwargs: dict[str, any],
) -> dict[str, any]:
    if color_by_category:
        # Inject colorBy:'data' into each bar series via per-series echartOptions
        # so mergeDeep doesn't overwrite the built series array.
        series = [
            dict(s, echartOptions=_COLOR_BY_DATA_SERIES_ECHART)
            if s.get("type") == "bar"
            else s
            for s in series
        ]
    config = {
        "type": "axis",
        "data": data,
        "title": title,
        "subtitle": subtitle,
        "xAxis": x_axis_config,
        "yAxis": {"title": y_axis_title},
        "series": series,
        **kwargs,
    }
    if color_by_category:
        config["echartOptions"] = _LEGEND_SHOW_ECHART
    return config


def get_horizontal_bar_chart_config(
    data: list[dict[str, any]],
    title: str,
    subtitle: str,
    category_key: str,
    value_key: str,
    category_title: str,
) -> dict[str, any]:
    """
    Returns a horizontal bar chart config (swapXY=True) with one color per bar
    and a scrollable legend, suitable for long category names (Customer, Team, Tag).
    The category field is mapped to xAxis.key so frappe-ui's swapXY logic reads
    the category from the correct column.
    colorBy:'data' is injected via per-series echartOptions to avoid overwriting
    the built series array during mergeDeep.
    """
    return {
        "type": "axis",
        "data": data,
        "title": title,
        "subtitle": subtitle,
        "xAxis": {
            "key": category_key,
            "type": "category",
            "title": category_title,
        },
        "yAxis": {"title": _("Tickets")},
        "swapXY": True,
        "series": [
            {
                "name": value_key,
                "type": "bar",
                "echartOptions": _COLOR_BY_DATA_SERIES_ECHART,
            }
        ],
        "echartOptions": _LEGEND_SHOW_ECHART,
    }
