from pathlib import Path
import sys


PY2KDM_PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PY2KDM_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PY2KDM_PROJECT_ROOT))


from PySide6.QtWidgets import QApplication

from py2kdm_gui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)

    window = MainWindow()
    window.resize(1550, 920)
    window.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
