#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Mar 22 11:43:00 2024
# Copyright (C) 2024-present {nicolas.blanc} @ HEIG-VD
# This file is licensed under the GPL-3.0-only. See LICENSE file for details.
# Third-party libraries and their licenses are listed in the NOTICE.md file.
"""

import os
import re
import urllib.parse
from pathlib import Path, PosixPath
from time import time

import geopandas as gpd
import meshio
import numpy as np
import pandas as pd
import rasterio as rio
import requests
import trimesh
from geopandas import GeoDataFrame
from pydelatin import Delatin
from pydelatin.util import rescale_positions
from rasterio import merge as rio_merge
from shapely import line_merge
from shapely.geometry import LineString, Polygon, box
from trimesh.base import Trimesh

from error_handling import check_file
from logging_config import logger

# %%
# Triggers and constants
LOGLEVEL = os.getenv("LOGLEVEL", "INFO")
BASEDIR = "/data"
TRACE_FILENAME = os.getenv("TRACE_FILENAME", None)
DOWNLOAD_TILE = os.getenv("DOWNLOAD_TILE", "false").lower() == "true"
CUSTOM_MESH = os.getenv("CUSTOM_MESH", "false").lower() == "true"
TRIANGULATION_MAX_ERR = 0.5
VERTEX_VERTICAL_OFFSET = -0.8
LOG_TAB = "\n\t\t\t\t"
# %%
# The box shape to swipe along the line axis (80x40cm by default)
box_arr = np.array([[0.0, 0.0], [0.8, 0.0], [0.8, 0.4], [0.0, 0.4], [0.0, 0.0]])
box_shift = np.array([-0.4, -0.2])
box_arr += box_shift
POLYGON = Polygon(box_arr)

# Parsing directories
directories = Path(BASEDIR).glob("*/")


def load_geojson(geojson_file: PosixPath) -> GeoDataFrame:
    """Load a GeoJSON file in a GeoDataFrame.

    Parameters:
    ----------
    geojson_file : str
        The path of a GeoJSON file on the disk. The file must exist.

    Returns:
    -------
    gdf : GeoDataFrame instance
        A GeoDataFrame object containing the features from the GeoJSON file.
    """
    gdf = None
    if geojson_file.is_file():
        gdf = gpd.read_file(geojson_file)
        gdf.set_crs(epsg=2056, allow_override=True, inplace=True)

    return gdf


def compute_bbox(gdf: GeoDataFrame) -> Polygon:
    """Compute a bbox out of a GeoDataFrame

    Parameters:
    ----------
    geojson_file : str
        The path of a GeoJSON file on the disk. The file must exist.

    Returns:
    -------
    gdf : Polygon instance
        A Polygon object containing the boundary shape of the entire GeoDataFrame.
    """

    return box(*gdf.total_bounds)


def extract_bbox_bounds(bbox: Polygon) -> dict:
    """Extract bbox bounds as a dict

    Parameters:
    ----------
    bbox : Polygon
        A boundary shape given as a Polygon.

    Returns:
    -------
    bounds : dict
        A dictionnary containing the min and max coordinates of the given Polygon
        along x and y axis.
    """
    _bounds = bbox.bounds
    bounds = {
        "xMin": _bounds[0],
        "yMin": _bounds[1],
        "xMax": _bounds[2],
        "yMax": _bounds[3],
    }

    return bounds


def build_download_url(params: dict) -> str:
    """Build the download URL for swissalti3D data

    Parameters:
    ----------
    params : dict
        A dictionary containing query params to build an URL in order to query
        the ogc.swisstopo.admin.ch service.

    Returns:
    -------
    fetch_url : str
        An URL build from the given query params for fetching data from the
        ogc.swisstopo.admin.ch services.
    """
    base_url = "https://ogd.swisstopo.admin.ch/services/swiseld/services/assets/ch.swisstopo.swissalti3d/search"
    encoded_query = urllib.parse.urlencode(params, doseq=True)
    fetch_url = f"{base_url}?{encoded_query}"

    return fetch_url


def download_swisstile(fetch_url: str, TEMP_DIR: PosixPath) -> PosixPath:
    """Download a tile asset to a file on disk

    Parameters:
    ----------
    fetch_url : str
        An URL to query a tile from the ogc.swisstopo.admin.ch services.
    TEMP_DIR: PosixPath instance
        A PosixPath object to a temporary folder on disk where to store the
        resulting tile.

    Returns:
    -------
    filename : PosixPath instance
        A PosixPath object to a tile file on disk.
    """
    filename = fetch_url.split("/")[-1]
    filename = Path(TEMP_DIR, filename)
    logger.info(f"Downloading URL {fetch_url} into {filename}...")
    response = requests.get(fetch_url, timeout=(5, 30))
    with open(filename, mode="wb") as f:
        f.write(response.content)

    return filename


def download_swisstiles(fetch_url: str, TEMP_DIR: PosixPath) -> PosixPath:
    """Fetch the provided URL and download tile assets to basedir

    Parameters:
    ----------
    fetch_url : str
        An URL to fetch JSON metadata e,neding tiles from the
        ogc.swisstopo.admin.ch services.
    TEMP_DIR: PosixPath instance
        A PosixPath object to a temporary folder on disk where to store the
        resulting tile.

    Returns:
    -------
    filename : PosixPath instance
        A PosixPath object to a tile file on disk.
    """
    logger.info(
        f"Fetching and parsing URL: {fetch_url}..."
        f"{LOG_TAB}this may take a long time if the survey area is large!"
        f"{LOG_TAB}It may even be blocked by the remote service if it's too large."
        f"{LOG_TAB}Please read: https://www.swisstopo.admin.ch/en/terms-of-use-free-geodata-and-geoservices"
    )
    response = requests.get(fetch_url, timeout=(5, 10))
    filename = None
    if response.status_code == 200:
        data = response.json()
        for item in data["items"]:
            filename = download_swisstile(item["ass_asset_href"], TEMP_DIR)
    else:
        logger.info(
            f"[HTTP status: {response.status_code}]: Could not properly GET {fetch_url}"
        )

    return filename


def build_new_filename(dem_filenames: list) -> str:
    """Build a new unique swissalti3d filename based on a list of tiles.

    Parameters:
    ----------
    dem_filenames : list
        An URL to fetch JSON metadata e,neding tiles from the
        ogc.swisstopo.admin.ch services.
    TEMP_DIR: PosixPath instance
        A PosixPath object to a temporary folder on disk where to store the
        resulting tile.

    Returns:
    -------
    filename : PosixPath instance
        A PosixPath object to a virtual tile file on disk where data would have
        been written.
    """
    # Regex pattern to match the swissalti3d filenames
    pattern = r"(\w+)_(\d+)_(\d+)-(\d+)_([\d.]+)_(\d+)_(\d+)"
    x_min = float("inf")
    y_min = float("inf")
    for dem_filename in dem_filenames:
        match = re.match(pattern, dem_filename.stem)

        # Check if a match was found and extract the values
        if match:
            values = match.groups()
            dataset = str(values[0])
            year = int(values[1])
            x_km = int(values[2])
            y_km = int(values[3])
            res = float(values[4])
            proj_xy = int(values[5])
            proj_z = int(values[6])

            # Update min_x and min_y
            x_min = min(x_min, x_km)
            y_min = min(y_min, y_km)

    extended_filename = dem_filename.parent.joinpath(
        f"{dataset}_{year}_{x_min}-{y_min}_{res}_{proj_xy}_{proj_z}_extended"
        + dem_filename.suffix
    )

    return extended_filename


def merge_rasters(dem_filenames: list) -> tuple:
    """Docstring

    Parameters:
    ----------
    dem_filenames : list
        A list of DEM pathlib.Path object poiting to DEM Tiff files on the disk.
        The files must exist. The list can contain a single DEM file but not 0.

    Returns:
    -------
    retval : tuple
        A tuple containing the DEM data as a numpy.array instance, the bounds
        as a tuple with (x_min, y_min, x_max, x_max) and a virtual filepath
        for what would have been the unique file name after merging the individual
        tiles.
    """
    dem, trans = rio_merge.merge(dem_filenames)
    dem = dem.reshape(-1, dem.shape[-1])
    ys, xs = dem.shape
    bounds = (
        trans.xoff,
        trans.yoff + ys * trans.e,
        trans.xoff + xs * trans.a,
        trans.yoff,
    )
    dem_filename = build_new_filename(dem_filenames)

    return (dem, bounds, dem_filename)


def import_dem_data(dem_filenames: list) -> tuple:
    """Docstring

    Parameters:
    ----------
    dem_filenames : list
        A list of DEM pathlib.Path object poiting to DEM Tiff files on the disk.
        The files must exist. The list can contain a single DEM file but not 0.

    Returns:
    -------
    retval : tuple
        A tuple containing the DEM data as a numpy.array instance, the bounds
        as a tuple with (x_min, y_min, x_max, x_max) and a virtual filepath
        for what would have been the unique file name after merging the individual
        tiles.
    """
    if len(dem_filenames) == 0:
        logger.error("No DEM files provided.")
        return None

    if len(dem_filenames) > 1:
        dem, bounds, dem_filename = merge_rasters(dem_filenames)
        logger.debug("DEM files imported successfully!")
    else:
        dem_filename = dem_filenames[0]
        with rio.open(dem_filename, "r") as ds:
            dem = ds.read()
            dem = dem.reshape(-1, dem.shape[-1])
            bounds = tuple(ds.bounds)
        logger.debug("DEM file imported successfully!")

    return (dem, bounds, dem_filename)


def triangulate(
    dem_filenames: list, max_error: int = 1, output_format: str = "ply"
) -> str:
    """Function to merge and triangulate a list of raster DEM files.
    It takes a list of raster DEM files as input and create a single ply file
    as output. The list can contain a single DEM file, but not 0.

    Parameters:
    ----------
    dem_filenames : list
        A list of DEM pathlib.Path object poiting to DEM Tiff files on the disk.
        The files must exist. The list can contain a single DEM file but not 0.
    max_error : float, default=1
        Maximum tolerance error between the raster DEM and the triangulation
        results. Given in [m].
    output_format : str, default="ply"
        The triangulated file format.

    Returns:
    -------
    mesh_filename : str
        A file path on disk where the result of the triangulation was saved.
    """
    logger.info(
        f"Starting triangulation with max_error: {max_error} and output_format: {output_format}"
    )
    t0 = time()
    dem, bounds, dem_filename = import_dem_data(dem_filenames)
    tin = Delatin(
        arr=dem,
        max_error=max_error,
    )
    vertices, triangles = tin.vertices, tin.triangles
    logger.debug(f"Offsetting vertices...: {vertices[1, :]}")
    vertices[:, -1] += VERTEX_VERTICAL_OFFSET
    logger.debug(f"Vertices offsetted successfully: {vertices[1, :]}")
    logger.debug(f"Rescalling vertices...: {vertices[1, :]}")
    rescaled_vertices = rescale_positions(vertices, bounds)
    logger.debug(f"Vertices rescaled successfully: {vertices[1, :]}")
    cells = [("triangle", triangles)]
    mesh = meshio.Mesh(rescaled_vertices, cells)
    mesh_filename = dem_filename.with_name(
        dem_filename.stem
        + "_delatin"
        + f"_err{str(max_error).replace('.', '')}."
        + output_format
    )
    mesh.write(mesh_filename)
    dt = time() - t0
    logger.info(f'Mesh written to file "{mesh_filename}" successfully.')
    logger.info(f"Triangulation executed successfully in {dt:.2f}s.")

    return mesh_filename


def load_mesh(MESH_INPUT_PATH: PosixPath) -> Trimesh:
    """Load a mesh from a mesh file given in the ply format.
    Notice: only the standard ply file format is accepted.

    Parameters:
    ----------
    MESH_INPUT_PATH : PosixPath instance
        A PosixPath object to a terrain mesh file given in the ply format
        on the disk.

    Returns:
    -------
    mesh : Trimesh
        A Trimesh instance of a mesh.
    """
    ext = MESH_INPUT_PATH.suffix.strip(".")
    mesh = None
    if ext == "ply":
        with open(MESH_INPUT_PATH, "rb") as f:
            mesh = trimesh.load(f, file_type=ext)
    else:
        logger.warning(
            f'Incompatible file extension "{ext}" for mesh file "{MESH_INPUT_PATH}". '
            'It needs to be ".ply".'
        )

    return mesh


def mesh2gdf(MESH_INPUT_PATH: str, set_2d: bool = False) -> GeoDataFrame:
    """Load a mesh from a mesh file given in the ply format and convert it to a
    GeoDataFrame.
    Notice: only the standard ply file format is accepted.

    Parameters:
    ----------
    MESH_INPUT_PATH : PosixPath instance
        A PosixPath object to a terrain mesh file given in the ply format
        on the disk.
    set_2d : bool, default=False
        A trigger to use if triangles have to be stored in 2D only.
        Default=False.

    Returns:
    -------
    gdf : GeoDataFrame instance
        A GeoDataFrame object containing the features from the mesh file.
    """
    mesh = load_mesh(MESH_INPUT_PATH)
    triangle_list = []
    triangles = mesh.triangles
    if set_2d:
        triangles = triangles[:, :, :2]

    for i, triangle in enumerate(triangles):
        triangle_list.append(Polygon(triangle))

    df = pd.DataFrame(triangle_list)
    gdf = GeoDataFrame(df, geometry=0, crs="EPSG:2056")
    gdf.rename_geometry("geom", inplace=True)

    return gdf


def ray_cast(geometry: LineString, mesh: Trimesh) -> LineString:
    """Wrapper function ready to be applied on DataFrame

    Parameters:
    ----------
    geometry : LineString instance
        A shapely LineString object
    mesh : Trimesh instance
        A terrain mesh.

    Returns:
    -------
    retval : LineString instance
        A 3D LineString object made up of the constituent points
        of the geometry that have been projected onto the mesh.
    """
    if not isinstance(geometry, LineString):
        return None

    points = np.array(geometry.coords)

    return ray_cast_array(points, mesh)


def ray_cast_array(points: np.array, mesh: Trimesh) -> LineString:
    """Cast a ray from a point to the mesh.

    Parameters:
    ----------
    points : np.array <nx2>
        A <nx2> numpy array of 2D points to cast onto the terrain mesh.
    mesh : Trimesh instance
        A terrain mesh.

    Returns:
    -------
    retval : LineString instance
        A 3D LineString object composed of the given points that have been
        projected on the mesh.
    """
    up_vectors = np.zeros_like(points)
    up_vectors[:, -1] = 1
    logger.debug("Ray casting points onto the mesh...")
    intersections, ray_indices, face_indices = mesh.ray.intersects_location(
        ray_origins=points,
        ray_directions=up_vectors,
        multiple_hits=False,
    )
    logger.debug(f"Intersections shape: {intersections.shape[0]}.")
    retval = LineString(points)
    # If there are at least two points, we can build a 3D line
    if intersections.shape[0] > 1:
        retval = LineString(intersections[np.argsort(ray_indices)])
        logger.debug("Ray casting points onto the mesh done successfully!")
    else:
        logger.warning(f"Oops! Some points are not on the mesh:\n{points}")

    return retval


# %%
def run():
    """Run current script"""
    logger.info(f'Script "{__file__}" launched...')
    for directory in directories:
        logger.info(f"Exploring project {directory=}...")
        TEMP_DIR = Path(directory, "TEMP")
        Path(TEMP_DIR).mkdir(parents=True, exist_ok=True)
        geojson_file = Path(directory, "INPUT", "TRACE", TRACE_FILENAME)
        check_file(geojson_file)  # exit(1) on error
        logger.info(f'Processing "{geojson_file}"...')
        gdf_pipe = load_geojson(geojson_file)
        logger.debug(
            f"The unique network elements types are: {np.unique(np.array(gdf_pipe.geometry.type))}"
        )

        bbox = compute_bbox(gdf_pipe)
        bounds = extract_bbox_bounds(bbox)
        params = {
            "format": "image/tiff; application=geotiff; profile=cloud-optimized",  # spaces are important here!
            "resolution": 0.5,
            "srid": 2056,
            "state": "current",
        }
        params.update(bounds)
        if DOWNLOAD_TILE:
            logger.warning(
                "Downloading tiles from online resources, this may take a while "
                "and it can be limited or blocked in any way by the API. "
                "Please make sure you accept the condition of the online ressource "
                f"when using {DOWNLOAD_TILE=}."
            )
            fetch_url = build_download_url(params)
            download_swisstiles(fetch_url, TEMP_DIR)
        else:
            logger.info(
                "Tiles will NOT be downloaded from online resource because you "
                f"set the flag {DOWNLOAD_TILE=}."
            )

        dem_filenames = [
            elem
            for elem in Path(TEMP_DIR).glob("swissalti3d*.tif")
            if "clipped" not in elem.name
        ]

        triangulate(
            dem_filenames,
            max_error=TRIANGULATION_MAX_ERR,
            output_format="ply",
        )

        MESH_INPUT_PATH = next(
            Path(TEMP_DIR).glob(
                f"swissalti3d*delatin_err{str(TRIANGULATION_MAX_ERR).replace('.', '')}.ply"
            ),
            None,
        )

        if CUSTOM_MESH:
            logger.debug(f"Using custom terrain mesh: {CUSTOM_MESH=}.")
            MESH_INPUT_PATH = next(Path(directory, "INPUT", "MESH").glob("*.ply"), None)
            logger.info(
                f"Custom terrain mesh file found: {MESH_INPUT_PATH.as_posix()}."
            )

        if not MESH_INPUT_PATH:
            logger.error(f'Invalid terrain mesh file: "{MESH_INPUT_PATH}".')

        check_file(MESH_INPUT_PATH)  # exit(1) on error

        gdf_triangle = mesh2gdf(MESH_INPUT_PATH, set_2d=True)
        gdf_pipe_overlay = gdf_pipe.overlay(
            GeoDataFrame(geometry=gdf_triangle.boundary),
            how="difference",
        )
        gdf_pipe_overlay["geometry"] = gdf_pipe_overlay.geometry.apply(line_merge)
        unique_geoms = np.unique(np.array(gdf_pipe_overlay.geom_type))
        logger.debug(f"Geometry type(s) of the new pipe overlay df: {unique_geoms}.")

        if MESH_INPUT_PATH.is_file():
            terrain_mesh = load_mesh(MESH_INPUT_PATH)
            terrain_mesh.apply_translation(np.array([0, 0, VERTEX_VERTICAL_OFFSET]))
            if len(np.unique(np.array(gdf_pipe_overlay.geometry.type))) > 1:
                logger.debug(
                    "The type of the network elements is not unique. Trying to explode gdf..."
                )
                gdf_pipe_overlay = gdf_pipe_overlay.explode(ignore_index=True)

            gdf_pipe_overlay["geometry"] = gdf_pipe_overlay.geometry.force_3d(z=0)
            gdf_pipe_overlay["geometry"] = gdf_pipe_overlay["geometry"].apply(
                ray_cast, args=(terrain_mesh,)
            )
            gdf_pipe_overlay.columns = gdf_pipe_overlay.columns.str.replace(
                "[-]", "_", regex=True
            )
            geojson_3d_file = Path(
                TEMP_DIR, geojson_file.stem + "_3D" + geojson_file.suffix
            )
            gdf_pipe_overlay.to_file(geojson_3d_file)
            logger.info(
                f'GeoDataFrame written to file "{geojson_3d_file}" successfully.'
            )
    logger.info(f'Script "{__file__}" run successfully!')


# %%

if __name__ == "__main__":
    run()
# %%
