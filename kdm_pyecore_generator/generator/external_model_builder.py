class ExternalModelBuilder:
    """
    Builds and reuses KDM elements for external libraries, builtins,
    external types, and unresolved external calls/imports.
    """

    def __init__(self, factory, segment):
        self.factory = factory
        self.segment = segment

        self.external_code_model = None
        self.library_units = {}
        self.external_targets = {}
        self.external_packages = {}
        self.internal_package_prefixes = set()
        self.internal_package_roots = set()
        self.internal_type_names = set()
        self.internal_module_names = set()
        self.external_aliases = {
            "np": "numpy",
            "pd": "pandas",
        }
        # Simple names that the Python extractor may report without their
        # import module.  These are external library symbols, not builtins.
        self.known_python_external_types = {
            "PID": "simple_pid.PID",
            "Subject": "rx.subject.Subject",
            "Observable": "rx.core.Observable",
            "Disposable": "rx.disposable.Disposable",
            "Observer": "rx.core.Observer",
            "CompositeDisposable": "rx.disposable.CompositeDisposable",
            "Redis": "aioredis.Redis",
            "HTTPException": "fastapi.HTTPException",
            "FastAPI": "fastapi.FastAPI",
            "Server": "uvicorn.Server",
            "Config": "uvicorn.Config",
            "ClientError": "aiohttp.client_exceptions.ClientError",
            "DataFrame": "pandas.DataFrame",
            "Path": "pathlib.Path",
            "PromptSession": "prompt_toolkit.PromptSession",
            "KeyBindings": "prompt_toolkit.key_binding.KeyBindings",
            "InfluxDBClient": "influxdb_client.InfluxDBClient",
            "Point": "influxdb_client.Point",
        }
        # Simple external functions/callables that may appear without their
        # module in unresolved calls/imports.  These must not fall back to
        # builtins.
        self.known_python_external_callables = {
            "create_input": "prompt_toolkit.input.create_input",
            "TypeVar": "typing.TypeVar",
            "wraps": "functools.wraps",
            "partial": "functools.partial",
            "Depends": "fastapi.Depends",
        }
        self.diagnostic_external_names = {
            "_scenario_common", "rx_utils", "api", "_config",
            "mape_config", "element_notify_path", "ops", "path",
            "unknown_external", "unknown_external_import",
        }
        self.valid_python_builtins = {
            "builtins.object", "builtins.type", "builtins.str", "builtins.int",
            "builtins.float", "builtins.bool", "builtins.bytes", "builtins.list",
            "builtins.dict", "builtins.set", "builtins.tuple", "builtins.None",
            "builtins.NoneType", "builtins.ValueError", "builtins.TypeError",
            "builtins.RuntimeError", "builtins.Exception", "builtins.BaseException",
            "builtins.NotImplementedError", "builtins.KeyError", "builtins.IndexError",
            "builtins.AttributeError", "builtins.ImportError", "builtins.OSError",
        }

    def set_internal_package_prefixes(self, prefixes):
        """Register project package prefixes that must not be externalized."""
        self.internal_package_prefixes = {str(p).strip() for p in (prefixes or set()) if str(p).strip()}
        # Keep top-level roots for defensive filtering.  This is used only in
        # combination with internal simple type names, so it does not blindly
        # classify every com.* package as internal.
        self.internal_package_roots = {p.split(".")[0] for p in self.internal_package_prefixes if p}

    def set_internal_type_names(self, names):
        """Register simple names of classes/interfaces declared by the project."""
        self.internal_type_names = {str(n).strip() for n in (names or set()) if str(n).strip()}

    def set_internal_module_names(self, names):
        """Register simple names of modules/packages declared by the project."""
        self.internal_module_names = {str(n).strip() for n in (names or set()) if str(n).strip()}

    def _normalize_external_ref(self, qualified_name: str):
        """Normalize prefixes and aliases used by unresolved external references."""
        if qualified_name is None:
            return None
        qn = self._strip_generic_arguments(qualified_name) or str(qualified_name).strip()
        qn = qn.strip().strip(">").strip()
        if not qn:
            return None
        for prefix in ("external_type:", "external:", "class:", "module:", "function:", "method:"):
            if qn.startswith(prefix):
                qn = qn[len(prefix):]
        qn = qn.strip().strip(">").strip()
        if not qn:
            return None
        root = qn.split(".")[0]
        if root in self.external_aliases:
            qn = self.external_aliases[root] + qn[len(root):]
        # If the extractor only gives a simple external class name, normalize it
        # to the real library-qualified name. This prevents symbols such as
        # PID, Subject, Redis, HTTPException or Server from being placed under
        # builtins or unknown_external.
        if "." not in qn and qn in self.known_python_external_types:
            qn = self.known_python_external_types[qn]
        elif "." not in qn and qn in self.known_python_external_callables:
            qn = self.known_python_external_callables[qn]
        return qn or None

    def _is_internal_name(self, qualified_name: str) -> bool:
        if not qualified_name:
            return False
        qn = self._normalize_external_ref(qualified_name)
        if not qn:
            return False
        simple = qn.split(".")[-1]
        root = qn.split(".")[0]
        if simple in self.internal_module_names:
            return True
        for prefix in self.internal_package_prefixes:
            if qn == prefix or qn.startswith(prefix + '.') or prefix.startswith(qn + '.'):
                return True
        # Some relationships arrive partially qualified, e.g. com.UserRepository
        # instead of com.example.repository.UserRepository.  If the root belongs
        # to the project and the simple type name is declared internally, do not
        # externalize it.
        if root in self.internal_package_roots and simple in self.internal_type_names:
            return True
        return False

    def _is_internal_simple_name(self, name: str) -> bool:
        return bool(name and str(name).split(".")[-1] in self.internal_type_names)

    def _is_internal_module_simple_name(self, name: str) -> bool:
        return bool(name and str(name).split(".")[-1] in self.internal_module_names)

    def _is_valid_builtin_reference(self, value: str) -> bool:
        """Return True only for real Python builtins or builtin exceptions.

        This prevents unresolved external callables from being placed in the
        builtins compilation unit merely because no library could be inferred.
        """
        if not value:
            return False
        qn = self._normalize_external_ref(value) or str(value).strip()
        if not qn:
            return False
        if qn in self.valid_python_builtins:
            return True
        simple = qn.split(".")[-1]
        return f"builtins.{simple}" in self.valid_python_builtins

    def _get_or_create_unresolved_unit(self, external_model=None):
        """Container for external symbols that cannot be assigned to a real library."""
        external_model = external_model or self.ensure_external_model()
        library_name = "ExternalUnresolved"
        if library_name in self.library_units:
            return self.library_units[library_name]
        unit = self.factory.create_compilation_unit(library_name)
        self.factory.add_attribute(unit, "external", "true")
        self.factory.add_attribute(unit, "external_kind", "unresolved")
        external_model.codeElement.append(unit)
        self.library_units[library_name] = unit
        return unit


    def _is_noise_external_name(self, qualified_name: str) -> bool:
        """Return True for expression fragments that must not become external packages.

        The Python extractor can expose unresolved receivers or aliases such as
        self, self._p_out, np, unknown_external or rx.create.  These are useful
        for diagnostics, but they are not stable libraries/packages and should
        not pollute ExternalLibraries_CodeModel.
        """
        if not qualified_name:
            return True
        qn = self._normalize_external_ref(qualified_name)
        if not qn:
            return True
        if qn in {"self", "None", "NoneType", "unknown_external", "unknown_external_import"}:
            return True
        if qn in self.diagnostic_external_names:
            return True
        root = qn.split(".")[0]
        simple = qn.split(".")[-1]
        if root in self.internal_type_names or root in self.internal_module_names:
            return True
        if root in self.diagnostic_external_names:
            return True
        if simple in self.internal_module_names and root not in {"typing", "builtins"}:
            return True
        if qn.startswith("builtins.") and qn not in self.valid_python_builtins:
            return True
        if qn.startswith("self") or qn.startswith("self."):
            return True
        if qn.startswith("unknown_external"):
            return True
        if qn in {"np", "rx.create"}:
            return True
        if qn.split(".")[0] in {"self", "unknown_external"}:
            return True
        # A single simple name that is also declared internally is not an
        # external package/type.  This catches names such as Element.
        if "." not in qn and (qn in self.internal_type_names or qn in self.internal_module_names):
            return True
        return False

    def _strip_generic_arguments(self, value):
        """Return the raw qualified name without generic arguments.

        Examples:
            java.util.Map<java.lang.Long, java.lang.String> -> java.util.Map
            typing.Optional[builtins.str] -> typing.Optional
        """
        if value is None:
            return None
        value = str(value).strip()
        depth = 0
        result = []
        for ch in value:
            if ch in "<[":
                depth += 1
                if depth == 1:
                    continue
            if ch in ">]":
                depth = max(0, depth - 1)
                continue
            if depth == 0:
                result.append(ch)
        value = "".join(result).strip().strip(">")
        return value.strip() or None

    def _clean_callable_name(self, value):
        if value is None:
            return None
        text = self._strip_generic_arguments(str(value)) or str(value).strip()
        text = text.replace(".<init>", "")
        if "(" in text:
            text = text.split("(", 1)[0]
        return text.strip().strip(")") or None

    def _canonicalize_external_qn(self, qualified_name: str):
        qn = self._normalize_external_ref(qualified_name)
        if not qn:
            return None
        simple = qn.split(".")[-1].strip().strip(">")
        java_lang = {
            "String", "Long", "Integer", "Boolean", "Double", "Float",
            "Short", "Byte", "Character", "Object", "RuntimeException",
            "IllegalArgumentException", "IllegalStateException", "Exception",
        }
        if qn.startswith("java.util.") and simple in java_lang:
            return f"java.lang.{simple}"
        return qn

    def _known_external_kind(self, qualified_name: str, fallback: str = "class") -> str:
        """Return the preferred KDM datatype kind for well-known external APIs.

        This is mainly used to avoid creating duplicates such as both
        ClassUnit and InterfaceUnit for java.util.List/java.util.Map.
        """
        qn = self._canonicalize_external_qn(qualified_name)
        if qn in {
            "java.util.List",
            "java.util.Map",
            "java.util.Collection",
            "java.lang.CharSequence",
            "java.lang.Comparable",
            "java.io.Serializable",
        }:
            return "interface"
        if qn == "java.lang.annotation.RetentionPolicy":
            return "enum"
        if qn in {"java.lang.Deprecated", "java.lang.annotation.Retention"}:
            return "annotation"
        return fallback or "class"

    def _register_external_aliases(self, qualified_name: str, element, kind: str = None, library_name: str = None, name: str = None):
        if not qualified_name or element is None:
            return
        qn = self._canonicalize_external_qn(qualified_name) or qualified_name
        simple = name or qn.split(".")[-1]
        package = qn.rsplit(".", 1)[0] if "." in qn else (library_name or "external")
        library = library_name or package.split(".")[0]
        self.external_targets.setdefault(qn, element)
        self.external_targets.setdefault(f"external_type:{qn}", element)
        if kind:
            self.external_targets.setdefault(f"{library}:external_type:{kind}:{qn}", element)
            self.external_targets.setdefault(f"{package}:external_type:{kind}:{simple}", element)
        self.external_targets.setdefault(f"{package}:class:{simple}", element)
        self.external_targets.setdefault(f"{library}:class:{simple}", element)

    def _infer_owner_and_member(self, call: dict):
        """Return (owner qualified name, member name) for external methods.

        This prevents external methods such as java.lang.String.trim or
        java.util.Map.put from being placed as loose callables in a generic
        CompilationUnit named 'java'.
        """
        candidates = [
            call.get("target_qualified_name"),
            call.get("targetId"),
            call.get("target_id"),
            call.get("qualifiedName"),
            call.get("qualified_name"),
            call.get("name"),
            call.get("call_signature"),
        ]
        for candidate in candidates:
            text = self._clean_callable_name(candidate)
            if not text or "." not in text:
                continue
            text = text.replace("external_type:", "")
            parts = [p for p in text.split(".") if p]
            if len(parts) >= 3 and parts[0] in {"java", "javax", "builtins", "typing"}:
                return ".".join(parts[:-1]), parts[-1]
        receiver_type = call.get("receiver_type") or call.get("receiverType")
        method = call.get("method") or call.get("function")
        if receiver_type and method:
            owner = self._canonicalize_external_qn(receiver_type)
            if owner and "." in owner and not self._is_internal_name(owner):
                return owner, self._clean_callable_name(method)
        return None, None

    def ensure_external_model(self):
        if self.external_code_model is None:
            self.external_code_model = self.factory.create_code_model(
                "ExternalLibraries_CodeModel"
            )
            self.segment.model.append(self.external_code_model)

        return self.external_code_model

    def get_or_create_external_package(self, qualified_name: str):
        """Create or reuse a code::Package under ExternalLibraries_CodeModel."""

        if not qualified_name:
            return None
        qualified_name = self._canonicalize_external_qn(qualified_name)
        if (
            not qualified_name
            or self._is_noise_external_name(qualified_name)
            or self._is_internal_name(qualified_name)
        ):
            return None

        if qualified_name in self.external_packages:
            return self.external_packages[qualified_name]

        external_model = self.ensure_external_model()
        parts = [part for part in qualified_name.split(".") if part]
        current = []
        parent = None
        for part in parts:
            current.append(part)
            current_qn = ".".join(current)
            if current_qn in self.external_packages:
                parent = self.external_packages[current_qn]
                continue

            package_unit = self.factory.create_package_unit(part)
            self.factory.add_attribute(package_unit, "external", "true")
            self.factory.add_attribute(package_unit, "qualified_name", current_qn)

            if parent is not None and self.factory.has_feature(parent, "codeElement"):
                parent.codeElement.append(package_unit)
            else:
                external_model.codeElement.append(package_unit)

            self.external_packages[current_qn] = package_unit
            parent = package_unit

        return self.external_packages.get(qualified_name)

    def get_or_create_external_target(self, call: dict):
        """
        Returns a KDM target for an external call.
        If the target does not exist yet, it is created.
        """

        target_id = call.get("target_id") or call.get("name")
        if target_id and self._is_internal_name(str(target_id).replace("external_type:", "")):
            return None

        library_name = self._infer_library_name(call)
        target_name = self._infer_target_name(call)
        target_kind = self._infer_target_kind(call)

        if (
            self._is_internal_simple_name(target_name)
            or self._is_internal_module_simple_name(target_name)
            or self._is_noise_external_name(target_name)
        ):
            return None

        # If the only inferred container is builtins, verify that the target is
        # truly a builtin.  Otherwise place the symbol in ExternalUnresolved
        # instead of polluting builtins with project-specific or third-party
        # unresolved callables such as RedisKeySpace or AsyncIOScheduler.
        if library_name == "builtins" and not self._is_valid_builtin_reference(target_name):
            library_name = "ExternalUnresolved"
        if self._is_noise_external_name(library_name):
            library_name = "ExternalUnresolved"

        owner_qn, member_name = self._infer_owner_and_member(call)
        if target_kind != "class" and owner_qn and member_name:
            return self.get_or_create_external_method(owner_qn, member_name)

        simple_target_name = str(target_name).split(".")[-1] if target_name else ""
        if target_kind == "class" and simple_target_name in self.known_python_external_types:
            qualified = self.known_python_external_types[simple_target_name]
            return self.get_or_create_external_type({
                "qualifiedName": qualified,
                "packageName": qualified.rsplit(".", 1)[0],
                "name": qualified.rsplit(".", 1)[1],
                "kind": "class",
            })
        if target_kind != "class" and simple_target_name in self.known_python_external_callables:
            qualified = self.known_python_external_callables[simple_target_name]
            owner = qualified.rsplit(".", 1)[0]
            member = qualified.rsplit(".", 1)[1]
            return self.get_or_create_external_method(owner, member)

        key = f"{library_name}:{target_kind}:{target_name}"

        if key in self.external_targets:
            return self.external_targets[key]

        external_model = self.ensure_external_model()
        if library_name == "ExternalUnresolved":
            library_unit = self._get_or_create_unresolved_unit(external_model)
        else:
            library_unit = self._get_or_create_library_unit(external_model, library_name)
        if library_unit is None:
            return None

        if target_kind == "class":
            target = self.factory.create_class_unit(target_name)
        else:
            target = self.factory.create_callable_unit(target_name)

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

        library_name = self._normalize_external_ref(library_name) or "unknown_external"
        if self._is_noise_external_name(library_name) or self._is_internal_module_simple_name(library_name):
            return None

        if library_name in self.library_units:
            return self.library_units[library_name]

        unit = self.factory.create_compilation_unit(library_name)
        external_model.codeElement.append(unit)

        self.library_units[library_name] = unit
        return unit

    def _infer_library_name(self, call: dict):
        classification = call.get("classification")

        name = call.get("name") or call.get("function") or call.get("class_name") or ""
        clean_name = self._clean_callable_name(name) or name
        simple_name = str(clean_name).split(".")[-1] if clean_name else ""
        if simple_name in self.known_python_external_types:
            return self.known_python_external_types[simple_name].split(".")[0]
        if simple_name in self.known_python_external_callables:
            return self.known_python_external_callables[simple_name].split(".")[0]

        if classification in {"builtin", "builtin_type_method"}:
            return "builtins"

        import_source = call.get("import_source")

        if import_source:
            module = import_source.get("module")
            if module:
                return module.split(".")[0]

        receiver = call.get("receiver")
        if receiver:
            return receiver.split(".")[0]

        target_id = call.get("target_id")
        if target_id and target_id.startswith("external_type:"):
            external_name = target_id.replace("external_type:", "")
            return external_name.split(".")[0]

        name = call.get("name", "unknown_external")
        if "." in name:
            return name.split(".")[0]

        return "ExternalUnresolved"

    def _infer_target_name(self, call: dict):
        if call.get("method"):
            return call["method"]

        if call.get("function"):
            return call["function"]

        name = call.get("name", "unknown_external")

        if "." in name:
            return name.split(".")[-1]

        return name

    def _infer_target_kind(self, call: dict):
        kind = call.get("kind")
        classification = call.get("classification")
        name = call.get("name", "")

        if kind == "constructor_call":
            return "class"

        if classification == "builtin" and name in {
            "ValueError",
            "Exception",
            "TypeError",
            "RuntimeError",
        }:
            return "class"

        import_source = call.get("import_source")
        if import_source and import_source.get("name") == "Path":
            return "class"

        return "callable"

    def get_or_create_external_class(self, library_name: str, class_name: str):
        library_name = self._normalize_external_ref(library_name) or "unknown_external"
        class_name = str(class_name or "UnknownExternalClass")
        class_name = self._clean_callable_name(class_name) or class_name
        simple_class_name = str(class_name).split(".")[-1]
        if simple_class_name in self.known_python_external_types and library_name in {"builtins", "unknown_external", "external", simple_class_name}:
            qualified = self.known_python_external_types[simple_class_name]
            return self.get_or_create_external_type({
                "qualifiedName": qualified,
                "packageName": qualified.rsplit(".", 1)[0],
                "name": qualified.rsplit(".", 1)[1],
                "kind": "class",
            })
        if (
            self._is_internal_simple_name(class_name)
            or self._is_internal_module_simple_name(class_name)
            or self._is_noise_external_name(class_name)
        ):
            return None
        if library_name == "builtins" and not self._is_valid_builtin_reference(class_name):
            library_name = "ExternalUnresolved"
        if self._is_noise_external_name(library_name):
            library_name = "ExternalUnresolved"
        candidate_qn = f"{library_name}.{class_name}" if library_name else class_name
        candidate_qn = self._canonicalize_external_qn(candidate_qn) or candidate_qn
        if self._is_internal_name(candidate_qn):
            return None

        preferred_kind = self._known_external_kind(candidate_qn, "class")
        existing = (
            self.external_targets.get(candidate_qn)
            or self.external_targets.get(f"external_type:{candidate_qn}")
        )
        if existing is not None:
            return existing

        # If the requested class is known to be an interface/annotation/enum,
        # delegate to the type builder so only one canonical element is created.
        if preferred_kind != "class":
            return self.get_or_create_external_type({
                "qualifiedName": candidate_qn,
                "packageName": candidate_qn.rsplit(".", 1)[0] if "." in candidate_qn else library_name,
                "name": candidate_qn.split(".")[-1],
                "kind": preferred_kind,
            })

        if "." in candidate_qn:
            library_name = candidate_qn.rsplit(".", 1)[0]
            class_name = candidate_qn.rsplit(".", 1)[1]

        key = f"{library_name}:class:{class_name}"

        if key in self.external_targets:
            return self.external_targets[key]

        external_model = self.ensure_external_model()
        if library_name == "ExternalUnresolved":
            library_unit = self._get_or_create_unresolved_unit(external_model)
        else:
            library_unit = self._get_or_create_library_unit(external_model, library_name)
        if library_unit is None:
            return None

        target = self.factory.create_class_unit(class_name)
        library_unit.codeElement.append(target)

        self.external_targets[key] = target
        qualified_name = f"{library_name}.{class_name}"
        self._register_external_aliases(qualified_name, target, kind="class", library_name=library_name, name=class_name)
        return target

    def get_or_create_external_method(self, owner_qualified_name: str, method_name: str):
        owner_qualified_name = self._canonicalize_external_qn(owner_qualified_name)
        method_name = self._clean_callable_name(method_name)
        if not owner_qualified_name or not method_name:
            return None
        if (
            self._is_noise_external_name(owner_qualified_name)
            or self._is_internal_name(owner_qualified_name)
            or self._is_internal_simple_name(owner_qualified_name.split(".")[-1])
        ):
            return None
        key = f"external_method:{owner_qualified_name}.{method_name}"
        if key in self.external_targets:
            return self.external_targets[key]
        owner_package = self._package_from_qualified_name(owner_qualified_name) or "unknown_external"
        owner_name = owner_qualified_name.split(".")[-1]
        owner = self.get_or_create_external_type({
            "qualifiedName": owner_qualified_name,
            "packageName": owner_package,
            "name": owner_name,
            "kind": "class",
        })
        if owner is None:
            return None
        method = self.factory.create_callable_unit(method_name)
        self.factory.add_attribute(method, "external", "true")
        self.factory.add_attribute(method, "external_kind", "method")
        self.factory.add_attribute(method, "qualified_name", f"{owner_qualified_name}.{method_name}")
        if hasattr(owner, "codeElement"):
            owner.codeElement.append(method)
        self.external_targets[key] = method
        self.external_targets[f"{owner_qualified_name}.{method_name}"] = method
        return method


    def get_or_create_external_type(self, type_model: dict):
        """
        Creates or reuses an external type declared by the common JSON schema.

        Expected fields:
            qualifiedName / qualified_name
            packageName / package_name
            name
            kind: class | interface | enum | annotation | callable | module
        """
        qualified_name = (
            type_model.get("qualifiedName")
            or type_model.get("qualified_name")
            or type_model.get("name")
        )

        qualified_name = self._canonicalize_external_qn(qualified_name)
        if (
            not qualified_name
            or self._is_noise_external_name(qualified_name)
            or self._is_internal_name(qualified_name)
        ):
            return None

        existing = (
            self.external_targets.get(str(qualified_name))
            or self.external_targets.get(f"external_type:{qualified_name}")
        )
        if existing is not None:
            return existing

        # The qualified name is the source of truth. Do not trust `name` or
        # `packageName` when they were derived from a generic type such as
        # java.util.Map<java.lang.Long, java.lang.String>. In such cases they
        # may contain fragments like "String>" or an entire raw type as a
        # package.
        inferred_name = str(qualified_name).split(".")[-1]
        raw_name = str(type_model.get("name") or inferred_name)
        name = self._strip_generic_arguments(raw_name) or inferred_name
        # Prefer the simple name derived from the canonical qualified name. This
        # prevents generic argument fragments such as String> from creating
        # classes in the wrong package, e.g. java.util.String.
        if ">" in raw_name or "<" in raw_name or name != inferred_name:
            name = inferred_name

        package_name = self._package_from_qualified_name(str(qualified_name))
        if not package_name:
            package_name = (
                self._strip_generic_arguments(type_model.get("packageName") or type_model.get("package_name"))
                or "unknown_external"
            )
        if self._is_internal_name(package_name):
            return None
        kind = str(type_model.get("kind") or type_model.get("type") or "class")
        kind = self._known_external_kind(qualified_name, kind)
        library_name = str(package_name).split(".")[0] if package_name else "unknown_external"
        if library_name == "builtins" and not self._is_valid_builtin_reference(str(qualified_name)):
            library_name = "ExternalUnresolved"
            package_name = "ExternalUnresolved"
        elif library_name in {"unknown_external", "external"}:
            library_name = "ExternalUnresolved"
            package_name = "ExternalUnresolved"
        key = f"{library_name}:external_type:{kind}:{qualified_name}"

        if key in self.external_targets:
            return self.external_targets[key]

        external_model = self.ensure_external_model()
        if library_name == "ExternalUnresolved":
            package_unit = self._get_or_create_unresolved_unit(external_model)
        else:
            package_unit = self.get_or_create_external_package(package_name)
            if package_unit is None:
                package_unit = self._get_or_create_library_unit(external_model, library_name)
        # Some unresolved or diagnostic names are intentionally filtered by
        # get_or_create_external_package/_get_or_create_library_unit.  In that
        # case the external type must be skipped instead of attempting to append
        # it to a None container.
        if package_unit is None:
            return None

        if kind in {"interface", "annotation", "annotation_type"}:
            target = self.factory.create_interface_unit(name)
        elif kind == "module":
            target = self.factory.create_compilation_unit(name)
        elif kind in {"callable", "function", "method"}:
            target = self.factory.create_callable_unit(name)
        else:
            target = self.factory.create_class_unit(name)

        self.factory.add_attribute(target, "external", "true")
        self.factory.add_attribute(target, "external_kind", kind)
        self.factory.add_attribute(target, "qualified_name", qualified_name)
        self.factory.add_attribute(target, "package", package_name)
        self.factory.add_attribute(target, "library", library_name)

        package_unit.codeElement.append(target)
        self.external_targets[key] = target
        self._register_external_aliases(
            str(qualified_name),
            target,
            kind=kind,
            library_name=library_name,
            name=name,
        )
        return target

    def _package_from_qualified_name(self, qualified_name: str):
        qualified_name = self._strip_generic_arguments(qualified_name)
        if not qualified_name or "." not in qualified_name:
            return None
        return qualified_name.rsplit(".", 1)[0]

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
            or import_model.get("name")
            or import_model.get("effective_name")
            or "unknown_external"
        )

        module_name = self._normalize_external_ref(module_name) or "unknown_external"
        if (
            self._is_noise_external_name(module_name)
            or self._is_internal_name(module_name)
            or self._is_internal_module_simple_name(module_name)
        ):
            return None
        library_name = module_name.split(".")[0] if module_name else "unknown_external"

        # For plain imports with aliases (e.g. import numpy as np), the target
        # is the real module, not the alias.
        if import_model.get("type") == "import" and not import_model.get("name"):
            target_name = module_name
        else:
            target_name = (
                import_model.get("name")
                or import_model.get("effective_name")
                or module_name
                or "unknown_external_import"
            )
        target_name = self._normalize_external_ref(str(target_name)) or "unknown_external_import"
        if (
            self._is_internal_simple_name(target_name)
            or self._is_internal_module_simple_name(target_name)
            or self._is_noise_external_name(target_name)
        ):
            return None

        target_kind = self._infer_import_target_kind(import_model)

        key = f"{library_name}:import:{target_kind}:{target_name}"

        if key in self.external_targets:
            return self.external_targets[key]

        external_model = self.ensure_external_model()
        library_unit = self._get_or_create_library_unit(external_model, library_name)
        if library_unit is None:
            return None

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
        }:
            return "class"

        if name and name[:1].isupper():
            return "class"

        # Plain import without imported name is better represented as a module.
        if module and name is None:
            return "module"

        return "callable"
