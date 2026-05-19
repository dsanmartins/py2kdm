import math
from collections import defaultdict

from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import (
    QColor,
    QBrush,
    QFont,
    QPainterPath,
    QPen,
    QPolygonF,
)
from PySide6.QtWidgets import (
    QGraphicsEllipseItem,
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
    "ManagedElement": QColor("#dddddd"),
    "Sensor": QColor("#cceeff"),
    "Effector": QColor("#ffcccc"),
}


class ArchitectureGraphView(QGraphicsView):
    """
    Architecture graph visualization.

    Step 2 improvement:
    - edges stop at node boundaries instead of crossing through node centers;
    - arrow heads are filled triangles;
    - opposite or repeated edges are curved so mapek_flow arrows do not overlap;
    - relationship labels are placed near the curve midpoint;
    - legend is preserved.
    """

    NODE_HALF_WIDTH = 75
    NODE_HALF_HEIGHT = 35

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setScene(QGraphicsScene(self))

    def render_model(self, model):
        self.scene().clear()

        if not model:
            return

        structure_model = model.get("structure_model", {})

        components = [
            component
            for component in structure_model.get("components", [])
            if component.get("materialize", True) is not False
        ]

        relationships = [
            relationship
            for relationship in structure_model.get("structure_relationships", [])
            if relationship.get("materialize", True) is not False
            and relationship.get("relationship_level") == "architectural"
        ]

        if not components:
            self._add_legend()
            return

        positions = self._compute_circle_layout(components, radius=270)
        edge_offsets = self._compute_edge_offsets(relationships)

        # Draw edges first, so nodes appear above them.
        for relationship in relationships:
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

        for component in components:
            component_id = component.get("id")
            x, y = positions[component_id]
            self._add_node(component, x, y)

        self._add_legend()

        self.scene().setSceneRect(
            self.scene().itemsBoundingRect().adjusted(-90, -90, 90, 90)
        )
        self.fitInView(
            self.scene().sceneRect(),
            Qt.AspectRatioMode.KeepAspectRatio,
        )

    # ------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------

    def _compute_circle_layout(self, components, radius=270):
        positions = {}
        count = len(components)

        for index, component in enumerate(components):
            angle = 2 * math.pi * index / max(count, 1)
            positions[component.get("id")] = (
                radius * math.cos(angle),
                radius * math.sin(angle),
            )

        return positions

    def _compute_edge_offsets(self, relationships):
        """
        Assigns curve offsets to edges.

        If A -> B and B -> A both exist, the two curves receive opposite offsets.
        If several edges share the same unordered pair, offsets are spread.
        """

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

            # Example for 2 edges: -35, +35
            # Example for 3 edges: -50, 0, +50
            center = (len(group) - 1) / 2
            spacing = 42

            for index, relationship in enumerate(group):
                offsets[id(relationship)] = int((index - center) * spacing)

        return offsets

    # ------------------------------------------------------------
    # Nodes
    # ------------------------------------------------------------

    def _add_node(self, component, x, y):
        role = component.get("role", "unknown")
        name = component.get("name", "Component")

        item = QGraphicsEllipseItem(
            x - self.NODE_HALF_WIDTH,
            y - self.NODE_HALF_HEIGHT,
            2 * self.NODE_HALF_WIDTH,
            2 * self.NODE_HALF_HEIGHT,
        )
        item.setBrush(QBrush(ROLE_COLORS.get(role, QColor("#eeeeee"))))

        pen = QPen(QColor("#444444"))
        pen.setWidth(2)

        if component.get("review_status") == "user_rejected":
            pen.setColor(QColor("#cc0000"))
            pen.setStyle(Qt.PenStyle.DashLine)

        item.setPen(pen)
        self.scene().addItem(item)

        label = QGraphicsSimpleTextItem(f"{name}\n[{role}]")
        label.setFont(QFont("Arial", 9))
        rect = label.boundingRect()
        label.setPos(x - rect.width() / 2, y - rect.height() / 2)
        self.scene().addItem(label)

    # ------------------------------------------------------------
    # Edges
    # ------------------------------------------------------------

    def _add_edge(self, relationship, source_pos, target_pos, curve_offset=0):
        relation_type = relationship.get("type", "relationship")

        pen = QPen(QColor("#d0d0d0"))
        pen.setWidth(2)

        if relation_type == "uses_knowledge":
            pen.setStyle(Qt.PenStyle.DashLine)
        else:
            pen.setStyle(Qt.PenStyle.SolidLine)

        start, end = self._edge_boundary_points(source_pos, target_pos)
        control = self._control_point(start, end, curve_offset)

        path = QPainterPath()
        path.moveTo(start)
        path.quadTo(control, end)

        edge_item = QGraphicsPathItem(path)
        edge_item.setPen(pen)
        self.scene().addItem(edge_item)

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
        """
        Returns approximate boundary points for ellipse-like nodes.

        This prevents edges from visually crossing through node centers.
        """

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

        # Unit perpendicular vector.
        px = -dy / length
        py = dx / length

        return QPointF(mx + px * offset, my + py * offset)

    def _add_filled_arrow_head(self, start, control, end, pen):
        """
        Draws a filled triangular arrow head at the target side of the curve.
        """

        # Tangent of quadratic Bezier at t=1 is end - control.
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
        self.scene().addItem(arrow)

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

        self.scene().addItem(background)
        self.scene().addItem(label)

    # ------------------------------------------------------------
    # Legend
    # ------------------------------------------------------------

    def _add_legend(self):
        x = -430
        y = -370

        title = QGraphicsSimpleTextItem("Legend")
        title.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        title.setBrush(QBrush(QColor("#ffffff")))
        title.setPos(x, y)
        self.scene().addItem(title)

        self._add_legend_line(
            x=x,
            y=y + 28,
            text="continuous curved line: mapek_flow / architectural flow",
            dashed=False,
        )
        self._add_legend_line(
            x=x,
            y=y + 52,
            text="dashed curved line: uses_knowledge",
            dashed=True,
        )

    def _add_legend_line(self, x, y, text, dashed=False):
        pen = QPen(QColor("#d0d0d0"))
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
