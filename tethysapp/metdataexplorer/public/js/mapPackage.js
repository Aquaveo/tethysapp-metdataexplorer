import {appProxyURL} from "./urlsPackage.js";
import {notifyOfInfo} from "./userMessagingPackage.js";

let changeWMSLayerOpacity;
let createDrawingLayers;
let createGeojosnMarker;
let createMapMarker;
let createWMSLayer;
let getMarkerGeojson;
let mapMarkerLayer;
let geojsonMarkerLayer;
let drawMenu;
let initBaseMaps;
let initMap;
let mapObj;
let mapDrawingMenu;
let removeTimeDimensionLayer;
let wmsTimeDimensionLayer;
let setUpMap;

changeWMSLayerOpacity = function (opacity) {
    if (mapObj.hasLayer(wmsTimeDimensionLayer)) {
        wmsTimeDimensionLayer.setOpacity(opacity);
    } else {
        console.log("Can't set opacity");
    }
}

createDrawingLayers = function (map) {
    if (map !== undefined) {
        mapMarkerLayer = L.featureGroup().addTo(map);
        geojsonMarkerLayer = L.geoJSON().addTo(map);
    }
};

createGeojosnMarker = function (geojsonFeature) {
    if (geojsonFeature !== undefined) {
        mapMarkerLayer.clearLayers();
        geojsonMarkerLayer.clearLayers();
        geojsonMarkerLayer.addData(geojsonFeature);
    }
};

createMapMarker = function (drawEvent) {
    if (drawEvent.layer !== undefined) {
        mapMarkerLayer.clearLayers();
        geojsonMarkerLayer.clearLayers();
        mapMarkerLayer.addLayer(drawEvent.layer);
        ACTIVE_VARIABLES_PACKAGE.geojson.type = drawEvent.layerType;
        ACTIVE_VARIABLES_PACKAGE.geojson.shapefile = false;
        ACTIVE_VARIABLES_PACKAGE.geojson.feature = drawEvent.layer.toGeoJSON();
    }
};

createWMSLayer = function () {
    const currentGroupId = ACTIVE_VARIABLES_PACKAGE.currentGroup.groupId;
    const currentFileId = ACTIVE_VARIABLES_PACKAGE.currentGroup.fileId;
    const wmsURL = ACTIVE_VARIABLES_PACKAGE.allServerData[currentGroupId].files[currentFileId].accessURLs.WMS;
    const variable = document.getElementById("variables-select").value;
    const dimensions = ACTIVE_VARIABLES_PACKAGE.allServerData[currentGroupId].files[currentFileId].variables[variable].dimensions;
    const min = document.getElementById("wms-bound-min").value;
    const max = $("#wms-bound-max").val();
    const range = `${min},${max}`;
    const style = $("#wmslayer-style").val();

    let proxyWMSURL;
    let wmsLayer;
    let additionalDimensionArray = {};

    dimensions.forEach((dimension) => {
        const dimensionType = ACTIVE_VARIABLES_PACKAGE.allServerData[currentGroupId].files[currentFileId].dimensions[dimension].dimensionType;
        if (dimensionType === "other") {
            additionalDimensionArray[dimension] = $(`#dimension-additional-${dimension}-select-values`).val();
        }
    });

    if (Object.keys(additionalDimensionArray).length <= 0) {
        additionalDimensionArray["null"] = null
    }

    try {
        removeTimeDimensionLayer();

        proxyWMSURL = `${appProxyURL}?main_url=${encodeURIComponent(wmsURL)}`;

        console.log(additionalDimensionArray[Object.keys(additionalDimensionArray)[0]])
        wmsLayer = L.tileLayer.wms(proxyWMSURL, {
            BGCOLOR: "0x000000",
            colorscalerange: range,
            crossOrigin: true,
            dimension: "time",
            elevation: additionalDimensionArray[Object.keys(additionalDimensionArray)[0]],
            format: "image/png",
            layers: variable,
            pane:"wmsLayer",
            styles: style,
            transparent: true,
            useCache: true
        });

        wmsTimeDimensionLayer = L.timeDimension.layer.wms(wmsLayer, {
            cacheForward: 200,
            name: `timeDimensionLayer`,
            requestTimefromCapabilities: false,
            updateTimeDimension: true,
            updateTimeDimensionMode: "replace"
        });

        wmsTimeDimensionLayer.addTo(mapObj);
    } catch (err) {
        console.error(err);
    }
};

getMarkerGeojson = function () {
    if (geojsonMarkerLayer.toGeoJSON().features.length > 0 && mapMarkerLayer.toGeoJSON().features.length <= 0) {
        return geojsonMarkerLayer.toGeoJSON();
    } else if (mapMarkerLayer.toGeoJSON().features.length > 0 && geojsonMarkerLayer.toGeoJSON().features.length <= 0) {
        return mapMarkerLayer.toGeoJSON();
    } else {
        notifyOfInfo("No features on the map.");
    }
};

initBaseMaps = function (map) {
    const basemapLayers = {
        "Esri Arial Imagery": L.tileLayer(
            "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
            {attribution: "Tiles &copy; Esri &mdash; Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EGP, and the GIS User Community"}).addTo(map),
        "USGS Arial Imagery": L.tileLayer(
            "https://basemap.nationalmap.gov/arcgis/rest/services/USGSImageryOnly/MapServer/tile/{z}/{y}/{x}",
            {attribution: "Tiles courtesy of the <a href='https://usgs.gov/'>U.S. Geological Survey</a>"}),
        "USGS Imagery With Labels": L.tileLayer(
            "https://basemap.nationalmap.gov/arcgis/rest/services/USGSImageryTopo/MapServer/tile/{z}/{y}/{x}",
            {attribution: "Tiles courtesy of the <a href='https://usgs.gov/'>U.S. Geological Survey</a>"}),
        "USGS Topographical": L.tileLayer(
            "https://basemap.nationalmap.gov/arcgis/rest/services/USGSTopo/MapServer/tile/{z}/{y}/{x}",
            {attribution: "Tiles courtesy of the <a href='https://usgs.gov/'>U.S. Geological Survey</a>"})
    };
    L.control.layers(basemapLayers, null, {collapsed: true}).addTo(map);
};

initMap = function () {
    mapObj = L.map("map", {
        boxZoom: true,
        center: [0, 0],
        fullscreenControl: true,
        minZoom: 2,
        timeDimension: true,
        timeDimensionControl: true,
        timeDimensionControlOptions: {
            autoPlay: true,
            backwardButton: true,
            forwardButton: true,
            loopButton: true,
            maxSpeed: 6,
            minSpeed: 2,
            position: "bottomleft",
            speedStep: 1,
            timeSliderDragUpdate: true
        },
        zoom: 3,
        zoomSnap: 0.5
    });

    mapObj.createPane("wmsLayer");
    mapObj.getPane("wmsLayer").style.zIndex = 250;
    return mapObj;
};

mapDrawingMenu = function (map) {
    let drawControl = new L.Control.Draw({
        draw: {
            circle: false,
            polyline: false
        },
        edit: {
            edit: true,
            featureGroup: mapMarkerLayer
        }
    });
    drawControl.addTo(map);
    return drawControl;
};

removeTimeDimensionLayer = function () {
    if (mapObj.hasLayer(wmsTimeDimensionLayer)) {
        mapObj.removeLayer(wmsTimeDimensionLayer);
    }
};

setUpMap = function (callback) {
    initMap();
    initBaseMaps(mapObj);
    createDrawingLayers(mapObj);
    drawMenu = mapDrawingMenu(mapObj);

    mapObj.on(L.Draw.Event.CREATED, function (drawEvent) {
        createMapMarker(drawEvent);
    });

    if (typeof callback === "function") {
        callback();
    }
};

export {
    changeWMSLayerOpacity,
    createGeojosnMarker,
    createMapMarker,
    createWMSLayer,
    drawMenu,
    getMarkerGeojson,
    mapObj,
    removeTimeDimensionLayer,
    setUpMap
};