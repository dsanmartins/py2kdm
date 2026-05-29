class ExternalModelBuilder:
    """
    Builds and reuses KDM elements for external libraries, builtins,
    external types, and unresolved external calls/imports.

    For Java projects this builder is intentionally conservative: it avoids
    promoting local variables, receivers, temporary expressions, literals, and
    method-call expressions to elements of ExternalLibraries_CodeModel. Those
    unresolved values should remain traceability information in the source
    ActionElement, not artificial external CompilationUnits.
    """

    JAVA_RESERVED_OR_NON_TYPES = {
        "this",
        "super",
        "null",
        "true",
        "false",
        "void",
        "return",
        "new",
    }

    JAVA_PRIMITIVE_TYPES = {
        "byte",
        "short",
        "int",
        "long",
        "float",
        "double",
        "boolean",
        "char",
        "void",
    }

    JAVA_LANG_TYPES = {
        "Object",
        "String",
        "StringBuilder",
        "StringBuffer",
        "Boolean",
        "Byte",
        "Short",
        "Integer",
        "Long",
        "Float",
        "Double",
        "Character",
        "CharSequence",
        "Class",
        "Enum",
        "Exception",
        "RuntimeException",
        "Throwable",
        "Error",
        "System",
        "Math",
        "Thread",
        "Runnable",
        "Iterable",
        "Comparable",
    }

    JAVA_EXTERNAL_PACKAGE_ROOTS = {
        "java",
        "javax",
        "android",
        "androidx",
        "org",
        "com",
        "net",
        "io",
        "kotlin",
        "junit",
    }

    def __init__(self, factory, segment, language="unknown"):
        self.factory = factory
        self.segment = segment
        self.language = str(language or "unknown").lower()

        self.external_code_model = None
        self.library_units = {}
        self.external_targets = {}

        # Populated from the intermediate model. These sets prevent internal
        # project classes and methods from being promoted to
        # ExternalLibraries_CodeModel when Java type resolution is incomplete.
        self.internal_type_names = set()
        self.internal_qualified_type_names = set()
        self.internal_callable_names = set()
        self.project_package_roots = set()
        self.imported_type_to_package = {}

    def ensure_external_model(self):
        if self.external_code_model is None:
            self.external_code_model = self.factory.create_code_model(
                "ExternalLibraries_CodeModel"
            )
            self.segment.model.append(self.external_code_model)

        return self.external_code_model


    def configure_from_project_model(self, data: dict):
        """
        Indexes internal Java symbols before external targets are created.

        The Java extractor may emit unresolved type identifiers such as
        ``external_type:MyDbHelper`` even when ``MyDbHelper`` is part of the
        analysed project. Without this index, those names are incorrectly
        materialized under ExternalLibraries_CodeModel.
        """

        if not isinstance(data, dict):
            return

        for element in data.get("elements", []) or []:
            self._register_internal_element(element)

        for file_model in data.get("files", []) or []:
            for cls in file_model.get("classes", []) or []:
                self._register_internal_element(cls)
            for interface in file_model.get("interfaces", []) or []:
                self._register_internal_element(interface)
            for enum in file_model.get("enums", []) or []:
                self._register_internal_element(enum)
            for function in file_model.get("functions", []) or []:
                name = function.get("name")
                if name:
                    self.internal_callable_names.add(str(name))

            for import_model in file_model.get("imports", []) or []:
                self._register_import(import_model)

    def _register_internal_element(self, element: dict):
        if not isinstance(element, dict):
            return

        kind = str(element.get("kind") or element.get("type") or "").lower()
        if kind and kind not in {"class", "interface", "enum", "enumeration", "classunit", "interfaceunit"}:
            # Methods are handled separately below.
            pass

        name = element.get("name")
        qualified_name = (
            element.get("qualifiedName")
            or element.get("qualified_name")
            or element.get("fullyQualifiedName")
        )

        if name:
            self.internal_type_names.add(str(name))

        if qualified_name:
            qualified_name = str(qualified_name)
            self.internal_qualified_type_names.add(qualified_name)
            parts = [part for part in qualified_name.split(".") if part]
            if len(parts) > 1:
                self.project_package_roots.add(parts[0])

        for method in element.get("methods", []) or []:
            method_name = method.get("name")
            if method_name:
                self.internal_callable_names.add(str(method_name))

    def _register_import(self, import_model):
        if isinstance(import_model, str):
            import_name = import_model.strip()
        elif isinstance(import_model, dict):
            if import_model.get("module") and import_model.get("name"):
                import_name = f"{import_model.get('module')}.{import_model.get('name')}"
            else:
                import_name = (
                    import_model.get("qualifiedName")
                    or import_model.get("qualified_name")
                    or import_model.get("imported")
                    or import_model.get("import")
                    or import_model.get("module")
                    or import_model.get("name")
                    or ""
                )
            import_name = str(import_name).strip()
        else:
            return

        if not import_name or import_name.endswith(".*"):
            return

        parts = [part for part in import_name.split(".") if part]
        if len(parts) < 2:
            return

        simple_name = parts[-1]
        package_name = ".".join(parts[:-1])

        if simple_name[:1].isupper():
            self.imported_type_to_package[simple_name] = package_name

    def get_or_create_external_target(self, call: dict):
        """
        Returns a KDM target for an external call.
        If the target does not exist yet, it is created.

        In Java mode, unresolved calls on local receivers such as mDb.insert(),
        values.put(), context.getResources(), or c.getString() are not promoted
        to external library roots because the receiver is a variable, not a
        package or type. This keeps ExternalLibraries_CodeModel focused on real
        external APIs and classes.
        """

        if self.language == "java" and not self._is_valid_java_external_call(call):
            return None

        library_name = self._infer_library_name(call)
        target_name = self._infer_target_name(call)
        target_kind = self._infer_target_kind(call)

        if self.language == "java":
            if target_kind == "class":
                target_name = self._normalize_java_type_name(target_name)
            else:
                target_name = self._normalize_java_callable_name(target_name)

            if not self._is_valid_java_external_library_name(library_name):
                library_name = "external_calls" if target_kind == "callable" else "unknown_external"

            if self._is_project_internal_type(target_name):
                return None

            # Java body mapping still needs native action::Calls relations even
            # when the exact target method cannot be resolved to a project
            # MethodUnit.  In that case, materialize a conservative external
            # CallableUnit under ExternalLibraries_CodeModel/external_calls.
            # This preserves KDM call semantics without promoting local
            # variables or receivers to external classes.
            if target_kind == "callable":
                if not self._looks_like_java_callable_reference(target_name):
                    return None
                if target_name in self.internal_callable_names:
                    return None
                if library_name in {"java.lang", "unknown_external", "external"}:
                    library_name = "external_calls"

            if target_kind == "class" and not self._looks_like_java_type_reference(target_name):
                return None

            if target_kind == "class" and library_name == "java.lang" and target_name not in self.JAVA_LANG_TYPES:
                return None

        key = f"{library_name}:{target_kind}:{target_name}"

        if key in self.external_targets:
            return self.external_targets[key]

        external_model = self.ensure_external_model()
        library_unit = self._get_or_create_library_unit(external_model, library_name)

        if target_kind == "class":
            target = self.factory.create_class_unit(target_name)
        else:
            target = self.factory.create_callable_unit(target_name)

        self.factory.add_attribute(target, "external", "true")
        self.factory.add_attribute(target, "external_kind", target_kind)
        self.factory.add_attribute(target, "library", library_name)

        library_unit.codeElement.append(target)
        self.external_targets[key] = target

        return target

    def _get_or_create_library_unit(self, external_model, library_name: str):
        """
        Creates or reuses the CompilationUnit representing an external library.

        This is the only helper used to place external elements under the
        ExternalLibraries_CodeModel. Do not call a non-existing
        get_or_create_external_library_model method.
        """

        library_name = str(library_name or "unknown_external").strip()

        if self.language == "java" and not self._is_valid_java_external_library_name(library_name):
            library_name = "unknown_external"

        if library_name in self.library_units:
            return self.library_units[library_name]

        unit = self.factory.create_compilation_unit(library_name)
        self.factory.add_attribute(unit, "external", "true")
        self.factory.add_attribute(unit, "external_kind", "library")
        external_model.codeElement.append(unit)

        self.library_units[library_name] = unit
        return unit

    def _infer_library_name(self, call: dict):
        classification = call.get("classification")

        if classification in {"builtin", "builtin_type_method"}:
            return "builtins" if self.language != "java" else "java.lang"

        import_source = call.get("import_source")

        if isinstance(import_source, dict):
            module = import_source.get("module")
            if module:
                return str(module).split(".")[0]

        target_id = call.get("target_id") or call.get("targetId")
        if target_id and isinstance(target_id, str):
            if target_id.startswith("external_type:"):
                external_name = target_id.replace("external_type:", "")
                return external_name.split(".")[0]

            # Fully qualified Java target, e.g. java.util.List.size.
            if self.language == "java" and self._looks_like_qualified_java_reference(target_id):
                return target_id.split(".")[0]

        receiver = call.get("receiver")
        if receiver:
            receiver = str(receiver)
            if self.language == "java" and not self._looks_like_qualified_java_reference(receiver):
                return "unknown_external"
            return receiver.split(".")[0]

        name = call.get("name", "unknown_external")
        if isinstance(name, str) and "." in name:
            return name.split(".")[0]

        return "builtins" if self.language != "java" else "java.lang"

    def _infer_target_name(self, call: dict):
        if call.get("method"):
            return str(call["method"])

        if call.get("function"):
            return str(call["function"])

        name = call.get("name", "unknown_external")
        name = str(name)

        if name.startswith("external_type:"):
            name = name.replace("external_type:", "")

        if "." in name:
            return name.split(".")[-1]

        return name

    def _infer_target_kind(self, call: dict):
        kind = call.get("kind")
        classification = call.get("classification")
        name = str(call.get("name", ""))

        if kind == "constructor_call":
            return "class"

        if classification == "builtin" and name in {
            "ValueError",
            "Exception",
            "TypeError",
            "RuntimeError",
            "Throwable",
        }:
            return "class"

        import_source = call.get("import_source")
        if isinstance(import_source, dict) and import_source.get("name") == "Path":
            return "class"

        target_id = call.get("target_id") or call.get("targetId")
        if isinstance(target_id, str) and target_id.startswith("external_type:"):
            return "class"

        return "callable"

    def get_or_create_external_class(self, library_name: str, class_name: str):
        library_name = str(library_name or "unknown_external").strip()
        class_name = str(class_name or "UnknownExternalClass").strip()

        if self.language == "java":
            class_name = self._normalize_java_type_name(class_name)

            if self._is_project_internal_type(class_name):
                return None

            imported_package = self.imported_type_to_package.get(class_name)
            if imported_package:
                library_name = imported_package

            if not self._looks_like_java_type_reference(class_name):
                return None
            if not self._is_valid_java_external_library_name(library_name):
                return None
            if library_name == "java.lang" and class_name not in self.JAVA_LANG_TYPES:
                return None

        key = f"{library_name}:class:{class_name}"

        if key in self.external_targets:
            return self.external_targets[key]

        external_model = self.ensure_external_model()
        library_unit = self._get_or_create_library_unit(external_model, library_name)

        target = self.factory.create_class_unit(class_name)
        self.factory.add_attribute(target, "external", "true")
        self.factory.add_attribute(target, "external_kind", "class")
        self.factory.add_attribute(target, "library", library_name)
        library_unit.codeElement.append(target)

        self.external_targets[key] = target
        return target

    def get_or_create_external_import_target(self, import_model: dict):
        """
        Creates or reuses an external target for an unresolved import.

        This method is defensive because Python imports can be relative and may
        carry module=None, for example:

            from . import config as mape_config

        Ideally, internal relative imports should be resolved by ImportResolver.
        This method only handles imports that still remain external/unresolved
        after that step.
        """

        module_name = (
            import_model.get("module")
            or import_model.get("imported_module")
            or import_model.get("resolved_module_qualified_name")
            or import_model.get("qualifiedName")
            or import_model.get("qualified_name")
            or import_model.get("name")
            or import_model.get("effective_name")
            or "unknown_external"
        )

        module_name = str(module_name or "unknown_external").strip()

        target_name = (
            import_model.get("name")
            or import_model.get("effective_name")
        )
        target_name = str(target_name).strip() if target_name is not None else ""

        # Java explicit imports are usually represented as module=<package>,
        # name=<Type>.  If a fully qualified name slipped into module_name,
        # split it here.
        if self.language == "java" and module_name and not target_name:
            if module_name.endswith(".*"):
                module_name = module_name[:-2]
                target_name = module_name
            elif "." in module_name:
                module_name, target_name = module_name.rsplit(".", 1)

        if not target_name:
            target_name = "unknown_external_import"

        target_kind = self._infer_import_target_kind(import_model)

        if self.language == "java":
            if target_kind == "module":
                library_name = module_name
                target_name = module_name
            else:
                library_name = module_name

            if target_kind == "class":
                target_name = self._normalize_java_type_name(target_name)
                if self._is_project_internal_type(target_name):
                    return None
                imported_package = self.imported_type_to_package.get(target_name)
                if imported_package:
                    library_name = imported_package

            if not self._is_valid_java_external_library_name(library_name):
                return None
            if target_kind == "class" and not self._looks_like_java_type_reference(target_name):
                return None
            if target_kind == "callable":
                return None
            if target_kind == "class" and library_name == "java.lang" and target_name not in self.JAVA_LANG_TYPES:
                return None
        else:
            library_name = module_name.split(".")[0] if module_name else "unknown_external"

        key = f"{library_name}:import:{target_kind}:{target_name}"

        if key in self.external_targets:
            return self.external_targets[key]

        external_model = self.ensure_external_model()
        library_unit = self._get_or_create_library_unit(external_model, library_name)

        if target_kind == "class":
            target = self.factory.create_class_unit(target_name)
        elif target_kind == "module":
            target = self.factory.create_compilation_unit(target_name)
        else:
            target = self.factory.create_callable_unit(target_name)

        self.factory.add_attribute(target, "external", "true")
        self.factory.add_attribute(target, "external_kind", "import")
        self.factory.add_attribute(target, "library", library_name)

        if import_model.get("alias"):
            self.factory.add_attribute(target, "alias", import_model.get("alias"))

        if import_model.get("level") is not None:
            self.factory.add_attribute(
                target,
                "relative_import_level",
                import_model.get("level"),
            )

        library_unit.codeElement.append(target)
        self.external_targets[key] = target

        return target

    def _infer_import_target_kind(self, import_model: dict):
        target_type = import_model.get("target_type")
        name = import_model.get("name")
        module = import_model.get("module")

        if target_type in {"class", "function", "module", "wildcard"}:
            if target_type == "function":
                return "callable"

            if target_type == "wildcard":
                return "module"

            return target_type

        if name in {
            "Path",
            "Exception",
            "ValueError",
            "TypeError",
            "RuntimeError",
            "Throwable",
        }:
            return "class"

        if name and str(name)[:1].isupper():
            return "class"

        # Plain import without imported name is better represented as a module.
        if module and name is None:
            return "module"

        return "callable"

    # ------------------------------------------------------------
    # Java conservative filtering helpers
    # ------------------------------------------------------------

    def _is_valid_java_external_call(self, call: dict) -> bool:
        classification = call.get("classification")
        kind = call.get("kind")
        target_id = call.get("target_id") or call.get("targetId")
        receiver = call.get("receiver")
        name = call.get("name") or call.get("method") or call.get("function")
        import_source = call.get("import_source")

        if classification in {"builtin", "builtin_type_method"}:
            return True

        if isinstance(import_source, dict) and import_source.get("module"):
            return True

        if kind == "constructor_call":
            constructor_name = self._simple_name(name)
            return self._looks_like_java_type_reference(constructor_name)

        if isinstance(target_id, str):
            if target_id.startswith("external_type:"):
                return True
            if self._looks_like_qualified_java_reference(target_id):
                return True

        # Local receivers such as mDb, c, values, or context are allowed for
        # unresolved call stubs. They are not used as library names; the target
        # is grouped under external_calls.
        if name:
            name = str(name).strip()
            if name.endswith("()"):
                name = name[:-2]
            if not self._looks_like_java_callable_reference(name):
                return False

        return True

    def _is_valid_java_external_library_name(self, library_name: str) -> bool:
        name = str(library_name or "").strip()

        if not name:
            return False

        if name in self.JAVA_RESERVED_OR_NON_TYPES:
            return False

        if name.endswith("()") or "(" in name or ")" in name:
            return False

        if name in {"unknown_external", "external", "external_calls"}:
            return True

        # Avoid treating the analysed project's own package root as an external
        # library, e.g. edu.hkust... in phoneadapter.
        if name in self.project_package_roots and name not in self.JAVA_EXTERNAL_PACKAGE_ROOTS:
            return False

        if "." not in name:
            return name in self.JAVA_EXTERNAL_PACKAGE_ROOTS or name == "builtins"

        return self._looks_like_qualified_java_reference(name)

    def _looks_like_java_type_reference(self, value: str) -> bool:
        if not value:
            return False

        value = str(value).strip()

        if not value or value in self.JAVA_RESERVED_OR_NON_TYPES:
            return False

        if value.endswith("()") or "(" in value or ")" in value:
            return False

        if value in self.JAVA_PRIMITIVE_TYPES:
            return True

        simple_name = self._simple_name(value)

        if not simple_name:
            return False

        return simple_name[:1].isupper()

    def _looks_like_java_callable_reference(self, value: str) -> bool:
        if not value:
            return False

        value = str(value).strip()

        if not value or value in self.JAVA_RESERVED_OR_NON_TYPES:
            return False

        if "(" in value or ")" in value:
            return False

        simple_name = self._simple_name(value)

        if not simple_name:
            return False

        return simple_name.replace("_", "").isalnum()

    def _looks_like_qualified_java_reference(self, value: str) -> bool:
        if not value:
            return False

        value = str(value).strip()

        if not value or value in self.JAVA_RESERVED_OR_NON_TYPES:
            return False

        if value.endswith("()") or "(" in value or ")" in value:
            return False

        if "." not in value:
            return False

        parts = [part for part in value.split(".") if part]

        if len(parts) < 2:
            return False

        if any(part in self.JAVA_RESERVED_OR_NON_TYPES for part in parts):
            return False

        # Accept package/type references. Reject expressions where the first
        # segment clearly looks like a local variable, e.g. mDb.insert.
        first = parts[0]
        if first in self.project_package_roots and first not in self.JAVA_EXTERNAL_PACKAGE_ROOTS:
            return False

        if first[:1].islower() and first not in self.JAVA_EXTERNAL_PACKAGE_ROOTS:
            return False

        return True


    def _normalize_java_callable_name(self, value: str) -> str:
        value = str(value or "").strip()

        if not value:
            return "call"

        if value.startswith("external_type:"):
            value = value.replace("external_type:", "")

        if "(" in value:
            value = value.split("(", 1)[0]

        value = value.replace(".<init>", "")

        if value.endswith("()"):
            value = value[:-2]

        if "." in value:
            value = value.rsplit(".", 1)[-1]

        value = value.strip()
        return value or "call"

    def _normalize_java_type_name(self, value: str) -> str:
        value = str(value or "").strip()

        if value.startswith("external_type:"):
            value = value.replace("external_type:", "")

        # Remove array suffixes and generic arguments.
        while value.endswith("[]"):
            value = value[:-2]

        if "<" in value:
            value = value.split("<", 1)[0]

        # Defensive cleanup for partially parsed generic fragments such as
        # String>, Rule>, or Integer>.
        value = value.rstrip(">")

        if "." in value:
            value = value.rsplit(".", 1)[-1]

        return value.strip()

    def _is_project_internal_type(self, value: str) -> bool:
        if not value:
            return False

        value = str(value).strip()
        simple_name = self._normalize_java_type_name(value)

        return (
            value in self.internal_qualified_type_names
            or simple_name in self.internal_type_names
        )

    def _simple_name(self, value: str) -> str:
        value = str(value or "").strip()

        if value.startswith("external_type:"):
            value = value.replace("external_type:", "")

        if "(" in value:
            value = value.split("(", 1)[0]

        if ":" in value:
            value = value.rsplit(":", 1)[-1]

        if "." in value:
            value = value.rsplit(".", 1)[-1]

        return value
