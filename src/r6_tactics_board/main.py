from r6_tactics_board.app import create_app
from r6_tactics_board.presentation.shell.main_window import MainWindow


def main() -> int:
    app = create_app()
    window = MainWindow()
    window.showMaximized()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
