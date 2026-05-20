import math
from collections import defaultdict, deque

from PySide6.QtCore import Qt, QPointF, QTimer
from PySide6.QtGui import (
    QColor,
    QBrush,
    QFont,
    QPainterPath,
    QPen,
    QPolygonF,
    QCursor,
)
from PySide6.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsPathItem,
    QGraphicsPolygonItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
    QGraphicsView,
)

ROLE_COLORS = {
    "Monitor": QColor("#b7d7ff"),
    "Analyzer": QColor("#ffe7a8"),
    "Planner": QColor("#ffd0a8"),
    "Executor": QColor("#ffb3b3"),
    "Knowledge": QColor("#b9f0c4"),
    "LoopManager": QColor("#d6c4ff"),
    "CL Manager": QColor("#d6c4ff"),
    "Loop": QColor("#c8b7ff"),
    "Control Loop": QColor("#c8b7ff"),
    "ReferenceInput": QColor("#f7e7a1"),
    "Reference Input": QColor("#f7e7a1"),
    "MeasuredOutput": QColor("#d7f0ff"),
    "Measured Output": QColor("#d7f0ff"),
    "Sensor": QColor("#cceeff"),
    "Effector": QColor("#ffcccc"),
    "Managing Subsystem": QColor("#e8e8e8"),
    "Managed Subsystem": QColor("#dddddd"),
    "Subsystem": QColor("#e8e8e8"),
    "ArchitectureView": QColor("#eeeeee"),
    "SoftwareSystem": QColor("#eeeeee"),
}


class _MovableNodeMixin:
    def _configure_node_item(self, view, node_id):
        self._graph_view = view
        self._node_id = node_id
        self.setData(0, "architecture_node")
        self.setData(1, node_id)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setZValue(10)

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            view = getattr(self, "_graph_view", None)
            if view is not None:
                view.request_edge_refresh()
        return super().itemChange(change, value)


class MovableEllipseNode(_MovableNodeMixin, QGraphicsEllipseItem):
    def __init__(self, view, node_id, *args):
        super().__init__(*args)
        self._configure_node_item(view, node_id)


class MovableRectNode(_MovableNodeMixin, QGraphicsRectItem):
    def __init__(self, view, node_id, *args):
        super().__init__(*args)
        self._configure_node_item(view, node_id)



class ArchitectureGraphView(QGraphicsView):
    """
    Architecture graph visualization.

    Current version:
    - renders subsystems, control loops and components;
    - uses containment relationships to show the recovered hierarchy;
    - preserves architectural relationships such as mapek_flow and uses_knowledge;
    - shows clearer role colors for Adaptive System Domain stereotypes.
    """

    NODE_HALF_WIDTH = 90
    NODE_HALF_HEIGHT = 36

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setScene(QGraphicsScene(self))

        self._zoom = 0
        self._zoom_min = -8
        self._zoom_max = 18
        self._zoom_factor = 1.18

        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)

        # Manual left-button panning. This is more predictable than relying
        # only on ScrollHandDrag, especially when the scene contains many items.
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self._panning = False
        self._last_pan_point = None
        self.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))

        self._nodes = {}
        self._relationships = []
        self._node_items = {}
        self._edge_items = []
        self._building_scene = False
        self._edge_refresh_pending = False

    def render_model(self, model):
        self.scene().clear()
        self._edge_items = []
        self._node_items = {}
        self._nodes = {}
        self._relationships = []

        if not model:
            return

        self._building_scene = True

        structure_model = model.get("structure_model", {})

        nodes = self._collect_nodes(structure_model)
        relationships = self._collect_relationships(structure_model)

        self._nodes = nodes
        self._relationships = relationships

        if not nodes:
            self._add_legend()
            self._building_scene = False
            return

        positions = self._compute_hierarchical_layout(nodes, relationships)

        # Nodes are added first. Edges are then drawn below them using z-values.
        for node_id, node in nodes.items():
            x, y = positions[node_id]
            self._add_node(node, x, y)

        self._redraw_edges()
        self._add_legend()

        self.scene().setSceneRect(
            self.scene().itemsBoundingRect().adjusted(-120, -120, 120, 120)
        )
        self.reset_zoom_fit()

        self._building_scene = False

    # ------------------------------------------------------------
    # Model normalization
    # ------------------------------------------------------------

    def _collect_nodes(self, structure_model):
        nodes = {}

        for subsystem in structure_model.get("subsystems", []):
            if subsystem.get("materialize", True) is False:
                continue
            node = dict(subsystem)
            node.setdefault("role", subsystem.get("stereotype_name", "Subsystem"))
            node.setdefault("node_kind", "subsystem")
            nodes[node.get("id")] = node

        for loop in structure_model.get("control_loops", []):
            if loop.get("materialize", True) is False:
                continue
            node = dict(loop)
            node["role"] = loop.get("stereotype_name") or "Control Loop"
            node.setdefault("node_kind", "control_loop")
            nodes[node.get("id")] = node

        for component in structure_model.get("components", []):
            if component.get("materialize", True) is False:
                continue
            node = dict(component)
            node.setdefault("node_kind", "component")
            nodes[node.get("id")] = node

        return {node_id: node for node_id, node in nodes.items() if node_id}

    def _collect_relationships(self, structure_model):
        relationships = []

        for relationship in structure_model.get("containment_relationships", []):
            if relationship.get("materialize", True) is False:
                continue
            item = dict(relationship)
            item.setdefault("relationship_level", "architectural")
            item.setdefault("type", "contains")
            relationships.append(item)

        for relationship in structure_model.get("structure_relationships", []):
            if relationship.get("materialize", True) is False:
                continue
            if relationship.get("relationship_level") != "architectural":
                continue

            key = (
                relationship.get("source"),
                relationship.get("type"),
                relationship.get("target"),
            )

            if any(
                key == (
                    existing.get("source"),
                    existing.get("type"),
                    existing.get("target"),
                )
                for existing in relationships
            ):
                continue

            relationships.append(relationship)

        return relationships

    # ------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------

    def _compute_hierarchical_layout(self, nodes, relationships):
        """
        Computes a domain-aware layout for self-adaptive architectures.

        Visual convention:
        - Managing Subsystem appears at the top.
        - CL Manager and Control Loop appear below it.
        - MAPE-K components appear in the middle.
        - Managed-side components, such as Sensor/Effector/Measured Output,
          appear above the Managed Subsystem.
        - Managed Subsystem appears at the bottom.

        This makes cross-boundary relationships visually readable:
            Monitor  -> Sensor / Measured Output
            Executor -> Effector
        """

        semantic_positions = self._compute_adaptive_system_layout(
            nodes,
            relationships,
        )

        if semantic_positions:
            return semantic_positions

        contains = [
            rel for rel in relationships
            if rel.get("type") == "contains"
            and rel.get("source") in nodes
            and rel.get("target") in nodes
        ]

        if not contains:
            return self._compute_circle_layout(nodes)

        children = defaultdict(list)
        parents = defaultdict(list)

        for rel in contains:
            children[rel.get("source")].append(rel.get("target"))
            parents[rel.get("target")].append(rel.get("source"))

        roots = [
            node_id for node_id, node in nodes.items()
            if not parents[node_id]
            and (
                node.get("node_kind") == "subsystem"
                or node.get("role") in {"Managing Subsystem", "Managed Subsystem"}
            )
        ]

        if not roots:
            roots = [node_id for node_id in nodes if not parents[node_id]]

        visited = set()
        levels = defaultdict(list)
        queue = deque()

        for root in roots:
            queue.append((root, 0))

        while queue:
            node_id, depth = queue.popleft()
            if node_id in visited:
                continue
            visited.add(node_id)
            levels[depth].append(node_id)

            for child in children[node_id]:
                queue.append((child, depth + 1))

        remaining = [node_id for node_id in nodes if node_id not in visited]
        if remaining:
            max_depth = max(levels.keys(), default=0) + 1
            levels[max_depth].extend(remaining)

        return self._positions_from_levels(levels, y_start=-260)

    def _compute_adaptive_system_layout(self, nodes, relationships):
        contains = [
            rel for rel in relationships
            if rel.get("type") == "contains"
            and rel.get("source") in nodes
            and rel.get("target") in nodes
        ]

        if not contains:
            return None

        children = defaultdict(list)
        parents = defaultdict(list)

        for rel in contains:
            children[rel.get("source")].append(rel.get("target"))
            parents[rel.get("target")].append(rel.get("source"))

        managing = self._find_node_by_role_or_name(
            nodes,
            {"Managing Subsystem"},
        )
        managed = self._find_node_by_role_or_name(
            nodes,
            {"Managed Subsystem"},
        )

        if not managing and not managed:
            return None

        control_loops = [
            node_id for node_id, node in nodes.items()
            if self._node_role(node) in {"Control Loop", "Loop"}
            or node.get("node_kind") == "control_loop"
        ]

        loop_managers = [
            node_id for node_id, node in nodes.items()
            if self._node_role(node) in {"CL Manager", "LoopManager"}
        ]

        managed_side_roles = {
            "Sensor",
            "Effector",
            "Measured Output",
            "MeasuredOutput",
        }

        managed_side = [
            node_id for node_id, node in nodes.items()
            if self._node_role(node) in managed_side_roles
        ]

        loop_internal_roles = {
            "Monitor",
            "Analyzer",
            "Planner",
            "Executor",
            "Knowledge",
            "Reference Input",
            "ReferenceInput",
        }

        loop_internal = [
            node_id for node_id, node in nodes.items()
            if self._node_role(node) in loop_internal_roles
        ]

        levels = defaultdict(list)

        if managing:
            levels[0].append(managing)

        for node_id in loop_managers:
            if node_id not in levels[1]:
                levels[1].append(node_id)

        for node_id in control_loops:
            if node_id not in levels[2]:
                levels[2].append(node_id)

        for node_id in loop_internal:
            if node_id not in levels[3]:
                levels[3].append(node_id)

        # Managed-side components are intentionally above Managed Subsystem.
        for node_id in managed_side:
            if node_id not in levels[4]:
                levels[4].append(node_id)

        if managed:
            levels[5].append(managed)

        assigned = {
            node_id for level_nodes in levels.values()
            for node_id in level_nodes
        }

        remaining = [
            node_id for node_id in nodes
            if node_id not in assigned
        ]

        if remaining:
            # Keep unclassified nodes between loop internals and managed side.
            levels[4].extend(remaining)

        return self._positions_from_levels(levels, y_start=-360, y_spacing=145)

    def _positions_from_levels(self, levels, y_start=-260, y_spacing=155):
        positions = {}
        x_spacing = 240

        for depth in sorted(levels.keys()):
            level_nodes = levels[depth]
            total_width = (len(level_nodes) - 1) * x_spacing

            for index, node_id in enumerate(level_nodes):
                x = index * x_spacing - total_width / 2
                y = y_start + depth * y_spacing
                positions[node_id] = (x, y)

        return positions

    def _find_node_by_role_or_name(self, nodes, expected_values):
        for node_id, node in nodes.items():
            role = self._node_role(node)
            name = node.get("name")
            if role in expected_values or name in expected_values:
                return node_id
        return None

    def _node_role(self, node):
        return node.get("stereotype_name") or node.get("role", "unknown")

    def _compute_circle_layout(self, nodes, radius=270):
        positions = {}
        node_ids = list(nodes.keys())
        count = len(node_ids)

        for index, node_id in enumerate(node_ids):
            angle = 2 * math.pi * index / max(count, 1)
            positions[node_id] = (
                radius * math.cos(angle),
                radius * math.sin(angle),
            )

        return positions

    def _compute_edge_offsets(self, relationships):
        groups = defaultdict(list)

        for relationship in relationships:
            source = relationship.get("source")
            target = relationship.get("target")

            if not source or not target or source == target:
                continue

            key = tuple(sorted([source, target]))
            groups[key].append(relationship)

        offsets = {}

        for _key, group in groups.items():
            if len(group) == 1:
                offsets[id(group[0])] = 0
                continue

            center = (len(group) - 1) / 2
            spacing = 42

            for index, relationship in enumerate(group):
                offsets[id(relationship)] = int((index - center) * spacing)

        return offsets

    # ------------------------------------------------------------
    # Nodes
    # ------------------------------------------------------------

    def _add_node(self, node, x, y):
        role = node.get("stereotype_name") or node.get("role", "unknown")
        name = node.get("name", "Component")
        node_kind = node.get("node_kind")
        node_id = node.get("id")

        if node_kind == "subsystem":
            item = MovableRectNode(
                self,
                node_id,
                -self.NODE_HALF_WIDTH,
                -self.NODE_HALF_HEIGHT,
                2 * self.NODE_HALF_WIDTH,
                2 * self.NODE_HALF_HEIGHT,
            )
        else:
            item = MovableEllipseNode(
                self,
                node_id,
                -self.NODE_HALF_WIDTH,
                -self.NODE_HALF_HEIGHT,
                2 * self.NODE_HALF_WIDTH,
                2 * self.NODE_HALF_HEIGHT,
            )

        item.setPos(x, y)
        item.setBrush(QBrush(ROLE_COLORS.get(role, QColor("#eeeeee"))))

        pen = QPen(QColor("#444444"))
        pen.setWidth(2)

        if node.get("review_status") == "user_rejected":
            pen.setColor(QColor("#cc0000"))
            pen.setStyle(Qt.PenStyle.DashLine)

        item.setPen(pen)
        self.scene().addItem(item)
        self._node_items[node_id] = item

        label = QGraphicsSimpleTextItem(f"{name}\n[{role}]", item)
        label.setFont(QFont("Arial", 9))
        label.setData(0, "architecture_node_label")
        label.setData(1, node_id)
        rect = label.boundingRect()
        label.setPos(-rect.width() / 2, -rect.height() / 2)
        label.setZValue(11)

    # ------------------------------------------------------------
    # Edges
    # ------------------------------------------------------------

    def _add_edge(self, relationship, source_pos, target_pos, curve_offset=0):
        relation_type = relationship.get("type", "relationship")

        pen = QPen(QColor("#d0d0d0"))
        pen.setWidth(2)

        if relation_type == "uses_knowledge":
            pen.setStyle(Qt.PenStyle.DashLine)
        elif relation_type == "contains":
            pen.setStyle(Qt.PenStyle.SolidLine)
            pen.setColor(QColor("#ffffff"))
        else:
            pen.setStyle(Qt.PenStyle.SolidLine)

        start, end = self._edge_boundary_points(source_pos, target_pos)
        control = self._control_point(start, end, curve_offset)

        path = QPainterPath()
        path.moveTo(start)
        path.quadTo(control, end)

        edge_item = QGraphicsPathItem(path)
        edge_item.setPen(pen)
        edge_item.setZValue(-10)
        self.scene().addItem(edge_item)
        self._edge_items.append(edge_item)

        self._add_filled_arrow_head(
            start=start,
            control=control,
            end=end,
            pen=pen,
        )

        label_pos = self._quadratic_point(start, control, end, 0.52)
        self._add_edge_label(
            text=relation_type,
            pos=(label_pos.x(), label_pos.y()),
        )

    def _edge_boundary_points(self, source_pos, target_pos):
        sx, sy = source_pos
        tx, ty = target_pos

        dx = tx - sx
        dy = ty - sy
        distance = math.hypot(dx, dy)

        if distance == 0:
            return QPointF(sx, sy), QPointF(tx, ty)

        ux = dx / distance
        uy = dy / distance

        start = QPointF(
            sx + self.NODE_HALF_WIDTH * ux,
            sy + self.NODE_HALF_HEIGHT * uy,
        )
        end = QPointF(
            tx - self.NODE_HALF_WIDTH * ux,
            ty - self.NODE_HALF_HEIGHT * uy,
        )

        return start, end

    def _control_point(self, start, end, offset):
        mx = (start.x() + end.x()) / 2
        my = (start.y() + end.y()) / 2

        dx = end.x() - start.x()
        dy = end.y() - start.y()
        length = math.hypot(dx, dy)

        if length == 0 or offset == 0:
            return QPointF(mx, my)

        px = -dy / length
        py = dx / length

        return QPointF(mx + px * offset, my + py * offset)

    def _add_filled_arrow_head(self, start, control, end, pen):
        dx = end.x() - control.x()
        dy = end.y() - control.y()
        angle = math.atan2(dy, dx)

        arrow_size = 13

        p_tip = QPointF(end.x(), end.y())
        p_left = QPointF(
            end.x() - arrow_size * math.cos(angle - math.pi / 7),
            end.y() - arrow_size * math.sin(angle - math.pi / 7),
        )
        p_right = QPointF(
            end.x() - arrow_size * math.cos(angle + math.pi / 7),
            end.y() - arrow_size * math.sin(angle + math.pi / 7),
        )

        polygon = QPolygonF([p_tip, p_left, p_right])

        arrow = QGraphicsPolygonItem(polygon)
        arrow.setPen(pen)
        arrow.setBrush(QBrush(pen.color()))
        arrow.setZValue(-9)
        self.scene().addItem(arrow)
        self._edge_items.append(arrow)

    def _quadratic_point(self, start, control, end, t):
        x = (
            (1 - t) * (1 - t) * start.x()
            + 2 * (1 - t) * t * control.x()
            + t * t * end.x()
        )
        y = (
            (1 - t) * (1 - t) * start.y()
            + 2 * (1 - t) * t * control.y()
            + t * t * end.y()
        )

        return QPointF(x, y)

    def _add_edge_label(self, text, pos):
        x, y = pos

        label = QGraphicsSimpleTextItem(text)
        label.setFont(QFont("Arial", 8))
        label.setBrush(QBrush(QColor("#ffffff")))

        rect = label.boundingRect()

        background = QGraphicsRectItem(
            x - rect.width() / 2 - 4,
            y - rect.height() / 2 - 2,
            rect.width() + 8,
            rect.height() + 4,
        )
        background.setBrush(QBrush(QColor(20, 20, 20, 210)))
        background.setPen(QPen(Qt.PenStyle.NoPen))

        label.setPos(
            x - rect.width() / 2,
            y - rect.height() / 2,
        )

        background.setZValue(-8)
        label.setZValue(-7)
        self.scene().addItem(background)
        self.scene().addItem(label)
        self._edge_items.append(background)
        self._edge_items.append(label)

    # ------------------------------------------------------------
    # Interactive node movement
    # ------------------------------------------------------------

    def request_edge_refresh(self):
        """
        Called whenever a node is moved. Edges are redrawn after the current
        Qt event finishes, avoiding excessive redraw recursion while dragging.
        """

        if self._building_scene:
            return

        if self._edge_refresh_pending:
            return

        self._edge_refresh_pending = True
        QTimer.singleShot(0, self._redraw_edges)

    def _redraw_edges(self):
        self._edge_refresh_pending = False

        for item in list(self._edge_items):
            if item.scene() is self.scene():
                self.scene().removeItem(item)

        self._edge_items = []

        if not self._relationships or not self._node_items:
            return

        positions = {
            node_id: (item.pos().x(), item.pos().y())
            for node_id, item in self._node_items.items()
        }

        edge_offsets = self._compute_edge_offsets(self._relationships)

        for relationship in self._relationships:
            source = relationship.get("source")
            target = relationship.get("target")

            if source in positions and target in positions:
                offset = edge_offsets.get(id(relationship), 0)
                self._add_edge(
                    relationship=relationship,
                    source_pos=positions[source],
                    target_pos=positions[target],
                    curve_offset=offset,
                )

    # ------------------------------------------------------------
    # Zoom and navigation
    # ------------------------------------------------------------

    def wheelEvent(self, event):
        """
        Zoom with mouse wheel.

        - Wheel up: zoom in.
        - Wheel down: zoom out.
        - The zoom is anchored under the mouse cursor.
        """

        if event.angleDelta().y() > 0:
            if self._zoom >= self._zoom_max:
                return
            zoom_factor = self._zoom_factor
            self._zoom += 1
        else:
            if self._zoom <= self._zoom_min:
                return
            zoom_factor = 1 / self._zoom_factor
            self._zoom -= 1

        self.scale(zoom_factor, zoom_factor)

    def _is_architecture_node_item(self, item):
        while item is not None:
            if item.data(0) == "architecture_node":
                return True
            item = item.parentItem()
        return False

    def mousePressEvent(self, event):
        """
        Left-button behavior:
        - if the cursor is over a node, let Qt move the node;
        - otherwise, pan the whole scene.
        """

        if event.button() == Qt.MouseButton.LeftButton:
            clicked_item = self.itemAt(event.position().toPoint())

            if self._is_architecture_node_item(clicked_item):
                super().mousePressEvent(event)
                return

            self._panning = True
            self._last_pan_point = event.position().toPoint()
            self.setCursor(QCursor(Qt.CursorShape.ClosedHandCursor))
            event.accept()
            return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """
        Move the view while the left mouse button is pressed.
        """

        if self._panning and self._last_pan_point is not None:
            current_pos = event.position().toPoint()
            delta = current_pos - self._last_pan_point
            self._last_pan_point = current_pos

            self.horizontalScrollBar().setValue(
                self.horizontalScrollBar().value() - delta.x()
            )
            self.verticalScrollBar().setValue(
                self.verticalScrollBar().value() - delta.y()
            )

            event.accept()
            return

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """
        Stop panning when the left mouse button is released.
        """

        if event.button() == Qt.MouseButton.LeftButton and self._panning:
            self._panning = False
            self._last_pan_point = None
            self.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))

            event.accept()
            return

        super().mouseReleaseEvent(event)

    def reset_zoom_fit(self):
        """
        Fits the whole architecture graph in the viewport and resets the zoom
        counter. Called after re-rendering the scene.
        """

        self.resetTransform()
        self._zoom = 0

        if not self.scene().items():
            return

        self.fitInView(
            self.scene().sceneRect(),
            Qt.AspectRatioMode.KeepAspectRatio,
        )

    # ------------------------------------------------------------
    # Legend
    # ------------------------------------------------------------

    def _add_legend(self):
        x = -520
        y = -420

        title = QGraphicsSimpleTextItem("Legend")
        title.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        title.setBrush(QBrush(QColor("#ffffff")))
        title.setPos(x, y)
        self.scene().addItem(title)

        self._add_legend_line(
            x=x,
            y=y + 28,
            text="continuous white line: contains",
            dashed=False,
            color=QColor("#ffffff"),
        )
        self._add_legend_line(
            x=x,
            y=y + 52,
            text="continuous grey line: mapek_flow / architectural flow",
            dashed=False,
            color=QColor("#d0d0d0"),
        )
        self._add_legend_line(
            x=x,
            y=y + 76,
            text="dashed grey line: uses_knowledge",
            dashed=True,
            color=QColor("#d0d0d0"),
        )

    def _add_legend_line(self, x, y, text, dashed=False, color=None):
        pen = QPen(color or QColor("#d0d0d0"))
        pen.setWidth(2)

        if dashed:
            pen.setStyle(Qt.PenStyle.DashLine)

        path = QPainterPath()
        path.moveTo(QPointF(x, y + 8))
        path.quadTo(QPointF(x + 27, y - 5), QPointF(x + 55, y + 8))

        line = QGraphicsPathItem(path)
        line.setPen(pen)
        self.scene().addItem(line)

        label = QGraphicsSimpleTextItem(text)
        label.setFont(QFont("Arial", 8))
        label.setBrush(QBrush(QColor("#ffffff")))
        label.setPos(x + 65, y)
        self.scene().addItem(label)
