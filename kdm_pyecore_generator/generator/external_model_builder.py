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

    PYTHON_BUILTIN_TYPES = {
        "object", "type", "None", "bool", "int", "float", "complex", "str",
        "bytes", "bytearray", "list", "tuple", "dict", "set", "frozenset",
        "range", "slice", "property", "staticmethod", "classmethod",
    }

    PYTHON_BUILTIN_EXCEPTIONS = {
        "BaseException", "Exception", "RuntimeError", "ValueError", "TypeError",
        "KeyError", "IndexError", "AttributeError", "ImportError", "OSError",
        "IOError", "StopIteration", "NotImplementedError", "AssertionError",
    }

    PYTHON_BUILTIN_CALLABLES = {
        "super", "len", "max", "min", "sum", "print", "range", "enumerate",
        "zip", "map", "filter", "sorted", "reversed", "isinstance",
        "issubclass", "getattr", "setattr", "hasattr", "dict", "list",
        "tuple", "set", "str", "int", "float", "bool", "type", "open",
    }

    # Names that commonly appear as local receivers, aliases, or runtime
    # variables in Python code. They should remain as traceability data on
    # ActionElement nodes, not be promoted to ExternalLibraries_CodeModel.
    PYTHON_NON_EXTERNAL_RECEIVERS = {
        "self", "cls", "logger", "log", "root", "args", "kwargs",
        "task", "cfg", "config", "spec", "event", "item", "value",
        "mape", "ops", "np", "path",
    }

    # Library/target names that are almost always local variables, aliases or
    # receiver names in Python projects.  They should not become standalone
    # external libraries.  Real external packages such as numpy are still kept
    # when the import module is explicit; only the alias np is filtered.
    PYTHON_NON_EXTERNAL_LIBRARY_NAMES = {
        "self", "cls", "logger", "log", "root", "args", "kwargs",
        "task", "cfg", "config", "spec", "event", "item", "value",
        "mape", "ops", "np", "path", "h_out", "h_err", "n",
        "unknown_external", "external",
    }

    PYTHON_INTERNAL_OR_LOCAL_CLASSIFICATIONS = {
        "internal",
        "internal_candidate",
        "internal_ambiguous",
        "unresolved_method_on_parameter",
        "unresolved_method_on_local",
        "unresolved_method_on_self",
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
        self.internal_module_names = set()
        self.internal_qualified_module_names = set()


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
            self._register_internal_module(file_model)

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

    def _register_internal_module(self, file_model: dict):
        if not isinstance(file_model, dict):
            return

        name = file_model.get("name")
        qualified_name = (
            file_model.get("qualifiedName")
            or file_model.get("qualified_name")
            or file_model.get("module")
            or file_model.get("id")
        )

        if isinstance(qualified_name, str) and qualified_name.startswith("module:"):
            qualified_name = qualified_name.replace("module:", "", 1)

        if name:
            self.internal_module_names.add(str(name))

        if qualified_name:
            qualified_name = str(qualified_name)
            self.internal_qualified_module_names.add(qualified_name)
            parts = [part for part in qualified_name.split(".") if part]
            if parts:
                self.project_package_roots.add(parts[0])
                self.internal_module_names.add(parts[-1])

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
            if kind in {"function", "method", "callable", "callableunit"}:
                self.internal_callable_names.add(str(name))
            else:
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

        if self.language == "python" and not self._is_valid_python_external_call(call):
            return None

        if self.language == "java" and not self._is_valid_java_external_call(call):
            return None

        library_name = self._infer_library_name(call)
        target_name = self._infer_target_name(call)
        target_kind = self._infer_target_kind(call)

        if self.language == "python":
            library_name = self._normalize_python_library_name(library_name, call)
            target_name = self._normalize_python_target_name(target_name)

            # If the target is already a resolved internal project element, do
            # not create an external stub.  Ambiguous/unresolved local receiver
            # calls are handled below as conservative external_calls targets so
            # that action::Calls semantics are preserved without creating noisy
            # libraries such as self/logger/mape/ops.
            if self._is_resolved_internal_python_call(call):
                return None

            if target_kind == "class" and self._is_python_builtin_name(target_name):
                library_name = "builtins"
            if target_kind == "callable" and target_name in self.PYTHON_BUILTIN_CALLABLES:
                library_name = "builtins"

            if not self._is_valid_python_external_library_name(library_name, target_name, call):
                if target_kind == "callable":
                    library_name = "external_calls"
                elif self._is_python_constructor_call(call, target_name):
                    # Preserve object creation semantics without creating noisy
                    # libraries from local receivers or aliases.  The target
                    # remains a ClassUnit so action::Creates can still be
                    # emitted by the body/reference mappers.
                    library_name = "external_constructors"
                else:
                    return None

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

        if self.language == "python":
            library_name = self._normalize_python_library_unit_name(library_name)

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

        if self.language == "python":
            class_name = self._normalize_python_target_name(class_name)
            library_name = self._normalize_python_library_unit_name(library_name)
            if self._is_project_internal_python_reference(class_name):
                return None
            if self._is_python_builtin_name(class_name):
                library_name = "builtins"
            if not self._is_valid_python_external_library_name(library_name, class_name):
                return None

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

        if self.language == "python":
            if self._is_python_internal_import(import_model, module_name, target_name):
                return None

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
            library_name = self._normalize_python_import_library(module_name, target_name, import_model)
            target_name = self._normalize_python_target_name(target_name)
            if self._is_python_builtin_name(target_name):
                library_name = "builtins"
            library_name = self._normalize_python_library_unit_name(library_name)
            if not self._is_valid_python_external_library_name(library_name, target_name, import_model):
                return None

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
    # Python conservative filtering helpers
    # ------------------------------------------------------------

    def _is_valid_python_external_call(self, call: dict) -> bool:
        if not isinstance(call, dict):
            return False

        # Only fully resolved internal calls are suppressed.  Ambiguous or
        # unresolved calls are still useful KDM semantics; they are later
        # grouped under external_calls instead of creating libraries from local
        # receivers such as self, logger, mape, ops, etc.
        if self._is_resolved_internal_python_call(call):
            return False

        name = call.get("name") or call.get("method") or call.get("function")
        target = self._normalize_python_target_name(name or "")

        # Nothing useful to materialize.
        if not target or target in {"unknown_external", "unknown_external_import"}:
            return False

        return True

    def _is_resolved_internal_python_call(self, call: dict) -> bool:
        if not isinstance(call, dict):
            return False

        classification = str(call.get("classification") or "").strip()
        resolved = call.get("resolved")
        target_id = call.get("target_id") or call.get("targetId")

        if classification == "internal" or resolved is True:
            return True

        if isinstance(target_id, str) and target_id.startswith(("class:", "function:", "method:", "module:")):
            return True

        return False

    def _is_internal_python_import_source(self, import_source) -> bool:
        if not isinstance(import_source, dict):
            return False

        classification = import_source.get("classification")
        resolved = import_source.get("resolved")
        target_id = import_source.get("target_id") or import_source.get("targetId")
        target_qualified_name = import_source.get("target_qualified_name")

        if classification == "internal" or resolved is True:
            return True

        if isinstance(target_id, str) and target_id.startswith(("class:", "function:", "method:", "module:")):
            return True

        if target_qualified_name and str(target_qualified_name) in (
            self.internal_qualified_type_names | self.internal_qualified_module_names
        ):
            return True

        return False

    def _is_python_local_receiver(self, receiver) -> bool:
        if not receiver:
            return False

        text = str(receiver).strip()
        if not text:
            return False

        root = text.split(".", 1)[0]
        if root in self.PYTHON_NON_EXTERNAL_RECEIVERS:
            return True

        if root in self.internal_module_names or root in self.internal_qualified_module_names:
            return True

        return False

    def _is_unqualified_python_local_name(self, name, call: dict | None = None) -> bool:
        if not name:
            return False

        text = str(name).strip()
        if not text:
            return False

        # Do not block true builtins or explicitly external imported calls.
        if self._is_python_builtin_name(text):
            return False

        import_source = call.get("import_source") if isinstance(call, dict) else None
        if isinstance(import_source, dict) and import_source.get("classification") == "external":
            return False

        root = text.split(".", 1)[0]
        if root in self.PYTHON_NON_EXTERNAL_RECEIVERS:
            return True
        if root in self.internal_module_names or root in self.internal_qualified_module_names:
            return True

        # Lowercase unqualified names with no external import are usually local
        # functions, parameters, variables, or aliases.  Keeping them out of the
        # external model avoids noise such as logger, self, mape, or ops.
        if "." not in text and text[:1].islower():
            return True

        return False

    def _is_python_internal_import(self, import_model: dict, module_name: str, target_name: str) -> bool:
        classification = import_model.get("classification")
        resolved = import_model.get("resolved")
        target_id = import_model.get("target_id") or import_model.get("targetId")

        if classification == "internal" or resolved is True:
            return True

        if isinstance(target_id, str) and target_id.startswith(("class:", "function:", "method:", "module:")):
            return True

        qualified = import_model.get("target_qualified_name") or import_model.get("qualifiedName") or import_model.get("qualified_name")
        if qualified and str(qualified) in self.internal_qualified_type_names | self.internal_qualified_module_names:
            return True

        if module_name in self.internal_qualified_module_names or module_name in self.internal_module_names:
            return True

        if target_name in self.internal_type_names or target_name in self.internal_callable_names:
            # Only treat simple-name matches as internal when the import itself
            # is explicitly resolved/internal. Otherwise third-party libraries
            # may legitimately export symbols with the same simple name.
            return classification == "internal" or resolved is True

        return False

    def _strip_python_external_marker(self, value: str) -> str:
        """Removes synthetic extractor prefixes from Python external names.

        The Python extractor sometimes emits identifiers such as
        ``external:asyncio`` or ``external_type:Observable``.  Those prefixes
        are useful in the intermediate JSON but should not become literal
        CompilationUnit names in ExternalLibraries_CodeModel.
        """
        text = str(value or "").strip()

        for prefix in ("external_type:", "external:"):
            if text.startswith(prefix):
                text = text.replace(prefix, "", 1).strip()

        return text

    def _normalize_python_library_name(self, library_name: str, call: dict) -> str:
        library_name = self._strip_python_external_marker(library_name)
        library_name = str(library_name or "unknown_external").strip() or "unknown_external"
        classification = str(call.get("classification") or "").strip() if isinstance(call, dict) else ""
        receiver = call.get("receiver") if isinstance(call, dict) else None
        import_source = call.get("import_source") if isinstance(call, dict) else None

        target_name = self._normalize_python_target_name(call.get("class_name") or call.get("function") or call.get("method") or call.get("name") or "") if isinstance(call, dict) else ""
        if self._is_python_builtin_name(target_name):
            return "builtins"

        # Preserve call semantics for unresolved/ambiguous local receiver calls,
        # but do not create noisy libraries from the receiver/alias itself.
        if classification in self.PYTHON_INTERNAL_OR_LOCAL_CLASSIFICATIONS:
            return "external_calls"
        if receiver and self._is_python_local_receiver(receiver):
            return "external_calls"

        if isinstance(import_source, dict):
            module = import_source.get("module") or import_source.get("imported_module")
            if module and import_source.get("classification") == "external":
                return str(module)
            if self._is_internal_python_import_source(import_source):
                return "external_calls"

        if library_name in self.internal_module_names or library_name in self.internal_qualified_module_names:
            return "external_calls"
        if library_name in self.PYTHON_NON_EXTERNAL_LIBRARY_NAMES or library_name.split('.', 1)[0] in self.PYTHON_NON_EXTERNAL_LIBRARY_NAMES:
            return "external_calls"
        return library_name

    def _normalize_python_import_library(self, module_name: str, target_name: str, import_model: dict) -> str:
        module_name = self._strip_python_external_marker(module_name)
        module_name = str(module_name or "unknown_external").strip() or "unknown_external"

        if module_name.startswith("builtin_type:") or module_name.startswith("builtin:"):
            return "builtins"

        if module_name in self.internal_module_names or module_name in self.internal_qualified_module_names:
            return "unknown_external"
        # Keep full external module names when they carry useful package
        # information, e.g. prompt_toolkit.shortcuts or simple_pid.
        return module_name

    def _normalize_python_target_name(self, value: str) -> str:
        value = self._strip_python_external_marker(value)
        value = str(value or "unknown_external").strip()
        if value.startswith("builtin:"):
            value = value.replace("builtin:", "", 1)
        if value.startswith("builtin_type:"):
            value = value.replace("builtin_type:", "", 1)
        if "(" in value:
            value = value.split("(", 1)[0]
        if value.endswith("()"):
            value = value[:-2]
        if ":" in value:
            value = value.rsplit(":", 1)[-1]
        if "." in value and value.split(".")[-1]:
            return value.split(".")[-1]
        return value or "unknown_external"

    def _is_python_builtin_name(self, value: str) -> bool:
        name = self._normalize_python_target_name(value)
        return (
            name in self.PYTHON_BUILTIN_TYPES
            or name in self.PYTHON_BUILTIN_EXCEPTIONS
            or name in self.PYTHON_BUILTIN_CALLABLES
        )

    def _is_project_internal_python_name(self, value: str) -> bool:
        """Backward-compatible alias for older cleanup logic.

        Python internal/external classification is centralized in
        _is_project_internal_python_reference(...). Some call sites only pass
        a class/type name, so this wrapper keeps the public behavior stable.
        """
        return self._is_project_internal_python_reference(value)

    def _is_project_internal_python_reference(self, value: str, call: dict | None = None) -> bool:
        if not value:
            return False
        text = str(value).strip()
        simple = self._normalize_python_target_name(text)
        if text in self.internal_qualified_type_names or text in self.internal_qualified_module_names:
            return True
        if simple in self.internal_type_names or simple in self.internal_callable_names:
            if call and call.get("classification") in {"external", "builtin", "builtin_type_method"}:
                return False
            return True
        return False


    def _is_valid_python_external_library_name(self, library_name: str, target_name: str | None = None, context: dict | None = None) -> bool:
        """Central gate for Python external model creation.

        This prevents local receivers, internal aliases and builtin-type
        markers from becoming CompilationUnit nodes under
        ExternalLibraries_CodeModel.  It is intentionally conservative: when
        the source says the reference is internal/resolved, the external target
        is suppressed.
        """
        library = str(library_name or "").strip()
        target = self._normalize_python_target_name(target_name or "")

        if not library:
            return False

        if library.startswith("builtin_type:"):
            return False

        if library in {"builtins", "external_calls"}:
            return True

        root = library.split(".", 1)[0]
        if library in self.PYTHON_NON_EXTERNAL_LIBRARY_NAMES or root in self.PYTHON_NON_EXTERNAL_LIBRARY_NAMES:
            return False

        if target in self.PYTHON_NON_EXTERNAL_LIBRARY_NAMES:
            return False

        if self._is_project_internal_python_reference(library, context):
            return False

        if library != "external_calls" and self._is_project_internal_python_reference(target, context):
            return False

        if isinstance(context, dict):
            classification = context.get("classification")
            resolved = context.get("resolved")
            target_id = context.get("target_id") or context.get("targetId")

            if classification == "internal" or resolved is True:
                return False

            if isinstance(target_id, str) and target_id.startswith(("class:", "function:", "method:", "module:")):
                return False

            if self._is_internal_python_import_source(context.get("import_source")):
                return False

            # A lowercase unqualified target with no explicit external import
            # is usually a parameter, local variable, receiver alias, or local
            # helper.  Keep the ActionElement traceability but do not create an
            # external model element for it.
            if library != "external_calls" and target and target[:1].islower() and "." not in str(target_name or target):
                import_source = context.get("import_source")
                if not (isinstance(import_source, dict) and import_source.get("classification") == "external"):
                    return False

        return True


    def _normalize_python_library_unit_name(self, library_name: str) -> str:
        """Normalizes Python library buckets before materialization.

        Builtins should not appear as standalone external libraries named
        ``super`` or ``builtin_type:*``.  They are grouped under the
        PythonBuiltins/builtins bucket used by the current generator.

        Synthetic prefixes such as ``external:`` and ``external_type:`` are
        stripped so the XMI contains clean library names like ``asyncio`` or
        ``Observable`` rather than ``external:asyncio``.
        """
        original = str(library_name or "unknown_external").strip() or "unknown_external"

        if original in {"external_calls", "external_constructors", "unknown_external"}:
            return original

        text = self._strip_python_external_marker(original) or "unknown_external"
        normalized = self._normalize_python_target_name(text)

        if text.startswith("builtin_type:") or text.startswith("builtin:"):
            return "builtins"

        if normalized in self.PYTHON_BUILTIN_TYPES or normalized in self.PYTHON_BUILTIN_EXCEPTIONS or normalized in self.PYTHON_BUILTIN_CALLABLES:
            return "builtins"

        if text == "super":
            return "builtins"

        return text

    def _is_python_constructor_call(self, call: dict | None, target_name: str | None = None) -> bool:
        if not isinstance(call, dict):
            return False

        kind = str(call.get("kind") or "")
        classification = str(call.get("classification") or "")
        name = target_name or call.get("class_name") or call.get("function") or call.get("name")
        name = self._normalize_python_target_name(name or "")

        if kind == "constructor_call" or classification == "constructor":
            return bool(name and name not in {"unknown_external", "unknown_external_import"})

        # Uppercase unresolved function calls in Python are often constructor
        # calls even when the extractor could not fully classify them.
        return bool(name and name[:1].isupper() and classification in {"external", "unresolved", "internal_candidate", "internal_ambiguous"})

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
