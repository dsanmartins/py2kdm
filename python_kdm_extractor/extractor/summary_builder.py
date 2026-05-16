class SummaryBuilder:
    """
    Builds a statistical summary of the intermediate project model.

    The summary is useful for quickly validating the extraction process
    and checking whether the model contains the expected number of modules,
    classes, methods, functions, calls, elements, relationships, and body nodes.
    """

    def build_summary(self, project_model: dict):
        """
        Builds and attaches a summary to the project model.
        """

        summary = {
            "modules": 0,
            "classes": 0,
            "methods": 0,
            "functions": 0,
            "class_attributes": 0,
            "instance_attributes": 0,
            "calls": 0,
            "resolved_calls": 0,
            "unresolved_calls": 0,
            "internal_calls": 0,
            "external_calls": 0,
            "builtin_calls": 0,
            "builtin_type_method_calls": 0,
            "constructor_calls": 0,
            "external_type_method_calls": 0,
            "ambiguous_calls": 0,
            "control_structures": 0,
            "statements": 0,
            "body_nodes": 0,
            "parameters": 0,
            "annotated_parameters": 0,
            "resolved_parameters": 0,
            "context_variables": 0,
            "resolved_context_variables": 0,
            "elements": len(project_model.get("elements", [])),
            "relationships": len(project_model.get("relationships", []))
        }

        for file_model in project_model.get("files", []):
            if "error" in file_model:
                continue

            summary["modules"] += 1

            functions = file_model.get("functions", [])
            summary["functions"] += len(functions)

            for function_model in functions:
                self._count_parameters(function_model, summary)
                self._count_context_variables(function_model, summary)
                self._count_calls(function_model, summary)
                self._count_body_nodes(
                    function_model.get("body", []),
                    summary
                )

            for class_model in file_model.get("classes", []):
                summary["classes"] += 1
                summary["methods"] += len(class_model.get("methods", []))
                summary["class_attributes"] += len(
                    class_model.get("attributes", [])
                )
                summary["instance_attributes"] += len(
                    class_model.get("instance_attributes", [])
                )

                for method_model in class_model.get("methods", []):
                    self._count_parameters(method_model, summary)
                    self._count_context_variables(method_model, summary)
                    self._count_calls(method_model, summary)
                    self._count_body_nodes(
                        method_model.get("body", []),
                        summary
                    )

        project_model["summary"] = summary

        return project_model

    def _count_calls(self, callable_model: dict, summary: dict):
        """
        Counts calls inside a function or method.
        """

        for call_model in callable_model.get("calls", []):
            summary["calls"] += 1

            classification = call_model.get("classification")
            kind = call_model.get("kind")

            if call_model.get("resolved"):
                summary["resolved_calls"] += 1
            elif classification == "external":
                pass
            else:
                summary["unresolved_calls"] += 1

            if classification == "internal":
                summary["internal_calls"] += 1

            elif classification == "external":
                summary["external_calls"] += 1

            elif classification == "builtin":
                summary["builtin_calls"] += 1

            elif classification == "builtin_type_method":
                summary["builtin_type_method_calls"] += 1

            elif classification == "external_type_method":
                summary["external_type_method_calls"] += 1

            elif classification in {
                "internal_ambiguous",
                "constructor_ambiguous"
            }:
                summary["ambiguous_calls"] += 1

            if kind == "constructor_call":
                summary["constructor_calls"] += 1

    def _count_body_nodes(self, body_nodes: list, summary: dict):
        """
        Counts body nodes recursively.

        Body nodes include control structures, statements, and exception handlers
        contained in the hierarchical body representation of functions and methods.
        """

        for body_node in body_nodes:
            summary["body_nodes"] += 1

            node_type = body_node.get("type")

            if node_type == "control_structure":
                summary["control_structures"] += 1

            elif node_type == "statement":
                summary["statements"] += 1

            elif node_type == "exception_handler":
                summary["statements"] += 1

            self._count_body_nodes(
                body_node.get("body", []),
                summary
            )

            self._count_body_nodes(
                body_node.get("orelse", []),
                summary
            )

            self._count_body_nodes(
                body_node.get("finalbody", []),
                summary
            )

            for handler in body_node.get("handlers", []):
                summary["body_nodes"] += 1
                summary["statements"] += 1

                self._count_body_nodes(
                    handler.get("body", []),
                    summary
                )

    def _count_parameters(self, callable_model: dict, summary: dict):
        """
        Counts parameters and annotated parameters.
        """

        for parameter in callable_model.get("parameters", []):
            summary["parameters"] += 1

            if isinstance(parameter, str):
                continue

            if parameter.get("annotation"):
                summary["annotated_parameters"] += 1

            if parameter.get("resolved_type_id"):
                summary["resolved_parameters"] += 1

    def _count_context_variables(self, callable_model: dict, summary: dict):
        """
        Counts variables introduced by context managers.
        """

        for variable in callable_model.get("context_variables", []):
            summary["context_variables"] += 1

            if variable.get("resolved_type_id"):
                summary["resolved_context_variables"] += 1
