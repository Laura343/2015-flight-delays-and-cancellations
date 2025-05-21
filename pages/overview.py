import dash
from dash import html, dcc, Input, Output
import dash_bootstrap_components as dbc
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import random

dash.register_page(__name__, path='/')

# Load data
flights = pd.read_csv('data/flights.csv', low_memory=False)
airlines = pd.read_csv('data/airlines.csv')
airports = pd.read_csv('data/airports.csv')

# Mappings and enrichment
airline_map = dict(zip(airlines['IATA_CODE'], airlines['AIRLINE']))
airport_coords = airports.set_index('IATA_CODE')[['LATITUDE', 'LONGITUDE']].dropna()
city_map = dict(zip(airports['IATA_CODE'], airports['CITY']))

flights['AIRLINE_NAME'] = flights['AIRLINE'].map(airline_map)
flights['ORIGIN_CITY'] = flights['ORIGIN_AIRPORT'].map(city_map)
flights['DEST_CITY'] = flights['DESTINATION_AIRPORT'].map(city_map)
flights['ROUTE'] = flights['ORIGIN_CITY'] + " → " + flights['DEST_CITY']
flights['DAY_NAME'] = flights['DAY_OF_WEEK'].map({1: 'Mon', 2: 'Tue', 3: 'Wed', 4: 'Thu', 5: 'Fri', 6: 'Sat', 7: 'Sun'})
flights['MONTH_NAME'] = flights['MONTH'].map({
    1: 'Jan', 2: 'Feb', 3: 'Mar', 4: 'Apr', 5: 'May', 6: 'Jun',
    7: 'Jul', 8: 'Aug', 9: 'Sep', 10: 'Oct', 11: 'Nov', 12: 'Dec'
})

layout = dbc.Container([
    html.H2("Flight Overview"),
    html.P("Analyze key airline and airport patterns."),

    html.Label("✈️ Select an airline for filtered visuals"),
    dcc.Dropdown(
        options=[{'label': name, 'value': code} for code, name in airline_map.items()],
        id='airline-selector',
        placeholder='Select an airline (optional)'
    ),
    html.Br(),

    # Airline-focused visuals
    dbc.Row([
        dbc.Col(dcc.Graph(id='airline-bar'), md=6),
        dbc.Col(dcc.Graph(id='top-routes'), md=6)
    ]),
    dbc.Row([
        dbc.Col(dcc.Graph(id='us-flight-map'), md=12)
    ]),

    # Time-focused trends
    html.Br(), html.Hr(),
    html.H4("📅 Time Trends"),
    dbc.Row([
        dbc.Col(dcc.Graph(id='day-busy-bar'), md=6),
        dbc.Col(dcc.Graph(id='month-trend'), md=6)
    ]),

    # Origin and destination insights
    html.Br(), html.Hr(),
    html.H4("🏙️ Top Origin/Destination Airports"),
    dbc.Row([
        dbc.Col(dcc.Graph(id='origin-treemap'), md=6),
        dbc.Col(dcc.Graph(id='dest-treemap'), md=6)
    ]),
    dbc.Row([
        dbc.Col(dcc.Graph(id='busiest-airports'), md=12)
    ])
], fluid=True)

# Callbacks
@dash.callback(Output('airline-bar', 'figure'), Input('airline-selector', 'value'))
def airline_share(airline):
    counts = flights['AIRLINE_NAME'].value_counts().reset_index()
    counts.columns = ['Airline', 'Flights']

    if airline:
        selected_name = airline_map.get(airline)
        counts['Highlight'] = counts['Airline'].apply(lambda x: 'Selected' if x == selected_name else 'Other')
        return px.bar(
            counts, x='Flights', y='Airline', orientation='h',
            title='Airline Market Share',
            color='Highlight',
            color_discrete_map={
                'Selected': 'darkred', 
                'Other': 'lightblue'
            }
        )
    else:
        fig = px.bar(
            counts, x='Flights', y='Airline', orientation='h',
            title='Airline Market Share'
        )
        fig.update_traces(marker_color='steelblue')
        return fig

@dash.callback(Output('top-routes', 'figure'), Input('airline-selector', 'value'))
def route_bar(airline):
    df = flights if airline is None else flights[flights['AIRLINE'] == airline]
    top_routes = df['ROUTE'].value_counts().head(20).reset_index()
    top_routes.columns = ['Route', 'Count']
    return px.bar(top_routes, x='Route', y='Count', title='Top 20 Routes',
                  color='Count',
                  color_continuous_scale=px.colors.sequential.Blugrn).update_layout(xaxis_tickangle=-45)


@dash.callback(Output('us-flight-map', 'figure'), Input('airline-selector', 'value'))
def show_map(selected_airline):
    # Filter data
    df = flights if selected_airline is None else flights[flights['AIRLINE'] == selected_airline]

    # Sample 300 routes with valid airport coordinates
    sample = df[['ORIGIN_AIRPORT', 'DESTINATION_AIRPORT']].dropna()
    sample = sample[
        sample['ORIGIN_AIRPORT'].isin(airport_coords.index) &
        sample['DESTINATION_AIRPORT'].isin(airport_coords.index)
    ].sample(min(300, len(df)), random_state=42)

    color_palette = px.colors.qualitative.Set3
    fig = go.Figure()

    # Draw arcs
    for i, (_, row) in enumerate(sample.iterrows()):
        origin_code = row['ORIGIN_AIRPORT']
        dest_code = row['DESTINATION_AIRPORT']
        origin = airport_coords.loc[origin_code]
        dest = airport_coords.loc[dest_code]

        fig.add_trace(go.Scattergeo(
            locationmode='USA-states',
            lon=[origin['LONGITUDE'], dest['LONGITUDE']],
            lat=[origin['LATITUDE'], dest['LATITUDE']],
            mode='lines',
            line=dict(width=2, color=color_palette[i % len(color_palette)]),
            opacity=0.7,
            hoverinfo='text',
            text=f"{origin_code} → {dest_code}"
        ))

    # Add markers for airports
    airports_used = pd.unique(sample[['ORIGIN_AIRPORT', 'DESTINATION_AIRPORT']].values.ravel())
    airport_points = airport_coords.loc[airports_used].copy()
    airport_points['code'] = airport_points.index

    fig.add_trace(go.Scattergeo(
        lon=airport_points['LONGITUDE'],
        lat=airport_points['LATITUDE'],
        mode='markers',
        marker=dict(size=5, color='black'),
        text=airport_points['code'],
        name='Airports'
    ))

    fig.update_geos(scope='usa')
    fig.update_layout(
        title='Flight Arcs Over USA (Airports Labeled)',
        height=550,
        margin=dict(l=10, r=10, t=50, b=10),
        showlegend=False
    )

    return fig

@dash.callback(Output('day-busy-bar', 'figure'), Input('airline-selector', 'value'))
def busiest_day(airline):
    df = flights if airline is None else flights[flights['AIRLINE'] == airline]
    day_order = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    day_counts = df['DAY_NAME'].value_counts().reindex(day_order).reset_index()
    day_counts.columns = ['Day', 'Flights']
    fig = px.bar(
        day_counts, x='Day', y='Flights',
        color='Flights',
        color_continuous_scale=px.colors.sequential.Viridis_r,
        title='Flights by Day of Week',
        hover_data={'Flights': True}
    )
    fig.update_layout(
        coloraxis_colorbar=dict(title='Flights'),
        coloraxis_showscale=True
    )
    return fig


@dash.callback(Output('month-trend', 'figure'), Input('airline-selector', 'value'))
def monthly_trend(airline):
    df = flights if airline is None else flights[flights['AIRLINE'] == airline]
    month_order = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    month_counts = df['MONTH_NAME'].value_counts().reindex(month_order).reset_index()
    month_counts.columns = ['Month', 'Flights']
    return px.line(month_counts, x='Month', y='Flights', title='Flights by Month',
                   markers=True, line_shape='spline',
                   color_discrete_sequence=['dodgerblue'])

@dash.callback(Output('origin-treemap', 'figure'), Input('airline-selector', 'value'))
def origin_treemap(airline):
    df = flights if airline is None else flights[flights['AIRLINE'] == airline]
    top = df['ORIGIN_CITY'].value_counts().head(20).reset_index()
    top.columns = ['City', 'Count']
    return px.treemap(top, path=['City'], values='Count',
                      title='Top Origin Cities (Treemap)',
                      color='Count',
                      color_continuous_scale='Bluered')

@dash.callback(Output('dest-treemap', 'figure'), Input('airline-selector', 'value'))
def dest_treemap(airline):
    df = flights if airline is None else flights[flights['AIRLINE'] == airline]
    top = df['DEST_CITY'].value_counts().head(20).reset_index()
    top.columns = ['City', 'Count']
    return px.treemap(top, path=['City'], values='Count',
                      title='Top Destination Cities (Treemap)',
                      color='Count',
                      color_continuous_scale='Bluered')


@dash.callback(Output('busiest-airports', 'figure'), Input('airline-selector', 'value'))
def airport_bar(airline):
    df = flights if airline is None else flights[flights['AIRLINE'] == airline]
    all_airports = pd.concat([df['ORIGIN_AIRPORT'], df['DESTINATION_AIRPORT']])
    airport_counts = all_airports.value_counts().head(10).reset_index()
    airport_counts.columns = ['Airport Code', 'Flights']
    
    airport_counts['City'] = airport_counts['Airport Code'].map(city_map)

    airport_counts['Label'] = airport_counts.apply(
        lambda row: f"{row['City']} ({row['Airport Code']})" if pd.notnull(row['City']) else row['Airport Code'],
        axis=1
    )
    return px.bar(
        airport_counts,
        x='Label',
        y='Flights',
        title='Top 10 Busiest Airports',
        color='Label',
        color_discrete_sequence=px.colors.qualitative.Bold
    )
