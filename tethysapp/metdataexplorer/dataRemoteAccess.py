from django.http import JsonResponse, HttpResponse
from siphon.catalog import TDSCatalog
from tethys_sdk.permissions import has_permission
from tethys_sdk.routing import controller

from .app import Metdataexplorer as app
from .databaseInterface import (
    determine_dimension_type,
    get_variable_metadata,
    add_variables_to_opendap_url,
    get_approximate_variable_value_range,
)

import cfbuild
import os
import json
import netCDF4
import requests

# DODS_CONF
# DAPRCFILE
# DODS_CACHE_INIT


def set_rc_vars():
    home_variable = app.get_custom_setting("server_home_directory")
    os.environ["USERPROFILE"] = home_variable
    return home_variable


def reset_home_var(home_variable):
    if home_variable is not None:
        os.environ["USERPROFILE"] = home_variable
    else:
        os.environ.pop("USERPROFILE")


@controller(name="getFoldersAndFilesFromCatalog", url="getFoldersAndFilesFromCatalog/")
def get_files_and_folders_from_catalog(request):
    try:
        home_variable = set_rc_vars()
        dict_of_folders = {}
        dict_of_files = {}

        url_for_catalog = request.POST.get("urlForCatalog")
        ds = TDSCatalog(url_for_catalog)
        correct_url = ds.catalog_url
        list_of_folders = ds.catalog_refs
        list_of_files = ds.datasets

        for folder_counter in range(len(list_of_folders)):
            dict_of_folders[list_of_folders[folder_counter].title] = list_of_folders[
                folder_counter
            ].href

        for file_counter in range(len(list_of_files)):
            access_url_array = {}

            for url_type in list_of_files[file_counter].access_urls:
                access_url_array[url_type.upper()] = list_of_files[
                    file_counter
                ].access_urls[url_type]

            dict_of_files[list_of_files[file_counter].name] = access_url_array

        dict_to_return = {
            "data": {
                "correctURL": correct_url,
                "files": dict_of_files,
                "folders": dict_of_folders,
            }
        }

        reset_home_var(home_variable)
    except Exception as e:
        dict_to_return = {
            "data": {
                "errorMessage": "An error occurred while connecting to the THREDDS catalog.",
                "error": str(e),
            }
        }
    return JsonResponse(dict_to_return)


@controller(name="getPermissionsFromServer", url="getPermissionsFromServer/")
def get_permissions_from_server(request):
    try:
        permissions = {
            "canDeleteGroups": has_permission(request, "delete_groups"),
            "canAddGroups": has_permission(request, "add_groups"),
        }
    except Exception as e:
        permissions = {
            "data": {
                "errorMessage": "An error occurred while loading the page.",
                "error": str(e),
            }
        }
    return JsonResponse(permissions)


@controller(
    name="getVariablesAndDimensionsForFile", url="getVariablesAndDimensionsForFile/"
)
def get_variables_and_dimensions_for_file(request):
    try:
        home_variable = set_rc_vars()

        opendap_url = request.POST.get("opendapURL")

        list_of_variables = {}

        ds = cfbuild.Dataset(opendap_url)
        all_variables = []
        list_of_incompatible_variables = []

        for variable in ds.variables:
            if ds.variables[variable].variable_type == "Georeferenced Data Variable":
                list_of_dimensions = []
                all_variables.append(ds.variables[variable].name)
                add_variable = True

                for dimension in ds.variables[variable].dimensions:
                    if dimension in ds.variables:
                        list_of_dimensions.append(dimension)
                        if dimension not in all_variables:
                            all_variables.append(dimension)
                    else:
                        add_variable = False
                        if variable not in list_of_incompatible_variables:
                            list_of_incompatible_variables.append(variable)

                if add_variable:
                    list_of_variables[ds.variables[variable].name] = list_of_dimensions
            else:
                list_of_incompatible_variables.append(variable)

        dict_to_return = {
            "data": {
                "listOfVariables": list_of_variables,
                "allVariables": all_variables,
                "incompatibleVariables": list_of_incompatible_variables,
            }
        }
        reset_home_var(home_variable)
    except Exception as e:
        dict_to_return = {
            "data": {
                "errorMessage": "An error occurred while connecting to the THREDDS catalog.",
                "error": str(e),
            }
        }
    return JsonResponse(dict_to_return)


@controller(name="updateFileData", url="updateFileData/")
def update_files(request):
    try:
        if (
            request.headers.get("x-requested-with") == "XMLHttpRequest"
            and request.method == "POST"
        ):

            file_dictionary = {
                "accessURLs": json.loads(request.POST.get("urls")),
                "fileType": request.POST.get("fileType"),
                "dimensions": {},
                "fileMetadata": {},
                "gridMapping": "",
                "variables": {},
                "variablesAndDimensions": json.loads(
                    request.POST.get("listOfVariables")
                ),
            }

            dimensional_variables = request.POST.getlist("listOfDimensionalVariable[]")

            list_for_opendap = []

            if len(file_dictionary["variablesAndDimensions"]) > 0:
                for variable in file_dictionary["variablesAndDimensions"]:
                    list_for_opendap.append(variable)

                for dimension in dimensional_variables:
                    list_for_opendap.append(dimension)

                opendap_url = add_variables_to_opendap_url(
                    file_dictionary["accessURLs"]["OPENDAP"], list_for_opendap
                )
            else:
                opendap_url = file_dictionary["accessURLs"]["OPENDAP"]

            dataset = netCDF4.Dataset(opendap_url)

            for key in dataset.__dict__:
                file_dictionary["fileMetadata"][key] = str(dataset.__dict__[key])

            if len(file_dictionary["variablesAndDimensions"]) == 0:
                ds = cfbuild.Dataset(opendap_url)

                for variable in ds.variables:
                    print(ds.variables[variable].variable_type)
                    if (
                        ds.variables[variable].variable_type
                        == "Georeferenced Data Variable"
                    ):
                        file_dictionary["variablesAndDimensions"][variable] = {
                            "title": variable
                        }
                    if ds.variables[variable].variable_type == "Grid Mapping Variable":
                        params = {}
                        print("!!!!!!!!!grid mapping!!!!!!!!!")
                        for attr in ds.variables[variable].attributes:
                            print(attr)
                            print(ds.variables[variable].attributes[attr])
                            params[attr] = ds.variables[variable].attributes[attr]

                        file_dictionary["gridMapping"] = {
                            "title": variable,
                            "params": params,
                        }

            for dimension in dataset.dimensions:
                if dimension in dataset.variables:
                    dimension_type = determine_dimension_type(
                        dataset.dimensions[dimension], dataset.variables
                    )
                    dimension_metadata = get_variable_metadata(
                        dataset.variables[dimension]
                    )
                    if dimension_type == "time":
                        if "units" in dimension_metadata:
                            if "calendar" in dimension_metadata:
                                calendar = dimension_metadata["calendar"]
                            else:
                                calendar = "standard"
                            date_time_list = netCDF4.num2date(
                                dataset.variables[dimension][:].data.tolist(),
                                dimension_metadata["units"],
                                calendar,
                            )
                            values = []
                            for time in date_time_list:
                                values.append(str(time))
                        else:
                            values = dataset.variables[dimension][:].data.tolist()
                    else:
                        values = dataset.variables[dimension][:].data.tolist()

                    file_dictionary["dimensions"][dimension] = {
                        "dimensionMetadata": dimension_metadata,
                        "dimensionType": dimension_type,
                        "title": dataset.dimensions[dimension].name,
                        "size": dataset.dimensions[dimension].size,
                        "values": values,
                    }

            for variable in file_dictionary["variablesAndDimensions"]:
                list_of_dimensions = []

                if "valueRange" in file_dictionary["variablesAndDimensions"][variable]:
                    actual_range = file_dictionary["variablesAndDimensions"][variable][
                        "valueRange"
                    ]
                elif "actual_range" in dataset.variables[variable].__dict__:
                    actual_range = dataset.variables[variable].__dict__["actual_range"]
                else:
                    actual_range = get_approximate_variable_value_range(
                        dataset.variables[variable]
                    )

                for dimension in dataset.variables[variable].dimensions:
                    list_of_dimensions.append(dimension)

                file_dictionary["variables"][variable] = {
                    "title": variable,
                    "dimensions": list_of_dimensions,
                    "shape": dataset.variables[variable].shape,
                    "wmsDisplayColor": "boxfill/rainbow",
                    "valueRange": actual_range,
                    "variableMetadata": get_variable_metadata(
                        dataset.variables[variable]
                    ),
                }

            file_to_return = {"file": file_dictionary}

        else:
            file_to_return = {"errorMessage": "There was an error retrieving the file"}

    except Exception as e:
        file_to_return = {
            "errorMessage": "There was an error retrieving the file",
            "error": str(e),
        }
    return JsonResponse(file_to_return)


@controller(name="getWMSImageFromServer", url="getWMSImageFromServer/")
def wms_image_from_server(request):
    try:
        if "main_url" in request.GET:
            request_url = request.GET.get("main_url")
            query_params = request.GET.dict()
            query_params.pop("main_url", None)
            home_variable = set_rc_vars()
            r = requests.get(request_url, params=query_params)
            reset_home_var(home_variable)
            return HttpResponse(r.content, content_type="image/png")
        else:
            return JsonResponse({})
    except Exception as e:
        print(e)
        return JsonResponse({"error": e})


@controller(
    name="getLegendImageFromServer",
    url="getLegendImageFromServer/",
)
def legend_image_from_server(request):
    try:
        if "main_url" in request.GET:
            request_url = request.GET.get("main_url")
            home_variable = set_rc_vars()
            r = requests.get(request_url)
            reset_home_var(home_variable)
            return HttpResponse(r.content, content_type="image/png")
        else:
            return JsonResponse({})
    except Exception as e:
        print(e)
        return JsonResponse({"error": e})
