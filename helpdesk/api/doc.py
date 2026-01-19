import frappe
from frappe import _
from frappe.desk.form.assign_to import set_status
from frappe.model import no_value_fields
from frappe.model.document import get_controller
from frappe.utils.caching import redis_cache
from pypika import Criterion

from helpdesk.api.dashboard import COUNT_NAME
from helpdesk.utils import (
    call_log_default_columns,
    check_permissions,
    contact_default_columns,
    parse_call_logs,
)


def build_complex_criterion(doctype, conditions, table=None):
    """
    Build a pypika Criterion from complex nested filter conditions.
    
    Format: 
    - Simple condition: ["fieldname", "operator", "value"]
    - Conjunction: "and" or "or"
    - Nested group: [condition1, "and"/"or", condition2, ...]
    
    Example: [["status", "==", "Open"], "and", [["priority", "==", "High"], "or", ["priority", "==", "Critical"]]]
    """
    if table is None:
        table = frappe.qb.DocType(doctype)
    
    if not conditions or len(conditions) == 0:
        return None
    
    # Check if this is a simple condition [field, operator, value]
    if _is_simple_condition(conditions):
        return _build_single_criterion(table, conditions[0], conditions[1], conditions[2])
    
    # Build compound criterion from list of conditions and conjunctions
    criteria = []
    conjunctions = []
    
    for item in conditions:
        if isinstance(item, str) and item.lower() in ("and", "or"):
            conjunctions.append(item.lower())
        elif isinstance(item, list):
            criterion = build_complex_criterion(doctype, item, table)
            if criterion is not None:
                criteria.append(criterion)
    
    if not criteria:
        return None
    
    if len(criteria) == 1:
        return criteria[0]
    
    # Combine criteria with conjunctions
    # Default to "and" if no conjunctions specified
    if not conjunctions:
        conjunctions = ["and"] * (len(criteria) - 1)
    
    result = criteria[0]
    for i, criterion in enumerate(criteria[1:]):
        conj = conjunctions[i] if i < len(conjunctions) else "and"
        if conj == "or":
            result = result | criterion
        else:
            result = result & criterion
    
    return result


def _is_simple_condition(conditions):
    """Check if conditions is a simple [field, operator, value] tuple."""
    return (
        len(conditions) == 3
        and isinstance(conditions[0], str)
        and isinstance(conditions[1], str)
        and conditions[0].lower() not in ("and", "or")
        and conditions[1].lower() not in ("and", "or")
    )


def _build_single_criterion(table, field, operator, value):
    """Build a single criterion from field, operator, and value."""
    column = getattr(table, field, None)
    if column is None:
        return None
    
    op = operator.lower() if isinstance(operator, str) else operator
    
    # Map operators to pypika operations
    if op in ("=", "==", "equals"):
        return column == value
    elif op in ("!=", "not equals"):
        return column != value
    elif op == ">":
        return column > value
    elif op == ">=":
        return column >= value
    elif op == "<":
        return column < value
    elif op == "<=":
        return column <= value
    elif op in ("like", "LIKE"):
        search_val = value if "%" in str(value) else f"%{value}%"
        return column.like(search_val)
    elif op in ("not like", "NOT LIKE"):
        search_val = value if "%" in str(value) else f"%{value}%"
        return column.not_like(search_val)
    elif op == "in":
        if isinstance(value, str):
            value = [v.strip() for v in value.split(",")]
        return column.isin(value)
    elif op in ("not in", "not_in"):
        if isinstance(value, str):
            value = [v.strip() for v in value.split(",")]
        return column.notin(value)
    elif op == "is":
        if str(value).lower() == "set":
            return column.isnotnull() & (column != "")
        else:  # "not set"
            return column.isnull() | (column == "")
    elif op == "between":
        if isinstance(value, str) and "," in value:
            parts = value.split(",")
            return (column >= parts[0].strip()) & (column <= parts[1].strip())
        elif isinstance(value, (list, tuple)) and len(value) == 2:
            return (column >= value[0]) & (column <= value[1])
    
    # Default to equals
    return column == value


def get_list_with_complex_filters(doctype, fields, conditions, order_by, page_length):
    """
    Get list data using complex nested filters with frappe.qb.
    """
    table = frappe.qb.DocType(doctype)
    
    # Build base query with all fields
    query = frappe.qb.from_(table)
    
    for field in fields:
        if "." in str(field):
            # Handle linked field like "contact.email_id" - just get the base field
            parts = str(field).split(".")
            col = getattr(table, parts[0], None)
            if col:
                query = query.select(col)
        else:
            col = getattr(table, field, None)
            if col:
                query = query.select(col)
    
    # Add complex filter criterion
    criterion = build_complex_criterion(doctype, conditions, table)
    if criterion is not None:
        query = query.where(criterion)
    
    # Add ordering
    if order_by:
        parts = order_by.split()
        field_name = parts[0]
        direction = parts[1].lower() if len(parts) > 1 else "asc"
        order_field = getattr(table, field_name, None)
        if order_field:
            if direction == "desc":
                query = query.orderby(order_field, order=frappe.qb.desc)
            else:
                query = query.orderby(order_field)
    
    # Add limit
    query = query.limit(page_length)
    
    return query.run(as_dict=True)


def get_count_with_complex_filters(doctype, conditions):
    """
    Get count using complex nested filters with frappe.qb.
    """
    table = frappe.qb.DocType(doctype)
    query = frappe.qb.from_(table).select(frappe.qb.functions.Count("*").as_("count"))
    
    criterion = build_complex_criterion(doctype, conditions, table)
    if criterion is not None:
        query = query.where(criterion)
    
    result = query.run()
    return result[0][0] if result else 0


def parse_filters_for_complex(filters):
    """
    Check if filters contain complex conditions and extract them.
    
    Returns: (simple_filters, complex_conditions)
    - simple_filters: dict of simple AND filters for frappe.get_list
    - complex_conditions: nested array for complex query builder (or None)
    """
    if not isinstance(filters, dict):
        return filters, None
    
    complex_conditions = None
    simple_filters = {}
    
    for key, value in filters.items():
        if key == "_conditions":
            # Complex nested conditions from CFConditions
            complex_conditions = value if isinstance(value, list) else None
        elif key.startswith("_"):
            # Skip other internal keys
            continue
        else:
            # Regular filter
            simple_filters[key] = value
    
    return simple_filters, complex_conditions


@frappe.whitelist()
def get_list_data(
    doctype: str,
    # flake8: noqa
    filters={},
    default_filters={},
    order_by: str = "modified desc",
    page_length=20,
    columns=None,
    rows=None,
    show_customer_portal_fields=False,
    view=None,
    is_default=False,
):
    is_custom = False

    rows = frappe.parse_json(rows or "[]")
    columns = frappe.parse_json(columns or "[]")
    filters = frappe.parse_json(filters or "[]")

    view_type = view.get("view_type") if view else None
    view_name = view.get("name") if view else None

    group_by_field = view.get("group_by_field") if view else None
    label_doc = view.get("label_doc") if view else None
    label_field = view.get("label_field") if view else None

    handle_at_me_support(filters)

    def pop_participant_filter(current_filters):
        if isinstance(current_filters, dict):
            return current_filters.pop("participant_email", None)

        if isinstance(current_filters, list):
            for idx, item in enumerate(list(current_filters)):
                if isinstance(item, dict) and item.get("name") == "participant_email":
                    current_filters.pop(idx)
                    return item.get("value")

                if isinstance(item, (list, tuple)) and len(item) >= 1:
                    fieldname = item[0]
                    if fieldname == "participant_email":
                        value = item[-1] if len(item) >= 2 else None
                        current_filters.pop(idx)
                        return value

        return None

    def normalize_participant_value(raw_value):
        if isinstance(raw_value, (list, tuple)) and raw_value:
            raw_value = raw_value[-1]

        raw_value = (raw_value or "").strip()
        if not raw_value:
            return None

        if raw_value.startswith("%") and raw_value.endswith("%"):
            return raw_value

        return f"%{raw_value}%"

    def add_ticket_name_filter(current_filters, ticket_names):
        if isinstance(current_filters, dict):
            current_filters["name"] = ["in", ticket_names]
            return current_filters

        if isinstance(current_filters, list):
            current_filters.append(["name", "in", ticket_names])
            return current_filters

        return {"name": ["in", ticket_names]}

    _list = get_controller(doctype)
    default_rows = []
    if hasattr(_list, "default_list_data"):
        default_rows = _list.default_list_data().get("rows")

    if columns or rows:
        is_default = False
        is_custom = True
        columns = frappe.parse_json(columns)
        rows = frappe.parse_json(rows)

    if not columns:
        columns = [
            {"label": "Name", "type": "Data", "key": "name", "width": "16rem"},
            {
                "label": "Last Modified",
                "type": "Datetime",
                "key": "modified",
                "width": "8rem",
            },
        ]

    if not rows:
        rows = ["name"]

    # flake8: noqa
    if is_default:
        default_view = default_view_exists(doctype)
        if not default_view:
            if doctype == "Contact":
                columns = contact_default_columns
            elif doctype == "TP Call Log":
                columns = call_log_default_columns
            elif hasattr(_list, "default_list_data"):
                columns = (
                    _list.default_list_data(show_customer_portal_fields).get("columns")
                    if doctype == "HD Ticket"
                    else _list.default_list_data().get("columns")
                )
                rows = default_rows
        else:
            [columns, rows] = handle_default_view(
                doctype, _list, show_customer_portal_fields
            )
            if default_filters and not filters:
                filters.append(default_filters)

    if rows is None:
        rows = []

    # check if rows has all keys from columns if not add them
    for column in columns:
        if column.get("key") not in rows:
            rows.append(column.get("key"))

    if group_by_field and group_by_field not in rows:
        rows.append(group_by_field)

    skip_ticket_query = False
    if doctype == "HD Ticket":
        participant_filter_value = pop_participant_filter(filters)
        participant_pattern = normalize_participant_value(participant_filter_value)

        if participant_pattern:
            Communication = frappe.qb.DocType("Communication")
            participant_ticket_names = (
                frappe.qb.from_(Communication)
                .select(Communication.reference_name)
                .distinct()
                .where(Communication.reference_doctype == "HD Ticket")
                .where(Communication.reference_name.isnotnull())
                .where(
                    Criterion.any(
                        [
                            Communication.sender.like(participant_pattern),
                            Communication.recipients.like(participant_pattern),
                        ]
                    )
                )
                .run(pluck=Communication.reference_name)
            )

            if not participant_ticket_names:
                skip_ticket_query = True
            else:
                filters = add_ticket_name_filter(filters, participant_ticket_names)

    rows.append("name") if "name" not in rows else rows
    if skip_ticket_query:
        data = []
    else:
        # Check for complex nested conditions
        simple_filters, complex_conditions = parse_filters_for_complex(filters)
        
        if complex_conditions and len(complex_conditions) > 0:
            # Use frappe.qb for complex nested filters
            try:
                data = get_list_with_complex_filters(
                    doctype,
                    rows,
                    complex_conditions,
                    order_by,
                    page_length,
                ) or []
            except Exception as e:
                frappe.log_error(f"Complex filter error: {e}")
                # Fallback to simple query
                data = (
                    frappe.get_list(
                        doctype,
                        fields=rows,
                        filters=simple_filters,
                        order_by=order_by,
                        page_length=page_length,
                    )
                    or []
                )
        else:
            # Use standard frappe.get_list for simple filters
            data = (
                frappe.get_list(
                    doctype,
                    fields=rows,
                    filters=simple_filters,
                    order_by=order_by,
                    page_length=page_length,
                )
                or []
            )

    if doctype == "TP Call Log":
        data = parse_call_logs(data)

    fields = frappe.get_meta(doctype).fields
    fields = [field for field in fields if field.fieldtype not in no_value_fields]
    fields = [
        {
            "label": field.label,
            "type": field.fieldtype,
            "value": field.fieldname,
            "options": field.options,
        }
        for field in fields
        if field.label and field.fieldname
    ]

    std_fields = [
        {"label": "Name", "type": "Data", "value": "name"},
        {"label": "Created On", "type": "Datetime", "value": "creation"},
        {"label": "Last Modified", "type": "Datetime", "value": "modified"},
        {
            "label": "Modified By",
            "type": "Link",
            "value": "modified_by",
            "options": "User",
        },
        {"label": "Assigned To", "type": "Text", "value": "_assign"},
        {"label": "Owner", "type": "Link", "value": "owner", "options": "User"},
    ]

    for field in std_fields:
        if field.get("value") not in rows:
            rows.append(field.get("value"))
        if field not in fields:
            fields.append(field)

    if show_customer_portal_fields:
        fields = get_customer_portal_fields(doctype, fields)

    if group_by_field and view_type == "group_by":

        def get_options(fieldtype, options):
            if fieldtype == "Select":
                return [option for option in options.split("\n")]
            else:
                has_empty_values = any([not d.get(group_by_field) for d in data])
                options = list(set([d.get(group_by_field) for d in data]))
                options = [u for u in options if u]
                options = [category_name for category_name in options if category_name]
                options = [
                    {
                        "label": frappe.db.get_value(
                            label_doc if label_doc else doctype,
                            option,
                            label_field if label_field else group_by_field,
                        ),
                        "value": option,
                    }
                    for option in options
                    if option
                ]
                if has_empty_values:
                    options.append({"label": "", "value": ""})

                if order_by and group_by_field in order_by:
                    order_by_fields = order_by.split(",")
                    order_by_fields = [
                        (field.split(" ")[0], field.split(" ")[1])
                        for field in order_by_fields
                    ]
                    if (group_by_field, "asc") in order_by_fields:
                        options.sort(key=lambda x: x.get("label"))
                    elif (group_by_field, "desc") in order_by_fields:
                        options.sort(reverse=True, key=lambda x: x.get("label"))
                else:
                    options.sort(key=lambda x: x.get("label"))

                # general category at first position
                idx = [
                    idx for idx, o in enumerate(options) if o.get("label") == "General"
                ]
                if len(idx) == 0:
                    return options

                idx = idx[0]
                default_category = options[idx]
                options.pop(idx)
                options.insert(0, default_category)
                return options

        for field in fields:
            if field.get("value") == group_by_field:
                options = get_options(field.get("type"), field.get("options"))
                group_by_field = {
                    "label": field.get("label"),
                    "name": field.get("value"),
                    "type": field.get("type"),
                    "options": options,
                }

    # Calculate total count using same filters
    if complex_conditions and len(complex_conditions) > 0:
        try:
            total_count = get_count_with_complex_filters(doctype, complex_conditions)
        except Exception:
            total_count = len(data)
    else:
        total_count = frappe.get_list(
            doctype,
            fields=[COUNT_NAME],
            filters=simple_filters,
        )[0].get("count", 0)

    return {
        "data": data,
        "columns": columns,
        "rows": rows,
        "fields": fields if doctype == "HD Ticket" else [],
        "total_count": total_count,
        "row_count": len(data),
        "group_by_field": group_by_field,
        "view_type": view_type,
    }


@frappe.whitelist()
@redis_cache()
def get_filterable_fields(
    doctype: str, show_customer_portal_fields=False, ignore_team_restrictions=False
):
    check_permissions(doctype, None)
    QBDocField = frappe.qb.DocType("DocField")
    QBCustomField = frappe.qb.DocType("Custom Field")
    allowed_fieldtypes = [
        "Check",
        "Data",
        "Float",
        "Int",
        "Link",
        "Long Text",
        "Select",
        "Small Text",
        "Text Editor",
        "Text",
        "Rating",
        "Duration",
        "Date",
        "Datetime",
    ]

    visible_custom_fields = get_visible_custom_fields()
    customer_portal_fields = [
        "name",
        "subject",
        "status",
        "priority",
        "response_by",
        "resolution_by",
        "creation",
    ]

    from_doc_fields = (
        frappe.qb.from_(QBDocField)
        .select(
            QBDocField.fieldname,
            QBDocField.fieldtype,
            QBDocField.label,
            QBDocField.name,
            QBDocField.options,
        )
        .where(QBDocField.parent == doctype)
        .where(QBDocField.hidden == False)
        .where(Criterion.any([QBDocField.fieldtype == i for i in allowed_fieldtypes]))
    )

    from_custom_fields = (
        frappe.qb.from_(QBCustomField)
        .select(
            QBCustomField.fieldname,
            QBCustomField.fieldtype,
            QBCustomField.label,
            QBCustomField.name,
            QBCustomField.options,
        )
        .where(QBCustomField.dt == doctype)
        .where(QBCustomField.hidden == False)
        .where(
            Criterion.any([QBCustomField.fieldtype == i for i in allowed_fieldtypes])
        )
    )

    # for customer portal show only fields present in customer_portal_fields
    if show_customer_portal_fields:
        from_doc_fields = from_doc_fields.where(
            QBDocField.fieldname.isin(customer_portal_fields)
        )
        if len(visible_custom_fields) > 0:
            from_custom_fields = from_custom_fields.where(
                QBCustomField.fieldname.isin(visible_custom_fields)
            )
            from_custom_fields = from_custom_fields.run(as_dict=True)
        else:
            from_custom_fields = []

    if not show_customer_portal_fields:
        from_custom_fields = from_custom_fields.run(as_dict=True)

    from_doc_fields = from_doc_fields.run(as_dict=True)
    # from hd ticket template get children with fieldname and hidden_from_customer

    res = []
    res.extend(from_doc_fields)
    # TODO: Ritvik => till a better way we have for custom fields, just show custom fields

    res.extend(from_custom_fields)
    if not show_customer_portal_fields and doctype == "HD Ticket":
        res.append(
            {
                "fieldname": "_assign",
                "fieldtype": "Link",
                "label": "Assigned to",
                "name": "_assign",
                "options": "HD Agent",
            }
        )
        res.append(
            {
                "fieldname": "_user_tags",
                "fieldtype": "Data",
                "label": "Tags",
                "name": "_user_tags",
            }
        )

    if not ignore_team_restrictions:
        enable_restrictions = frappe.db.get_single_value(
            "HD Settings", "restrict_tickets_by_agent_group"
        )
        if enable_restrictions and doctype == "HD Ticket":
            res = [r for r in res if r.get("fieldname") != "agent_group"]

    standard_fields = [
        {"fieldname": "name", "fieldtype": "Link", "label": "ID", "options": doctype},
        {
            "fieldname": "owner",
            "fieldtype": "Link",
            "label": "Created By",
            "options": "User",
        },
        {
            "fieldname": "modified_by",
            "fieldtype": "Link",
            "label": "Last Updated By",
            "options": "User",
        },
        {"fieldname": "creation", "fieldtype": "Datetime", "label": "Created On"},
        {"fieldname": "modified", "fieldtype": "Datetime", "label": "Last Updated On"},
    ]
    for field in standard_fields:
        if field.get("fieldname") not in [r.get("fieldname") for r in res]:
            res.append(field)
    return res


@frappe.whitelist()
def sort_options(doctype: str, show_customer_portal_fields=False):
    fields = frappe.get_meta(doctype).fields
    fields = [field for field in fields if field.fieldtype not in no_value_fields]
    fields = [
        {
            "label": field.label,
            "value": field.fieldname,
        }
        for field in fields
        if field.label and field.fieldname
    ]

    if show_customer_portal_fields:
        fields = get_customer_portal_fields(doctype, fields)

    standard_fields = [
        {"label": "Name", "value": "name"},
        {"label": "Created On", "value": "creation"},
        {"label": "Last Modified", "value": "modified"},
        {"label": "Modified By", "value": "modified_by"},
        {"label": "Owner", "value": "owner"},
    ]

    fields.extend(standard_fields)

    return fields


@frappe.whitelist()
def get_quick_filters(doctype: str, show_customer_portal_fields=False):
    meta = frappe.get_meta(doctype)
    fields = [field for field in meta.fields if field.in_standard_filter]
    quick_filters = []
    name_filter = {"label": "ID", "name": "name", "type": "Data"}
    if doctype == "Contact":
        quick_filters.append(name_filter)
        return quick_filters
    elif doctype == "TP Call Log":
        quick_filters.append(name_filter)
        return quick_filters
    name_filter_doctypes = ["HD Agent", "HD Customer", "HD Ticket"]
    if doctype in name_filter_doctypes:
        quick_filters.append(name_filter)

    for field in fields:
        options = []
        if field.fieldtype == "Select":
            options = field.options.split("\n")
            options = [{"label": option, "value": option} for option in options]
            options.insert(0, {"label": "", "value": ""})

        if field.fieldtype == "Link":
            options = field.options

        quick_filters.append(
            {
                "label": _(field.label),
                "name": field.fieldname,
                "type": field.fieldtype,
                "options": options,
            }
        )

    if doctype == "HD Ticket":
        quick_filters.append(
            {
                "label": _("From/To Email"),
                "name": "participant_email",
                "type": "Data",
                "options": [],
            }
        )
    else:
        return quick_filters

    _list = get_controller(doctype)
    if hasattr(_list, "filter_standard_fields") and show_customer_portal_fields:
        # to filter out more fields from customer remember to update customer_not_allowed_fields in hd_ticket.py
        quick_filters = _list.filter_standard_fields(quick_filters)

    return quick_filters


def get_customer_portal_fields(doctype, fields):
    visible_custom_fields = get_visible_custom_fields()
    customer_portal_fields = [
        "name",
        "subject",
        "status",
        "priority",
        "response_by",
        "resolution_by",
        "creation",
        *visible_custom_fields,
    ]
    fields = [field for field in fields if field.get("value") in customer_portal_fields]
    return fields


def get_visible_custom_fields():
    return frappe.db.get_all(
        "HD Ticket Template Field",
        {"parent": "Default", "hide_from_customer": 0},
        pluck="fieldname",
    )


def default_view_exists(doctype):
    return frappe.db.exists(
        "HD View",
        {
            "is_default": 1,
            "user": frappe.session.user,
            "dt": doctype,
        },
    )


def handle_default_view(doctype, _list, show_customer_portal_fields):
    [columns, rows] = frappe.get_value(
        "HD View",
        {
            "is_default": 1,
            "user": frappe.session.user,
            "dt": doctype,
        },
        ["columns", "rows"],
    )
    columns = frappe.parse_json(columns)
    rows = frappe.parse_json(rows)

    if not columns:
        if doctype == "Contact":
            columns = contact_default_columns
            rows = ["name", "email_id", "creation"]
        elif doctype == "TP Call Log":
            columns = call_log_default_columns
            rows = ["name", "caller", "receiver", "creation"]
        else:
            columns = (
                _list.default_list_data(show_customer_portal_fields).get("columns")
                if doctype == "HD Ticket"
                else _list.default_list_data().get("columns")
            )
    if not rows:
        rows = _list.default_list_data().get("rows")

    return [columns, rows]


def handle_at_me_support(filters):
    # Converts @me in filters to current user
    for key in filters:
        value = filters[key]
        if isinstance(value, list):
            if "@me" in value:
                value[value.index("@me")] = frappe.session.user
            elif "%@me%" in value:
                index = [i for i, v in enumerate(value) if v == "%@me%"]
                for i in index:
                    value[i] = "%" + frappe.session.user + "%"
        elif value == "@me":
            filters[key] = frappe.session.user

    return filters


@frappe.whitelist()
def remove_assignments(doctype, name, assignees, ignore_permissions=False):
    assignees = frappe.parse_json(assignees)

    if not assignees:
        return

    for assign_to in assignees:
        set_status(
            doctype,
            name,
            todo=None,
            assign_to=assign_to,
            status="Cancelled",
            ignore_permissions=ignore_permissions,
        )
