from collections import defaultdict

from app.schemas.analysis import RELATIONSHIP_TYPES


TRACEABILITY_SEQUENCE = (
    "business_objective",
    "capability",
    "requirement",
    "user_story",
    "acceptance_criterion",
    "uat_scenario",
)

STAKEHOLDER_RELATIONSHIPS = {
    "sponsors": "sponsor_or_owner",
    "owns": "sponsor_or_owner",
    "approves": "approver",
    "acts_as_sme_for": "subject_matter_expert",
    "executes": "user_persona",
    "consulted_on": "consulted",
    "informed_of": "informed",
}

# Add mapping for column names
COLUMN_MAPPING = {
    "acceptance_criterion": "acceptance_criteria",
}


def build_traceability_matrix(analysis: dict) -> list[dict]:
    relationships = [
        relationship
        for relationship in analysis.get("entity_relationships") or []
        if relationship.get("relationship_type") in RELATIONSHIP_TYPES
        and relationship.get("source_type") in TRACEABILITY_SEQUENCE
        and relationship.get("target_type") in TRACEABILITY_SEQUENCE
    ]
    stakeholder_links = [
        relationship
        for relationship in analysis.get("entity_relationships") or []
        if relationship.get("source_type") == "stakeholder"
        and relationship.get("relationship_type") in STAKEHOLDER_RELATIONSHIPS
    ]
    names = _entity_names(analysis)
    outgoing = defaultdict(list)
    incoming = set()
    stakeholder_by_target = defaultdict(list)

    for relationship in relationships:
        outgoing[relationship["source_id"]].append(relationship)
        incoming.add(relationship["target_id"])
    for link in stakeholder_links:
        stakeholder_by_target[link["target_id"]].append(link)

    roots = [
        relationship["source_id"]
        for relationship in relationships
        if relationship["source_id"] not in incoming
    ]
    rows = []

    def walk(entity_id: str, row: dict, visited: set[str]):
        links = outgoing.get(entity_id) or []
        if not links:
            rows.append(_attach_stakeholders(row, stakeholder_links, names))
            return
        for relationship in links:
            target_id = relationship["target_id"]
            if target_id in visited:
                continue
            next_row = dict(row)
            target_type = relationship["target_type"]
            column = COLUMN_MAPPING.get(target_type, target_type)
            next_row[column] = names.get(target_id, target_id)
            walk(target_id, next_row, {*visited, target_id})

    for root in dict.fromkeys(roots):
        root_type = next(
            (relationship["source_type"]
             for relationship in relationships
             if relationship["source_id"] == root),
            "unknown"
        )
        row = {column: "" for column in TRACEABILITY_SEQUENCE}
        row["acceptance_criteria"] = ""
        row.pop("acceptance_criterion", None)
        row[root_type] = names.get(root, root)
        walk(root, row, {root})

    return _unique_rows(rows)


def _attach_stakeholders(row: dict, stakeholder_links: list[dict], names: dict[str, str]) -> dict:
    result = {
        **row,
        "sponsor_or_owner": "",
        "approver": "",
        "subject_matter_expert": "",
        "user_persona": "",
        "consulted": "",
        "informed": "",
    }
    row_entities = set(row.values())
    role_values = defaultdict(list)
    for relationship in stakeholder_links:
        if names.get(relationship["target_id"], relationship["target_id"]) not in row_entities:
            continue
        column = STAKEHOLDER_RELATIONSHIPS[relationship["relationship_type"]]
        role_values[column].append(names.get(relationship["source_id"], relationship["source_id"]))
    for column, values in role_values.items():
        result[column] = ", ".join(dict.fromkeys(values))
    return result


def _entity_names(analysis: dict) -> dict[str, str]:
    names = {}

    def visit(value):
        if isinstance(value, dict):
            if value.get("id"):
                names[str(value["id"])] = str(
                    value.get("name")
                    or value.get("description")
                    or value.get("story")
                    or value.get("scenario")
                    or ", ".join(value.get("criteria") or [])
                    or value["id"]
                )
            for key, child in value.items():
                if key != "entity_relationships":
                    visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(analysis)
    return names


def _unique_rows(rows: list[dict]) -> list[dict]:
    unique = []
    seen = set()
    for row in rows:
        key = tuple(sorted(row.items()))
        if key not in seen:
            seen.add(key)
            unique.append(row)
    return unique
