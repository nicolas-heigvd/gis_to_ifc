#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Nov 7 10:24:00 2024
# Copyright (C) 2024-present {nicolas.blanc} @ HEIG-VD
# This file is licensed under the GPL-3.0-only. See LICENSE file for details.
# Third-party libraries and their licenses are listed in the NOTICE.md file.
"""

# %%
import os
from pathlib import Path, PosixPath

import geopandas as gpd
import ifcopenshell
import ifcopenshell.api.aggregate
import ifcopenshell.api.context
import ifcopenshell.api.geometry
import ifcopenshell.api.georeference
import ifcopenshell.api.project
import ifcopenshell.api.root
import ifcopenshell.api.spatial
import ifcopenshell.api.type
import ifcopenshell.api.unit
import ifcopenshell.util.pset
import numpy as np
from geopandas import GeoDataFrame

from error_handling import check_file
from logging_config import logger

logger.debug(f"IfcOpenShell version: {ifcopenshell.__version__}")

# %%
# Triggers and constants
BASEDIR = "/data"
LOGLEVEL = os.getenv("LOGLEVEL", "INFO")
TRACE_FILENAME = os.getenv("TRACE_FILENAME", None)
IFC_SCHEMA_IDENTIFIER = os.getenv("IFC_SCHEMA_IDENTIFIER", "IFC4X3_ADD2")
OBJECT_NAME = os.getenv("OBJECT_NAME", "NIS_Nummer")

AUTHOR_NAME = os.getenv("AUTHOR_NAME", "")
AUTHOR_EMAIL = os.getenv("AUTHOR_EMAIL", "")
ORGANIZATION_NAME = os.getenv("ORGANIZATION_NAME", "")
ORGANIZATION_EMAIL = os.getenv("ORGANIZATION_EMAIL", "")
AUTHORIZATION_NAME = os.getenv("AUTHORIZATION_NAME", "")

SHIFT_LV95_ORIGIN = os.getenv("SHIFT_LV95_ORIGIN", "false").lower() == "true"

if SHIFT_LV95_ORIGIN:
    origin_shift = np.array([-2600000, -1200000, 0])

# Parsing directories
directories = Path(BASEDIR).glob("*/")
# %%


def load_geojson(geojson_file: PosixPath) -> GeoDataFrame:
    """Load a GeoJSON file in a GeoDataFrame

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

    logger.debug(f'File "{geojson_file}" loaded successfully!')

    return gdf


def build_ifc(
    schema_identifier: str,
    gdf_3d: GeoDataFrame,
    ifc_site_name: str,
    ifc_filename: str,
    ifc_project_name: str = "MyIFCProject",
) -> ifcopenshell.file:
    """Build an IFC file out of a GeoDataFrame containine network lines.

    Parameters:
    ----------
    schema_identifier : str
        A valid schema_identifieraccording to the ifcopenshell documentation:
        https://docs.ifcopenshell.org/autoapi/ifcopenshell/index.html
    gdf_3d : str
        A GeoDataFrame object containing 3D line features.
    ifc_site_name : str
        The name of the IfcSite.
    ifc_filename : str
        The name of the IFC file that will be used to save the results on the disk.
    ifc_project_name : str
        The name that will be used for the IfcProject.

    Returns:
    -------
    model : ifcopenshell.file instance
        An ifcopenshell.file object containing the features from the 3D GeoJSON file.
    """

    # Start a new model.
    model = ifcopenshell.api.project.create_file(version=schema_identifier)
    model.wrapped_data.header.file_name.name = f"{str(ifc_filename)}"
    if AUTHOR_NAME and AUTHOR_EMAIL:
        model.wrapped_data.header.file_name.author = (
            AUTHOR_NAME,
            AUTHOR_EMAIL,
        )
    if ORGANIZATION_NAME and ORGANIZATION_EMAIL:
        model.wrapped_data.header.file_name.organization = (
            ORGANIZATION_NAME,
            ORGANIZATION_EMAIL,
        )
    if AUTHORIZATION_NAME:
        model.wrapped_data.header.file_name.authorization = AUTHORIZATION_NAME

    # A project is needed before units can be assigned.
    project = ifcopenshell.api.root.create_entity(
        file=model,
        ifc_class="IfcProject",
        name=ifc_project_name,
    )

    # Set coordinates units to meters.
    length = ifcopenshell.api.unit.add_si_unit(file=model, unit_type="LENGTHUNIT")
    area = ifcopenshell.api.unit.add_si_unit(file=model, unit_type="AREAUNIT")
    volume = ifcopenshell.api.unit.add_si_unit(file=model, unit_type="VOLUMEUNIT")
    ifcopenshell.api.unit.assign_unit(file=model, units=[length, area, volume])

    # If we plan to store 3D geometry in our IFC model, we have to setup a "Model" context.
    model3d = ifcopenshell.api.context.add_context(file=model, context_type="Model")

    # Add georeferencing AFTER add_context because it needs a context !
    ifcopenshell.api.georeference.add_georeferencing(
        file=model,
    )
    barycentre = gdf_3d.get_coordinates(include_z=True).mean().round().to_numpy()
    ifcopenshell.api.georeference.edit_georeferencing(
        file=model,
        projected_crs={
            # The name shall be taken from the list recognized by the European Petroleum Survey Group EPSG.
            # It should then be qualified by the EPSG namespace, for example as 'EPSG:5555'.
            "Name": "EPSG:2056",
            "Description": "CH1903+/LV95",  # Informal description of this coordinate reference system.
            "GeodeticDatum": "CH1903+",  # Name by which this datum is identified.
            "VerticalDatum": "LHN95 height",  # Name by which the vertical datum is identified.
        },
        coordinate_operation={
            "Eastings": barycentre[0],  # The architect nominates a false origin
            "Northings": barycentre[1],  # The architect nominates a false origin
            "OrthogonalHeight": barycentre[2],  # The architect nominates a false origin
            # Note: this is the angle difference between Project North
            # and Grid North. Remember: True North should never be used!
            "XAxisAbscissa": 0,  # The architect nominates a project north
            "XAxisOrdinate": 0,  # The architect nominates a project north
            "Scale": 1,  # Ask your surveyor for your site's average combined scale factor!
        },
    )

    body = ifcopenshell.api.context.add_context(
        file=model,
        context_type="Model",
        context_identifier="Body",
        target_view="MODEL_VIEW",
        parent=model3d,
    )

    # Creating a site.
    site = ifcopenshell.api.root.create_entity(
        file=model,
        ifc_class="IfcSite",
        name=ifc_site_name,
    )

    # Since the site is our top level location, assign it to the project
    # Then place sub elements on the site, and subsub element in the sub element
    ifcopenshell.api.aggregate.assign_object(
        file=model,
        relating_object=project,
        products=[site],
    )

    # Let's imagine we have a new type of an IFC Class element.
    pipe_segment_type = ifcopenshell.api.root.create_entity(
        file=model,
        ifc_class="IfcPipeSegmentType",
        name="NIS_pipe_segment_type",
    )

    builder = ifcopenshell.util.shape_builder.ShapeBuilder(ifc_file=model)
    attributes = gdf_3d.columns.drop("geometry")
    column_idx = gdf_3d.columns.get_loc(OBJECT_NAME)
    # Iterate over single features
    for row in gdf_3d.itertuples():
        path = np.array(row.geometry.coords)
        if SHIFT_LV95_ORIGIN:
            path += -1 * np.array(barycentre)
        path = np.round(path, 6).tolist()
        if len(path) == 0:
            logger.info(f'Whoops, len(path) is null: "{path}"; continuing...')
            continue

        curve = builder.polyline(path)
        swept_curve = builder.create_swept_disk_solid(curve, 0.4)

        # Create a carrier segment.
        # Our carrier segment currently has no object placement or representations.
        pipe_segment = ifcopenshell.api.root.create_entity(
            file=model,
            ifc_class="IfcPipeSegment",
            predefined_type="NIS_pipe_segment_type",
            # Set object main main from constant (env var)
            name=f"{str(row[column_idx + 1])}",
        )

        pipe_segment_pset = ifcopenshell.api.pset.add_pset(
            file=model,
            product=pipe_segment,
            name="NIS_PipeSegmentCommon",
        )
        properties = dict(zip(attributes, list(row)[1:-1]))  # remove index and geom
        ifcopenshell.api.pset.edit_pset(
            file=model,
            pset=pipe_segment_pset,
            properties=properties,
        )

        # Assign the pipe_segment to the pipe_segment_type.
        # If the pipe_segment_type had a representation,
        # the furniture occurrence will also now have the exact same representation.
        # This is highly efficient as you don't need to define the representation
        # for every occurrence.
        ifcopenshell.api.type.assign_type(
            file=model,
            related_objects=[pipe_segment],
            relating_type=pipe_segment_type,
        )

        # The pipe_segment is in the site
        # https://docs.ifcopenshell.org/autoapi/ifcopenshell/api/spatial/assign_container/index.html
        ifcopenshell.api.spatial.assign_container(
            file=model,
            relating_structure=site,
            products=[pipe_segment],
        )

        # Set our carrier segment's Object Placement using our matrix.
        # `is_si=True` states that we are using SI units instead of project units.
        if True:
            matrix = np.eye(4)
            if SHIFT_LV95_ORIGIN and False:
                matrix[:, 3][:3] -= origin_shift

            # IfcLocalPlacement
            ifcopenshell.api.geometry.edit_object_placement(
                file=model,
                product=pipe_segment,
                matrix=matrix,
                is_si=True,
            )

        representation = builder.get_representation(body, swept_curve)

        # Assign our new body representation back to our element
        ifcopenshell.api.geometry.assign_representation(
            file=model,
            product=pipe_segment,
            representation=representation,
        )

    return model


def convert_geojson_to_ifc(
    schema_identifier: str,
    geojson_3d_file: str,
    ifc_filename: str,
    ifc_project_name: str = "MyIFCProject",
) -> bool:
    """Convert a GeoJSON file containing linestrings to an IFC file.

    Parameters:
    ----------
    schema_identifier : str
        A valid schema_identifieraccording to the ifcopenshell documentation:
        https://docs.ifcopenshell.org/autoapi/ifcopenshell/index.html
    geojson_3d_file : str
        A path to a GeoJSON file on disk containg 3D lines.
    ifc_filename : str
        The name of the IFC file that will be used to save the results on the disk.
    ifc_project_name : str
        The name that will be used for the IfcProject.

    Returns:
    -------
    Nothing; this is a helper function.
    """
    ifc_site_name = str(Path(geojson_3d_file).parts[-2])
    gdf_3d = load_geojson(geojson_3d_file)
    model = build_ifc(
        schema_identifier,
        gdf_3d,
        ifc_site_name,
        ifc_filename,
        ifc_project_name,
    )
    model.write(ifc_filename)
    logger.info(f'Model correctly dumped to file "{ifc_filename}"')


def run():
    """Run current script"""
    logger.info(f'Script "{__file__}" launched...')
    for directory in directories:
        IFC_DIR = Path(directory, "OUTPUT", "IFC")
        geojson_3d_file = Path(
            directory,
            "TEMP",
            Path(TRACE_FILENAME).stem + "_3D" + Path(TRACE_FILENAME).suffix,
        )
        check_file(geojson_3d_file)  # exit(1) on error
        if geojson_3d_file.is_file():
            logger.info(
                f'Processing file: "{geojson_3d_file}" with schema: {IFC_SCHEMA_IDENTIFIER}'
            )
            ifc_filename = Path(
                IFC_DIR, geojson_3d_file.stem + str(IFC_SCHEMA_IDENTIFIER) + ".ifc"
            )
            convert_geojson_to_ifc(
                IFC_SCHEMA_IDENTIFIER,
                geojson_3d_file,
                ifc_filename,
                "SEPM",
            )
        else:
            logger.error(f'GeoJSON 3D file "{geojson_3d_file}" doesn\'t exist.')

    logger.info(f'Script "{__file__}" run successfully!')


# %%
if __name__ == "__main__":
    run()
# %%
