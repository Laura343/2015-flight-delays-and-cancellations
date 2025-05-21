import dash
from dash import html, dcc, Input, Output
import dash_bootstrap_components as dbc
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

dash.register_page(__name__, path='/delays')

# Load and preprocess data
flights = pd.read_csv('data/flights.csv', low_memory=False)
airlines = pd.read_csv('data/airlines.csv')
airline_map = dict(zip(airlines['IATA_CODE'], airlines['AIRLINE']))
flights['AIRLINE_NAME'] = flights['AIRLINE'].map(airline_map)

# Extract safe hour
flights['SCHED_HOUR'] = flights['SCHEDULED_DEPARTURE'].apply(lambda x: int(str(int(x)).zfill(4)[:2]))

# On time / delayed label
flights['ON_TIME'] = flights['DEPARTURE_DELAY'].apply(lambda x: 'On Time' if x <= 0 else 'Delayed')

layout = dbc.Container([
    html.H2("Delay Analysis"),
    html.P("Analyze delays by time, cause, and distance."),

    html.Label("⏰ Select Scheduled Departure Hour"),
    dcc.Slider(min=0, max=23, step=1, value=12, id='hour-slider',
               marks={i: str(i) for i in range(0, 24)}),
    html.Br(),

    # Hour-sensitive plots
    dbc.Row([
        dbc.Col(dcc.Graph(id='delay-boxplot'), md=6),
        dbc.Col(dcc.Graph(id='delay-line'), md=6)
    ]),
    dbc.Row([
        dbc.Col(dcc.Graph(id='violin-plot'), md=6),
        dbc.Col(dcc.Graph(id='delay-heatmap'), md=6),
    ]),
    dbc.Row([
        dbc.Col(dcc.Graph(id='distance-delay-bar'), md=6),
        dbc.Col(dcc.Graph(id='avg-delay-bar'), md=6),
    ]),
    dbc.Row([
        dbc.Col(dcc.Graph(id='delay-cause-bar'), md=6),
        dbc.Col(dcc.Graph(id='ontime-pie'), md=6),
    ])

], fluid=True)

@dash.callback(Output('delay-boxplot', 'figure'), Input('hour-slider', 'value'))
def update_boxplot(hour):
    df = flights[(flights['SCHED_HOUR'] == hour) & (flights['CANCELLED'] == 0)]
    fig = go.Figure()
    for airline in df['AIRLINE_NAME'].dropna().unique():
        fig.add_trace(go.Box(
            y=df[df['AIRLINE_NAME'] == airline]['DEPARTURE_DELAY'],
            name=airline))
    fig.update_layout(title=f"Delays at {hour}:00", yaxis_title="Delay (min)")
    return fig

@dash.callback(Output('delay-line', 'figure'), Input('hour-slider', 'value'))
def delay_trend_animation(_):
    df = flights[flights['CANCELLED'] == 0]
    grouped = df.groupby(['AIRLINE_NAME', 'SCHED_HOUR'])['DEPARTURE_DELAY'].mean().reset_index()
    return px.line(grouped, x='SCHED_HOUR', y='DEPARTURE_DELAY', color='AIRLINE_NAME',
                   title='Average Delay by Hour',
                   labels={'SCHED_HOUR': 'Hour of Day', 'DEPARTURE_DELAY': 'Avg Delay (min)'},
                   color_discrete_sequence=px.colors.qualitative.Bold)

@dash.callback(Output('violin-plot', 'figure'), Input('hour-slider', 'value'))
def delay_violin(hour):
    df = flights[(flights['SCHED_HOUR'] == hour) & (flights['DEPARTURE_DELAY'].between(-10, 180))]
    return px.violin(df.sample(min(1000, len(df))), y='DEPARTURE_DELAY', x='AIRLINE_NAME', box=True,
                     title='Delay Distribution by Airline (Delays -10 to 180 mins)',
                     color_discrete_sequence=px.colors.qualitative.Prism)

@dash.callback(Output('delay-heatmap', 'figure'), Input('hour-slider', 'value'))
def delay_heatmap(_):
    df = flights[flights['CANCELLED'] == 0]
    data = df.groupby(['AIRLINE_NAME', 'SCHED_HOUR'])['DEPARTURE_DELAY'].mean().reset_index()
    return px.density_heatmap(data, x='SCHED_HOUR', y='AIRLINE_NAME', z='DEPARTURE_DELAY',
                              title='Average Delay Heatmap (Hour × Airline)',
                              color_continuous_scale='Plasma')


@dash.callback(Output('distance-delay-bar', 'figure'), Input('hour-slider', 'value'))
def delay_by_distance_range(hour):
    df = flights[
        (flights['CANCELLED'] == 0) &
        (flights['SCHED_HOUR'] == hour) &
        (flights['DISTANCE'] < 3000)
    ].copy()
    bins = [0, 500, 1000, 1500, 2000, 2500, 3000]
    labels = ['<500', '500-999', '1000-1499', '1500-1999', '2000-2499', '2500+']
    df['DISTANCE_BIN'] = pd.cut(df['DISTANCE'], bins=bins, labels=labels)
    avg = df.groupby('DISTANCE_BIN', observed=True)['DEPARTURE_DELAY'].mean().reset_index()
    fig = px.bar(
        avg, x='DISTANCE_BIN', y='DEPARTURE_DELAY',
        title='Average Delay by Distance Range'
    )
    fig.update_traces(marker_color='steelblue')
    return fig


@dash.callback(Output('avg-delay-bar', 'figure'), Input('hour-slider', 'value'))
def avg_delay(_):
    df = flights[flights['CANCELLED'] == 0]
    data = df.groupby('AIRLINE_NAME')['DEPARTURE_DELAY'].mean().reset_index()
    data = data.sort_values('DEPARTURE_DELAY', ascending=False)
    fig = px.bar(
        data, x='AIRLINE_NAME', y='DEPARTURE_DELAY',
        title='Average Delay per Airline',
        labels={'DEPARTURE_DELAY': 'Avg Delay (min)'},
        color_discrete_sequence=px.colors.qualitative.Bold
    )
    return fig

@dash.callback(Output('delay-cause-bar', 'figure'), Input('hour-slider', 'value'))
def delay_cause_bar(_):
    cause_cols = ['AIR_SYSTEM_DELAY', 'SECURITY_DELAY', 'AIRLINE_DELAY', 'LATE_AIRCRAFT_DELAY', 'WEATHER_DELAY']
    df = flights[['AIRLINE_NAME'] + cause_cols].dropna()
    melted = df.melt(id_vars='AIRLINE_NAME', value_vars=cause_cols, var_name='Cause', value_name='Minutes')
    grouped = melted.groupby(['AIRLINE_NAME', 'Cause'])['Minutes'].mean().reset_index()
    return px.bar(grouped, x='AIRLINE_NAME', y='Minutes', color='Cause',
                  title='Average Delay by Cause per Airline',
                  color_discrete_sequence=px.colors.qualitative.Set1)

@dash.callback(Output('ontime-pie', 'figure'), Input('hour-slider', 'value'))
def on_time_vs_delayed(hour):
    df = flights[(flights['CANCELLED'] == 0) & (flights['SCHED_HOUR'] == hour)]
    data = df['ON_TIME'].value_counts().reset_index()
    data.columns = ['Status', 'Count']
    return px.pie(data, values='Count', names='Status', title='On-Time vs Delayed',
                  color_discrete_sequence=px.colors.qualitative.Bold)
