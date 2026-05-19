import sys
from PySide6.QtWidgets import QApplication
from kdm_architecture_review.gui.main_window import MainWindow

def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.resize(1400, 850)
    window.show()
    return app.exec()

if __name__ == "__main__":
    raise SystemExit(main())
