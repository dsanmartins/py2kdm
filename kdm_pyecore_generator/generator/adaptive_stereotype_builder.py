class AdaptiveStereotypeBuilder:
    """
    Builds the Adaptive System Domain as a KDM ExtensionFamily contained
    directly by the KDM Segment, outside the KDM models.

    This version supports both possible containment feature names:

        Segment.extensionFamily
        Segment.extension

    The example KDM XMI uses:

        <extensionFamily name="Example extensions">
            <stereotype name="Java method"/>
        </extensionFamily>

    Therefore, the preferred feature is extensionFamily.
    """

    DOMAIN_NAME = "Adaptive System Domain"

    # Keep this order stable because XMI references use stereotype indexes.
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

    ROLE_TO_STEREOTYPE = {
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
        # Kept for compatibility with older recovery outputs.
        "Alternative": "Planner",
    }

    SUBSYSTEM_TO_STEREOTYPE = {
        "ManagingSubsystem": "Managing Subsystem",
        "Managing Subsystem": "Managing Subsystem",
        "managing_subsystem": "Managing Subsystem",
        "subsystem:managing_subsystem": "Managing Subsystem",
        "ManagedSubsystem": "Managed Subsystem",
        "Managed Subsystem": "Managed Subsystem",
        "managed_subsystem": "Managed Subsystem",
        "subsystem:managed_subsystem": "Managed Subsystem",
    }

    def __init__(self, factory, segment):
        self.factory = factory
        self.segment = segment
        self.extension_family = None
        self.stereotype_index = {}
        self.segment_extension_feature = None

    # ------------------------------------------------------------
    # Domain creation
    # ------------------------------------------------------------

    def build_domain(self):
        """
        Creates the ExtensionFamily directly under the KDM Segment.

        Preferred serialization:

            <extensionFamily name="Adaptive System Domain">
                <stereotype name="Monitor" type="structure:Component"/>
                ...
            </extensionFamily>
        """

        if self.extension_family is not None:
            return self.extension_family

        feature_name = self._resolve_segment_extension_feature()
        self.segment_extension_feature = feature_name

        self.extension_family = self.factory.create_extension_family(
            self.DOMAIN_NAME
        )

        for stereotype_name, stereotype_type in self.STEREOTYPE_TYPES.items():
            stereotype = self.factory.create_stereotype(
                name=stereotype_name,
                stereotype_type=stereotype_type,
            )
            self._add_stereotype_to_family(stereotype)
            self.stereotype_index[stereotype_name] = stereotype

        getattr(self.segment, feature_name).append(self.extension_family)

        return self.extension_family

    def _resolve_segment_extension_feature(self):
        """
        MoDisco/KDM examples commonly use extensionFamily.
        Some Ecore variants may use extension. Try both.
        """

        for feature_name in ["extensionFamily", "extension"]:
            if self.factory.has_feature(self.segment, feature_name):
                return feature_name

        available = [
            feature.name
            for feature in self.segment.eClass.eAllStructuralFeatures()
        ]

        raise ValueError(
            "Segment does not have feature 'extensionFamily' or 'extension'. "
            f"Available Segment features are: {available}"
        )

    # ------------------------------------------------------------
    # Application
    # ------------------------------------------------------------

    def apply_component_stereotype(self, element, component_data: dict):
        stereotype_name = self._normalize_component_stereotype(
            component_data.get("stereotype_name")
            or component_data.get("role")
        )

        if not stereotype_name:
            return False

        return self.apply_stereotype(element, stereotype_name)

    def apply_subsystem_stereotype(self, element, subsystem_data: dict):
        stereotype_name = self._normalize_subsystem_stereotype(subsystem_data)

        if not stereotype_name:
            return False

        return self.apply_stereotype(element, stereotype_name)

    def apply_stereotype(self, element, stereotype_name: str):
        self.build_domain()

        stereotype = self.stereotype_index.get(stereotype_name)

        if stereotype is None:
            raise ValueError(
                f"Unknown Adaptive System Domain stereotype: {stereotype_name}"
            )

        if not self.factory.has_feature(element, "stereotype"):
            available = [
                feature.name
                for feature in element.eClass.eAllStructuralFeatures()
            ]
            raise ValueError(
                f"{element.eClass.name} does not support feature 'stereotype'. "
                f"Available features are: {available}"
            )

        if stereotype not in list(element.stereotype):
            element.stereotype.append(stereotype)

        return True

    # ------------------------------------------------------------
    # Normalization
    # ------------------------------------------------------------

    def _normalize_component_stereotype(self, role_or_stereotype):
        if role_or_stereotype is None:
            return None

        return self.ROLE_TO_STEREOTYPE.get(
            role_or_stereotype,
            role_or_stereotype,
        )

    def _normalize_subsystem_stereotype(self, subsystem_data: dict):
        candidates = [
            subsystem_data.get("stereotype_name"),
            subsystem_data.get("name"),
            subsystem_data.get("id"),
        ]

        for candidate in candidates:
            if candidate in self.SUBSYSTEM_TO_STEREOTYPE:
                return self.SUBSYSTEM_TO_STEREOTYPE[candidate]

        text = (
            f"{subsystem_data.get('id', '')} "
            f"{subsystem_data.get('name', '')}"
        ).lower()

        if "managing" in text:
            return "Managing Subsystem"

        if "managed" in text:
            return "Managed Subsystem"

        return None

    # ------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------

    def _add_stereotype_to_family(self, stereotype):
        if not self.factory.has_feature(self.extension_family, "stereotype"):
            available = [
                feature.name
                for feature in self.extension_family.eClass.eAllStructuralFeatures()
            ]
            raise ValueError(
                "ExtensionFamily does not have feature 'stereotype'. "
                f"Available features are: {available}"
            )

        self.extension_family.stereotype.append(stereotype)
