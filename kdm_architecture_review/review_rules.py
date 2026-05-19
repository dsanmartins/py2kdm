from dataclasses import dataclass

OK = "ok"
WARNING = "warning"
FORBIDDEN = "forbidden"

@dataclass(frozen=True)
class ReviewRule:
    id: str
    level: str
    title: str
    description: str

ALLOWED_COMPONENT_ROLES = {
    "Monitor", "Analyzer", "Planner", "Executor", "Knowledge", "LoopManager",
    "ManagedElement", "Sensor", "Effector", "ReferenceInput", "Alternative",
}

ALLOWED_RELATIONSHIP_TYPES = {
    "mapek_flow", "uses_knowledge", "subscribes_to", "depends_on",
    "controls", "observes", "updates",
}

STANDARD_MAPEK_FLOW = {
    ("Monitor", "Analyzer"),
    ("Monitor", "Planner"),
    ("Analyzer", "Planner"),
    ("Planner", "Executor"),
}

RULES = {
    "ARV-OK-01": ReviewRule("ARV-OK-01", OK, "Accepted component", "A proposed component was accepted."),
    "ARV-OK-02": ReviewRule("ARV-OK-02", OK, "Rejected component", "A component was rejected and will not be materialized."),
    "ARV-OK-03": ReviewRule("ARV-OK-03", OK, "Valid role override", "A component role was changed to an allowed role."),
    "ARV-OK-04": ReviewRule("ARV-OK-04", OK, "Accepted relationship", "A relationship was accepted."),
    "ARV-W-01": ReviewRule("ARV-W-01", WARNING, "Partial control loop", "A control loop is missing one or more MAPE roles."),
    "ARV-W-02": ReviewRule("ARV-W-02", WARNING, "Component without implementation", "A materialized component has no implementation link."),
    "ARV-W-03": ReviewRule("ARV-W-03", WARNING, "Unresolved implementation", "An implementation reference could not be resolved."),
    "ARV-W-04": ReviewRule("ARV-W-04", WARNING, "Multiple roles by same code", "The same code element implements multiple architectural roles."),
    "ARV-W-05": ReviewRule("ARV-W-05", WARNING, "Unusual MAPE-K flow", "A mapek_flow relationship has a non-standard direction."),
    "ARV-W-06": ReviewRule("ARV-W-06", WARNING, "MAPE-K flow skips roles", "A mapek_flow relationship skips intermediate roles."),
    "ARV-W-07": ReviewRule("ARV-W-07", WARNING, "Technical relationship promoted", "A technical relationship was promoted to architectural."),
    "ARV-W-08": ReviewRule("ARV-W-08", WARNING, "Low-confidence component accepted", "A low-confidence component was accepted."),
    "ARV-W-09": ReviewRule("ARV-W-09", WARNING, "Repeated role in loop", "A loop has multiple components with the same MAPE-K role."),
    "ARV-W-10": ReviewRule("ARV-W-10", WARNING, "Shared Knowledge", "Multiple loops share the same Knowledge component."),
    "ARV-W-11": ReviewRule("ARV-W-11", WARNING, "Missing hierarchy level", "Multiple loops exist but one has no explicit level."),
    "ARV-W-12": ReviewRule("ARV-W-12", WARNING, "Mixed subsystem", "A subsystem contains managing and managed elements."),
    "ARV-F-01": ReviewRule("ARV-F-01", FORBIDDEN, "Invalid role", "A component role is not allowed."),
    "ARV-F-02": ReviewRule("ARV-F-02", FORBIDDEN, "Duplicate component id", "Materialized components have duplicate ids."),
    "ARV-F-03": ReviewRule("ARV-F-03", FORBIDDEN, "Missing relationship source", "A relationship source does not exist."),
    "ARV-F-04": ReviewRule("ARV-F-04", FORBIDDEN, "Missing relationship target", "A relationship target does not exist."),
    "ARV-F-05": ReviewRule("ARV-F-05", FORBIDDEN, "Relationship to non-materialized component", "A materialized relationship references a rejected component."),
    "ARV-F-06": ReviewRule("ARV-F-06", FORBIDDEN, "Loop references non-materialized component", "A materialized loop references a rejected component."),
    "ARV-F-07": ReviewRule("ARV-F-07", FORBIDDEN, "Invalid uses_knowledge target", "uses_knowledge must target Knowledge."),
    "ARV-F-08": ReviewRule("ARV-F-08", FORBIDDEN, "Invalid relationship type", "A relationship type is not supported."),
    "ARV-F-09": ReviewRule("ARV-F-09", FORBIDDEN, "Empty control loop", "A materialized control loop has no components."),
    "ARV-F-10": ReviewRule("ARV-F-10", FORBIDDEN, "Duplicate relationship", "Duplicate relationship with same source, target and type."),
}
