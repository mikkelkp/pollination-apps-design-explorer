"""Module for app."""
import os
import dash
from dash import html, dcc, dash_table, Patch, ALL, ctx
from dash.dependencies import Input, Output, State
from pathlib import Path
import pandas as pd
import plotly.express as px
import dash_bootstrap_components as dbc
import numpy as np
import pollination_dash_io
import base64
import zipfile
from io import BytesIO
from flask import send_from_directory

from containers import logo_title, create_radio_container, select_sample_project, \
    create_color_by_children, create_color_by_container, create_sort_by_children, \
    create_sort_by_container, create_images_grid_children, create_images_container
from helper import process_dataframe
from samples import sample_alias


base_path = os.getenv('POLLINATION_API_URL', 'https://api.staging.pollination.cloud')

app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP, dbc.icons.BOOTSTRAP],
    suppress_callback_exceptions=True
)
app.title = 'Design Explorer'
server = app.server

@server.route('/pollination/<path:path>')
def serve_image(path):
    directory = Path(__file__).parent.joinpath('pollination')
    return send_from_directory(directory, path)

api_key = pollination_dash_io.ApiKey()

project_folder = 'assets/samples/daylight-factor'
csv = Path(__file__).parent.joinpath('assets', 'samples', 'daylight-factor', 'data.csv')
df = pd.read_csv(csv)
df_records = df.to_dict('records')

labels, parameters, input_columns, output_columns, image_columns = \
    process_dataframe(df)

# color by first output column, or first input column
if output_columns:
    color_by = output_columns[0]
    sort_by = output_columns[0]
else:
    color_by = input_columns[0]
    sort_by = output_columns[0]

fig = px.parallel_coordinates(df, color=color_by, labels=labels)
# fig.update_traces(unselected_line_opacity=0)

img_column = df.filter(regex=f'^img:').columns[0]

images_div = []
minimum, maximum = df[color_by].min(), df[color_by].max()
sorted_df = df.sort_values(by=sort_by, ascending=False)
sorted_df_records = sorted_df.to_dict('records')
images_grid_children = create_images_grid_children(
    sorted_df_records, color_by, minimum, maximum, img_column, project_folder)

columns = []
for value in parameters.values():
    if value['type'] != 'img':
        columns.append({'id': value['label'], 'name': value['display_name']})
    else:
        columns.append(
            {'id': value['label'], 'name': value['display_name'], 'hidden': True})


def hello_user(api_key: pollination_dash_io.ApiKey, base_path: str):
    """Function to create a Div for authentication of user."""
    hello_user_container = html.Div(children=[
            html.Span(id='hello-user', children='Hi!', className='hi-user'),
            pollination_dash_io.AuthUser(id='auth-user', basePath=base_path),
            api_key.component,
        ],
        id='hello',
        className='hello'
    )
    return hello_user_container


def select_pollination_project():
    """Function to create a Div for selecting a project on Pollination."""
    select_project_container = html.Div(children=[
        html.Div(id='select-account-container', className='pollination-dropdown'),
        html.Div(id='select-project-container', className='pollination-dropdown'),
        html.Div(id='select-artifact-container', className='pollination-dropdown')
        ],
        id='select-pollination-project',
        className='select-pollination-project'
    )

    return select_project_container


def info_box():
    info_box = html.Div(
        dbc.Row([
            dbc.Col(html.P(
                'This app is a work in progress. The aim is to build an app '
                'that can be used in an integrated workflow with Pollination '
                'Fly and Pollination Cloud. Check out the video on the right '
                'to see how Pollination Fly works.', className='justify-text'
            )),
            dbc.Col(html.Iframe(
                src='https://www.youtube.com/embed/X7hrUg71scE?si=o7zuXoT6B2IUdnXY'
            ))]
        ),
        className='info-box',
    )

    return info_box


app.layout = dbc.Container([
    #api_key.component,
    logo_title(app),
    info_box(),
    hello_user(api_key, base_path),
    create_radio_container(),
    select_sample_project(),
    select_pollination_project(),
    # pollination_dash_io.AuthUser(id='auth-user', basePath=base_path),
    # pollination_dash_io.SelectAccount(id='select-account', basePath=base_path),
    # pollination_dash_io.SelectProject(id='select-project', basePath=base_path),
    # html.Div(id='select-artifact-container'),
    #pollination_dash_io.SelectCloudArtifact(id='select-artifact', basePath=base_path),
    create_color_by_container(parameters, color_by),
    dcc.Store(id='project-folder', data=project_folder),
    dcc.Loading(children=[dcc.Store(id='df', data=df_records)],
        className='custom-spinner', type='default', fullscreen=True),
    dcc.Store(id='df-columns', data=df.columns),
    dcc.Store(id='labels', data=labels),
    dcc.Store(id='parameters', data=parameters),
    dcc.Store(id='img-column', data=img_column),
    dcc.Store(id='active-filters', data={}),
    dcc.Store(id='active-records', data=df_records),
    dcc.Store(id='parallel-coordinates-figure-highlight', data={}),
    dcc.Store(id='parallel-coordinates-figure', data=fig),
    dcc.Graph(id='parallel-coordinates', figure=fig),
    create_sort_by_container(parameters, sort_by),
    create_images_container(images_grid_children),
    dash_table.DataTable(
        id='table', data=df.to_dict('records'),
        columns=columns,
        style_table={'padding': '20px'},
        sort_action='native')
], style={'padding': '20px'}, fluid=True)


api_key.create_api_key_callback(
    app=app,
    component_ids=['auth-user']
)


# @app.callback(
#     [Output('hello-user', 'children'),
#      Output('hello', 'style')],
#     Input('auth-user', 'authUser'),
#     prevent_initial_call=True
# )
# def update_hello(authUser):
#     msg = f'Hi {authUser["name"]}!'
#     return msg, {'visibility': 'visible'}


@app.callback(
    Output('select-artifact-container', 'children'),
    [Input('select-project', 'project'),
     State('auth-user', 'apiKey')],
    prevent_initial_call=True
)
def update_select_artifact_container(project, apiKey):
    """Function to change the children of select-artifact-container."""
    if project is None:
        return dash.no_update
    project_owner = project['owner']['name']
    project_name = project['name']
    select_cloud_artifact = \
        pollination_dash_io.SelectCloudArtifact(id='select-artifact',
                                                projectOwner=project_owner,
                                                projectName=project_name,
                                                basePath=base_path,
                                                apiKey=apiKey,
                                                fileNameMatch='.zip')

    return select_cloud_artifact


@app.callback(
    Output('select-project-container', 'children'),
    [Input('select-account', 'account'),
     State('auth-user', 'apiKey')],
    prevent_initial_call=True
)
def update_select_project_container(account, apiKey):
    """Function to change the children of select-project-container."""
    if account is None:
        return dash.no_update
    project_owner = account.get('account_name') or account.get('username')
    select_project = \
        pollination_dash_io.SelectProject(id='select-project',
                                          projectOwner=project_owner,
                                          basePath=base_path,
                                          apiKey=apiKey)
    return select_project


@app.callback(
    [Output('select-account-container', 'children'),
     Output('select-sample', 'style'),
     Output('select-pollination-project', 'style')],
    [Input('radio-items-input', 'value'),
     State('auth-user', 'apiKey')],
    prevent_initial_call=True
)
def update_select_account_container(value, apiKey):
    """Function to change the children of select-account-container."""
    if value:
        select_cloud_artifact = \
            pollination_dash_io.SelectAccount(id='select-account',
                                              basePath=base_path,
                                              apiKey=apiKey)
        return select_cloud_artifact, {'display': 'none'}, {'display': 'flex'}
    else:
        return dash.no_update, {}, {'display': 'none'}


@app.callback(
    [Output('project-folder', 'data', allow_duplicate=True),
     Output('df', 'data', allow_duplicate=True),
     Output('active-records', 'data', allow_duplicate=True),
     Output('active-filters', 'data', allow_duplicate=True),
     Output('df-columns', 'data', allow_duplicate=True),
     Output('labels', 'data', allow_duplicate=True),
     Output('img-column', 'data', allow_duplicate=True),
     Output('parameters', 'data', allow_duplicate=True),
     Output('parallel-coordinates', 'figure', allow_duplicate=True),
     Output('sort-by', 'children', allow_duplicate=True),
     Output('color-by', 'children', allow_duplicate=True),
     Output('table', 'columns', allow_duplicate=True),
     Output('selected-image-info', 'children', allow_duplicate=True),
     Output('selected-image-container', 'style', allow_duplicate=True),
     Output('images-grid', 'style', allow_duplicate=True)],
    [Input('select-artifact', 'value'),
     State('select-artifact', 'name'),
     State('select-project', 'project')],
    prevent_initial_call=True
)
def load_project_from_pollination(value, name, project):
    if value is None or name is None:
        return dash.no_update

    bytes_value = base64.b64decode(value)
    file = Path(name)
    extension = file.suffix
    if extension == '.csv':
        return dash.no_update
    elif extension == '.zip':
        zip_file_like = BytesIO(bytes_value)
        output_folder = Path(__file__).parent.joinpath('pollination', project['owner']['id'], project['id'], file.stem)
        project_folder = f'/pollination/{project["owner"]["id"]}/{project["id"]}/{file.stem}'
        with zipfile.ZipFile(zip_file_like, 'r') as zip_file:
            zip_file.extractall(output_folder)
        csv_file = output_folder.joinpath('data.csv')
        assert csv_file.exists(), 'File data.csv does not exists in zip file.'
        dff = pd.read_csv(csv_file)
        df_records = dff.to_dict('records')

        labels, parameters, input_columns, output_columns, image_columns = \
            process_dataframe(dff)

        if output_columns:
            color_by = output_columns[0]
            sort_by = output_columns[0]
        else:
            color_by = input_columns[0]
            sort_by = output_columns[0]

        fig = px.parallel_coordinates(dff, color=color_by, labels=labels)

        img_column = dff.filter(regex=f'^img:').columns[0]

        columns = []
        for value in parameters.values():
            if value['type'] != 'img':
                columns.append({'id': value['label'], 'name': value['display_name']})
            else:
                columns.append(
                    {'id': value['label'], 'name': value['display_name'], 'hidden': True})

        sort_by_children = create_sort_by_children(parameters, sort_by)
        color_by_children = create_color_by_children(parameters, color_by)

        active_filters = {}
        selected_image_info = None
        selected_image_container_style = {}
        image_grid_style = {}

        return (project_folder, df_records, df_records, active_filters, dff.columns,
                labels, img_column, parameters, fig, sort_by_children,
                color_by_children, columns, selected_image_info,
                selected_image_container_style, image_grid_style)
    else:
        raise ValueError('Wrong file type!')
    return dash.no_update


@app.callback(
    [Output('project-folder', 'data', allow_duplicate=True),
     Output('df', 'data', allow_duplicate=True),
     Output('active-records', 'data', allow_duplicate=True),
     Output('active-filters', 'data', allow_duplicate=True),
     Output('df-columns', 'data', allow_duplicate=True),
     Output('labels', 'data', allow_duplicate=True),
     Output('img-column', 'data'),
     Output('parameters', 'data', allow_duplicate=True),
     Output('parallel-coordinates', 'figure', allow_duplicate=True),
     Output('select-sample-dropdown', 'label', allow_duplicate=True),
     Output('sort-by', 'children', allow_duplicate=True),
     Output('color-by', 'children', allow_duplicate=True),
     Output('table', 'columns', allow_duplicate=True),
     Output('selected-image-info', 'children', allow_duplicate=True),
     Output('selected-image-container', 'style', allow_duplicate=True),
     Output('images-grid', 'style', allow_duplicate=True)],
    Input({'select_sample_project': ALL}, 'n_clicks'),
    prevent_initial_call=True
)
def update_sample_project(n_clicks):
    """If a click is registered in the sort by dropdown, the data is updated in
    sort-by-column, and the label is updated in sort-by-dropdown."""
    sample_project = ctx.triggered_id.select_sample_project
    project_folder = f'assets/samples/{sample_project}'
    select_sample_dropdown_label = sample_alias[sample_project]['display_name']
    csv = Path(__file__).parent.joinpath(
        'assets', 'samples', sample_project, 'data.csv')
    dff = pd.read_csv(csv)
    df_records = dff.to_dict('records')

    labels, parameters, input_columns, output_columns, image_columns = \
        process_dataframe(dff)

    # color by first output column, or first input column
    if output_columns:
        color_by = output_columns[0]
        sort_by = output_columns[0]
    else:
        color_by = input_columns[0]
        sort_by = output_columns[0]

    fig = px.parallel_coordinates(dff, color=color_by, labels=labels)

    img_columns = dff.filter(regex=f'^img:').columns
    if img_columns.empty:
        img_column = None
    else:
        img_column = img_columns[0]

    columns = []
    for value in parameters.values():
        if value['type'] != 'img':
            columns.append({'id': value['label'], 'name': value['display_name']})
        else:
            columns.append(
                {'id': value['label'], 'name': value['display_name'], 'hidden': True})

    sort_by_children = create_sort_by_children(parameters, sort_by)
    color_by_children = create_color_by_children(parameters, color_by)

    active_filters = {}
    selected_image_info = None
    selected_image_container_style = {}
    image_grid_style = {}

    return (project_folder, df_records, df_records, active_filters, dff.columns,
            labels, img_column, parameters, fig, select_sample_dropdown_label,
            sort_by_children, color_by_children, columns, selected_image_info,
            selected_image_container_style, image_grid_style)


@app.callback(
    [Output(component_id='sort-ascending', component_property='data'),
     Output(component_id='button-ascending-icon', component_property='className')],
    [Input(component_id='button-ascending', component_property='n_clicks'),
     State(component_id='sort-ascending', component_property='data')],
    prevent_initial_call=True
)
def update_sort_ascending(n_clicks, sort_ascending):
    """If a click is registered in the button-ascending, the data is updated in
    sort-ascending, the className is updated in button-ascending-icon, and the
    children is updated in button-ascending-text."""
    if sort_ascending:
        return  False, 'bi bi-sort-down'
    else:
        return True, 'bi bi-sort-up'


@app.callback(
    [Output('sort-by-column', 'data'),
     Output('sort-by-dropdown', 'label')],
    [Input({'sort_by_dropdown': ALL}, 'n_clicks'),
     State('labels', 'data')],
    prevent_initial_call=True
)
def update_sort_by(n_clicks, labels):
    """If a click is registered in the sort by dropdown, the data is updated in
    sort-by-column, and the label is updated in sort-by-dropdown."""
    if all(v is None for v in n_clicks):
        return dash.no_update

    sort_by = ctx.triggered_id.sort_by_dropdown

    return sort_by, labels[sort_by]


@app.callback(
    [Output('parallel-coordinates', 'figure'),
     Output('color-by-column', 'data'),
     Output('color-by-dropdown', 'label')],
    [Input({'color_by_dropdown': ALL}, 'n_clicks'),
     State('df', 'data'),
     State('labels', 'data'),
     State('parallel-coordinates', 'figure')],
    prevent_initial_call=True
)
def update_color_by(n_clicks, df_records, labels, figure):
    """If a click is registered in the color by dropdown, the figure is updated
    in parallel-coordinates, the data is updated in color-by-column, and the
    label is updated in color-by-dropdown."""
    if all(v is None for v in n_clicks):
        return dash.no_update

    dff = pd.DataFrame.from_records(df_records)
    color_by = ctx.triggered_id.color_by_dropdown

    if color_by:
        new_fig = Patch()
        new_fig['data'][0]['dimensions'] = figure['data'][0]['dimensions']
        new_fig['data'][0]['line']['color'] = dff[color_by]
        return new_fig, color_by, labels[color_by]
    else:
        new_fig = Patch()
        new_fig['data'][0]['dimensions'] = figure['data'][0]['dimensions']
        new_fig['data'][0]['line']['color'] = None
        return new_fig, color_by, 'None'


@app.callback(
    Output('images-grid-div', 'style'),
    Input('img-column', 'data'),
    prevent_initial_call=True
)
def update_images_grid_div_display(img_column):
    """If img-column is None, the display is changed to none."""
    if img_column is None:
        return {'display': 'none'}
    else:
        return {}


@app.callback(
    [Output('selected-image-data', 'data', allow_duplicate=True),
     Output('selected-image-info', 'children', allow_duplicate=True)],
    [Input({'image': ALL}, 'n_clicks'),
     State('df', 'data'),
     State('labels', 'data'),
     State('img-column', 'data'),
     State('parameters', 'data')],
    prevent_initial_call=True
)
def update_clicked_image_grid(n_clicks, df_records, labels, img_column, parameters):
    """If a click is registered in any of the images in images-grid, the data is
    updated in selected-image-table."""
    if all(item is None for item in n_clicks):
        # no clicks, no update
        return dash.no_update
    # get the clicked image
    image_id = ctx.triggered_id.image
    dff = pd.DataFrame.from_records(df_records)
    selected_df = dff.loc[dff[img_column] == image_id]
    select_image_info = []
    record = selected_df.to_dict('records')
    for label in labels:
        select_image_info.append(
            html.Div(children=[
                html.Span(f'{parameters[label]["display_name"]}: ', className='label-bold'),
                f'{record[0][label]}'
                ])
        )
    return record, select_image_info


@app.callback(
    [Output('selected-image', 'src', allow_duplicate=True),
     Output('selected-image', 'n_clicks', allow_duplicate=True),
     Output('selected-image-data', 'data', allow_duplicate=True),
     Output('selected-image-info', 'children', allow_duplicate=True),
     Output('selected-image-container', 'style', allow_duplicate=True),
     Output('images-grid', 'style', allow_duplicate=True)],
    Input('selected-image', 'n_clicks'),
    prevent_initial_call=True
)
def update_click_selected_image(n_clicks):
    """If a click is registered on selected-image.
    
    When this happens we reset everything related to the selected-image. The
    style of images-grid is also reset to its original state."""
    if n_clicks is not None:
        selected_image_container_style = {}
        image_grid_style = {}
        return None, None, None, None, selected_image_container_style, image_grid_style


@app.callback(
    [Output('selected-image', 'src', allow_duplicate=True),
     Output('selected-image-container', 'style', allow_duplicate=True),
     Output('images-grid', 'style', allow_duplicate=True)],
    [Input('selected-image-data', 'data'),
     State('img-column', 'data'),
     State('project-folder', 'data')],
    prevent_initial_call=True,
)
def update_selected_image_table(selected_image_data, img_column, project_folder):
    """If the data in selected-image-table is changed.
    
    The src of selected-image is taken from selected-image-table. The styles of
    selected-image-container and images-grid are also updated."""
    if selected_image_data is None:
        return dash.no_update

    project_folder = Path(project_folder)
    src = project_folder.joinpath(selected_image_data[0][img_column]).as_posix()

    selected_image_container_style = {
        'width': '75%'
    }

    image_grid_style = {
        'grid-template-columns': 'repeat(auto-fill, minmax(10%, 1fr))',
        'width': '25%'
    }

    return src, selected_image_container_style, image_grid_style


@app.callback(
    Output('images-grid', 'children', allow_duplicate=True),
    [Input('active-records', 'data'),
     State('df', 'data'),
     Input('color-by-column', 'data'),
     Input('sort-by-column', 'data'),
     Input('sort-ascending', 'data'),
     State('img-column', 'data'),
     State('project-folder', 'data')],
    prevent_initial_call=True,
)
def update_images_grid(
        active_records, df_records, color_by_column, sort_by_column,
        sort_ascending, img_column, project_folder):
    """If the data in active-records is changed, the children will be updated
    in images-grid.
    
    The images-grid is a grid showing all the images of the selected filters in
    the parallel coordinate plot.

    The data coming from table is a list. Here is an example:
    [
        {'in:X': 1, 'in:Y': 4, 'in:Z': 3.6, 'img:Perspective': 'X_1_Y_4_Z_3.6.png'},
        {'in:X': 2, 'in:Y': 4, 'in:Z': 3.6, 'img:Perspective': 'X_2_Y_4_Z_3.6.png'}
    ]
    """
    if img_column is None:
        return []
    images_div = []
    if color_by_column:
        dff = pd.DataFrame.from_records(df_records)
        minimum, maximum = dff[color_by_column].min(), dff[color_by_column].max()
    border_color = '#636EFA'
    if sort_by_column:
        dff = pd.DataFrame.from_records(active_records)
        sorted_df = dff.sort_values(by=sort_by_column, ascending=sort_ascending)
        active_records = sorted_df.to_dict('records')
    project_folder = Path(project_folder)
    for d in active_records:
        if color_by_column:
            samplepoints = np.interp(d[color_by_column], [minimum, maximum], [0, 1])
            border_color = px.colors.sample_colorscale(
                'plasma', samplepoints=samplepoints
            )[0]
        src = project_folder.joinpath(d[img_column])
        image = html.Div(
            html.Img(src=src.as_posix(),
                     id={'image': f'{d[img_column]}'},
                     className='image-grid',
                     style={'border-color': border_color}
            ),
            style={
                'aspect-ratio': '1',
                'width': '100%',
                'height': '100%',
                'position': 'relative',
                'display': 'flex',
                'align-items': 'center',
                'justify-content': 'center',
                }
        )
        images_div.append(image)

    return images_div


@app.callback(
    Output('table', 'data', allow_duplicate=True),
    Input('active-records', 'data'),
    prevent_initial_call=True,
)
def update_table_data(active_records):
    """If the active-records is changed, the data will be updated in table."""
    return active_records


@app.callback(
    Output('active-records', 'data', allow_duplicate=True),
    [Input('active-filters', 'data'),
     State('df', 'data')],
    prevent_initial_call=True,
)
def update_active_records(data, df_records):
    """If the data in active-filters is changed, the data will be updated in
    active-records.
    
    The data coming from active-filters is a dictionary. Here is an example:
    {
        'In:X': [
            [3.37548768432072, 5.8024196759539395]
        ],
        'In:Z': None,
        'Out:Volume': [
            [
                [127.00292472850138, 341.43381398170953],
                [627.3416663193204, 739.2186520166465]
            ]
        ]
    }

    The keys are the column names in the DataFrame. The values are selections,
    i.e., [min, max], and one column can have multiple selections. The value can
    also be None if a selection has previously been made for this column but
    since removed.
    """
    if data:
        dff = pd.DataFrame.from_records(df_records)
        for col in data:
            if data[col]:
                # there is a selection, i.e., the value is not None
                rng = data[col][0]
                if isinstance(rng[0], list):
                    # if multiple choices combine df
                    dff3 = pd.DataFrame(columns=dff.columns)
                    for i in rng:
                        dff2 = dff[dff[col].between(i[0], i[1])]
                        dff3 = pd.concat([dff3, dff2])
                    dff = dff3
                else:
                    # there is one selection
                    dff = dff[dff[col].between(rng[0], rng[1])]
        return dff.to_dict('records')
    return dash.no_update


@app.callback(
    Output('active-filters', 'data'),
    [Input('parallel-coordinates', 'restyleData'),
     State('df-columns', 'data')],
    prevent_initial_call=True,
)
def update_active_filters(data, df_columns):
    """If a selection is made in the parallel coordinate plot, the data will be
    updated in active-filters."""
    if data:
        key = list(data[0].keys())[0]
        col = df_columns[int(key.split('[')[1].split(']')[0])]
        new_data = Patch()
        new_data[col] = data[0][key]
        return new_data
    return dash.no_update


if __name__ == '__main__':
    app.run_server(debug=True)
