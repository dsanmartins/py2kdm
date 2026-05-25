from collections import defaultdict

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QTreeWidget, QTreeWidgetItem


class ArchitectureTreeView(QTreeWidget):
    """
    Hierarchical architecture view built from containment_relationships.

    It displays:
        Managing Subsystem -> CL Manager -> Control Loop -> MAPE-K
        Managed Subsystem  -> Sensor / Effector / Measured Output
    """

    element_selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHeaderLabels(["Architecture element", "Role / Stereotype"])
        self.itemSelectionChanged.connect(self._selection_changed)

    def render_model(self, model):
        self.clear()

        if not model:
            return

        structure_model = model.get("structure_model", {})
        nodes = self._collect_nodes(structure_model)
        contains = self._collect_contains(structure_model, nodes)

        children = defaultdict(list)
        parents = defaultdict(list)

        for relationship in contains:
            source = relationship.get("source")
            target = relationship.get("target")
            children[source].append(target)
            parents[target].append(source)

        roots = [
            node_id for node_id, node in nodes.items()
            if not parents[node_id]
            and node.get("node_kind") == "subsystem"
        ]

        if not roots:
            roots = [node_id for node_id in nodes if not parents[node_id]]

        visited = set()

        for root_id in roots:
            self._add_node_recursive(
                parent_item=None,
                node_id=root_id,
                nodes=nodes,
                children=children,
                visited=visited,
            )

        # Add disconnected nodes if any.
        for node_id in nodes:
            if node_id not in visited:
                self._add_node_recursive(
                    parent_item=None,
                    node_id=node_id,
                    nodes=nodes,
                    children=children,
                    visited=visited,
                )

        self.expandAll()
        self.resizeColumnToContents(0)
        self.resizeColumnToContents(1)

    def _collect_nodes(self, structure_model):
        nodes = {}

        for subsystem in structure_model.get("subsystems", []):
            if subsystem.get("materialize", True) is False:
                continue
            node = dict(subsystem)
            node.setdefault("node_kind", "subsystem")
            node.setdefault("role", subsystem.get("stereotype_name", "Subsystem"))
            nodes[node.get("id")] = node

        for loop in structure_model.get("control_loops", []):
            if loop.get("materialize", True) is False:
                continue
            node = dict(loop)
            node.setdefault("node_kind", "control_loop")
            node["role"] = loop.get("stereotype_name") or "Control Loop"
            nodes[node.get("id")] = node

        for component in structure_model.get("components", []):
            if component.get("materialize", True) is False:
                continue
            node = dict(component)
            node.setdefault("node_kind", "component")
            nodes[node.get("id")] = node

        return {node_id: node for node_id, node in nodes.items() if node_id}

    def _collect_contains(self, structure_model, nodes):
        relationships = []

        for relationship in structure_model.get("containment_relationships", []):
            if relationship.get("materialize", True) is False:
                continue
            if relationship.get("type") != "contains":
                continue
            if (
                relationship.get("source") in nodes
                and relationship.get("target") in nodes
            ):
                relationships.append(relationship)

        return relationships

    def _add_node_recursive(self, parent_item, node_id, nodes, children, visited):
        if node_id in visited:
            return

        visited.add(node_id)
        node = nodes[node_id]

        name = node.get("name", node_id)
        role = node.get("stereotype_name") or node.get("role", "-")
        status = node.get("status") or node.get("review_status") or ""

        label = f"{name}"
        if status:
            label += f" ({status})"

        item = QTreeWidgetItem([label, role])
        item.setData(0, Qt.ItemDataRole.UserRole, node_id)

        if parent_item is None:
            self.addTopLevelItem(item)
        else:
            parent_item.addChild(item)

        for child_id in children[node_id]:
            self._add_node_recursive(
                parent_item=item,
                node_id=child_id,
                nodes=nodes,
                children=children,
                visited=visited,
            )

    def _selection_changed(self):
        items = self.selectedItems()
        if not items:
            return

        element_id = items[0].data(0, Qt.ItemDataRole.UserRole)
        if element_id:
            self.element_selected.emit(element_id)
