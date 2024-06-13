import grids
import json
import os
import geopandas as gpd
import ncarrays

from django.http import JsonResponse

from .geospatialFuctions import print_geojson_to_file, shift_shape_bounds
from .app import Metdataexplorer as app
from .model import Shapefiles
from tethys_sdk.routing import controller

Persistent_Store_Name = "thredds_db"


@controller(name="extractTimeseries", url="extractTimeseries/")
def extract_time_series_using_grids(request):
    try:
        if (
            request.headers.get("x-requested-with") == "XMLHttpRequest"
            and request.method == "POST"
        ):
            credentials = json.loads(request.POST.get("userCredentials"))
            dimensions = request.POST.getlist("dimensions[]")
            dimension_values = json.loads(request.POST.get("dimensionsAndValues"))
            # engine = request.POST.get('engine')
            geojson_feature = json.loads(request.POST.get("geojson"))
            geojson_type = request.POST.get("geojsonType")
            opendap_url = request.POST.get("opendapURL")
            variable = request.POST.get("variable")
            shapefile_behavior = json.loads(request.POST.get("shapefileBehavior"))
            statistic = request.POST.get("statistic")

            # print(engine)

            # if engine == 'grids':
            # print('engine is grids')
            (
                dimensions_for_grids,
                _,
                formatted_values,
                filepath_to_geojson,
                filepath_to_shifted_geojson,
            ) = prep_parameters_for_grids(
                geojson_type, geojson_feature, dimensions, dimension_values
            )
            print(dimensions_for_grids)
            if credentials != "none":
                grids_initializer = grids.TimeSeries(
                    [opendap_url],
                    variable,
                    dimensions_for_grids,
                    user=credentials["username"],
                    pswd=credentials["password"],
                )
                print("initializer")
                print(grids_initializer)
            else:
                grids_initializer = grids.TimeSeries(
                    [opendap_url], variable, dimensions_for_grids
                )

            if geojson_type == "marker":
                print("marker")
                time_series = get_time_series_with_point(
                    grids_initializer, formatted_values
                )
            elif geojson_type == "rectangle":

                time_series = get_time_series_with_box(
                    grids_initializer, formatted_values, statistic
                )
            else:
                time_series = get_time_series_with_shapefile(
                    grids_initializer,
                    filepath_to_shifted_geojson,
                    shapefile_behavior,
                    statistic,
                )

            time_series["datetime"] = format_datetime(time_series["datetime"])

            os.remove(filepath_to_geojson)
            os.remove(filepath_to_shifted_geojson)
            # else:
            #     print('engine is ncarrays')
            #     time_series = ''

            time_series_array = {"timeSeries": time_series}
        else:
            time_series_array = {
                "errorMessage": "The time series could not be retrieved",
                "error": "The time series could not be retrieved",
            }
    except Exception as e:
        print(e)
        time_series_array = {
            "errorMessage": "The time series could not be retrieved",
            "error": str(e),
        }
    return JsonResponse(time_series_array)


def format_datetime(date_time_list):
    string_time = []
    for time in date_time_list:
        string_time.append(str(time))
    return string_time


def format_dimension_variables(
    dimensions_for_grids, dimension_values, final_coordinates
):
    formatted_values = []
    if final_coordinates["type"] == "marker":
        tuple_of_values = []
        for dimension in dimensions_for_grids:
            if dimension_values[dimension]["dimensionType"] == "time":
                tuple_of_values.append(None)
            elif dimension_values[dimension]["dimensionType"] == "x":
                tuple_of_values.append(final_coordinates["x"])
            elif dimension_values[dimension]["dimensionType"] == "y":
                tuple_of_values.append(final_coordinates["y"])
            else:
                tuple_of_values.append(dimension_values[dimension]["value"])
        formatted_values.append(tuple_of_values)
    elif final_coordinates["type"] == "rectangle":
        for i in range(2):
            box_number = str(i + 1)
            tuple_of_values = []
            for dimension in dimensions_for_grids:
                if dimension_values[dimension]["dimensionType"] == "time":
                    if len(dimension_values[dimension]) == 3:
                        if i == 0:
                            tuple_of_values.append(
                                dimension_values[dimension]["firstValue"]
                            )
                        else:
                            tuple_of_values.append(
                                dimension_values[dimension]["secondValue"]
                            )
                    else:
                        tuple_of_values.append(None)
                elif dimension_values[dimension]["dimensionType"] == "x":
                    tuple_of_values.append(final_coordinates["x" + box_number])
                elif dimension_values[dimension]["dimensionType"] == "y":
                    tuple_of_values.append(final_coordinates["y" + box_number])
                else:
                    tuple_of_values.append(dimension_values[dimension]["value"])
            formatted_values.append(tuple(tuple_of_values))
    else:
        tuple_of_values = []
        for dimension in dimensions_for_grids:
            if dimension_values[dimension]["dimensionType"] == "time":
                tuple_of_values.append(None)
            elif dimension_values[dimension]["dimensionType"] == "other":
                tuple_of_values.append(dimension_values[dimension]["value"])
        formatted_values.append(tuple_of_values)
    return formatted_values


def format_final_coordinates(geojson_type, filepath_to_shifted_geojson):
    final_coordinates = {}
    if geojson_type == "marker":
        geojson_feature_shifted = gpd.read_file(filepath_to_shifted_geojson)
        final_coordinates["type"] = "marker"
        final_coordinates["x"] = geojson_feature_shifted["geometry"][0].coords[0][0]
        final_coordinates["y"] = geojson_feature_shifted["geometry"][0].coords[0][1]
    elif geojson_type == "rectangle":
        geojson_feature_shifted = gpd.read_file(filepath_to_shifted_geojson)
        final_coordinates["type"] = "rectangle"
        final_coordinates["x1"] = geojson_feature_shifted["geometry"][
            0
        ].exterior.coords[0][0]
        final_coordinates["x2"] = geojson_feature_shifted["geometry"][
            0
        ].exterior.coords[2][0]
        final_coordinates["y1"] = geojson_feature_shifted["geometry"][
            0
        ].exterior.coords[0][1]
        final_coordinates["y2"] = geojson_feature_shifted["geometry"][
            0
        ].exterior.coords[2][1]
    else:
        final_coordinates["type"] = "shapefile"
        final_coordinates["filepath"] = filepath_to_shifted_geojson
    return final_coordinates


def prep_parameters_for_grids(
    geojson_type, geojson_feature, dimensions, dimension_values
):
    if geojson_type == "shapefile":
        shapefile_name = geojson_feature
        SessionMaker = app.get_persistent_store_database(
            Persistent_Store_Name, as_sessionmaker=True
        )
        session = SessionMaker()
        shapefile_from_database = (
            session.query(Shapefiles).filter(Shapefiles.title == shapefile_name).first()
        )
        geojson_feature = json.loads(shapefile_from_database.geometry)
        session.close()

    dimensions_for_grids = tuple(dimensions)
    bounds = {"x": {"max": None, "min": None}, "y": {"max": None, "min": None}}

    for dimension in dimension_values:
        dimension_type = dimension_values[dimension]["dimensionType"]

        if dimension_type == "x":
            bounds["x"]["max"] = max(dimension_values[dimension]["value"])
            bounds["x"]["min"] = min(dimension_values[dimension]["value"])
        if dimension_type == "y":
            bounds["y"]["max"] = max(dimension_values[dimension]["value"])
            bounds["y"]["min"] = min(dimension_values[dimension]["value"])

    filepath_to_geojson = print_geojson_to_file(geojson_feature, "temp")
    filepath_to_shifted_geojson = shift_shape_bounds(bounds, filepath_to_geojson)

    final_coordinates = format_final_coordinates(
        geojson_type, filepath_to_shifted_geojson
    )
    formatted_values = format_dimension_variables(
        dimensions_for_grids, dimension_values, final_coordinates
    )
    return (
        dimensions_for_grids,
        final_coordinates,
        formatted_values,
        filepath_to_geojson,
        filepath_to_shifted_geojson,
    )


@controller(name="formatParametersForGrids", url="formatParametersForGrids/")
def format_parameters_for_grids(request):
    try:
        if (
            request.headers.get("x-requested-with") == "XMLHttpRequest"
            and request.method == "POST"
        ):
            credentials = json.loads(request.POST.get("userCredentials"))
            dimensions = request.POST.getlist("dimensions[]")
            dimension_values = json.loads(request.POST.get("dimensionsAndValues"))
            geojson_feature = json.loads(request.POST.get("geojson"))
            geojson_type = request.POST.get("geojsonType")
            opendap_url = request.POST.get("opendapURL")
            variable = request.POST.get("variable")

            (
                dimensions_for_grids,
                _,
                formatted_values,
                filepath_to_geojson,
                filepath_to_shifted_geojson,
            ) = prep_parameters_for_grids(
                geojson_type, geojson_feature, dimensions, dimension_values
            )

            if credentials != "none":
                grids_initializer = (
                    f"grids_time_series = grids.TimeSeries(['{opendap_url}'], '{variable}', "
                    f"{dimensions_for_grids}, user='{credentials['username']}', "
                    f"pswd='{credentials['password']}')"
                )
            else:
                grids_initializer = (
                    f"grids_time_series = grids.TimeSeries(['{opendap_url}'], "
                    f"'{variable}', {dimensions_for_grids})"
                )

            if geojson_type == "marker":
                if len(formatted_values[0]) == 1:
                    time_series = f"time_series = grids_time_series.point({formatted_values[0][1]})"
                elif len(formatted_values[0]) == 2:
                    time_series = (
                        f"time_series = grids_time_series.point({formatted_values[0][0]}, "
                        f"{formatted_values[0][1]})"
                    )
                elif len(formatted_values[0]) == 3:
                    time_series = (
                        f"time_series = grids_time_series.point({formatted_values[0][0]}, "
                        f"{formatted_values[0][1]}, {formatted_values[0][2]})"
                    )
                elif len(formatted_values[0]) == 4:
                    time_series = (
                        f"time_series = grids_time_series.point({formatted_values[0][0]}, "
                        f"{formatted_values[0][1]}, {formatted_values[0][2]}, {formatted_values[0][3]})"
                    )
                elif len(formatted_values[0]) == 5:
                    time_series = (
                        f"time_series = grids_time_series.point({formatted_values[0][0]}, "
                        f"{formatted_values[0][1]}, {formatted_values[0][2]}, {formatted_values[0][3]}, "
                        f"{formatted_values[0][4]})"
                    )
            elif geojson_type == "rectangle":
                time_series = (
                    f"time_series = grids_time_series.bound({formatted_values[0]}, "
                    f"{formatted_values[1]}, stats='all')"
                )
            else:
                time_series = (
                    "time_series = grids_time_series.shape('Add the filepath to your geojson here!', "
                    "behavior='dissolve', stats='all')"
                )

            os.remove(filepath_to_geojson)
            os.remove(filepath_to_shifted_geojson)

            formatted_array = {
                "gridsInitializer": grids_initializer,
                "timeSeries": time_series,
            }
        else:
            formatted_array = {
                "errorMessage": "Failed to generate the notebook",
                "error": "Failed to generate the notebook",
            }
    except Exception as e:
        print(e)
        formatted_array = {
            "errorMessage": "Failed to generate the notebook",
            "error": str(e),
        }
    return JsonResponse(formatted_array)


def get_time_series_with_point(grids_initializer, dimension_values):
    print(dimension_values)
    print(len(dimension_values))
    if len(dimension_values[0]) == 1:
        time_series = grids_initializer.point(dimension_values[0][1])
    elif len(dimension_values[0]) == 2:
        time_series = grids_initializer.point(
            dimension_values[0][0], dimension_values[0][1]
        )
    elif len(dimension_values[0]) == 3:
        time_series = grids_initializer.point(
            dimension_values[0][0], dimension_values[0][1], dimension_values[0][2]
        )
    elif len(dimension_values[0]) == 4:
        time_series = grids_initializer.point(
            dimension_values[0][0],
            dimension_values[0][1],
            dimension_values[0][2],
            dimension_values[0][3],
        )
    elif len(dimension_values[0]) == 5:
        time_series = grids_initializer.point(
            dimension_values[0][0],
            dimension_values[0][1],
            dimension_values[0][2],
            dimension_values[0][3],
            dimension_values[0][4],
        )
    print("finished")
    return time_series


def get_time_series_with_box(grids_initializer, dimension_values, statistic):
    time_series = grids_initializer.bound(
        dimension_values[0], dimension_values[1], stats=statistic
    )
    return time_series


def get_time_series_with_shapefile(
    grids_initializer, filepath_to_geojson, behavior, statistic
):
    if behavior["behavior"] == "feature":
        time_series = grids_initializer.shape(
            filepath_to_geojson,
            behavior=behavior["behavior"],
            label_attr=behavior["labelAttr"],
            feature=behavior["feature"],
            stats=statistic,
        )
    elif behavior["behavior"] == "features":
        time_series = grids_initializer.shape(
            filepath_to_geojson,
            behavior=behavior["behavior"],
            label_attr=behavior["labelAttr"],
            stats=statistic,
        )
    else:
        time_series = grids_initializer.shape(
            filepath_to_geojson, behavior="dissolve", stats=statistic
        )
    return time_series
