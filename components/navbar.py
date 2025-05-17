import dash_bootstrap_components as dbc
from dash import html

navbar = dbc.NavbarSimple(
    children=[
        dbc.NavItem(dbc.NavLink("Overview", href="/")),
        dbc.NavItem(dbc.NavLink("Delay Analysis", href="/delays")),
        dbc.NavItem(dbc.NavLink("Cancelled Flights", href="/cancelled")),
    ],
    brand="Flight Delay Dashboard",
    color="primary",
    dark=True,
    sticky="top"
)
