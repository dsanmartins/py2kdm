ADAPTIVE_STEREOTYPE_DOMAIN = "Adaptive System Domain"

# Thesis-level stereotypes. Alternative is intentionally not included:
# alternatives are treated as internal Planner evidence, not as structural components.
STEREOTYPE_TYPES = {
    "Monitor": "structure:Component",
    "Analyzer": "structure:Component",
    "Planner": "structure:Component",
    "Executor": "structure:Component",
    "Knowledge": "structure:Component",
    "Reference Input": "structure:Component",
    "Measured Output": "structure:Component",
    "CL Manager": "structure:Component",
    "Control Loop": "structure:Component",
    "Sensor": "structure:Component",
    "Effector": "structure:Component",
    "Managing Subsystem": "structure:Subsystem",
    "Managed Subsystem": "structure:Subsystem",
}

COMPONENT_ROLE_TO_STEREOTYPE = {
    "Monitor": "Monitor",
    "Analyzer": "Analyzer",
    "Planner": "Planner",
    "Executor": "Executor",
    "Knowledge": "Knowledge",
    "ReferenceInput": "Reference Input",
    "Reference Input": "Reference Input",
    "MeasuredOutput": "Measured Output",
    "Measured Output": "Measured Output",
    "LoopManager": "CL Manager",
    "Loop Manager": "CL Manager",
    "CL Manager": "CL Manager",
    "Loop": "Control Loop",
    "Control Loop": "Control Loop",
    "Sensor": "Sensor",
    "Effector": "Effector",
}

SUBSYSTEM_TO_STEREOTYPE = {
    "Managing Subsystem": "Managing Subsystem",
    "Managed Subsystem": "Managed Subsystem",
    "managing_subsystem": "Managing Subsystem",
    "managed_subsystem": "Managed Subsystem",
    "subsystem:managing_subsystem": "Managing Subsystem",
    "subsystem:managed_subsystem": "Managed Subsystem",
}


def stereotype_for_component_role(role: str):
    stereotype_name = COMPONENT_ROLE_TO_STEREOTYPE.get(role)

    if stereotype_name is None:
        return None

    return {
        "stereotype_name": stereotype_name,
        "stereotype_domain": ADAPTIVE_STEREOTYPE_DOMAIN,
        "stereotype_type": STEREOTYPE_TYPES[stereotype_name],
    }


def stereotype_for_subsystem(subsystem: dict):
    candidates = [
        subsystem.get("stereotype_name"),
        subsystem.get("name"),
        subsystem.get("id"),
    ]

    for candidate in candidates:
        if candidate in SUBSYSTEM_TO_STEREOTYPE:
            stereotype_name = SUBSYSTEM_TO_STEREOTYPE[candidate]
            return {
                "stereotype_name": stereotype_name,
                "stereotype_domain": ADAPTIVE_STEREOTYPE_DOMAIN,
                "stereotype_type": STEREOTYPE_TYPES[stereotype_name],
            }

    text = f"{subsystem.get('id', '')} {subsystem.get('name', '')}".lower()

    if "managing" in text:
        stereotype_name = "Managing Subsystem"
    elif "managed" in text:
        stereotype_name = "Managed Subsystem"
    else:
        return None

    return {
        "stereotype_name": stereotype_name,
        "stereotype_domain": ADAPTIVE_STEREOTYPE_DOMAIN,
        "stereotype_type": STEREOTYPE_TYPES[stereotype_name],
    }


def architecture_profile():
    return {
        "name": ADAPTIVE_STEREOTYPE_DOMAIN,
        "type": "KDM ExtensionFamily",
        "stereotypes": [
            {"name": name, "type": type_}
            for name, type_ in STEREOTYPE_TYPES.items()
        ],
    }
