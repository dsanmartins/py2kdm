class JsonToKDMMapper:
    def __init__(self, factory, inventory_builder=None, external_builder=None):
        self.factory = factory
        self.inventory_builder = inventory_builder
        self.external_builder = external_builder

        # Generic indexes.
        self.id_index = {}
        self.qualified_name_index = {}
        self.class_name_index = {}

        # Project language.
        self.language = "unknown"
        self.project_name = "UnknownProject"

        # Elements that can receive code::HasType.
        self.typable_elements = []

        # Elements that can receive code::HasValue.
        self.value_elements = []

        # StorableUnit index used by access, return and value resolvers.
        self.storable_index = {}

        # Generic model support.
        self.compilation_unit_by_path = {}
        self.package_index = {}
        self.package_qualified_name_index = {}

        # Formal KDM extension support for Java annotations and Python decorators.
        self.segment = None
        self.annotation_extension_family = None
        self.annotation_stereotypes = {}

        # De-duplication for generic code/action relations.
        self._mapped_import_keys = set()
        self._mapped_call_keys = set()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def transform_structure(self, data: dict):
        """
        Backward-compatible method.

        Creates a new Segment and maps the CodeModel into it.
        Useful when no InventoryModel is created beforehand.
        """
        project_name = data.get("projectName", "UnknownProject")
        segment = self.factory.create_segment(project_name)

        return self.transform_structure_into_segment(data, segment)

    def transform_structure_into_segment(self, data: dict, segment):
        """
        Maps the JSON structure into an existing Segment.

        Supports both:

        1. The older py2kdm format, where classes and functions are nested
           inside files[].

        2. The generic static model format, where language-specific extractors
           produce:

              files[]
              elements[]
              relationships[]

        This allows Python, Java and future extractors to share the same
        JSON-to-KDM mapper.
        """
        project_name = data.get("projectName", "UnknownProject")
        self.language = data.get("language", "unknown")
        self.project_name = project_name
        self.segment = segment

        code_model = self.factory.create_code_model(f"{project_name}_CodeModel")
        segment.model.append(code_model)

        # First create Package elements from the common schema.
        self._map_common_packages(code_model, data)

        # Then create CompilationUnit elements for every source file.
        for file_model in data.get("files", []):
            self._map_file(code_model, file_model)

        # Then map language-independent structural elements.
        for element in data.get("elements", []):
            self._map_generic_element(code_model, element)

        # Register external types before generic relationships so imports,
        # creates, throws and uses_type can resolve their targets.
        self._map_common_external_types(data)

        # Map imports declared directly on files. Some extractors provide imports
        # both as file metadata and relationships; the mapper de-duplicates them.
        self._map_file_level_imports(data)

        # Finally map generic relationships when possible.
        self._map_generic_relationships(data)

        return segment

    # ------------------------------------------------------------------
    # Registration and metadata helpers
    # ------------------------------------------------------------------

    def _register(self, json_id: str, kdm_element, model_element: dict = None):
        if json_id:
            self.id_index[json_id] = kdm_element

        if not model_element:
            return

        qualified_name = (
            model_element.get("qualified_name")
            or model_element.get("qualifiedName")
            or model_element.get("qualifiedSignature")
            or model_element.get("qualified_signature")
        )

        safe_qualified_name = model_element.get("safeQualifiedName")

        name = model_element.get("name")

        element_type = (
            model_element.get("type")
            or model_element.get("kind")
        )

        if qualified_name:
            self.qualified_name_index[qualified_name] = kdm_element
            self.id_index.setdefault(qualified_name, kdm_element)

        if safe_qualified_name:
            self.qualified_name_index[safe_qualified_name] = kdm_element
            self.id_index.setdefault(safe_qualified_name, kdm_element)

        if element_type in {"class", "interface", "enum", "annotation", "annotation_type"} and name:
            self.class_name_index.setdefault(name, []).append(kdm_element)

    def _add_common_metadata(self, kdm_element, model_element: dict):
        """
        Adds non-physical metadata.

        Physical traceability is represented using source::SourceRef and
        source::SourceRegion. Structural information is represented by KDM
        containment and native properties where possible.

        Important:
        Do not add the tag 'kind' as an Attribute. The validator treats it as
        obsolete in this context. Use element_kind or method_kind instead.
        """
        metadata = {
            "qualified_name": (
                model_element.get("qualified_name")
                or model_element.get("qualifiedName")
            ),
            "package": (
                model_element.get("package_name")
                or model_element.get("packageName")
            ),
        }

        self.factory.add_attributes_from_dict(kdm_element, metadata)

    def _append_code_element(self, parent, child):
        if self.factory.has_feature(parent, "codeElement"):
            parent.codeElement.append(child)
            return True

        return False

    def _append_code_relation(self, source, relation):
        if self.factory.has_feature(source, "codeRelation"):
            source.codeRelation.append(relation)
            return True

        return False

    def _append_action_relation(self, source, relation):
        if self.factory.has_feature(source, "actionRelation"):
            source.actionRelation.append(relation)
            return True

        return False

    def _strip_generic_arguments(self, value):
        if value is None:
            return None
        value = str(value).strip()
        for marker in ("<", "["):
            if marker in value:
                value = value.split(marker, 1)[0]
        return value.strip() or None

    def _safe_join(self, values):
        if not values:
            return None

        return ", ".join(str(value) for value in values)

    # ------------------------------------------------------------------
    # Common schema packages and external types
    # ------------------------------------------------------------------

    def _map_common_packages(self, code_model, data: dict):
        """Create the project package hierarchy in the main CodeModel.

        Only packages that belong to source files/elements are materialized in
        the project CodeModel. Packages that come only from imports or
        externalTypes are delegated to ExternalLibraries_CodeModel. This keeps
        the recovered project architecture clean:

            <project>_CodeModel          -> internal packages only
            ExternalLibraries_CodeModel -> external packages/libraries
        """

        source_package_names = self._collect_source_package_names(data)
        if self.external_builder is not None and hasattr(self.external_builder, "set_internal_package_prefixes"):
            self.external_builder.set_internal_package_prefixes(source_package_names)
        if self.external_builder is not None and hasattr(self.external_builder, "set_internal_type_names"):
            self.external_builder.set_internal_type_names(self._collect_internal_type_names(data))
        if self.external_builder is not None and hasattr(self.external_builder, "set_internal_module_names"):
            self.external_builder.set_internal_module_names(self._collect_internal_module_names(data))
        packages = self._collect_package_models(
            data,
            source_package_names=source_package_names,
            include_external=False,
        )

        if packages:
            self._create_package_hierarchy(code_model, packages)

        external_packages = self._collect_package_models(
            data,
            source_package_names=source_package_names,
            include_external=True,
        )
        self._map_common_external_packages(external_packages)

    def _collect_internal_type_names(self, data: dict):
        names = set()
        for element in data.get("elements", []) or []:
            kind = element.get("kind") or element.get("type")
            if kind in {"class", "interface", "enum", "annotation", "annotation_type"}:
                name = element.get("name")
                if name:
                    names.add(str(name).strip())
        for file_model in data.get("files", []) or []:
            for cls in file_model.get("classes", []) or []:
                name = cls.get("name")
                if name:
                    names.add(str(name).strip())
            # Java extractor may expose declarations directly as elements, but
            # keep this defensive for future schemas.
            for declaration in file_model.get("declarations", []) or []:
                kind = declaration.get("kind") or declaration.get("type")
                if kind in {"class", "interface", "enum", "annotation", "annotation_type"}:
                    name = declaration.get("name")
                    if name:
                        names.add(str(name).strip())
        return names

    def _collect_internal_module_names(self, data: dict):
        """Return simple names of modules/packages declared by the project.

        Python imports sometimes reach the external builder only as a short
        unresolved name, for example ``_scenario_common`` or ``rx_utils``, even
        though the fully-qualified internal module exists in the model.  Keeping
        these simple names prevents the external model from being polluted by
        internal relative-import fragments.
        """
        names = set()

        def add_qn(value):
            if not value:
                return
            text = str(value).strip()
            if not text:
                return
            simple = text.rsplit(".", 1)[-1]
            if simple:
                names.add(simple)

        for file_model in data.get("files", []) or []:
            add_qn(file_model.get("name"))
            add_qn(file_model.get("packageName") or file_model.get("package_name"))
            add_qn(file_model.get("qualifiedName") or file_model.get("qualified_name"))

        for element in data.get("elements", []) or []:
            kind = element.get("kind") or element.get("type")
            if kind in {"project", "module"}:
                add_qn(element.get("name"))
                add_qn(element.get("packageName") or element.get("package_name"))
                add_qn(element.get("qualifiedName") or element.get("qualified_name"))

        for package in data.get("packages", []) or []:
            add_qn(package.get("name"))
            add_qn(package.get("qualifiedName") or package.get("qualified_name"))

        return names

    def _is_already_mapped_element(self, element: dict) -> bool:
        """True when an element was already created by the nested file mapper.

        Python keeps backward-compatible nested structures in files[] and also
        provides a flat common ``elements`` list.  Mapping both creates duplicate
        ClassUnit/CallableUnit objects directly under the CodeModel.  Java, in
        contrast, usually relies on the flat elements list, so we only skip when
        the exact id or qualified name is already registered.
        """
        keys = [
            element.get("id"),
            element.get("qualifiedName"),
            element.get("qualified_name"),
            element.get("safeQualifiedName"),
            element.get("qualifiedSignature"),
            element.get("qualified_signature"),
        ]
        return any(key and (key in self.id_index or key in self.qualified_name_index) for key in keys)

    def _collect_source_package_names(self, data: dict):
        """Packages that are actually owned by source files/elements."""

        source_packages = set()

        for file_model in data.get("files", []) or []:
            package_qn = file_model.get("packageName") or file_model.get("package_name")
            if package_qn:
                source_packages.add(str(package_qn).strip())
            path = str(file_model.get("path") or "")
            qualified_qn = file_model.get("qualifiedName") or file_model.get("qualified_name")
            # __init__.py denotes a real Python package; ordinary .py modules
            # should be CompilationUnit only, not Package.
            if qualified_qn and path.endswith("__init__.py"):
                source_packages.add(str(qualified_qn).strip())

        for element in data.get("elements", []) or []:
            # Only project/module elements define source packages. Class,
            # function or method packageName values may include declaration
            # names in some extractor outputs and must not become packages.
            kind = element.get("kind") or element.get("type")
            if kind in {"project", "module"}:
                package_qn = element.get("packageName") or element.get("package_name")
                if package_qn:
                    source_packages.add(str(package_qn).strip())
                if kind == "project":
                    qn = element.get("qualifiedName") or element.get("qualified_name")
                    if qn:
                        source_packages.add(str(qn).strip())

        return {qn for qn in source_packages if qn}

    def _is_project_package(self, qn: str, source_package_names: set) -> bool:
        """Return True when qn is internal to the analyzed project.

        A package is internal when it is a source package, a parent of a source
        package, or a child of a source package. This handles Java packages
        such as com.example.service and Python packages such as
        pymape_hierarchical.mape.utils without assuming that the project name
        is a valid package prefix.
        """

        if not qn:
            return False
        qn = str(qn).strip()
        for source_qn in source_package_names or set():
            if not source_qn:
                continue
            if qn == source_qn:
                return True
            if source_qn.startswith(qn + "."):
                return True
        return False

    def _is_descendant_of_source_package(self, qn: str, source_package_names: set) -> bool:
        if not qn:
            return False
        qn = str(qn).strip()
        for source_qn in source_package_names or set():
            if source_qn and qn.startswith(source_qn + "."):
                return True
        return False

    def _create_package_hierarchy(self, code_model, packages):
        by_qn = {}
        for package in packages:
            qn = package.get("qualifiedName") or package.get("qualified_name")
            if qn:
                by_qn[qn] = package

        remaining = set(by_qn.keys())
        while remaining:
            progressed = False
            for qn in list(remaining):
                package = by_qn[qn]
                parent_qn = package.get("parent") or package.get("parentQualifiedName")
                if parent_qn and parent_qn in by_qn and parent_qn not in self.package_qualified_name_index:
                    continue
                self._create_package_from_model(code_model, package)
                remaining.remove(qn)
                progressed = True
            if not progressed:
                # Cycle or missing parent. Create the remaining nodes at the
                # CodeModel level rather than dropping them.
                for qn in list(remaining):
                    self._create_package_from_model(code_model, by_qn[qn])
                    remaining.remove(qn)

    def _map_common_external_packages(self, packages):
        if self.external_builder is None:
            return
        for package in packages or []:
            qn = package.get("qualifiedName") or package.get("qualified_name")
            if not qn:
                continue
            self.external_builder.get_or_create_external_package(qn)

    def _collect_package_models(
        self,
        data: dict,
        source_package_names: set = None,
        include_external: bool = False,
    ):
        """Return a parent-complete list of package models.

        Input packages are merged with packages inferred from files, elements
        and externalTypes. The include_external flag controls whether the
        returned set is the project-internal package tree or the external
        package tree.
        """

        source_package_names = source_package_names or set()
        by_qn = {}

        # Python modules (.py files) are represented as CompilationUnit, not as
        # Package.  Keep only directory/package names as Package nodes.
        file_module_qns = set()
        for file_model in data.get("files", []) or []:
            path = str(file_model.get("path") or "")
            qn = file_model.get("qualifiedName") or file_model.get("qualified_name")
            if qn and not path.endswith("__init__.py"):
                file_module_qns.add(str(qn).strip())

        def add_package_qn(qn, explicit_model=None):
            if not qn:
                return
            qn = self._strip_generic_arguments(qn)
            if not qn:
                return
            if qn in file_module_qns:
                return

            is_internal = self._is_project_package(qn, source_package_names)
            is_source_descendant = self._is_descendant_of_source_package(qn, source_package_names)
            if include_external and (is_internal or is_source_descendant):
                return
            if not include_external and not is_internal:
                return

            parts = [part for part in qn.split(".") if part]
            current = []
            parent = None
            for part in parts:
                current.append(part)
                current_qn = ".".join(current)

                # Recompute internal/external status for parent packages.
                parent_is_internal = self._is_project_package(current_qn, source_package_names)
                parent_is_source_descendant = self._is_descendant_of_source_package(current_qn, source_package_names)
                if include_external and (parent_is_internal or parent_is_source_descendant):
                    parent = current_qn
                    continue
                if not include_external and not parent_is_internal:
                    parent = current_qn
                    continue

                by_qn.setdefault(
                    current_qn,
                    {
                        "name": part,
                        "qualifiedName": current_qn,
                        "parent": parent if parent in by_qn else None,
                    },
                )
                parent = current_qn

            if explicit_model and qn in by_qn:
                normalized = by_qn[qn]
                normalized.update(
                    {
                        "name": explicit_model.get("name") or normalized.get("name"),
                        "qualifiedName": qn,
                        "parent": explicit_model.get("parent")
                        or explicit_model.get("parentQualifiedName")
                        or normalized.get("parent"),
                        "safeQualifiedName": explicit_model.get("safeQualifiedName")
                        or explicit_model.get("safe_qualified_name"),
                    }
                )

        for package in data.get("packages", []) or []:
            qn = package.get("qualifiedName") or package.get("qualified_name")
            add_package_qn(qn, package)

        for file_model in data.get("files", []) or []:
            add_package_qn(file_model.get("packageName") or file_model.get("package_name"))
            path = str(file_model.get("path") or "")
            if path.endswith("__init__.py"):
                add_package_qn(file_model.get("qualifiedName") or file_model.get("qualified_name"))

        for element in data.get("elements", []) or []:
            kind = element.get("kind") or element.get("type")
            if kind in {"project", "module"}:
                add_package_qn(element.get("packageName") or element.get("package_name"))
                if kind == "project":
                    add_package_qn(element.get("qualifiedName") or element.get("qualified_name"))

        if include_external:
            for type_model in data.get("externalTypes", []) or []:
                # Prefer the package inferred from the raw qualified name.
                # Some extractor outputs may carry a generic full type in
                # packageName; using it would create packages such as
                # java.util.Map.java.lang.
                add_package_qn(
                    self._package_from_qualified_name(
                        type_model.get("qualifiedName") or type_model.get("qualified_name")
                    )
                    or type_model.get("packageName")
                    or type_model.get("package_name")
                )

        return sorted(by_qn.values(), key=lambda item: item.get("qualifiedName", "").count("."))

    def _package_from_qualified_name(self, qualified_name):
        qualified_name = self._strip_generic_arguments(qualified_name)
        if not qualified_name or "." not in str(qualified_name):
            return None
        return str(qualified_name).rsplit(".", 1)[0]

    def _create_package_from_model(self, code_model, package: dict):
        qn = package.get("qualifiedName") or package.get("qualified_name")
        if not qn or qn in self.package_qualified_name_index:
            return self.package_qualified_name_index.get(qn)

        name = package.get("name") or str(qn).rsplit(".", 1)[-1]
        package_unit = self.factory.create_package_unit(name)

        parent_qn = package.get("parent") or package.get("parentQualifiedName")
        parent = self.package_qualified_name_index.get(parent_qn)
        if parent is not None:
            self._append_code_element(parent, package_unit)
        else:
            code_model.codeElement.append(package_unit)

        self._add_common_metadata(package_unit, package)
        self.package_qualified_name_index[qn] = package_unit
        self.package_index[qn] = package_unit
        self.qualified_name_index[qn] = package_unit
        self.id_index.setdefault(qn, package_unit)
        if package.get("safeQualifiedName"):
            self.id_index.setdefault(package.get("safeQualifiedName"), package_unit)
            self.qualified_name_index[package.get("safeQualifiedName")] = package_unit
        return package_unit

    def _find_parent_package_for_file(self, file_model: dict):
        package_name = (
            file_model.get("packageName")
            or file_model.get("package_name")
        )
        if not package_name:
            return None
        return self.package_qualified_name_index.get(package_name)

    def _map_common_external_types(self, data: dict):
        if self.external_builder is None:
            return
        for type_model in data.get("externalTypes", []) or []:
            target = self.external_builder.get_or_create_external_type(type_model)
            if target is None:
                continue
            self._register_external_type(target, type_model)

    def _register_external_type(self, kdm_element, type_model: dict):
        qn = type_model.get("qualifiedName") or type_model.get("qualified_name")
        safe_qn = type_model.get("safeQualifiedName")
        if qn:
            self.qualified_name_index[qn] = kdm_element
            self.id_index.setdefault(qn, kdm_element)
            self.id_index.setdefault(f"external_type:{qn}", kdm_element)
        if safe_qn:
            self.qualified_name_index[safe_qn] = kdm_element
            self.id_index.setdefault(safe_qn, kdm_element)

    def _create_class_like_unit(self, name: str, kind: str):
        if kind in {"interface", "annotation", "annotation_type"}:
            return self.factory.create_interface_unit(name)
        return self.factory.create_class_unit(name)

    def _is_kdm_datatype(self, element) -> bool:
        """Return True if a PyEcore KDM element is a code::Datatype.

        The generated KDM metamodel makes ClassUnit and InterfaceUnit inherit
        from Datatype, while CallableUnit inherits from ControlElement.  This
        helper keeps relationship mappers defensive without depending on a
        concrete Python class hierarchy.
        """
        if element is None or not hasattr(element, "eClass"):
            return False

        eclass = element.eClass
        names = {getattr(eclass, "name", None)}

        for attr in ("eAllSuperTypes", "eSuperTypes"):
            try:
                for super_type in getattr(eclass, attr, []) or []:
                    names.add(getattr(super_type, "name", None))
            except Exception:
                pass

        return "Datatype" in names


    def _is_kdm_data_element(self, element) -> bool:
        """Return True if a PyEcore KDM element is a code::DataElement.

        action::Throws.to is typed as code::DataElement in the KDM Ecore
        model used by this project.  Exception classes are Datatype
        specializations (ClassUnit/InterfaceUnit), so they cannot be used as
        the direct target of Throws.  A StorableUnit representing the thrown
        exception object must be used instead.
        """
        if element is None or not hasattr(element, "eClass"):
            return False

        eclass = element.eClass
        names = {getattr(eclass, "name", None)}

        for attr in ("eAllSuperTypes", "eSuperTypes"):
            try:
                for super_type in getattr(eclass, attr, []) or []:
                    names.add(getattr(super_type, "name", None))
            except Exception:
                pass

        return "DataElement" in names

    def _safe_kdm_name(self, value) -> str:
        text = str(value or "element")
        safe = []
        for char in text:
            if char.isalnum() or char == "_":
                safe.append(char)
            else:
                safe.append("_")
        result = "".join(safe).strip("_")
        return result or "element"

    def _get_or_create_thrown_exception_data(self, action, target_key, target_element=None):
        """Create/reuse a StorableUnit that represents the thrown exception.

        The common JSON schema stores the exception *type* as the target of a
        throws relation (e.g. ValueError or java.lang.IllegalArgumentException).
        In this KDM Ecore metamodel, Throws.to expects a DataElement, not the
        exception ClassUnit itself.  We therefore create a small StorableUnit
        below the throw ActionElement and optionally attach HasType to the
        exception class when the target is a Datatype.
        """
        if action is None or not self.factory.has_feature(action, "codeElement"):
            return None

        target_text = str(target_key or getattr(target_element, "name", None) or "exception")
        short_name = target_text.replace(".<init>", "").split(".")[-1]
        storable_name = f"thrown_{self._safe_kdm_name(short_name)}"

        for child in getattr(action, "codeElement", []) or []:
            if getattr(child.eClass, "name", None) == "StorableUnit" and getattr(child, "name", None) == storable_name:
                return child

        exception_data = self.factory.create_storable_unit(storable_name)
        self.factory.add_attributes_from_dict(
            exception_data,
            {
                "role": "thrown_exception",
                "exception_type": target_text,
            },
        )

        # Preserve type information when the exception type is represented as a
        # ClassUnit/InterfaceUnit. HasType is a code relation on DataElement and
        # its target must be a Datatype.
        if target_element is not None and self._is_kdm_datatype(target_element):
            try:
                has_type = self.factory.create_has_type_relation(target_element)
                self._append_code_relation(exception_data, has_type)
            except Exception:
                # Keep generation robust; the Throws relation itself is more
                # important than a secondary HasType annotation.
                pass

        action.codeElement.append(exception_data)
        return exception_data

    def _resolve_or_create_external_type(self, target_key):
        if not target_key or self.external_builder is None:
            return None
        existing = self._resolve_indexed_element(target_key)
        if existing is not None:
            return existing
        target_text = str(target_key)
        type_model = {
            "qualifiedName": target_text,
            "name": target_text.split(".")[-1],
            "packageName": target_text.rsplit(".", 1)[0] if "." in target_text else "builtins",
            "kind": "class" if target_text.split(".")[-1][:1].isupper() else "callable",
            "external": True,
        }
        target = self.external_builder.get_or_create_external_type(type_model)
        if target is not None:
            self._register_external_type(target, type_model)
        return target

    # ------------------------------------------------------------------
    # File mapping
    # ------------------------------------------------------------------

    def _map_file(self, code_model, file_model: dict):
        unit_name = file_model.get("path", file_model.get("name", "unknown.py"))

        compilation_unit = self.factory.create_compilation_unit(unit_name)
        package_parent = self._find_parent_package_for_file(file_model)
        if package_parent is not None:
            self._append_code_element(package_parent, compilation_unit)
        else:
            code_model.codeElement.append(compilation_unit)

        path = file_model.get("path")
        if path:
            self.compilation_unit_by_path[path] = compilation_unit
            self.id_index.setdefault(path, compilation_unit)

        source_file = self._get_source_file(file_model)

        self.factory.add_source_region(
            compilation_unit,
            path=file_model.get("path"),
            language=self.language,
            file_item=source_file,
        )

        self._add_common_metadata(compilation_unit, file_model)

        self._register(
            file_model.get("id") or file_model.get("path"),
            compilation_unit,
            file_model,
        )

        # Backward-compatible mapping for the older nested Python model.
        for cls in file_model.get("classes", []):
            self._map_class(compilation_unit, cls, file_model)

        for func in file_model.get("functions", []):
            self._map_function(compilation_unit, func, file_model)

    # ------------------------------------------------------------------
    # Backward-compatible py2kdm structural mapping
    # ------------------------------------------------------------------

    def _map_class(self, parent, cls: dict, file_model: dict):
        class_unit = self.factory.create_class_unit(
            cls.get("name", "AnonymousClass")
        )
        parent.codeElement.append(class_unit)

        source_file = self._get_source_file(file_model)

        self.factory.add_source_region(
            class_unit,
            path=file_model.get("path"),
            language=self.language,
            start_line=cls.get("line_start"),
            end_line=cls.get("line_end"),
            file_item=source_file,
        )

        self._add_common_metadata(class_unit, cls)
        self._add_native_annotations(class_unit, cls)

        self._register(cls.get("id"), class_unit, cls)

        for attr in cls.get("attributes", []):
            self._map_storable(class_unit, attr, file_model, cls)

        for attr in cls.get("instance_attributes", []):
            self._map_storable(class_unit, attr, file_model, cls)

        for method in cls.get("methods", []):
            self._map_method(class_unit, method, file_model)

    def _map_method(self, parent, method: dict, file_model: dict):
        method_unit = self.factory.create_method_unit(
            method.get("name", "anonymous_method")
        )
        parent.codeElement.append(method_unit)

        source_file = self._get_source_file(file_model)

        self.factory.add_source_region(
            method_unit,
            path=file_model.get("path"),
            language=self.language,
            start_line=method.get("line_start"),
            end_line=method.get("line_end"),
            file_item=source_file,
        )

        self._add_common_metadata(method_unit, method)
        self._add_callable_signature_metadata(method_unit, method)
        self._add_native_annotations(method_unit, method)

        self._register(method.get("id"), method_unit, method)
        self._register_callable_aliases(method_unit, method, None)

        for param in method.get("parameters", []):
            self._map_parameter(method_unit, param)

        for var in method.get("local_variables", []):
            self._map_storable(method_unit, var, file_model, method)

        for var in method.get("context_variables", []):
            self._map_storable(method_unit, var, file_model, method)

    def _map_function(self, parent, func: dict, file_model: dict):
        callable_unit = self.factory.create_callable_unit(
            func.get("name", "anonymous_function")
        )
        parent.codeElement.append(callable_unit)

        source_file = self._get_source_file(file_model)

        self.factory.add_source_region(
            callable_unit,
            path=file_model.get("path"),
            language=self.language,
            start_line=func.get("line_start"),
            end_line=func.get("line_end"),
            file_item=source_file,
        )

        self._add_common_metadata(callable_unit, func)
        self._add_callable_signature_metadata(callable_unit, func)
        self._add_native_annotations(callable_unit, func)

        self._register(func.get("id"), callable_unit, func)
        self._register_callable_aliases(callable_unit, func, None)

        for param in func.get("parameters", []):
            self._map_parameter(callable_unit, param)

        for var in func.get("local_variables", []):
            self._map_storable(callable_unit, var, file_model, func)

        for var in func.get("context_variables", []):
            self._map_storable(callable_unit, var, file_model, func)

    def _map_parameter(self, parent, param: dict):
        parameter_unit = self.factory.create_parameter_unit(
            param.get("name", "param")
        )

        if self.factory.has_feature(parent, "parameterUnit"):
            parent.parameterUnit.append(parameter_unit)
        else:
            parent.codeElement.append(parameter_unit)

        self._apply_parameter_native_properties(parameter_unit, param)
        self._add_native_annotations(parameter_unit, param)

        self._register_typable(parameter_unit, param)

        # Keep only metadata that has no native KDM counterpart in this
        # generator. Parameter kind and position are represented by
        # ParameterUnit.kind and ParameterUnit.pos. Type information is
        # represented by native type and HasType.
        metadata = {
            "default_value": param.get("default_value"),
        }

        self.factory.add_attributes_from_dict(parameter_unit, metadata)


    def _storable_identity_keys(self, var: dict, owner_model: dict = None):
        keys = []
        if not var:
            return keys
        for key_name in (
            "id",
            "qualifiedName",
            "qualified_name",
            "safeQualifiedName",
            "safe_qualified_name",
            "fullName",
            "full_name",
        ):
            value = var.get(key_name)
            if value:
                keys.append(str(value))
        owner_qn = None
        if owner_model:
            owner_qn = (
                owner_model.get("qualifiedName")
                or owner_model.get("qualified_name")
                or owner_model.get("safeQualifiedName")
                or owner_model.get("name")
            )
        name = var.get("name")
        if owner_qn and name:
            keys.append(f"{owner_qn}.{name}")
            keys.append(f"{owner_qn}:field:{name}")
        return [key for key in keys if key]

    def _find_existing_storable(self, var: dict, owner_model: dict = None):
        for key in self._storable_identity_keys(var, owner_model):
            existing = (
                self.storable_index.get(key)
                or self.id_index.get(key)
                or self.qualified_name_index.get(key)
            )
            if existing is not None:
                return existing
        return None

    def _register_storable_aliases(self, storable_unit, var: dict, owner_model: dict = None):
        for key in self._storable_identity_keys(var, owner_model):
            self.storable_index.setdefault(key, storable_unit)
            self.id_index.setdefault(key, storable_unit)
            self.qualified_name_index.setdefault(key, storable_unit)

    def _extend_source_region_if_needed(self, kdm_element, line_start=None, line_end=None):
        # SourceRegion ranges are not merged in-place because the generated
        # Ecore model may represent regions in a tool-specific way.  We keep
        # the first structural region and rely on Reads/Writes to capture all
        # concrete assignments.  This helper exists as a safe extension point.
        return kdm_element

    def _map_storable(
        self,
        parent,
        var: dict,
        file_model: dict,
        owner_model: dict = None,
    ):
        existing = self._find_existing_storable(var, owner_model)
        if existing is not None:
            self._register_typable(existing, var)
            self._register_value_element(existing, var, owner_model)
            self._register_storable(existing, var, owner_model)
            self._register_storable_aliases(existing, var, owner_model)
            self._extend_source_region_if_needed(
                existing,
                line_start=var.get("line") or var.get("lineStart") or var.get("line_start"),
                line_end=var.get("line") or var.get("lineEnd") or var.get("line_end"),
            )
            return existing

        storable_unit = self.factory.create_storable_unit(
            var.get("name", "variable")
        )
        parent.codeElement.append(storable_unit)

        self._register_typable(storable_unit, var)
        self._register_value_element(storable_unit, var, owner_model)
        self._register_storable(storable_unit, var, owner_model)
        self._register_storable_aliases(storable_unit, var, owner_model)

        source_file = self._get_source_file(file_model)

        self.factory.add_source_region(
            storable_unit,
            path=file_model.get("path"),
            language=self.language,
            start_line=var.get("line"),
            end_line=var.get("line"),
            file_item=source_file,
        )

        self._apply_data_native_properties(
            storable_unit,
            var,
            default_kind="local",
        )
        self._add_native_annotations(storable_unit, var)

        # Keep only metadata that has no reliable native KDM counterpart.
        # declared_type/resolved_type are represented by type and HasType.
        metadata = {
            "full_name": var.get("full_name"),
            "value_kind": var.get("value_kind") or var.get("valueKind"),
            "value_type": var.get("value_type") or var.get("valueType"),
        }

        self.factory.add_attributes_from_dict(storable_unit, metadata)

    # ------------------------------------------------------------------
    # Generic static model mapping
    # ------------------------------------------------------------------

    def _map_generic_element(self, code_model, element: dict):
        """
        Maps a language-independent static model element.

        Expected generic element kinds:

            class | interface | enum | function | callable

        The mapper avoids language-specific branches. Java, Python and future
        extractors should all produce this generic representation.
        """
        kind = element.get("kind") or element.get("type")

        if self._is_already_mapped_element(element):
            return

        if kind in {"class", "interface", "enum", "annotation", "annotation_type"}:
            parent = self._find_parent_compilation_unit(code_model, element)
            self._map_generic_class_like(parent, element)
            return

        if kind in {"function", "callable"}:
            parent = self._find_parent_compilation_unit(code_model, element)
            self._map_generic_function(parent, element)
            return

    def _find_parent_compilation_unit(self, code_model, element: dict):
        file_path = element.get("filePath") or element.get("file_path")

        if file_path and file_path in self.compilation_unit_by_path:
            return self.compilation_unit_by_path[file_path]

        return code_model

    def _generic_file_model(self, element_or_relation: dict):
        path = (
            element_or_relation.get("filePath")
            or element_or_relation.get("file_path")
            or element_or_relation.get("sourceFile")
            or element_or_relation.get("source_file")
            or element_or_relation.get("path")
        )

        return {"path": path} if path else {}

    def _map_generic_class_like(self, parent, element: dict):
        kind = element.get("kind") or element.get("type")
        name = element.get("name", "AnonymousClass")

        class_unit = self._create_class_like_unit(name, kind)
        self._append_code_element(parent, class_unit)

        file_model = self._generic_file_model(element)
        source_file = self._get_source_file(file_model)

        self.factory.add_source_region(
            class_unit,
            path=file_model.get("path"),
            language=self.language,
            start_line=element.get("line_start") or element.get("lineStart"),
            end_line=element.get("line_end") or element.get("lineEnd"),
            file_item=source_file,
        )

        self._apply_class_native_properties(class_unit, element)
        self._add_common_metadata(class_unit, element)
        if kind in {"interface", "annotation", "annotation_type", "enum"}:
            self.factory.add_attribute(class_unit, "element_kind", kind)
        self._add_native_annotations(class_unit, element)

        self._register(
            element.get("id")
            or element.get("qualifiedName")
            or element.get("qualified_name"),
            class_unit,
            element,
        )

        for field in element.get("fields", []):
            self._map_generic_field(class_unit, field, element)

        for method in element.get("methods", []):
            self._map_generic_method(class_unit, method, element)

    def _map_generic_function(self, parent, element: dict):
        callable_unit = self.factory.create_callable_unit(
            element.get("name", "anonymous_function")
        )
        self._append_code_element(parent, callable_unit)

        self._apply_callable_native_properties(callable_unit, element)

        file_model = self._generic_file_model(element)
        source_file = self._get_source_file(file_model)

        self.factory.add_source_region(
            callable_unit,
            path=file_model.get("path"),
            language=self.language,
            start_line=element.get("line_start") or element.get("lineStart"),
            end_line=element.get("line_end") or element.get("lineEnd"),
            file_item=source_file,
        )

        self._add_common_metadata(callable_unit, element)
        self._add_native_annotations(callable_unit, element)

        qualified_signature = (
            element.get("qualifiedSignature")
            or element.get("qualified_signature")
        )

        self._register(
            element.get("id") or qualified_signature,
            callable_unit,
            element,
        )
        self._register_callable_aliases(callable_unit, element, None)

        signature = self._create_callable_signature(
            owner=callable_unit,
            callable_model=element,
        )

        for param in element.get("parameters", []):
            self._map_generic_parameter(signature, param, element)

        self._map_return_parameter(signature, element)

    def _map_generic_field(self, parent, field: dict, owner_element: dict):
        existing = self._find_existing_storable(field, owner_element)
        if existing is not None:
            resolved_type_existing = field.get("resolvedType") or field.get("resolved_type")
            normalized_existing = dict(field)
            normalized_existing["resolved_type_id"] = self._infer_type_id(resolved_type_existing)
            normalized_existing["resolved_type_qualified_name"] = resolved_type_existing
            self._register_typable(existing, normalized_existing)
            self._register_storable(existing, normalized_existing, owner_element)
            self._register_storable_aliases(existing, normalized_existing, owner_element)
            return existing

        storable_unit = self.factory.create_storable_unit(
            field.get("name", "field")
        )
        self._append_code_element(parent, storable_unit)

        resolved_type = field.get("resolvedType") or field.get("resolved_type")

        self._apply_data_native_properties(
            storable_unit,
            field,
            default_kind="unknown",
        )
        self._add_native_annotations(storable_unit, field)

        normalized_field = dict(field)
        normalized_field["resolved_type_id"] = self._infer_type_id(resolved_type)
        normalized_field["resolved_type_qualified_name"] = resolved_type

        self._register_typable(storable_unit, normalized_field)
        self._register_storable(storable_unit, normalized_field, owner_element)
        self._register_storable_aliases(storable_unit, normalized_field, owner_element)

        owner_qn = (
            owner_element.get("qualifiedName")
            or owner_element.get("qualified_name")
            or owner_element.get("name")
        )

        if owner_qn and field.get("name"):
            field_key = f"{owner_qn}.{field.get('name')}"
            self.storable_index[field_key] = storable_unit
            self.id_index.setdefault(field_key, storable_unit)


    def _normalize_type_name_for_signature(self, type_name):
        """Normalize Java/Python type text for signature-based lookup."""
        if not type_name:
            return None
        text = self._strip_generic_arguments(type_name)
        if not text:
            return None
        text = str(text).strip()
        java_lang = {
            "String": "java.lang.String",
            "Long": "java.lang.Long",
            "Integer": "java.lang.Integer",
            "Boolean": "java.lang.Boolean",
            "Double": "java.lang.Double",
            "Float": "java.lang.Float",
            "Short": "java.lang.Short",
            "Byte": "java.lang.Byte",
            "Character": "java.lang.Character",
            "Object": "java.lang.Object",
            "RuntimeException": "java.lang.RuntimeException",
            "IllegalArgumentException": "java.lang.IllegalArgumentException",
            "IllegalStateException": "java.lang.IllegalStateException",
        }
        primitives = {
            "int": "int",
            "long": "long",
            "boolean": "boolean",
            "double": "double",
            "float": "float",
            "short": "short",
            "byte": "byte",
            "char": "char",
            "void": "void",
        }
        if self.language == "java":
            return java_lang.get(text) or primitives.get(text) or text
        if text.startswith("builtins."):
            return text.replace("builtins.", "")
        return text

    def _parameter_type_for_signature(self, param: dict):
        return self._normalize_type_name_for_signature(
            param.get("resolvedType")
            or param.get("resolved_type")
            or param.get("type")
            or param.get("annotation")
        )

    def _short_parameter_type_for_signature(self, type_name):
        if not type_name:
            return None
        text = self._strip_generic_arguments(type_name)
        if not text:
            return None
        text = str(text)
        return text.rsplit(".", 1)[-1]

    def _method_resolution_aliases(self, method: dict, owner_element: dict):
        """Return all useful lookup aliases for a MethodUnit/CallableUnit.

        Java relationships often use fully qualified signatures such as
        com.example.Service.find(java.lang.Long), whereas the Java extractor's
        method objects may only contain name + parameters or a short signature.
        Registering these aliases prevents calls from being dropped because the
        source/target cannot be found.
        """
        aliases = []

        def add(value):
            if value:
                text = str(value).strip()
                if text and text not in aliases:
                    aliases.append(text)

        owner_qn = None
        if owner_element:
            owner_qn = (
                owner_element.get("qualifiedName")
                or owner_element.get("qualified_name")
                or owner_element.get("safeQualifiedName")
                or owner_element.get("name")
            )

        name = method.get("name")
        add(method.get("id"))
        add(method.get("qualifiedName"))
        add(method.get("qualified_name"))
        add(method.get("qualifiedSignature"))
        add(method.get("qualified_signature"))

        params = method.get("parameters", []) or []
        full_types = []
        short_types = []
        for param in params:
            full_t = self._parameter_type_for_signature(param)
            short_t = self._short_parameter_type_for_signature(full_t)
            if full_t:
                full_types.append(full_t)
            if short_t:
                short_types.append(short_t)

        if owner_qn and name:
            add(f"{owner_qn}.{name}")
            add(f"{owner_qn}.{name}({','.join(full_types)})")
            add(f"{owner_qn}.{name}({','.join(short_types)})")
            # Java constructor signatures in relationships use <init>().
            if name in {"<init>", owner_qn.rsplit('.', 1)[-1]} or method.get("method_kind") == "constructor" or method.get("kind") == "constructor":
                add(f"{owner_qn}.<init>({','.join(full_types)})")
                add(f"{owner_qn}.<init>({','.join(short_types)})")

        signature = method.get("signature") or method.get("signatureText") or method.get("signature_text")
        if owner_qn and signature:
            sig = str(signature).strip()
            if sig:
                add(f"{owner_qn}.{sig}")

        return aliases

    def _register_callable_aliases(self, kdm_element, callable_model: dict, owner_element: dict = None):
        for alias in self._method_resolution_aliases(callable_model, owner_element):
            self.id_index.setdefault(alias, kdm_element)
            self.qualified_name_index.setdefault(alias, kdm_element)

    def _map_generic_method(self, parent, method: dict, owner_element: dict):
        method_unit = self.factory.create_method_unit(
            method.get("name", "anonymous_method")
        )
        self._append_code_element(parent, method_unit)

        self._apply_method_native_properties(method_unit, method)

        self._add_common_metadata(method_unit, method)
        self._add_native_annotations(method_unit, method)

        qualified_signature = (
            method.get("qualifiedSignature")
            or method.get("qualified_signature")
        )

        self._register(
            method.get("id") or qualified_signature,
            method_unit,
            method,
        )
        self._register_callable_aliases(method_unit, method, owner_element)

        signature = self._create_callable_signature(
            owner=method_unit,
            callable_model=method,
        )

        for param in method.get("parameters", []):
            self._map_generic_parameter(signature, param, method)

        self._map_return_parameter(signature, method)

        for local_var in (
            method.get("localVariables", [])
            or method.get("local_variables", [])
        ):
            self._map_generic_local_variable(method_unit, local_var, method, owner_element)

    def _map_generic_parameter(self, parent, param: dict, owner_callable: dict = None):
        parameter_unit = self.factory.create_parameter_unit(
            param.get("name", "param")
        )
        self._append_parameter_unit(parent, parameter_unit)

        resolved_type = (
            param.get("resolvedType")
            or param.get("resolved_type")
            or param.get("type")
        )

        self._apply_parameter_native_properties(parameter_unit, param)
        self._add_native_annotations(parameter_unit, param)

        normalized_param = dict(param)
        normalized_param["resolved_type_id"] = self._infer_type_id(resolved_type)
        normalized_param["resolved_type_qualified_name"] = resolved_type

        self._register_typable(parameter_unit, normalized_param)

        callable_qs = None
        if owner_callable:
            callable_qs = (
                owner_callable.get("qualifiedSignature")
                or owner_callable.get("qualified_signature")
                or owner_callable.get("id")
            )

        if callable_qs and param.get("name"):
            param_key = f"{callable_qs}:parameter:{param.get('name')}"
            self.id_index.setdefault(param_key, parameter_unit)
            # Parameters are intentionally not registered in storable_index:
            # Reads/Writes in this generator are restricted to StorableUnit.
            self.id_index.setdefault((callable_qs, "parameter", param.get("name")), parameter_unit)

    def _map_generic_local_variable(
        self,
        parent,
        local_var: dict,
        owner_callable: dict,
        owner_element: dict = None,
    ):
        """Maps Java/generic localVariables entries to StorableUnit."""

        storable_unit = self.factory.create_storable_unit(
            local_var.get("name", "local_variable")
        )
        self._append_code_element(parent, storable_unit)

        resolved_type = (
            local_var.get("resolvedType")
            or local_var.get("resolved_type")
            or local_var.get("assignedType")
            or local_var.get("assigned_type")
        )

        normalized_var = dict(local_var)
        normalized_var["resolved_type_id"] = self._infer_type_id(resolved_type)
        normalized_var["resolved_type_qualified_name"] = resolved_type

        self._register_typable(storable_unit, normalized_var)
        self._register_value_element(storable_unit, normalized_var, owner_callable)
        self._register_storable(storable_unit, normalized_var, owner_callable)

        callable_qs = (
            owner_callable.get("qualifiedSignature")
            or owner_callable.get("qualified_signature")
            or owner_callable.get("id")
        )

        if callable_qs and local_var.get("name"):
            self.storable_index.setdefault(
                (callable_qs, local_var.get("name")),
                storable_unit,
            )
            self.id_index.setdefault(
                f"{callable_qs}:local:{local_var.get('name')}",
                storable_unit,
            )

        file_model = self._generic_file_model(owner_element or owner_callable)
        source_file = self._get_source_file(file_model)
        line = local_var.get("line") or local_var.get("lineStart") or local_var.get("line_start")

        self.factory.add_source_region(
            storable_unit,
            path=file_model.get("path"),
            language=self.language,
            start_line=line,
            end_line=line,
            file_item=source_file,
        )

        self._apply_data_native_properties(
            storable_unit,
            local_var,
            default_kind="local",
        )
        self._add_native_annotations(storable_unit, local_var)



    # ------------------------------------------------------------------
    # Native KDM class/data metadata helpers
    # ------------------------------------------------------------------

    def _apply_class_native_properties(self, class_unit, class_model: dict):
        """
        Maps class-level JSON metadata to native KDM properties when
        available.

        Redundant extractor attributes such as element_kind, modifiers and
        annotations are intentionally not emitted as kdm:Attribute elements.
        """

        modifiers = set(class_model.get("modifiers", []) or [])

        if self.factory.has_feature(class_unit, "export"):
            class_unit.export = self._visibility_from_modifiers(modifiers)

        if self.factory.has_feature(class_unit, "isFinal"):
            class_unit.isFinal = "final" in modifiers

        if self.factory.has_feature(class_unit, "isAbstract"):
            class_unit.isAbstract = "abstract" in modifiers

    def _apply_data_native_properties(
        self,
        data_element,
        data_model: dict,
        default_kind: str = "unknown",
    ):
        """
        Maps variable, field and local-variable metadata to native KDM
        properties when supported by the concrete metaclass.

        Type information is handled by TypeRelationResolver through the native
        type reference and HasType. Annotations are represented as kdm:Annotation.
        """

        modifiers = set(data_model.get("modifiers", []) or [])

        if self.factory.has_feature(data_element, "kind"):
            data_element.kind = self._normalize_storable_kind(
                data_model.get("kind") or data_model.get("storableKind") or default_kind
            )

        if self.factory.has_feature(data_element, "export"):
            data_element.export = self._visibility_from_modifiers(modifiers)

        if self.factory.has_feature(data_element, "isStatic"):
            data_element.isStatic = "static" in modifiers

        if self.factory.has_feature(data_element, "isFinal"):
            data_element.isFinal = "final" in modifiers

    def _normalize_storable_kind(self, kind):
        if kind in {"global", "local", "external", "register", "unknown"}:
            return kind

        if kind in {"field", "member"}:
            # The current generator still represents fields as StorableUnit.
            # A future, stricter mapping can migrate Java fields to MemberUnit.
            return "unknown"

        return "unknown"


    # ------------------------------------------------------------------
    # Native KDM callable/signature helpers
    # ------------------------------------------------------------------

    def _create_callable_signature(self, owner, callable_model: dict):
        signature_name = (
            callable_model.get("signature")
            or callable_model.get("name")
            or "signature"
        )

        signature = self.factory.create_signature(signature_name)

        self._append_code_element(owner, signature)

        if self.factory.has_feature(owner, "type"):
            owner.type = signature

        # Do not attach SourceRegion directly to Signature.
        # The owning MethodUnit/CallableUnit already carries the source
        # traceability. Creating a second SourceRegion for Signature is fragile
        # in Python generic models because callable entries may not carry a
        # stable file/path context.

        callable_key = (
            callable_model.get("qualifiedSignature")
            or callable_model.get("qualified_signature")
            or callable_model.get("id")
            or callable_model.get("name")
        )

        if callable_key:
            self.id_index.setdefault(f"{callable_key}:signature", signature)

        return signature

    def _map_return_parameter(self, signature, callable_model: dict):
        resolved_return_type = (
            callable_model.get("resolvedReturnType")
            or callable_model.get("resolved_return_type")
            or callable_model.get("returnType")
            or callable_model.get("return_type")
        )

        if not resolved_return_type:
            return

        method_kind = callable_model.get("kind") or callable_model.get("method_kind")

        if method_kind == "constructor":
            return

        return_param = self.factory.create_parameter_unit("return")
        self._append_parameter_unit(signature, return_param)

        if self.factory.has_feature(return_param, "kind"):
            return_param.kind = "return"

        if self.factory.has_feature(return_param, "pos"):
            return_param.pos = 0

        normalized_return = {
            "name": f"{callable_model.get('name', 'callable')}:return",
            "resolved_type_id": self._infer_type_id(resolved_return_type),
            "resolved_type_qualified_name": resolved_return_type,
        }

        self._register_typable(return_param, normalized_return)

    def _append_parameter_unit(self, parent, parameter_unit):
        if parent is None or parameter_unit is None:
            return False

        if self.factory.has_feature(parent, "parameterUnit"):
            parent.parameterUnit.append(parameter_unit)
            return True

        return self._append_code_element(parent, parameter_unit)

    def _apply_method_native_properties(self, method_unit, method: dict):
        method_kind = method.get("kind") or method.get("method_kind") or "method"

        if self.factory.has_feature(method_unit, "kind"):
            method_unit.kind = self._normalize_method_kind(method_kind)

        modifiers = set(method.get("modifiers", []) or [])

        if self.factory.has_feature(method_unit, "export"):
            method_unit.export = self._visibility_from_modifiers(modifiers)

        if self.factory.has_feature(method_unit, "isStatic"):
            method_unit.isStatic = "static" in modifiers

        if self.factory.has_feature(method_unit, "isFinal"):
            method_unit.isFinal = "final" in modifiers

        if self.factory.has_feature(method_unit, "isAbstract"):
            method_unit.isAbstract = "abstract" in modifiers

    def _apply_callable_native_properties(self, callable_unit, callable_model: dict):
        callable_kind = (
            callable_model.get("callable_kind")
            or callable_model.get("kind")
            or "regular"
        )

        if self.factory.has_feature(callable_unit, "kind"):
            callable_unit.kind = self._normalize_callable_kind(callable_kind)

        modifiers = set(callable_model.get("modifiers", []) or [])

        if self.factory.has_feature(callable_unit, "isStatic"):
            callable_unit.isStatic = "static" in modifiers

    def _apply_parameter_native_properties(self, parameter_unit, param: dict):
        kind = param.get("kind") or "byValue"

        if self.factory.has_feature(parameter_unit, "kind"):
            parameter_unit.kind = self._normalize_parameter_kind(kind)

        index = param.get("index")

        if index is None:
            index = param.get("position")

        if index is not None and self.factory.has_feature(parameter_unit, "pos"):
            try:
                parameter_unit.pos = int(index) + 1
            except Exception:
                parameter_unit.pos = index

        modifiers = set(param.get("modifiers", []) or [])

        if self.factory.has_feature(parameter_unit, "isFinal"):
            parameter_unit.isFinal = "final" in modifiers

    def _normalize_method_kind(self, kind):
        if kind in {"method", "constructor", "destructor", "operator"}:
            return kind

        return "unknown"

    def _normalize_callable_kind(self, kind):
        if kind in {"regular", "external", "operator", "stored"}:
            return kind

        if kind == "function":
            return "regular"

        return "unknown"

    def _normalize_parameter_kind(self, kind):
        if kind in {
            "byValue",
            "byName",
            "byReference",
            "variadic",
            "return",
            "throws",
            "exception",
            "catchall",
        }:
            return kind

        return "byValue"

    def _visibility_from_modifiers(self, modifiers):
        if "public" in modifiers:
            return "public"

        if "private" in modifiers:
            return "private"

        if "protected" in modifiers:
            return "protected"

        return "unknown"

    def _add_native_annotations(self, kdm_element, model_element: dict):
        """
        Models Java annotations and Python decorators using KDM semantics.

        The primary representation is a native kdm:Annotation attached to the
        annotated element. In addition, when the element is extendable, the
        mapper adds a formal KDM extension:

        - ExtensionFamily: LanguageAnnotations
        - Stereotype: JavaAnnotationUsage or PythonDecoratorUsage
        - TaggedValue entries:
          annotation_name
          annotation_text
          annotation_value
          annotation_language

        This avoids representing annotations as loose kdm:Attribute entries.
        """

        normalized_annotations = self._normalize_annotation_entries(
            model_element.get("annotations", []) or model_element.get("decorators", []) or []
        )

        if not normalized_annotations:
            return

        stereotype, tag_defs = self._get_or_create_annotation_stereotype()

        if stereotype is not None:
            self.factory.add_stereotype_to_element(kdm_element, stereotype)

        for annotation in normalized_annotations:
            text = annotation["text"]
            name = annotation["name"]
            values = annotation.get("values") or {}

            self._add_annotation_text_once(kdm_element, text)

            if stereotype is not None and tag_defs:
                self.factory.add_tagged_value(
                    kdm_element,
                    tag_defs.get("annotation_name"),
                    name,
                )
                self.factory.add_tagged_value(
                    kdm_element,
                    tag_defs.get("annotation_text"),
                    text,
                )
                self.factory.add_tagged_value(
                    kdm_element,
                    tag_defs.get("annotation_language"),
                    self.language,
                )

                for key, value in values.items():
                    self.factory.add_tagged_value(
                        kdm_element,
                        tag_defs.get("annotation_value"),
                        f"{key}={value}",
                    )

    def _add_annotation_text_once(self, kdm_element, text: str):
        if kdm_element is None or not text:
            return None

        if not self.factory.has_feature(kdm_element, "annotation"):
            return None

        for existing in kdm_element.annotation:
            if getattr(existing, "text", None) == text:
                return existing

        if hasattr(self.factory, "add_annotation"):
            return self.factory.add_annotation(kdm_element, text)

        annotation_cls = getattr(self.factory, "Annotation", None)

        if annotation_cls is None:
            return None

        annotation = annotation_cls()

        if self.factory.has_feature(annotation, "text"):
            annotation.text = text

        kdm_element.annotation.append(annotation)
        return annotation

    def _get_or_create_annotation_stereotype(self):
        if self.segment is None:
            return None, None

        stereotype_name = (
            "JavaAnnotationUsage"
            if self.language == "java"
            else "PythonDecoratorUsage"
            if self.language == "python"
            else "SourceAnnotationUsage"
        )

        if stereotype_name in self.annotation_stereotypes:
            return self.annotation_stereotypes[stereotype_name]

        family = self._get_or_create_annotation_extension_family()

        if family is None:
            return None, None

        stereotype = None

        if self.factory.has_feature(family, "stereotype"):
            for existing in family.stereotype:
                if getattr(existing, "name", None) == stereotype_name:
                    stereotype = existing
                    break

        if stereotype is None:
            stereotype = self.factory.create_stereotype(
                stereotype_name,
                "code:CodeItem",
            )

            if self.factory.has_feature(family, "stereotype"):
                family.stereotype.append(stereotype)

        tag_defs = self._ensure_annotation_tag_definitions(stereotype)

        self.annotation_stereotypes[stereotype_name] = (stereotype, tag_defs)
        return stereotype, tag_defs

    def _get_or_create_annotation_extension_family(self):
        if self.annotation_extension_family is not None:
            return self.annotation_extension_family

        if self.segment is None:
            return None

        if not self.factory.has_feature(self.segment, "extensionFamily"):
            return None

        for family in self.segment.extensionFamily:
            if getattr(family, "name", None) == "LanguageAnnotations":
                self.annotation_extension_family = family
                return family

        family = self.factory.create_extension_family("LanguageAnnotations")
        self.segment.extensionFamily.append(family)
        self.annotation_extension_family = family
        return family

    def _ensure_annotation_tag_definitions(self, stereotype):
        if stereotype is None or not self.factory.has_feature(stereotype, "tag"):
            return {}

        required = {
            "annotation_name": "String",
            "annotation_text": "String",
            "annotation_value": "String",
            "annotation_language": "String",
        }

        tag_defs = {}

        for existing in stereotype.tag:
            tag_name = getattr(existing, "tag", None)
            if tag_name in required:
                tag_defs[tag_name] = existing

        for tag_name, value_type in required.items():
            if tag_name in tag_defs:
                continue

            tag_definition = self.factory.create_tag_definition(
                tag_name,
                value_type,
            )
            stereotype.tag.append(tag_definition)
            tag_defs[tag_name] = tag_definition

        return tag_defs

    def _normalize_annotation_entries(self, annotations):
        normalized = []

        for annotation in annotations:
            parsed = self._normalize_single_annotation(annotation)

            if parsed is not None:
                normalized.append(parsed)

        return normalized

    def _normalize_single_annotation(self, annotation):
        if isinstance(annotation, dict):
            name = (
                annotation.get("name")
                or annotation.get("qualifiedName")
                or annotation.get("qualified_name")
                or annotation.get("type")
            )

            values = (
                annotation.get("values")
                or annotation.get("arguments")
                or annotation.get("members")
                or {}
            )

            if isinstance(values, list):
                values = {
                    str(index): value
                    for index, value in enumerate(values)
                }

            if values is None:
                values = {}

            if not isinstance(values, dict):
                values = {"value": values}

            if not name:
                text = str(annotation)
                name = text
            else:
                text = self._format_annotation_text(name, values)

            return {
                "name": str(name).lstrip("@"),
                "text": text,
                "values": {
                    str(key): str(value)
                    for key, value in values.items()
                },
            }

        text = str(annotation).strip()

        if not text:
            return None

        if not text.startswith("@"):
            text = f"@{text}"

        name, values = self._parse_annotation_text(text)

        return {
            "name": name,
            "text": text,
            "values": values,
        }

    def _parse_annotation_text(self, text: str):
        clean_text = text.strip()

        if clean_text.startswith("@"):
            clean_text = clean_text[1:]

        if "(" not in clean_text:
            return clean_text, {}

        name, raw_values = clean_text.split("(", 1)
        raw_values = raw_values.rsplit(")", 1)[0].strip()

        values = {}

        if raw_values:
            parts = self._split_annotation_arguments(raw_values)

            for index, part in enumerate(parts):
                if "=" in part:
                    key, value = part.split("=", 1)
                    values[key.strip()] = value.strip().strip('"')
                else:
                    values[str(index)] = part.strip().strip('"')

        return name.strip(), values

    def _split_annotation_arguments(self, raw_values: str):
        parts = []
        current = []
        depth = 0
        in_string = False
        quote = None

        for char in raw_values:
            if in_string:
                current.append(char)

                if char == quote:
                    in_string = False

                continue

            if char in {"'", '"'}:
                in_string = True
                quote = char
                current.append(char)
                continue

            if char in {"(", "{", "["}:
                depth += 1
                current.append(char)
                continue

            if char in {")", "}", "]"}:
                depth = max(0, depth - 1)
                current.append(char)
                continue

            if char == "," and depth == 0:
                parts.append("".join(current).strip())
                current = []
                continue

            current.append(char)

        if current:
            parts.append("".join(current).strip())

        return parts

    def _format_annotation_text(self, name: str, values: dict):
        clean_name = str(name).lstrip("@")

        if not values:
            return f"@{clean_name}"

        formatted_values = ", ".join(
            f"{key}={value}"
            for key, value in values.items()
        )

        return f"@{clean_name}({formatted_values})"



    def _map_generic_relationships(self, data: dict):
        relationships = data.get("relationships", [])

        if not relationships:
            return

        for relationship in relationships:
            relation_type = relationship.get("type")

            if relation_type == "calls":
                self._map_generic_calls_relationship(relationship)
            elif relation_type == "imports":
                self._map_generic_imports_relationship(relationship)
            elif relation_type == "extends":
                self._map_generic_extends_relationship(relationship)
            elif relation_type == "implements":
                self._map_generic_implements_relationship(relationship)
            elif relation_type == "uses_type":
                self._map_generic_uses_type_relationship(relationship)
            elif relation_type == "reads":
                self._map_generic_access_relationship(relationship, access_kind="reads")
            elif relation_type == "writes":
                self._map_generic_access_relationship(relationship, access_kind="writes")
            elif relation_type == "creates":
                self._map_generic_creates_relationship(relationship)
            elif relation_type == "throws":
                self._map_generic_throws_relationship(relationship)

    def _call_relation_key(self, source_key, target_key, line=None):
        return (str(source_key or ""), str(target_key or ""), str(line or ""))

    def _map_generic_calls_relationship(self, relationship: dict):
        source_key = relationship.get("source")
        target_key = relationship.get("target")
        line = (
            relationship.get("line")
            or relationship.get("lineStart")
            or relationship.get("line_start")
        )
        relation_key = self._call_relation_key(source_key, target_key, line)
        if relation_key in self._mapped_call_keys:
            return

        source = self._resolve_indexed_element(source_key)
        target = self._resolve_indexed_element(target_key)

        if source is None:
            return

        # KDM action::Calls must originate from an ActionElement contained in
        # an executable body.  If a relationship source resolves to a data,
        # package or compilation unit, keep the model valid by omitting only
        # that invalid relationship.
        if not self._can_own_action_body(source):
            return

        body_block = self._get_or_create_callable_body(source)

        action = self.factory.create_action_element(
            name=self._call_action_name(target_key),
            kind="call",
        )

        file_model = self._generic_file_model(relationship)
        source_file = self._get_source_file(file_model)

        self.factory.add_source_region(
            action,
            path=file_model.get("path"),
            language=self.language,
            start_line=line,
            end_line=line,
            file_item=source_file,
        )

        self._append_code_element(body_block, action)

        if target is None:
            target = self._get_or_create_external_call_target(
                target_key=target_key,
                relationship=relationship,
            )

        if target is not None:
            calls_relation = self.factory.create_calls_relation(target)
            self._append_action_relation(action, calls_relation)
            self._mapped_call_keys.add(relation_key)

    def _get_or_create_external_call_target(self, target_key, relationship: dict):
        """
        Creates a conservative external CallableUnit for a call target that is
        outside the analyzed project.

        This avoids storing temporary attributes such as resolution_status or
        unresolved_target_name. If no target key is available, the call remains
        without a Calls relation rather than inventing an unreliable target.
        """

        if not target_key or self.external_builder is None:
            return None

        target_name = str(target_key)

        call_model = {
            "name": target_name,
            "target_id": target_name,
            "classification": "external",
            "kind": "call",
        }

        return self.external_builder.get_or_create_external_target(call_model)

    def _get_or_create_external_import_relationship_target(self, relationship: dict):
        if self.external_builder is None:
            return None
        target_key = relationship.get("target")
        if not target_key:
            return None
        target_text = str(target_key)

        # Java imports usually point to a type (java.util.List,
        # java.lang.annotation.Retention, com.example.Foo).  Represent such
        # targets as external Datatype/ClassUnit/InterfaceUnit elements rather
        # than as loose imported callables.  This is also safe for other
        # languages when the target is a qualified type-like name.
        simple_name = target_text.rsplit(".", 1)[-1] if "." in target_text else target_text
        target_type = relationship.get("targetType") or relationship.get("target_type")
        looks_like_type = bool(simple_name[:1].isupper()) or target_type in {"class", "interface", "annotation", "enum"}
        if looks_like_type or target_text.startswith(("java.", "javax.")):
            kind = target_type or "class"
            type_model = {
                "qualifiedName": target_text,
                "packageName": target_text.rsplit(".", 1)[0] if "." in target_text else "ExternalUnresolved",
                "name": simple_name,
                "kind": kind,
                "external": True,
            }
            target = self.external_builder.get_or_create_external_type(type_model)
        else:
            import_model = {
                "module": target_text.rsplit(".", 1)[0] if "." in target_text else target_text,
                "name": target_text.rsplit(".", 1)[-1] if "." in target_text else None,
                "target_type": target_type,
                "classification": "external",
            }
            target = self.external_builder.get_or_create_external_import_target(import_model)

        if target is not None:
            self.id_index.setdefault(target_text, target)
            self.qualified_name_index.setdefault(target_text, target)
        return target


    def _import_relation_key(self, source_key, target_key, line=None):
        # One KDM Imports relation per source artifact and imported target.
        # Ignore line to de-duplicate the same import when it is provided both
        # by files[].imports and relationships[type=imports].
        return (str(source_key or ""), str(target_key or ""))

    def _map_file_level_imports(self, data: dict):
        for file_model in data.get("files", []) or []:
            source_key = file_model.get("path") or file_model.get("id") or file_model.get("qualifiedName") or file_model.get("qualified_name")
            imports = file_model.get("imports", []) or []
            for imported in imports:
                if isinstance(imported, dict):
                    target_key = (
                        imported.get("target_qualified_name")
                        or imported.get("targetQualifiedName")
                        or imported.get("resolved_module_qualified_name")
                        or imported.get("resolvedModuleQualifiedName")
                    )
                    if not target_key:
                        module = imported.get("module") or imported.get("imported_module") or imported.get("importedModule")
                        name = imported.get("name") or imported.get("imported_name") or imported.get("importedName")
                        if module and name:
                            target_key = f"{module}.{name}"
                        else:
                            target_key = module or name
                    line = imported.get("line")
                    target_type = imported.get("target_type") or imported.get("targetType")
                else:
                    target_key = str(imported)
                    line = None
                    target_type = None

                if not source_key or not target_key:
                    continue

                self._map_generic_imports_relationship(
                    {
                        "type": "imports",
                        "source": source_key,
                        "target": target_key,
                        "sourceFile": file_model.get("path"),
                        "line": line,
                        "targetType": target_type,
                    }
                )

    def _map_generic_imports_relationship(self, relationship: dict):
        source_key = relationship.get("source")
        target_key = relationship.get("target")
        line = relationship.get("line") or relationship.get("lineStart") or relationship.get("line_start")
        relation_key = self._import_relation_key(source_key, target_key, line)
        if relation_key in self._mapped_import_keys:
            return

        # Imports in the common schema are usually declared by source-file path.
        # Prefer the CompilationUnit associated with that path instead of any
        # previously indexed artifact with the same string.  This avoids losing
        # file-level Java imports if the path is also represented elsewhere
        # (for example in inventory/source references).
        source = None
        source_text = str(source_key or "")
        if source_text:
            source = self.compilation_unit_by_path.get(source_text)
            if source is None:
                source_norm = source_text.replace("\\", "/")
                for known_path, compilation_unit in self.compilation_unit_by_path.items():
                    known_norm = str(known_path).replace("\\", "/")
                    if known_norm == source_norm or known_norm.endswith("/" + source_norm.split("/")[-1]):
                        source = compilation_unit
                        break

        if source is None:
            source = self._resolve_indexed_element(source_key)

        # A valid KDM Imports relation must be contained by an element with
        # codeRelation.  If the resolved source is not a CodeItem capable of
        # owning codeRelation, fall back to the sourceFile path.
        if source is not None and not self.factory.has_feature(source, "codeRelation"):
            file_model_for_source = self._generic_file_model(relationship)
            file_path = file_model_for_source.get("path")
            if file_path:
                source = self.compilation_unit_by_path.get(str(file_path), source)

        if source is None or not self.factory.has_feature(source, "codeRelation"):
            return

        target = self._resolve_indexed_element(target_key)
        if target is None:
            target = self._get_or_create_external_import_relationship_target(relationship)

        if target is None:
            return

        imports_relation = self.factory.create_imports_relation(target)

        file_model = self._generic_file_model(relationship)
        source_file = self._get_source_file(file_model)

        self.factory.add_source_region(
            imports_relation,
            path=file_model.get("path"),
            language=self.language,
            start_line=line,
            end_line=line,
            file_item=source_file,
        )

        if self._append_code_relation(source, imports_relation):
            self._mapped_import_keys.add(relation_key)

    def _map_generic_extends_relationship(self, relationship: dict):
        source = self._resolve_indexed_element(relationship.get("source"))
        target = self._resolve_indexed_element(relationship.get("target"))

        if source is None:
            return

        if target is None:
            target = self._resolve_or_create_external_type(relationship.get("target"))

        if target is None:
            return

        # KDM code::Extends.to is typed as code::Datatype.  In dynamic
        # Python models, some inferred extends-like relations may point to
        # callables, functions, modules, or decorators.  Those are useful for
        # analysis, but they are not valid KDM inheritance targets.  Only
        # emit Extends when both endpoints can legally participate as KDM
        # datatype/class-like elements.
        if not self._is_kdm_datatype(source) or not self._is_kdm_datatype(target):
            return

        extends_relation = self.factory.create_extends_relation(target)
        self._append_code_relation(source, extends_relation)

    def _map_generic_implements_relationship(self, relationship: dict):
        source = self._resolve_indexed_element(relationship.get("source"))
        target = self._resolve_indexed_element(relationship.get("target"))

        if source is None:
            return

        if target is None:
            target = self._resolve_or_create_external_type(relationship.get("target"))

        if target is None:
            return

        # code::Implements also targets interface/class-like datatypes in this
        # KDM Ecore.  Skip relations that resolved to CallableUnit, MethodUnit,
        # Package, CompilationUnit, etc.
        if not self._is_kdm_datatype(source) or not self._is_kdm_datatype(target):
            return

        implements_relation = self.factory.create_implements_relation(target)
        self._append_code_relation(source, implements_relation)

    def _map_generic_uses_type_relationship(self, relationship: dict):
        """Map explicit common-schema uses_type relations to code::HasType."""
        source = self._resolve_indexed_element(relationship.get("source"))
        if source is None:
            return

        target = self._resolve_indexed_element(relationship.get("target"))
        if target is None:
            target = self._resolve_or_create_external_type(relationship.get("target"))

        if target is None:
            return

        # KDM code::HasType.to is typed as code::Datatype.
        # The common JSON schema may contain uses_type relations whose target
        # is a function, method, package, module, or another non-datatype
        # element, especially in dynamic Python projects.  Creating HasType to
        # those elements is invalid in the KDM metamodel and raises a PyEcore
        # BadValueError.  Therefore, only emit HasType when the resolved target
        # is a Datatype, e.g. ClassUnit, InterfaceUnit, or another Datatype
        # specialization. Calls to functions remain represented by Calls/Writes,
        # not by HasType.
        if not self._is_kdm_datatype(target):
            return

        if not self.factory.has_feature(source, "codeRelation"):
            return

        # Avoid obvious duplicates.
        for existing in getattr(source, "codeRelation", []):
            if getattr(existing.eClass, "name", None) == "HasType" and getattr(existing, "to", None) is target:
                return

        has_type_relation = self.factory.create_has_type_relation(target)
        self._append_code_relation(source, has_type_relation)

    def _map_generic_access_relationship(self, relationship: dict, access_kind: str):
        source = self._resolve_indexed_element(relationship.get("source"))

        if source is None:
            return

        action = self._get_or_create_relationship_action(
            source=source,
            relationship=relationship,
            default_name=access_kind,
            default_kind=access_kind,
        )

        if action is None:
            return

        target = self._resolve_access_target(
            relationship.get("target"),
            relationship.get("source"),
        )

        if target is None:
            return


        # KDM access relations are intentionally restricted by the validator
        # to StorableUnit targets. The generic JSON index may also resolve a
        # reference to ParameterUnit, especially in Python projects where
        # parameters are indexed as addressable elements. Creating Reads/Writes
        # to ParameterUnit makes the KDM invalid, so we skip those generic
        # access relations here. Parameter types are still represented through
        # ParameterUnit + HasType.
        if not self._is_valid_access_target(target):
            return


        if access_kind == "reads":
            relation = self.factory.create_reads_relation(target)
        else:
            relation = self.factory.create_writes_relation(target)

        self._append_action_relation(action, relation)


    def _is_valid_access_target(self, target) -> bool:
        """Return True only for KDM targets valid for Reads/Writes."""

        if target is None:
            return False

        try:
            return target.eClass.name == "StorableUnit"
        except AttributeError:
            return False

    def _map_generic_creates_relationship(self, relationship: dict):
        source = self._resolve_indexed_element(relationship.get("source"))

        if source is None:
            return

        action = self._get_or_create_relationship_action(
            source=source,
            relationship=relationship,
            default_name=self._call_action_name(relationship.get("target")),
            default_kind="constructor",
        )

        if action is None:
            return

        target = self._resolve_indexed_element(relationship.get("target"))

        if target is None:
            target = self._resolve_or_create_external_type(relationship.get("target"))

        if target is None:
            return

        creates_relation = self.factory.create_creates_relation(target)
        self._append_action_relation(action, creates_relation)

    def _map_generic_throws_relationship(self, relationship: dict):
        source = self._resolve_indexed_element(relationship.get("source"))

        if source is None:
            return

        action = self._get_or_create_relationship_action(
            source=source,
            relationship=relationship,
            default_name="throw",
            default_kind="throw",
        )

        if action is None:
            return

        target_key = relationship.get("target")
        target = self._resolve_indexed_element(target_key)

        if target is None:
            target = self._resolve_or_create_external_type(target_key)

        # KDM action::Throws.to is typed as DataElement. The normalized JSON
        # usually points to an exception *type* (ClassUnit/InterfaceUnit), which
        # cannot be assigned directly. Create a StorableUnit that represents the
        # thrown exception object and, when possible, type it with HasType.
        if target is not None and self._is_kdm_data_element(target):
            exception_data = target
        else:
            exception_data = self._get_or_create_thrown_exception_data(
                action=action,
                target_key=target_key,
                target_element=target,
            )

        if exception_data is None:
            self.factory.add_attributes_from_dict(
                action,
                {
                    "unresolved_throw_target": target_key,
                },
            )
            return

        throws_relation = self.factory.create_throws_relation(exception_data)
        self._append_action_relation(action, throws_relation)

    # ------------------------------------------------------------------
    # Callable bodies and calls
    # ------------------------------------------------------------------

    def _get_or_create_relationship_action(
        self,
        source,
        relationship: dict,
        default_name: str,
        default_kind: str,
    ):
        # Only ControlElement-like callables can contain executable BlockUnit
        # bodies. Some generic reads/writes relationships in the common schema
        # may have a StorableUnit/DataElement as source (for example an attribute
        # reading another value). DataElement also has a codeElement feature in
        # KDM, but that feature is typed to Datatype, so appending BlockUnit to
        # it raises a PyEcore BadValueError. In those cases we simply skip the
        # synthetic action; field-level access relations are not executable
        # actions in KDM.
        if not self._can_own_action_body(source):
            return None

        body_block = self._get_or_create_callable_body(source)
        if body_block is None:
            return None

        line = (
            relationship.get("line")
            or relationship.get("lineStart")
            or relationship.get("line_start")
        )

        action = self._find_body_action_by_line(body_block, line)

        if action is not None:
            return action

        action = self.factory.create_action_element(
            name=default_name or default_kind or "action",
            kind=default_kind or "action",
        )

        file_model = self._generic_file_model(relationship)
        source_file = self._get_source_file(file_model)

        self.factory.add_source_region(
            action,
            path=file_model.get("path"),
            language=self.language,
            start_line=line,
            end_line=line,
            file_item=source_file,
        )

        self._append_code_element(body_block, action)
        return action

    def _find_body_action_by_line(self, body_block, line):
        if body_block is None or line is None:
            return None

        if not self.factory.has_feature(body_block, "codeElement"):
            return None

        for child in body_block.codeElement:
            if getattr(child.eClass, "name", None) != "ActionElement":
                continue

            for source_ref in getattr(child, "source", []):
                for region in getattr(source_ref, "region", []):
                    if getattr(region, "startLine", None) == line:
                        return child

        return None

    def _resolve_access_target(self, target_name, source_key=None):
        if not target_name:
            return None

        target = self._resolve_indexed_element(target_name)
        if target is not None:
            return target

        if source_key:
            for key in (
                (source_key, target_name),
                f"{source_key}:parameter:{target_name}",
                f"{source_key}:local:{target_name}",
            ):
                target = self.storable_index.get(key) or self.id_index.get(key)
                if target is not None:
                    return target

        simple_target = str(target_name)

        if simple_target.startswith("this."):
            field_name = simple_target.split(".", 1)[1]
            owner_qn = self._owner_qualified_name_from_callable(source_key)
            if owner_qn:
                target = self.storable_index.get(f"{owner_qn}.{field_name}")
                if target is not None:
                    return target
            simple_target = field_name

        return self.storable_index.get(simple_target) or self.id_index.get(simple_target)

    def _owner_qualified_name_from_callable(self, source_key):
        if not source_key or not isinstance(source_key, str):
            return None

        if ".<init>" in source_key:
            return source_key.split(".<init>", 1)[0]

        before_args = source_key.split("(", 1)[0]
        if "." not in before_args:
            return None

        return before_args.rsplit(".", 1)[0]


    def _can_own_action_body(self, element) -> bool:
        """Return True if element can legally contain BlockUnit/ActionElement.

        MethodUnit and CallableUnit are ControlElement specializations and can
        contain BlockUnit in their codeElement containment. DataElement
        specializations such as StorableUnit also expose a codeElement feature
        in the KDM Ecore model, but that feature expects Datatype children and
        cannot contain BlockUnit.
        """
        if element is None:
            return False
        try:
            return element.eClass.name in {"MethodUnit", "CallableUnit"}
        except AttributeError:
            return False

    def _get_or_create_callable_body(self, callable_unit):
        """
        Returns the body BlockUnit of a MethodUnit or CallableUnit.

        KDM validation requires executable ActionElement nodes to be contained
        in a BlockUnit, not directly inside MethodUnit or CallableUnit.
        """
        if not self.factory.has_feature(callable_unit, "codeElement"):
            return callable_unit

        for child in callable_unit.codeElement:
            if child.eClass.name == "BlockUnit":
                return child

        block = self.factory.create_block_unit(name="body", kind="body")

        self.factory.add_attributes_from_dict(
            block,
            {
                "role": "callable_body",
            },
        )

        callable_unit.codeElement.append(block)

        return block

    def _call_action_name(self, target_key: str):
        """
        Extracts the called method name from a qualified signature.

        Example:
            com.example.Repository.findNameById(java.lang.Long)

        must become:
            findNameById

        A naive rsplit('.', 1) fails because parameter types may also contain
        dots, e.g. java.lang.Long.
        """
        if not target_key:
            return "call"

        signature = str(target_key)

        if "(" in signature:
            before_params = signature.split("(", 1)[0]
        else:
            before_params = signature

        method_name = before_params.rsplit(".", 1)[-1]

        return method_name or "call"

    # ------------------------------------------------------------------
    # Resolution helpers
    # ------------------------------------------------------------------

    def _resolve_indexed_element(self, key: str):
        if not key:
            return None

        if key in self.id_index:
            return self.id_index[key]

        if key in self.qualified_name_index:
            return self.qualified_name_index[key]

        if self.external_builder is not None:
            external = self.external_builder.external_targets.get(key)
            if external is not None:
                return external
            external = self.external_builder.external_targets.get(f"external_type:{key}")
            if external is not None:
                return external

        simple_name = key.split(".")[-1]
        candidates = self.class_name_index.get(simple_name, [])

        if len(candidates) == 1:
            return candidates[0]

        return None

    def _infer_type_id(self, qualified_name: str):
        if not qualified_name:
            return None

        primitive_or_builtin = {
            "int",
            "long",
            "short",
            "byte",
            "float",
            "double",
            "boolean",
            "char",
            "void",
            "str",
            "string",
            "bool",
            "None",
            "NoneType",
        }

        if qualified_name in primitive_or_builtin:
            return f"builtin_type:{qualified_name}"

        if qualified_name.startswith("java.lang."):
            java_name = qualified_name.replace("java.lang.", "")

            if java_name in {
                "String",
                "Integer",
                "Long",
                "Boolean",
                "Float",
                "Double",
                "Short",
                "Byte",
                "Character",
            }:
                return f"external_type:{qualified_name}"

        return f"external_type:{qualified_name}"

    # ------------------------------------------------------------------
    # Callable and signature metadata
    # ------------------------------------------------------------------

    def _add_callable_signature_metadata(self, callable_unit, callable_model: dict):
        """
        Deprecated compatibility hook.

        Callable and method signatures are represented with native
        code:Signature and code:ParameterUnit elements. Python decorators are
        represented by _add_native_annotations using kdm:Annotation,
        Stereotype and TaggedValue.
        """
        return

    def _add_decorator_metadata(self, kdm_element, model_element: dict):
        """
        Deprecated compatibility hook.

        Do not emit Attribute tag="decorators" or tag="decorator_N".
        Decorators are represented by _add_native_annotations.
        """
        self._add_native_annotations(kdm_element, model_element)


    # ------------------------------------------------------------------
    # Registration helpers
    # ------------------------------------------------------------------

    def _register_typable(self, kdm_element, source_model: dict):
        if not source_model:
            return

        self.typable_elements.append(
            {
                "kdm_element": kdm_element,
                "source_model": source_model,
            }
        )

    def _register_value_element(
        self,
        kdm_element,
        source_model: dict,
        owner_model: dict = None,
    ):
        self.value_elements.append(
            {
                "kdm_element": kdm_element,
                "source_model": source_model,
                "owner_id": owner_model.get("id") if owner_model else None,
            }
        )

    def _get_source_file(self, file_model: dict):
        if self.inventory_builder is None:
            return None

        return self.inventory_builder.get_source_file_by_path(
            file_model.get("path")
        )

    def _register_storable(self, storable_unit, var: dict, owner_model: dict = None):
        keys = set()

        name = var.get("name")
        full_name = var.get("full_name")
        defined_in = var.get("defined_in")
        owner_id = owner_model.get("id") if owner_model else None
        owner_qn = None

        if owner_model:
            owner_qn = (
                owner_model.get("qualifiedName")
                or owner_model.get("qualified_name")
                or owner_model.get("qualifiedSignature")
                or owner_model.get("qualified_signature")
            )

        if name:
            keys.add(name)

        if full_name:
            keys.add(full_name)

        if defined_in and name:
            keys.add(f"{defined_in}.{name}")

        if owner_id and name:
            keys.add((owner_id, name))

        if owner_id and full_name:
            keys.add((owner_id, full_name))

        if owner_qn and name:
            keys.add(f"{owner_qn}.{name}")

        for key in keys:
            self.storable_index[key] = storable_unit
            self.id_index.setdefault(key, storable_unit)
