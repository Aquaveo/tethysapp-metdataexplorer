import os
import json
import netCDF4
import geopandas
import math
import numpy as np

from glob import glob
from datetime import datetime

from tethys_sdk.permissions import has_permission
from tethys_sdk.workspaces import get_app_workspace
from django.http import JsonResponse
from .app import Metdataexplorer as app
from .model import Files, Groups, Variables, Shapefiles

from tethys_sdk.routing import controller

Persistent_Store_Name = "thredds_db"


def add_variables_to_opendap_url(opendap_url, list_of_variables):
    opendap_url += "?"
    for variable in list_of_variables:
        if variable == list_of_variables[-1]:
            opendap_url += variable
        else:
            opendap_url += variable + ","
    return opendap_url


@controller(name="addFileToDatabase", url="addFileToDatabase/")
def add_file_to_database(request):
    try:
        if (
            request.headers.get("x-requested-with") == "XMLHttpRequest"
            and request.method == "POST"
        ):
            file_dictionary = {
                "accessURLs": json.loads(request.POST.get("url")),
                "description": request.POST.get("description"),
                "dimensionalVariables": [],
                "fileType": request.POST.get("fileType"),
                "group": request.POST.get("group"),
                "title": request.POST.get("title"),
                "userCredentials": json.loads(request.POST.get("userCredentials")),
                "variables": {},
                "variablesAndDimensions": json.loads(
                    request.POST.get("variablesAndDimensions")
                ),
            }

            all_variables = request.POST.getlist("allVariables[]")

            list_for_opendap = []

            SessionMaker = app.get_persistent_store_database(
                Persistent_Store_Name, as_sessionmaker=True
            )
            session = SessionMaker()

            current_group = session.query(Groups).filter(
                Groups.title == file_dictionary["group"]
            )[0]

            for file_to_check in current_group.files:
                if file_to_check.title == file_dictionary["title"]:
                    array_to_return = {
                        "errorMessage": "There is already a file with that name. Please provide a different name."
                    }
                    session.close()
                    return JsonResponse(array_to_return)

            if file_dictionary["fileType"] == "catalog":
                file_to_add = Files(
                    authentication=json.dumps(file_dictionary["userCredentials"]),
                    description=file_dictionary["description"],
                    dimensional_variables=json.dumps(
                        file_dictionary["dimensionalVariables"]
                    ),
                    file_type=file_dictionary["fileType"],
                    title=file_dictionary["title"],
                    urls=json.dumps(file_dictionary["accessURLs"]),
                )

                variable_to_add = Variables(
                    title="",
                    value_range=json.dumps([]),
                )
                file_to_add.variables.append(variable_to_add)
            else:
                for variable in file_dictionary["variablesAndDimensions"]:
                    list_for_opendap.append(variable)
                    for dimension in file_dictionary["variablesAndDimensions"][
                        variable
                    ]:
                        if dimension not in file_dictionary["dimensionalVariables"]:
                            file_dictionary["dimensionalVariables"].append(dimension)
                        if (
                            dimension in all_variables
                            and dimension not in list_for_opendap
                        ):
                            list_for_opendap.append(dimension)

                opendap_url = add_variables_to_opendap_url(
                    file_dictionary["accessURLs"]["OPENDAP"], list_for_opendap
                )

                dataset = netCDF4.Dataset(opendap_url)

                file_to_add = Files(
                    authentication=json.dumps(file_dictionary["userCredentials"]),
                    description=file_dictionary["description"],
                    dimensional_variables=json.dumps(
                        file_dictionary["dimensionalVariables"]
                    ),
                    file_type=file_dictionary["fileType"],
                    title=file_dictionary["title"],
                    urls=json.dumps(file_dictionary["accessURLs"]),
                )

                for variable in file_dictionary["variablesAndDimensions"]:
                    if "actual_range" in dataset.variables[variable].__dict__:
                        actual_range_list = []
                        for value in dataset.variables[variable].__dict__[
                            "actual_range"
                        ]:
                            actual_range_list.append(value)
                        if len(actual_range_list) != 2:
                            actual_range = get_approximate_variable_value_range(
                                dataset.variables[variable]
                            )
                        else:
                            actual_range = {
                                "min": actual_range_list[0],
                                "max": actual_range_list[1],
                            }
                    else:
                        actual_range = get_approximate_variable_value_range(
                            dataset.variables[variable]
                        )

                    file_dictionary["variables"][variable] = {
                        "title": variable,
                        "valueRange": actual_range,
                    }

                    variable_to_add = Variables(
                        title=file_dictionary["variables"][variable]["title"],
                        value_range=json.dumps(
                            file_dictionary["variables"][variable]["valueRange"]
                        ),
                    )

                    file_to_add.variables.append(variable_to_add)

            current_group.files.append(file_to_add)
            session.add(current_group)

            session.commit()
            session.close()
            file_to_return = {"file": file_dictionary}

        else:
            file_to_return = {
                "errorMessage": "There was an error while adding the group"
            }

    except Exception as e:
        file_to_return = {
            "errorMessage": "There was an error while adding the group",
            "error": str(e),
        }

    return JsonResponse(file_to_return)


@controller(name="addGroupToDatabase", url="addGroupToDatabase/")
def add_group_to_database(request):
    try:
        if (
            request.headers.get("x-requested-with") == "XMLHttpRequest"
            and request.method == "POST"
        ):
            SessionMaker = app.get_persistent_store_database(
                Persistent_Store_Name, as_sessionmaker=True
            )
            session = SessionMaker()
            group = {
                "title": request.POST.get("title"),
                "description": request.POST.get("description"),
            }
            group_database_obj = Groups(
                title=group["title"], description=group["description"]
            )
            session.add(group_database_obj)
            session.commit()
            session.close()
        else:
            group = {"errorMessage": "There was an error while adding the group"}
    except Exception as e:
        group = {
            "errorMessage": "There was an error while adding the group",
            "error": str(e),
        }
    return JsonResponse(group)


@controller(name="calculateNewDataset", url="calculateNewDataset/")
def calculate_new_dataset(request):
    try:
        if (
            request.headers.get("x-requested-with") == "XMLHttpRequest"
            and request.method == "POST"
        ):
            dataset_array = json.loads(request.POST.get("datasetArray"))
            math_string = dataset_array["mathString"].replace("^", "**")
            new_name = dataset_array["newName"]
            new_dataset_values = []
            datasets_in_expression = []
            datetime_lists = []
            datetimes_match = True
            cumulative = False

            if math_string[:10] == "Cumulative":
                cumulative = True
                math_string = math_string[11:-10]

            split_math_string = math_string.split("!")

            for index, parts_of_expression in enumerate(split_math_string):
                if index % 2 == 1:
                    datasets_in_expression.append(parts_of_expression)

            for dataset in datasets_in_expression:
                datetime_list = []
                for time in dataset_array[dataset]["x"]:
                    datetime_list.append(datetime.strptime(time, "%Y-%m-%d %H:%M:%S"))
                datetime_lists.append(datetime_list)

            for datetime_list in datetime_lists:
                if not datetime_list == datetime_lists[0]:
                    datetimes_match = False

            if datetimes_match:
                if len(split_math_string) >= 1:
                    for value in range(len(dataset_array[split_math_string[1]]["y"])):
                        math_expression = ""
                        valid_expression = True
                        for index, expression in enumerate(split_math_string):
                            if index % 2 == 0:
                                math_expression += expression
                            else:
                                if isinstance(
                                    dataset_array[expression]["y"][value], int
                                ) or isinstance(
                                    dataset_array[expression]["y"][value], float
                                ):
                                    math_expression += str(
                                        dataset_array[expression]["y"][value]
                                    )
                                else:
                                    valid_expression = False
                        if valid_expression:
                            new_dataset_values.append(eval(math_expression))
                        else:
                            new_dataset_values.append(None)

                if cumulative:
                    time_series_values = np.array(new_dataset_values)
                    time_series_length = len(time_series_values)
                    ones_triangle = np.tril(
                        np.ones((time_series_length, time_series_length)), 0
                    )
                    cumulative = np.matmul(ones_triangle, time_series_values)
                    new_dataset_values = cumulative.tolist()

                time_series = {
                    new_name: new_dataset_values,
                    "datetime": dataset_array[split_math_string[1]]["x"],
                }

                array_to_return = {"dataArray": time_series}
            else:
                array_to_return = {
                    "errorMessage": "The timesteps for each dataset used must match."
                }
        else:
            array_to_return = {
                "errorMessage": "There was an error while calculating the new dataset."
            }
    except Exception as e:
        print(e)
        array_to_return = {
            "errorMessage": "There was an error while calculating the new dataset.",
            "error": str(e),
        }
    return JsonResponse(array_to_return)


def commit_shapefile_to_database(geojson, filename):
    SessionMaker = app.get_persistent_store_database(
        Persistent_Store_Name, as_sessionmaker=True
    )
    session = SessionMaker()
    shapefiles = session.query(Shapefiles).all()
    has_same_name = False

    for shapefile_to_check in shapefiles:
        if filename == shapefile_to_check.title:
            has_same_name = True
        else:
            has_same_name = False

    if has_same_name:
        session.close()
        return True
    else:
        shapefile = Shapefiles(title=filename, geometry=geojson)
        session.add(shapefile)
        session.commit()
        session.close()
        return False


@controller(name="addShapefileToDAtabase", url="addShapefileToDAtabase/")
def add_shapefile_to_database(request):
    try:
        if (
            request.headers.get("x-requested-with") == "XMLHttpRequest"
            and request.method == "POST"
        ):
            shapefiles = request.FILES.getlist("uploadedFiles")

            app_workspace = get_app_workspace(app)
            path_to_shapefile_folder = app_workspace.path

            for n, shapefile in enumerate(shapefiles):
                with open(
                    os.path.join(path_to_shapefile_folder, shapefile.name), "wb"
                ) as dst:
                    for chunk in shapefiles[n].chunks():
                        dst.write(chunk)

            main_shapefile = glob(os.path.join(path_to_shapefile_folder, "*.shp"))[0]
            shapefile_name = os.path.splitext(os.path.basename(main_shapefile))[0]
            all_shapefiles = glob(
                os.path.join(path_to_shapefile_folder, shapefile_name + "*")
            )
            path_to_shapefile = os.path.join(
                path_to_shapefile_folder, shapefile_name + ".shp"
            )

            geojson = geopandas.read_file(path_to_shapefile)

            for shapefile_to_delete in all_shapefiles:
                os.remove(shapefile_to_delete)

            has_same_name = commit_shapefile_to_database(geojson, shapefile_name)

            if has_same_name:
                shapefile_array = {
                    "errorMessage": "There is already a shapefile with that name. "
                    "Please rename your file and try again.",
                    "error": "There is already a shapefile with that name. "
                    "Please rename your file and try again.",
                }
            else:
                shapefile_array = {
                    "name": shapefile_name,
                }
        else:
            shapefile_array = {
                "errorMessage": "There was an error while saving the shapefile",
                "error": "There was an error while saving the shapefile",
            }
    except Exception as e:
        shapefile_array = {
            "errorMessage": "There was an error while saving the shapefile",
            "error": str(e),
        }
    return JsonResponse(shapefile_array)


@controller(name="deleteFilesFromDatabase", url="deleteFilesFromDatabase/")
def delete_files_from_database(request):
    try:
        if has_permission(request, "delete_groups"):
            if (
                request.headers.get("x-requested-with") == "XMLHttpRequest"
                and request.method == "POST"
            ):
                files = request.POST.getlist("titles[]")

                SessionMaker = app.get_persistent_store_database(
                    Persistent_Store_Name, as_sessionmaker=True
                )
                session = SessionMaker()

                for current_file in files:
                    current_file_from_database = (
                        session.query(Files).filter(Files.title == current_file).first()
                    )
                    session.delete(current_file_from_database)

                session.commit()
                session.close()
                result_message = {"successMessage": "The files were deleted."}
            else:
                result_message = {
                    "errorMessage": "The files were not deleted due to an error",
                    "error": "The files were not deleted due to an error",
                }
    except Exception as e:
        result_message = {
            "errorMessage": "The files were not deleted due to an error",
            "error": str(e),
        }
    return JsonResponse(result_message)


@controller(name="deleteGroupsFromDatabase", url="deleteGroupsFromDatabase/")
def delete_groups_from_database(request):
    try:
        if has_permission(request, "delete_groups"):
            if (
                request.headers.get("x-requested-with") == "XMLHttpRequest"
                and request.method == "POST"
            ):
                groups = request.POST.getlist("titles[]")

                SessionMaker = app.get_persistent_store_database(
                    Persistent_Store_Name, as_sessionmaker=True
                )
                session = SessionMaker()

                for group in groups:
                    group_from_database = (
                        session.query(Groups).filter(Groups.title == group).first()
                    )
                    session.delete(group_from_database)

                session.commit()
                session.close()
                result_message = {"successMessage": "The groups were deleted."}
            else:
                result_message = {
                    "errorMessage": "The groups were not deleted due to an error",
                    "error": "The groups were not deleted due to an error",
                }
    except Exception as e:
        result_message = {
            "errorMessage": "The groups were not deleted due to an error",
            "error": str(e),
        }
    return JsonResponse(result_message)


@controller(name="deleteShapefileFromDatabase", url="deleteShapefileFromDatabase/")
def delete_shapefile_from_database(request):
    try:
        if (
            request.headers.get("x-requested-with") == "XMLHttpRequest"
            and request.method == "POST"
        ):
            shapefile_name = request.POST.get("name")

            SessionMaker = app.get_persistent_store_database(
                Persistent_Store_Name, as_sessionmaker=True
            )
            session = SessionMaker()

            shapefile_from_database = (
                session.query(Shapefiles)
                .filter(Shapefiles.title == shapefile_name)
                .first()
            )
            session.delete(shapefile_from_database)

            session.commit()
            session.close()
            result_message = {"successMessage": "The shapefile was deleted."}
        else:
            result_message = {
                "errorMessage": "The groups were not deleted due to an error",
                "error": "The groups were not deleted due to an error",
            }
    except Exception as e:
        result_message = {
            "errorMessage": "The shapefile was not deleted due to an error",
            "error": str(e),
        }
    return JsonResponse(result_message)


def determine_dimension_type(dimension, variables):
    list_of_time_dimensions = [
        "time",
        "date",
        "month",
        "day",
        "year",
        "hour",
        "minute",
        "second",
    ]
    list_of_x_dimensions = [
        "lon",
        "lng",
        "longitude",
        "x",
        "degrees east",
        "degrees west",
    ]
    list_of_y_dimensions = ["lat", "latitude", "y", "degrees north", "degrees south"]

    if dimension.name in variables and "axis" in variables[dimension.name].__dict__:
        if variables[dimension.name].__dict__["axis"] == "T":
            dimension_type = "time"
        elif variables[dimension.name].__dict__["axis"] == "X":
            dimension_type = "x"
        elif variables[dimension.name].__dict__["axis"] == "Y":
            dimension_type = "y"
        else:
            dimension_type = "other"
    else:
        if (
            dimension.name.lower() in list_of_time_dimensions
            or "time" in dimension.name.lower()
        ):
            dimension_type = "time"
        elif (
            dimension.name.lower() in list_of_x_dimensions
            or "lon" in dimension.name.lower()
        ):
            dimension_type = "x"
        elif (
            dimension.name.lower() in list_of_y_dimensions
            or "lat" in dimension.name.lower()
        ):
            dimension_type = "y"
        else:
            dimension_type = "other"
    return dimension_type


@controller(name="getAllGroupsFromDatabase", url="getAllGroupsFromDatabase/")
def get_all_groups_from_database(request):
    try:
        thredds_groups_list = []

        SessionMaker = app.get_persistent_store_database(
            Persistent_Store_Name, as_sessionmaker=True
        )
        session = SessionMaker()

        thredds_groups = session.query(Groups).all()

        for group in thredds_groups:
            layer_obj = {"title": group.title, "description": group.description}
            thredds_groups_list.append(layer_obj)

        list_catalog = {"groups": thredds_groups_list}
        session.close()
    except Exception as e:
        list_catalog = {
            "errorMessage": "There was an error while adding the group",
            "error": str(e),
        }
    return JsonResponse(list_catalog)


@controller(
    name="getAllThreddsFilesFromDatabase", url="getAllThreddsFilesFromDatabase/"
)
def get_all_files_from_a_group(request):
    try:
        group_title = request.GET.get("group")

        SessionMaker = app.get_persistent_store_database(
            Persistent_Store_Name, as_sessionmaker=True
        )
        session = SessionMaker()  # Initiate a session
        files_in_group = (
            session.query(Groups).filter(Groups.title == group_title)[0].files
        )
        list_of_files = []

        for current_file in files_in_group:
            current_file_array = {
                "accessURLs": json.loads(current_file.urls),
                "description": current_file.description,
                "dimensionalVariables": json.loads(current_file.dimensional_variables),
                "fileType": current_file.file_type,
                "title": current_file.title,
                "userCredentials": json.loads(current_file.authentication),
                "variables": {},
            }

            for variable in current_file.variables:
                variable_array = {
                    "title": variable.title,
                    "valueRange": json.loads(variable.value_range),
                }
                current_file_array["variables"][variable.title] = variable_array

            list_of_files.append(current_file_array)

        session.close()
        array_to_return = {"listOfFiles": list_of_files}
    except Exception as e:
        array_to_return = {
            "listOfFiles": {
                "errorMessage": "An error occurred while retrieving the files",
                "error": str(e),
            }
        }
    return JsonResponse(array_to_return)


def get_approximate_variable_value_range(variable):
    try:
        var_size = variable.shape
        indexing_list = []

        for dim_size in var_size:
            if dim_size <= 5:
                index_number = 1
            else:
                index_number = math.floor(dim_size / 5)

            indexing_list.append(index_number)

        if len(var_size) == 1:
            small_array = variable[:: indexing_list[0]]
        elif len(var_size) == 2:
            small_array = variable[:: indexing_list[0], :: indexing_list[1]]
        elif len(var_size) == 3:
            small_array = variable[
                :: indexing_list[0], :: indexing_list[1], :: indexing_list[2]
            ]
        elif len(var_size) == 4:
            small_array = variable[
                :: indexing_list[0],
                :: indexing_list[1],
                :: indexing_list[2],
                :: indexing_list[3],
            ]
        elif len(var_size) == 5:
            small_array = variable[
                :: indexing_list[0],
                :: indexing_list[1],
                :: indexing_list[2],
                :: indexing_list[3],
                :: indexing_list[4],
            ]
        elif len(var_size) == 6:
            small_array = variable[
                :: indexing_list[0],
                :: indexing_list[1],
                :: indexing_list[2],
                :: indexing_list[3],
                :: indexing_list[4],
                :: indexing_list[5],
            ]

        min_value = np.nanmin(small_array)
        max_value = np.nanmax(small_array)
        min_max_array = {"min": str(min_value), "max": str(max_value)}
    except Exception as e:
        print(e)
        min_max_array = {"min": str(0), "max": str(100)}
    return min_max_array


@controller(
    name="getDisclaimerFromServer",
    url="getDisclaimerFromServer/",
)
def get_disclaimer(request):
    try:
        disclaimer_message = app.get_custom_setting("disclaimer_message")
        disclaimer_header = app.get_custom_setting("disclaimer_header")

        array_to_return = {"header": disclaimer_header, "message": disclaimer_message}
    except Exception as e:
        array_to_return = {"errorMessage": "An error occurred.", "error": str(e)}
    return JsonResponse(array_to_return)


def get_variable_metadata(variable):
    variable_metadata = {}
    for key in variable.__dict__:
        variable_metadata[key] = str(variable.__dict__[key])
    return variable_metadata


@controller(
    name="getShapefileCoordinatesFromDatabase",
    url="getShapefileCoordinatesFromDatabase/",
)
def get_shapefile_coordinates(request):
    try:
        if (
            request.headers.get("x-requested-with") == "XMLHttpRequest"
            and request.method == "POST"
        ):
            shapefile_name = request.POST.get("name")

            SessionMaker = app.get_persistent_store_database(
                Persistent_Store_Name, as_sessionmaker=True
            )
            session = SessionMaker()

            shapefile_from_database = (
                session.query(Shapefiles)
                .filter(Shapefiles.title == shapefile_name)
                .first()
            )

            session.close()
            array_to_return = {
                "geojson": json.loads(shapefile_from_database.geometry),
                "name": shapefile_from_database.title,
            }
        else:
            array_to_return = {
                "errorMessage": "The shapefile could not be retrieved",
                "error": "The shapefile could not be retrieved",
            }
    except Exception as e:
        array_to_return = {
            "errorMessage": "The shapefile could not be retrieved",
            "error": str(e),
        }
    return JsonResponse(array_to_return)


@controller(name="getShapefileNamesFromDatabase", url="getShapefileNamesFromDatabase/")
def get_shapefile_names(request):
    try:
        list_of_names = []
        SessionMaker = app.get_persistent_store_database(
            Persistent_Store_Name, as_sessionmaker=True
        )
        session = SessionMaker()
        shapefiles = session.query(Shapefiles).all()

        for shapefile in shapefiles:
            list_of_names.append(shapefile.title)

        array_to_return = {"listOfShapefileNames": list_of_names}
        session.close()
    except Exception as e:
        array_to_return = {
            "listOfFiles": {
                "errorMessage": "An error occurred while retrieving the files",
                "error": str(e),
            }
        }
    return JsonResponse(array_to_return)
