import dash
from dash import html, dcc, Input, Output
import dash_bootstrap_components as dbc
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

dash.register_page(__name__, path='/cancelled')

flights = pd.read_csv('data/flights.csv', low_memory=False)
airlines = pd.read_csv('data/airlines.csv')
airports = pd.read_csv('data/airports.csv')

airline_map = dict(zip(airlines['IATA_CODE'], airlines['AIRLINE']))
airport_coords = airports.set_index('IATA_CODE')[['LATITUDE', 'LONGITUDE']].dropna()
city_map = dict(zip(airports['IATA_CODE'], airports['CITY']))

flights['AIRLINE_NAME'] = flights['AIRLINE'].map(airline_map)
flights['ORIGIN_CITY'] = flights['ORIGIN_AIRPORT'].map(city_map)
flights['DEST_CITY'] = flights['DESTINATION_AIRPORT'].map(city_map)
flights['ROUTE'] = flights['ORIGIN_CITY'] + " → " + flights['DEST_CITY']
flights['DAY_NAME'] = flights['DAY_OF_WEEK'].map({1: 'Mon', 2: 'Tue', 3: 'Wed', 4: 'Thu', 5: 'Fri', 6: 'Sat', 7: 'Sun'})
flights['HOUR'] = flights['SCHEDULED_DEPARTURE'].apply(lambda x: int(str(int(x)).zfill(4)[:2]))

layout = dbc.Container([
    html.H2("Cancelled Flights Analysis"),
    html.P("Explore flight cancellations by cause, location, and time."),

    dbc.Row([
        dbc.Col(dcc.Graph(id='cancelled-barplot'), md=6),
        dbc.Col(dcc.Graph(id='cancelled-vs-completed'), md=6)
    ]),
    dbc.Row([
        dbc.Col(dcc.Graph(id='cancelled-by-day'), md=6),
        dbc.Col(dcc.Graph(id='cancelled-heatmap'), md=6),
    ]),
    dbc.Row([
        dbc.Col(dcc.Graph(id='cancelled-reason-pie'), md=6),
        dbc.Col(dcc.Graph(id='cancelled-by-airport'), md=6),
    ]),
    dbc.Row([
        dbc.Col(dcc.Graph(id='cancelled-map'), md=6),
        dbc.Col(dcc.Graph(id='cancelled-routes'), md=6),
    ]),
    dbc.Row([
        dbc.Col(dcc.Graph(id='cancel-rate-route'), md=6),
        dbc.Col(dcc.Graph(id='cancelled-by-tail'), md=6)
    ]),
    dbc.Row([
        dbc.Col(width=1),
        dbc.Col(dcc.Graph(id='cancelled-animated'), md=10),
        dbc.Col(width=1),
    ])
], fluid=True)

@dash.callback(Output('cancelled-barplot', 'figure'), Input('cancelled-barplot', 'id'))
def cancelled_bar(_):
    cancelled = flights[flights['CANCELLED'] == 1]
    data = cancelled.groupby('AIRLINE_NAME').size().reset_index(name='count')
    return px.bar(data.sort_values('count'), x='count', y='AIRLINE_NAME', orientation='h',
                  title="Cancelled Flights per Airline",
                  color='AIRLINE_NAME', color_discrete_sequence=px.colors.qualitative.Set3)

@dash.callback(Output('cancelled-vs-completed', 'figure'), Input('cancelled-vs-completed', 'id'))
def cancelled_pie(_):
    pie_data = flights['CANCELLED'].value_counts().reset_index()
    pie_data.columns = ['Cancelled', 'Count']
    pie_data['Cancelled'] = pie_data['Cancelled'].map({1: 'Cancelled', 0: 'Completed'})
    return px.pie(pie_data, values='Count', names='Cancelled', title='Cancelled vs Completed Flights',
                  color_discrete_sequence=px.colors.qualitative.Bold)

@dash.callback(Output('cancelled-by-day', 'figure'), Input('cancelled-by-day', 'id'))
def cancel_day_bar(_):
    df = flights.groupby('DAY_NAME').agg(cancelled=('CANCELLED', 'sum'), total=('CANCELLED', 'count')).reset_index()
    df['rate'] = 100 * df['cancelled'] / df['total']
    return px.bar(df, x='DAY_NAME', y='rate', title='Cancellation Rate by Day',
                  labels={'rate': '% Cancelled'},
                  color='DAY_NAME', color_discrete_sequence=px.colors.qualitative.Bold)

@dash.callback(Output('cancelled-heatmap', 'figure'), Input('cancelled-heatmap', 'id'))
def cancel_heat(_):
    df = flights.groupby(['AIRLINE_NAME', 'DAY_NAME']).agg(cancelled=('CANCELLED', 'sum'), total=('CANCELLED', 'count')).reset_index()
    df['rate'] = 100 * df['cancelled'] / df['total']
    return px.density_heatmap(df, x='DAY_NAME', y='AIRLINE_NAME', z='rate',
                              title='Cancellation Rate Heatmap',
                              color_continuous_scale='Plasma')

@dash.callback(Output('cancelled-reason-pie', 'figure'), Input('cancelled-reason-pie', 'id'))
def cancel_reason_pie(_):
    pie = flights[flights['CANCELLED'] == 1]['CANCELLATION_REASON'].value_counts().reset_index()
    pie.columns = ['Reason', 'Count']
    reason_map = {'A': 'Airline', 'B': 'Weather', 'C': 'NAS', 'D': 'Security'}
    pie['Reason'] = pie['Reason'].map(reason_map)
    return px.pie(pie, values='Count', names='Reason', title='Reasons for Cancellation',
                  color_discrete_sequence=px.colors.qualitative.Bold)

@dash.callback(Output('cancelled-by-airport', 'figure'), Input('cancelled-by-airport', 'id'))
def cancel_airport_bar(_):
    df = flights[flights['CANCELLED'] == 1]['ORIGIN_AIRPORT'].value_counts().head(10).reset_index()
    df.columns = ['Airport', 'Cancelled']
    df['City'] = df['Airport'].map(city_map)
    return px.bar(df, x='City', y='Cancelled', title='Top Cancelled Airports',
                  color='City', color_discrete_sequence=px.colors.qualitative.Set3)

@dash.callback(Output('cancelled-map', 'figure'), Input('cancelled-map', 'id'))
def cancel_map(_):
    # Filter only cancelled flights with valid airport locations
    df = flights[flights['CANCELLED'] == 1]
    df = df[
        df['ORIGIN_AIRPORT'].isin(airport_coords.index) &
        df['DESTINATION_AIRPORT'].isin(airport_coords.index)
    ].sample(min(300, len(df)), random_state=42)

    color_palette = px.colors.qualitative.Set2
    fig = go.Figure()

    # Draw colored flight arcs with airport hover labels
    for i, (_, row) in enumerate(df.iterrows()):
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
            text=f"{origin_code} → {dest_code}",
            hoverinfo='text'
        ))

    # Add airport markers with codes
    airports_used = pd.unique(df[['ORIGIN_AIRPORT', 'DESTINATION_AIRPORT']].values.ravel())
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
        title='Cancelled Flights Map (Airports & Colored Arcs)',
        height=550,
        margin=dict(l=10, r=10, t=50, b=10),
        showlegend=False
    )

    return fig


@dash.callback(Output('cancelled-routes', 'figure'), Input('cancelled-routes', 'id'))
def cancel_route_bar(_):
    df = flights[flights['CANCELLED'] == 1]
    routes = df['ROUTE'].value_counts().head(15).reset_index()
    routes.columns = ['Route', 'Cancelled']
    return px.bar(routes, x='Route', y='Cancelled', title='Top Cancelled Routes',
                  color='Cancelled', color_continuous_scale='Reds').update_layout(xaxis_tickangle=-45)

@dash.callback(Output('cancel-rate-route', 'figure'), Input('cancel-rate-route', 'id'))
def cancel_rate_bar(_):
    df = flights.groupby('ROUTE').agg(cancelled=('CANCELLED', 'sum'), total=('CANCELLED', 'count')).reset_index()
    df['rate'] = 100 * df['cancelled'] / df['total']
    top = df.sort_values('rate', ascending=False).head(15)
    return px.bar(top, y='ROUTE', x='rate', orientation='h',
                  title='Routes with Highest Cancellation Rates (%)',
                  color='rate', color_continuous_scale='OrRd')

@dash.callback(Output('cancelled-by-tail', 'figure'), Input('cancelled-by-tail', 'id'))
def cancelled_tail_bar(_):
    df = flights[flights['CANCELLED'] == 1]['TAIL_NUMBER'].value_counts().head(10).reset_index()
    df.columns = ['Tail Number', 'Cancellations']
    return px.bar(df, x='Tail Number', y='Cancellations', title='Most Cancelled Aircraft (Tail)',
                  color='Cancellations', color_continuous_scale='sunset')

@dash.callback(Output('cancelled-animated', 'figure'), Input('cancelled-animated', 'id'))
def cancel_animated_bar(_):
    df = flights[flights['CANCELLED'] == 1]
    grouped = df.groupby(['HOUR', 'AIRLINE_NAME']).size().reset_index(name='count')

    return px.bar(grouped, x='AIRLINE_NAME', y='count',
                  animation_frame='HOUR', color='AIRLINE_NAME',
                  title='Hourly Cancelled Flights by Airline',
                  color_discrete_sequence=px.colors.qualitative.Set3,
                  range_y=[0, grouped['count'].max() + 10])

