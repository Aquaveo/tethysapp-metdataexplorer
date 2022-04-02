import {addFileMetadata, buildBaseMenuForSelectedVariable} from "./htmlPackage.js";
import {moveCarouselLeft, moveCarouselRight} from "./htmlHelpersForBaseMenu.js";
import {changeWMSLayerOpacity, createWMSLayer, drawMenu, mapObj} from "./mapPackage.js";
import {notifyOfDanger, notifyOfInfo} from "./userMessagingPackage.js";
import {extractTimeseriesAjax} from "./dataRemoteAccessPackage.js";
import {createGraph, makeTrace} from "./graphPackage.js";
import {formatCSV, formatHTML, formatJSON, formatPython} from "./formatFilesPackage.js";
import {formatValuesFromGrids} from "./auxilaryPackage.js";

let setBaseMenuEventListeners;

setBaseMenuEventListeners = function () {
    //Carousel navigation buttons
    $(".single-indicator").on("click", (event) => {
        const slideToWhichToMove = event.target.id.slice(-1);
        if (slideToWhichToMove >= 1 && slideToWhichToMove <= 4) {
            let currentHash = parseInt(window.location.hash.slice(-1));

            if (currentHash === 1 || currentHash === 2 || currentHash === 3 || currentHash === 4) {
                let numbersToSlide = currentHash - slideToWhichToMove;
                [...Array(Math.abs(numbersToSlide))].forEach(number => {
                    if (numbersToSlide < 0) {
                        moveCarouselLeft();
                    } else if (numbersToSlide > 0) {
                        moveCarouselRight();
                    }
                });
            } else {
                window.location.hash = 1;
            }
        }
    });

    document.getElementById("move-carousel-right").addEventListener("click", () => {
        moveCarouselRight();
    });

    document.getElementById("move-carousel-left").addEventListener("click", () => {
        moveCarouselLeft();
    });

    //Carousel container 1
    $("#variables-select").on("changed.bs.select", () => {
        $("#additional-dimensions-div").empty();
        buildBaseMenuForSelectedVariable();
    });

    $("#select-drawing-option").on("changed.bs.select", () => {
        try {
            if($("#select-drawing-option").val() === "use-shapefile") {
                mapObj.removeControl(drawMenu);
                $("#modalShapefileList").modal("show");
            } else if($("#select-drawing-option").val() === "draw-on-map") {
                drawMenu.addTo(mapObj);
            }
        } catch (error) {
            notifyOfDanger("An error occurred");
            console.error(error);
        };
    });

    /*
    TODO fix time dimension subsetting
    document.getElementById("time-dimensions-div").addEventListener("click", (event) => {
        const clickedElement = event.target;

        if (clickedElement.classList.contains("disabled-true") || clickedElement.parentElement?.classList.contains("disabled-true")) {
            const divId = clickedElement.closest(".disabled-true").id;

            $(`#dimension-${divId}-first`).prop("disabled", false).selectpicker("refresh");
            $(`#dimension-${divId}-second`).prop("disabled", false).selectpicker("refresh");

            $(`#${divId}`).removeClass("disabled-true");
            $(`#${divId}`).addClass("disabled-false");
        } else if (clickedElement.classList.contains("disabled-false") || clickedElement.parentElement?.classList.contains("disabled-true")) {
            const divId = clickedElement.closest(".disabled-false").id;

            $(`#dimension-${divId}-first`).prop("disabled", true).selectpicker("refresh");
            $(`#dimension-${divId}-second`).prop("disabled", true).selectpicker("refresh");

            $(`#${divId}`).removeClass("disabled-false");
            $(`#${divId}`).addClass("disabled-true");
        }
    });
     */

    document.getElementById("opacity-slider").addEventListener("change", (event) => {
        const newValueAsDecimal = event.target.value;
        const newValueAsPercent = Math.round(newValueAsDecimal * 100);
        $("#opacity-value").empty().append(newValueAsPercent);
        changeWMSLayerOpacity(newValueAsDecimal);
    });

    document.getElementById("hide-data-layer-button").addEventListener("click", () => {
        document.getElementById("opacity-slider").value = 0;
        $("#opacity-value").empty().append(0);
        changeWMSLayerOpacity(0);
    });

    document.getElementById("plot-time-series-button").addEventListener("click", async () => {
        try {
            const parametersForGrids = formatValuesFromGrids();
            const variable = $("#variables-select").val();
            notifyOfInfo("Retrieving data. This may take several minutes.");
            const result = await extractTimeseriesAjax(parametersForGrids);
            if (result.errorMessage !== undefined) {
                if (result.error === "All arrays must be of the same length") {
                    notifyOfDanger("The data could not be retrieved. Refresh the file and try again.");
                } else {
                    notifyOfDanger(result.errorMessage);
                }
                console.error(result.error);
            } else {
                const timeSeries = JSON.parse(result.timeSeries);
                Object.keys(timeSeries).forEach((key) => {
                    if (key !== "datetime") {
                        makeTrace(timeSeries[key], timeSeries["datetime"], key, variable);
                    }
                });
                createGraph();
                moveCarouselLeft();
            }
        } catch (error) {
            notifyOfDanger("An error occurred. Please refresh the page and try again.");
            console.error(error);
        }
    });

    document.getElementById("update-display-settings").addEventListener("click", () => {
        createWMSLayer();
    });

    //carousel container 2
    document.getElementById("clear-graph-button").addEventListener("click", () => {
        ACTIVE_VARIABLES_PACKAGE.dataForGraph = {
            scatter: [],
            box: []
        };
        createGraph();
    });

    $("#graph-type-select").on("changed.bs.select", () => {
        createGraph();
    });

    $("#download-data-select").on("changed.bs.select", async () => {
        const whatToDownload = $("#download-data-select").val();
        const dataOnGraph = ACTIVE_VARIABLES_PACKAGE.dataForGraph.scatter;
        let fileToDownload;
        let fileType;

        if (whatToDownload === "csv") {
            fileType = "csv";
            fileToDownload = formatCSV(dataOnGraph);
        } else if (whatToDownload === "json") {
            fileType = "json";
            fileToDownload = formatJSON(dataOnGraph);
        } else if (whatToDownload === "NetCDF") {
            //Todo add netCDF subsetting functionality
            console.log("we are still working on this")
        } else if (whatToDownload === "html") {
            fileType = "html";
            fileToDownload = formatHTML();
        } else if (whatToDownload === "python") {
            fileType = "ipynb";
            fileToDownload = await formatPython();
        }

        if (fileToDownload === false) {
            notifyOfDanger("The file could not be downloaded.");
        } else {
            let blob = new Blob([fileToDownload], {type: `text/${fileType};charset=utf-8;`});
            let link = document.createElement("a");
            let url = URL.createObjectURL(blob);
            let currentdate = new Date();
            let datetime = `${currentdate.getDate()}-${(currentdate.getMonth() + 1)}-${currentdate.getFullYear()}-${currentdate.getHours()}:${currentdate.getMinutes()}:${currentdate.getSeconds()}`;
            link.setAttribute("href", url);
            link.setAttribute("download", `${datetime}.${fileType}`);
            link.style.visibility = 'hidden';
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        }
    });

    //carousel container 4
    document.getElementById("list-of-variables-div").addEventListener("click", (event) => {
        const clickedElement = event.target;
        if (clickedElement.classList.contains("metadata-info") || clickedElement.parentElement?.classList.contains("metadata-info")) {
            const variable = clickedElement.closest(".metadata-info").value;
            const html = addFileMetadata(false, variable);
            $("#metadata_vars").empty().append(html);
            $("#modalMetaDataForVariable").modal("show");
        }
    });
};

export {
    setBaseMenuEventListeners
}


