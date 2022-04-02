import {
    addFileMetadata,
    addListOfVariablesToBaseMenu,
    buildBaseMenuForSelectedVariable,
    createOptionForSelect
} from "./htmlPackage.js";
import {sizeWindows} from "./auxilaryPackage.js";
import {createGraph} from "./graphPackage.js";
import {
    populateDeleteGroupsModal,
    htmlForDeleteGroups
} from "./htmlHelpersForModals.js";
import {
    notifyOfDanger,
    notifyOfInfo
} from "./userMessagingPackage.js";

let setNavigationEventListeners;

setNavigationEventListeners = function () {
    document.getElementById("help-modal-btn").addEventListener("click", (event) => {
        $("#modalHelp").modal("show");
    });
    // Catalogs container
    document.getElementById("add-groups").addEventListener("click", (event) => {
        $("#modalAddGroupToDatabase").modal("show");
    });

    document.getElementById("delete-groups").addEventListener("click", (event) => {
        populateDeleteGroupsModal();
    });

    /*
    TODO Fix this event listener
    document.getElementById("filter-groups").addEventListener("click", (event) => {

        $("#modalFilterFilesByVariable").modal("show");
    });
     */

    // Each group container
    document.getElementById("groups-in-navigation-container").addEventListener("click", (event) => {
        const clickedElement = event.target;
        const groupId = clickedElement.closest(".container-for-single-group").id.slice(6);
        ACTIVE_VARIABLES_PACKAGE.currentGroup.groupId = groupId;

        //Group Buttons
        if (clickedElement.classList.contains("group-information") || clickedElement.parentElement?.classList.contains("group-information")) {
            let description_html;
            let groupTitle = ACTIVE_VARIABLES_PACKAGE.allServerData[groupId].title;
            let groupDescription = ACTIVE_VARIABLES_PACKAGE.allServerData[groupId].description;

            description_html = `<h3>Catalog Title</h3>
                                    <p>${groupTitle}</p>
                                    <h3>Catalog Description</h3>
                                    <p>${groupDescription}</p>`;
            $("#pop-up_description2").html("");
            $("#pop-up_description2").html(description_html);
            $("#modalInformationAboutGroup").modal("show");
        } else if (clickedElement.classList.contains("add-file-to-group") || clickedElement.parentElement?.classList.contains("add-file-to-group")) {
            $("#modalAddFileToDatabase").modal("show");
        } else if (clickedElement.classList.contains("delete-file-from-group") || clickedElement.parentElement?.classList.contains("delete-file-from-group")) {
            try {
                if (Object.keys(ACTIVE_VARIABLES_PACKAGE.allServerData[groupId].files).length > 0) {
                    let html = htmlForDeleteGroups(ACTIVE_VARIABLES_PACKAGE.allServerData[groupId].files, "File Name");
                    ACTIVE_VARIABLES_PACKAGE.currentGroup.groupId = groupId;
                    $("#div-for-delete-files-table").empty().append(html);
                    $("#modalDeleteFileFromDatabase").modal("show");
                } else {
                    notifyOfInfo("There are no files to delete.");
                }
            } catch (error) {
                notifyOfDanger("An error occurred while opening form");
                console.error(error);
            };
        // File Buttons
        } else if (clickedElement.classList.contains("file-name") || clickedElement.parentElement?.classList.contains("file-name")) {
            const fileId = event.target.closest(".file-and-buttons-container").id.slice(10);

            ACTIVE_VARIABLES_PACKAGE.currentGroup.fileId = fileId;

            const fileMetadataHtml = addFileMetadata();
            const listOfVariablesHtml = addListOfVariablesToBaseMenu();
            let variableToSelect = "";

            $("#variables-select").empty();
            $("#additional-dimensions-div").empty();

            Object.keys(ACTIVE_VARIABLES_PACKAGE.allServerData[groupId].files[fileId].variables).forEach((variable, index) => {
                const option = createOptionForSelect(variable);
                if (index === 0) {
                    variableToSelect = variable;
                }
                $("#variables-select").append(option);
            });
            $("#variables-select").selectpicker("refresh");

            if (variableToSelect !== "") {
                $("#variables-select").val(variableToSelect);
                $("#variables-select").selectpicker("render");
            }

            buildBaseMenuForSelectedVariable();

            $("#slider-bar").css("left", "50%");
            sizeWindows();
            createGraph();

            $("#file-metadata-div").empty().append(fileMetadataHtml);
            $("#list-of-variables-div").empty().append(listOfVariablesHtml);

        } else if (clickedElement.classList.contains("refresh-file") || clickedElement.parentElement?.classList.contains("refresh-file")) {
            console.log("refresh the file");
        } else if (clickedElement.classList.contains("edit-file") || clickedElement.parentElement?.classList.contains("edit-file")) {
            console.log("show model to edit file");
        } else if (clickedElement.classList.contains("add-variable") || clickedElement.parentElement?.classList.contains("add-variable")) {
            console.log("show model to add a variable to the file");
        } else if (clickedElement.classList.contains("delete-variable") || clickedElement.parentElement?.classList.contains("delete-variable")) {
            console.log("show model to delete a variable from the file");
        }
    });
};

export {
    setNavigationEventListeners
};