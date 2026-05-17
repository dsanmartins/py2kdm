import hashlib


class BodyCallSynchronizer:
    """
    Synchronizes flat call models with calls embedded in hierarchical body nodes.

    During extraction, calls appear in two places:

    1. As a flat list in each callable model:

        callable_model["calls"]

    2. Inside hierarchical body nodes, for example:

        body_node["call"]
        body_node["value_call"]
        body_node["value_calls"]
        body_node["condition_calls"]
        body_node["iter_calls"]
        body_node["exception_calls"]
        with_item["context_calls"]

    CallResolver enriches the flat calls with semantic information such as
    classification, target_id, receiver_type and candidate_targets. This
    synchronizer copies that information back into the corresponding body calls.

    This is required because kdm_pyecore_generator builds the executable KDM
    action structure from the hierarchical body representation, not only from
    the flat call list.
    """

    def sync_project_body_calls(self, project_model: dict):
        """
        Synchronizes body calls for all functions and methods in a project.

        Parameters
        ----------
        project_model:
            Intermediate project model produced by the extractor.

        Returns
        -------
        dict
            The same project model, enriched in place.
        """

        for file_model in project_model.get("files", []):
            if "error" in file_model:
                continue

            for function_model in file_model.get("functions", []):
                self._sync_callable_body_calls(function_model)

            for class_model in file_model.get("classes", []):
                for method_model in class_model.get("methods", []):
                    self._sync_callable_body_calls(method_model)

        return project_model

    def _sync_callable_body_calls(self, callable_model: dict):
        """
        Synchronizes all body calls inside a single function or method.

        The process has three steps:

        1. Assign stable ids to flat calls.
        2. Build an index of flat calls by name and line.
        3. Recursively synchronize calls inside body nodes.
        """

        self._assign_call_ids(callable_model)

        call_index = self._build_call_index(callable_model)

        self._sync_body_nodes(
            callable_model.get("body", []),
            call_index,
        )

    def _assign_call_ids(self, callable_model: dict):
        """
        Assigns stable ids to flat calls inside callable_model["calls"].

        Calls are identified by callable id, call name, source line and
        occurrence index. The occurrence index avoids collisions when the same
        call appears multiple times on the same line.
        """

        occurrence_counter = {}

        for call_model in callable_model.get("calls", []):
            call_name = call_model.get("name")
            line = call_model.get("line")

            key = (call_name, line)

            occurrence_index = occurrence_counter.get(key, 0)
            occurrence_counter[key] = occurrence_index + 1

            call_model["occurrence_index"] = occurrence_index

            if "id" not in call_model:
                call_model["id"] = self._make_call_id(
                    callable_model.get("id"),
                    call_name,
                    line,
                    occurrence_index,
                )

    def _build_call_index(self, callable_model: dict):
        """
        Builds an index of flat calls by call name and source line.

        Returns
        -------
        dict
            Mapping from (call_name, line) to a list of call models.
        """

        call_index = {}

        for call_model in callable_model.get("calls", []):
            key = (
                call_model.get("name"),
                call_model.get("line"),
            )

            call_index.setdefault(key, []).append(call_model)

        return call_index

    def _sync_body_nodes(self, body_nodes: list, call_index: dict):
        """
        Recursively synchronizes calls inside hierarchical body nodes.
        """

        for body_node in body_nodes:
            if body_node.get("statement_type") == "call":
                self._sync_call_statement(body_node, call_index)

            self._sync_single_embedded_call(
                body_node,
                "value_call",
                call_index,
            )

            self._sync_call_list(
                body_node,
                "value_calls",
                call_index,
            )

            self._sync_call_list(
                body_node,
                "condition_calls",
                call_index,
            )

            self._sync_call_list(
                body_node,
                "iter_calls",
                call_index,
            )

            self._sync_call_list(
                body_node,
                "exception_calls",
                call_index,
            )

            self._sync_with_item_context_calls(body_node, call_index)

            self._sync_body_nodes(
                body_node.get("body", []),
                call_index,
            )

            self._sync_body_nodes(
                body_node.get("orelse", []),
                call_index,
            )

            self._sync_body_nodes(
                body_node.get("finalbody", []),
                call_index,
            )

            for handler in body_node.get("handlers", []):
                self._sync_body_nodes(
                    handler.get("body", []),
                    call_index,
                )

    def _sync_call_statement(self, body_node: dict, call_index: dict):
        """
        Synchronizes a body node of type statement/call.
        """

        body_call = body_node.get("call")

        if not body_call:
            return

        matched_call = self._find_matching_flat_call(body_call, call_index)

        if matched_call is None:
            body_node["call_sync_status"] = "unmatched"
            return

        body_node["call_id"] = matched_call.get("id")
        body_node["call_sync_status"] = "matched"
        body_node["call"] = self._merge_call_information(
            body_call,
            matched_call,
        )

    def _sync_single_embedded_call(
        self,
        body_node: dict,
        call_field: str,
        call_index: dict,
    ):
        """
        Synchronizes a single embedded call field.

        Example
        -------
        value_call in an assignment:

            user = User()
        """

        body_call = body_node.get(call_field)

        if not body_call:
            return

        matched_call = self._find_matching_flat_call(body_call, call_index)

        if matched_call is None:
            body_node[f"{call_field}_sync_status"] = "unmatched"
            return

        body_node[f"{call_field}_id"] = matched_call.get("id")
        body_node[f"{call_field}_sync_status"] = "matched"
        body_node[call_field] = self._merge_call_information(
            body_call,
            matched_call,
        )

    def _sync_call_list(
        self,
        body_node: dict,
        call_field: str,
        call_index: dict,
    ):
        """
        Synchronizes a list of embedded calls.

        Examples
        --------
        - value_calls inside return expressions.
        - condition_calls inside if or while conditions.
        - exception_calls inside raise expressions.
        """

        calls = body_node.get(call_field)

        if not calls:
            return

        synced_calls = []
        unmatched_calls = []

        for body_call in calls:
            matched_call = self._find_matching_flat_call(body_call, call_index)

            if matched_call is None:
                unmatched_calls.append(body_call)
                synced_calls.append(body_call)
                continue

            synced_calls.append(
                self._merge_call_information(body_call, matched_call)
            )

        body_node[call_field] = synced_calls

        if unmatched_calls:
            body_node[f"{call_field}_sync_status"] = "partially_matched"
            body_node[f"{call_field}_unmatched"] = unmatched_calls
        else:
            body_node[f"{call_field}_sync_status"] = "matched"

    def _sync_with_item_context_calls(self, body_node: dict, call_index: dict):
        """
        Synchronizes context calls inside with items.

        Example
        -------
        with open(...) as file:
            ...
        """

        if body_node.get("control_type") not in {"with", "async_with"}:
            return

        for item in body_node.get("items", []):
            calls = item.get("context_calls")

            if not calls:
                continue

            synced_calls = []
            unmatched_calls = []

            for body_call in calls:
                matched_call = self._find_matching_flat_call(
                    body_call,
                    call_index,
                )

                if matched_call is None:
                    unmatched_calls.append(body_call)
                    synced_calls.append(body_call)
                    continue

                synced_calls.append(
                    self._merge_call_information(body_call, matched_call)
                )

            item["context_calls"] = synced_calls

            if unmatched_calls:
                item["context_calls_sync_status"] = "partially_matched"
                item["context_calls_unmatched"] = unmatched_calls
            else:
                item["context_calls_sync_status"] = "matched"

    def _find_matching_flat_call(self, body_call: dict, call_index: dict):
        """
        Finds the corresponding flat call using name and source line.

        The first available candidate is consumed with pop(0), which preserves
        occurrence order when several identical calls appear on the same line.
        """

        key = (
            body_call.get("name"),
            body_call.get("line"),
        )

        candidates = call_index.get(key, [])

        if not candidates:
            return None

        return candidates.pop(0)

    def _merge_call_information(self, body_call: dict, matched_call: dict):
        """
        Copies resolution information from a flat call into a body call.

        The body call keeps its original syntactic information, while semantic
        fields produced by CallResolver are copied from the matched flat call.
        """

        merged_call = dict(body_call)

        fields_to_copy = [
            "id",
            "kind",
            "name",
            "receiver",
            "method",
            "function",
            "class_name",
            "line",
            "classification",
            "resolved",
            "target_id",
            "candidate_targets",
            "import_source",
            "receiver_type",
            "receiver_type_id",
            "occurrence_index",
            "chained_receiver",
            "base_receiver",
            "base_receiver_type",
            "base_receiver_type_id",
            "previous_method",
            "previous_return_type",
            "inferred_from_chained_call",
            "external_factory",
            "resolved_from_cls",
            "resolved_from_context_manager",
            "context_variable",
            "context_factory",
        ]

        for field in fields_to_copy:
            if field in matched_call:
                merged_call[field] = matched_call.get(field)

        return merged_call

    def _make_call_id(
        self,
        callable_id: str,
        call_name: str,
        line: int,
        occurrence_index: int,
    ):
        """
        Builds a stable call id.

        The id is based on the callable id, call name, source line and
        occurrence index.
        """

        raw_key = f"{callable_id}|{call_name}|{line}|{occurrence_index}"

        digest = hashlib.sha1(
            raw_key.encode("utf-8")
        ).hexdigest()[:12]

        return f"call:{digest}"
