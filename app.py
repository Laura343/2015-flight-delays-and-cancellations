import dash
import dash_bootstrap_components as dbc
from dash import dcc, html, Input, Output
from components.navbar import navbar

app = dash.Dash(__name__, use_pages=True, external_stylesheets=[dbc.themes.FLATLY])
server = app.server

app.layout = dbc.Container([
    dcc.Location(id='url', refresh=False),
    navbar,
    dash.page_container
], fluid=True)

if __name__ == '__main__':
    app.run(debug=True)
