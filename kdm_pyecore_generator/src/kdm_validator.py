class KDMValidationReport:
    def __init__(self):
        self.errors = []
        self.warnings = []
        self.stats = {}

    def add_error(self, message: str):
        self.errors.append(message)

    def add_warning(self, message: str):
        self.warnings.append(message)

    def set_stat(self, key: str, value):
        self.stats[key] = value

    def has_errors(self):
        return len(self.errors) > 0

    def print_report(self):
        print("\n=== KDM VALIDATION REPORT ===")
        print(f"Errors: {len(self.errors)}")
        for error in self.errors:
            print(f"[ERROR] {error}")

        print(f"\nWarnings: {len(self.warnings)}")
        for warning in self.warnings:
            print(f"[WARNING] {warning}")

        print("\nStats:")
        for key, value in self.stats.items():
            print(f"- {key}: {value}")


class KDMValidator:
    def __init__(self):
        self.report = KDMValidationReport()

    def validate(self, segment):
        self.report = KDMValidationReport()

        all_elements = list(self._walk(segment))

        self._collect_stats(all_elements)
        self._validate_inventory(segment)
        self._validate_source_regions(all_elements)
        self._validate_has_type(all_elements)
        self._validate_has_value(all_elements)
        self._validate_calls_and_creates(all_elements)
        self._validate_reads_writes(all_elements)
        self._validate_no_obsolete_attributes(all_elements)
        self._validate_imports_and_extends(all_elements)

        return self.report

    # ------------------------------------------------------------
    # Traversal
    # ------------------------------------------------------------

    def _walk(self, root):
        """
        Recursively walks only Ecore model elements.

        It ignores primitive values such as strings, integers, booleans,
        and non-containment references.
        """

        if root is None:
            return

        # Ignore primitive values or non-Ecore objects
        if not hasattr(root, "eClass"):
            return

        yield root

        for feature in root.eClass.eAllStructuralFeatures():
            # Only traverse containment references
            if not getattr(feature, "containment", False):
                continue

            value = getattr(root, feature.name, None)

            if value is None:
                continue

            # PyEcore containment-many references behave like collections,
            # but they are not always plain Python lists.
            if hasattr(value, "__iter__") and not isinstance(value, (str, bytes)):
                for child in value:
                    if hasattr(child, "eClass"):
                        yield from self._walk(child)
            else:
                if hasattr(value, "eClass"):
                    yield from self._walk(value)

    def _has_feature(self, obj, feature_name: str):
        if obj is None or not hasattr(obj, "eClass"):
            return False

        return feature_name in [
            feature.name for feature in obj.eClass.eAllStructuralFeatures()
        ]

    def _is_instance_of(self, element, class_name: str):
        eclass = element.eClass

        if eclass.name == class_name:
            return True

        for super_type in eclass.eAllSuperTypes():
            if super_type.name == class_name:
                return True

        return False

    def _get_name(self, element):
        if self._has_feature(element, "name"):
            return getattr(element, "name", None)
        return None

    # ------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------

    def _collect_stats(self, all_elements):
        counters = {}

        for element in all_elements:
            name = element.eClass.name
            counters[name] = counters.get(name, 0) + 1

        interesting = [
            "Segment",
            "InventoryModel",
            "SourceFile",
            "CodeModel",
            "CompilationUnit",
            "ClassUnit",
            "MethodUnit",
            "CallableUnit",
            "ParameterUnit",
            "StorableUnit",
            "ActionElement",
            "SourceRef",
            "SourceRegion",
            "Imports",
            "Extends",
            "Calls",
            "Creates",
            "Reads",
            "Writes",
            "HasType",
            "HasValue",
            "Value",
            "Attribute",
        ]

        for key in interesting:
            self.report.set_stat(key, counters.get(key, 0))

    # ------------------------------------------------------------
    # Inventory and source traceability
    # ------------------------------------------------------------

    def _validate_inventory(self, segment):
        inventory_models = []

        if self._has_feature(segment, "model"):
            for model in segment.model:
                if model.eClass.name == "InventoryModel":
                    inventory_models.append(model)

        if len(inventory_models) == 0:
            self.report.add_error("No InventoryModel found in Segment.")

        if len(inventory_models) > 1:
            self.report.add_warning(
                f"More than one InventoryModel found: {len(inventory_models)}."
            )

        source_files = []

        for inventory_model in inventory_models:
            if not self._has_feature(inventory_model, "inventoryElement"):
                self.report.add_error(
                    "InventoryModel does not have inventoryElement feature."
                )
                continue

            for item in inventory_model.inventoryElement:
                if item.eClass.name == "SourceFile":
                    source_files.append(item)

                    if not getattr(item, "path", None):
                        self.report.add_error(
                            f"SourceFile '{self._get_name(item)}' has no path."
                        )

        if len(source_files) == 0:
            self.report.add_error("No SourceFile found inside InventoryModel.")

    def _validate_source_regions(self, all_elements):
        source_regions = [
            element for element in all_elements if element.eClass.name == "SourceRegion"
        ]

        for region in source_regions:
            has_file = self._has_feature(region, "file") and getattr(region, "file", None)
            has_path = self._has_feature(region, "path") and getattr(region, "path", None)

            if not has_file and not has_path:
                self.report.add_error(
                    "SourceRegion has neither file reference nor path."
                )

            start_line = getattr(region, "startLine", None) if self._has_feature(region, "startLine") else None
            end_line = getattr(region, "endLine", None) if self._has_feature(region, "endLine") else None

            if start_line is not None and end_line is not None:
                if int(start_line) > int(end_line):
                    self.report.add_error(
                        f"SourceRegion has startLine > endLine: {start_line} > {end_line}."
                    )

    # ------------------------------------------------------------
    # Type relations
    # ------------------------------------------------------------

    def _validate_has_type(self, all_elements):
        for element in all_elements:
            if element.eClass.name != "HasType":
                continue

            target = getattr(element, "to", None)

            if target is None:
                self.report.add_error("HasType relation without target.")
                continue

            if not self._is_instance_of(target, "Datatype"):
                self.report.add_error(
                    f"HasType target is not a Datatype: {target.eClass.name}."
                )

    # ------------------------------------------------------------
    # Value relations
    # ------------------------------------------------------------

    def _validate_has_value(self, all_elements):
        for element in all_elements:
            if element.eClass.name != "HasValue":
                continue

            target = getattr(element, "to", None)

            if target is None:
                self.report.add_error("HasValue relation without target.")
                continue

            valid_target = (
                target.eClass.name == "Value"
                or self._is_instance_of(target, "ActionElement")
            )

            if not valid_target:
                self.report.add_error(
                    f"HasValue target must be Value or ActionElement, got {target.eClass.name}."
                )

    # ------------------------------------------------------------
    # Call/create relations
    # ------------------------------------------------------------

    def _validate_calls_and_creates(self, all_elements):
        for element in all_elements:
            if element.eClass.name not in {"Calls", "Creates"}:
                continue

            target = getattr(element, "to", None)

            if target is None:
                self.report.add_error(f"{element.eClass.name} relation without target.")

        for element in all_elements:
            if element.eClass.name != "ActionElement":
                continue

            kind = getattr(element, "kind", None) if self._has_feature(element, "kind") else None

            if kind == "constructor_call":
                has_creates = False

                if self._has_feature(element, "actionRelation"):
                    for relation in element.actionRelation:
                        if relation.eClass.name == "Creates":
                            has_creates = True
                            break

                if not has_creates:
                    self.report.add_warning(
                        f"Constructor ActionElement '{self._get_name(element)}' has no Creates relation."
                    )

    # ------------------------------------------------------------
    # Reads/Writes
    # ------------------------------------------------------------

    def _validate_reads_writes(self, all_elements):
        for element in all_elements:
            if element.eClass.name not in {"Reads", "Writes"}:
                continue

            target = getattr(element, "to", None)

            if target is None:
                self.report.add_error(f"{element.eClass.name} relation without target.")
                continue

            if not self._is_instance_of(target, "StorableUnit"):
                self.report.add_error(
                    f"{element.eClass.name} target must be StorableUnit, got {target.eClass.name}."
                )

    # ------------------------------------------------------------
    # Imports / Extends
    # ------------------------------------------------------------

    def _validate_imports_and_extends(self, all_elements):
        for element in all_elements:
            if element.eClass.name not in {"Imports", "Extends"}:
                continue

            target = getattr(element, "to", None)

            if target is None:
                self.report.add_error(f"{element.eClass.name} relation without target.")

    # ------------------------------------------------------------
    # Obsolete attributes
    # ------------------------------------------------------------

    def _validate_no_obsolete_attributes(self, all_elements):
        obsolete_tags = {
            "line",
            "line_start",
            "line_end",
            "path",
            "language",
            "assigned_value",
            "assigned_type",
            "resolved_type_qualified_name",
            "annotation",
            "kind",
            "function",
            "method",
            "class_name",
            "base_name",
            "source_class",
        }

        for element in all_elements:
            if element.eClass.name != "Attribute":
                continue

            tag = getattr(element, "tag", None)

            if tag in obsolete_tags:
                self.report.add_warning(
                    f"Obsolete Attribute found: tag='{tag}', value='{getattr(element, 'value', None)}'."
                )
