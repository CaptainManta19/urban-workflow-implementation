from pathlib import Path

from dash import Dash

from frontend.callbacks import register_callbacks
from frontend.layout import build_app_layout

ASSETS_DIR = Path(__file__).resolve().parent / "assets"

app = Dash(__name__, assets_folder=str(ASSETS_DIR))
app.title = "Madrid District Explorer"
app.layout = build_app_layout()
register_callbacks(app)


def main() -> None:
    app.run(debug=False)


if __name__ == "__main__":
    main()
