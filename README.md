# SEPM ELE to BIM

## Status
![Python Version](https://img.shields.io/badge/Python-3.11.11-blue.svg?logo=python&logoColor=f5f5f5)
[![License: MIT/X Consortium License](https://img.shields.io/github/license/nicolas-heigvd/gis_to_ifc)](./LICENSE)
[![Deploy Docker Image](https://github.com/nicolas-heigvd/gis_to_ifc/actions/workflows/build.yml/badge.svg?branch=main)](https://github.com/nicolas-heigvd/gis_to_ifc/actions/workflows/build.yml)
![Python CI](https://github.com/nicolas-heigvd/gis_to_ifc/actions/workflows/deploy.yml/badge.svg?branch=main)



## Introduction

This repository contains the code of a Python application to convert GIS data given as a GeoJSON file to an IFC file compliant with the IFC 4.3 ADD2 official schema. It's based on the [IfcOpenShell](https://ifcopenshell.org/) Python package.

Each step described here is assumed to be executed from the home project's folder, unless otherwise specified.


## Prerequisites

A machine having Docker engine 27.5.1 with Docker Compose v2.5.0 is needed to run the code.

You can get Docker [here](https://docs.docker.com/get-started/get-docker/).

### Note to Windows users

Please make sure you are using Docker with [WSL2 (Windows Subsystem for Linux)](https://learn.microsoft.com/en-us/windows/wsl/install) to run Linux containers.


## Preparing a file structure on the host for storing input and output data

In order to run the code on your own data, you need a place outside the home project's folder for storing both input and output data.

To do so, a file structure as follow is needed on the host:
```sh
/data
  ├── Project_Site_folder_1/
  │   └── INPUT/
  │       ├── TRACE/
  │       │   └── Strom Einfaches Trasse Achse_3D.geojson
  │       └── MESH/
  │           └── Site1_terrain_mesh.ply (optional)
  ├── Project_Site_folder_2/
  │   └── INPUT/
  │       ├── TRACE/
  │       │   └── Strom Einfaches Trasse Achse_3D.geojson
  │       └── MESH/
  │           └── Site2_terrain_mesh.ply (optional)
  └── Project_Site_folder_3/
      └── INPUT/
          ├── TRACE/
          │   └── Strom Einfaches Trasse Achse_3D.geojson
          └── MESH/
              └── Site3_terrain_mesh.ply (optional)
```

### About custom terrain meshes
You can store custom terrain meshes in the `INPUT/MESH` folder inside each project.  

- If you want to use those meshes, you have to set the environment variable `CUSTOM_MESH=True`.
- If the environment variable `DOWNLOAD_TILE` is also set to `True`, the custom mesh will take precedence.  


## Setting up the environment

For the code to run smoothly, you need to define a few environment variables in a `.env` file.

To this end, copy the `env.sample` file to `.env`: `cp env.sample .env` in the home project's folder and change the variables defined in this `.env` file according to your own environment.

The `.env` file MUST contain the definition of those 8 variables:
| Variable    | Content description |
| ----------- | ------- |
| `ENV` | MUST be set to either `DEV` or `PROD`. However, the code is not ready yet to be deployed in a production server. |
| `LOGLEVEL` | MUST be one of the officially supported [logging levels](https://docs.python.org/3/library/logging.html#logging-levels), for example `DEBUG` or `INFO`. |
| `SHIFT_LV95_ORIGIN` | MUST be set to a valid [Python boolean](https://docs.python.org/3/library/stdtypes.html#boolean-type-bool) which is either `True` or `False`. If set to `False`, the original coordinates will be kept as they are. <br> ⚠️ But great care MUST be taken, because in this case, the resulting IFC file may not be correctly read by some softwares, particularly those with a 32bit architecture. |
| `AUTHOR_NAME` | MUST be the full name of the person creating the output IFC file (the author name will be stored in the IFC file). This is a header element. |
| `AUTHOR_EMAIL` | MUST be the valid e-mail address of the person creating the output IFC file (the author e-mail address will be stored in the IFC file). This is a header element. |
| `ORGANIZATION_NAME` | MUST be the name of the organization or company to which the person creating the output IFC file belongs (the organization's e-mail address will be stored in the IFC file). This is a header element. |
| `ORGANIZATION_EMAIL` | MUST be the e-mail address of the organization or company to which the person creating the output IFC file belongs (the organization's e-mail address will be stored in the IFC file). This is a header element. |
| `AUTHORIZATION_NAME` | MUST be the name of the organization authoring the output IFC file (the organization's name will be stored in the IFC file). This is a header element. |
| `HOST_DATA_DIRECTORY` | MUST be the path to the root of the data folder on the localhost. It may be given as a relative path to the project home directory. |
| `IFC_SCHEMA_IDENTIFIER` | MUST be valid schema_identifier value according to the [ifcopenshell documentation](https://docs.ifcopenshell.org/autoapi/ifcopenshell/index.html). |
| `OBJECT_NAME` | MUST be the name of one of the existing properties of the features found in the GeoJSON file(s). |
| `TRACE_FILENAME` | MUST be the name (string) for the input GeoJSON trace filename. This name MUST be unique acros project folders. |
| `DOWNLOAD_TILE` |  MUST be set to a valid [Python boolean](https://docs.python.org/3/library/stdtypes.html#boolean-type-bool) which is either `True` or `False`. Set to `False` only if you don't want to download the tiles from Internet. This is particularly useful when the tiles are already in the TEMP folder of your projects. |
| `CUSTOM_MESH` | MUST be set to a valid [Python boolean](https://docs.python.org/3/library/stdtypes.html#boolean-type-bool) which is either `True` or `False`. If set to `False`, the mesh will be build from the swisstopo API. <br> ⚠️ In this case the download may take a few minutes, depending on your connection speed. |

Once the `.env` file is correctly set up, you can move on to the next step.


## Test data
There is `./tests/data` folder in the project. It contains some test data that are used to demonstrate the project's feasibility.

This data should normaly build the following IFC 4.3_ADD2 file:

```
ISO-10303-21;
HEADER;
FILE_DESCRIPTION(('ViewDefinition[DesignTransferView]'),'2;1');
FILE_NAME('/data/Test_Project_Site/OUTPUT/IFC/pipe_lv95_3DIFC4X3_ADD2.ifc','2025-02-07T12:27:20+01:00',('Jonh Doe','john.doe@corp.com'),('Corp','contact@corp.com'),'IfcOpenShell 0.8.1-alpha250205','IfcOpenShell 0.8.1-alpha250205','Authorizer');
FILE_SCHEMA(('IFC4X3_ADD2'));
ENDSEC;
DATA;
#1=IFCPROJECT('0X77HvlZT1qxyuQiLXi_RO',$,'SEPM',$,$,$,$,(#10),#5);
#2=IFCSIUNIT(*,.LENGTHUNIT.,$,.METRE.);
#3=IFCSIUNIT(*,.AREAUNIT.,$,.SQUARE_METRE.);
#4=IFCSIUNIT(*,.VOLUMEUNIT.,$,.CUBIC_METRE.);
#5=IFCUNITASSIGNMENT((#4,#2,#3));
#6=IFCCARTESIANPOINT((0.,0.,0.));
#7=IFCDIRECTION((0.,0.,1.));
#8=IFCDIRECTION((1.,0.,0.));
#9=IFCAXIS2PLACEMENT3D(#6,#7,#8);
#10=IFCGEOMETRICREPRESENTATIONCONTEXT($,'Model',3,1.E-05,#9,$);
#11=IFCPROJECTEDCRS('EPSG:2056','CH1903+/LV95','CH1903+','LHN95 height',$,$,$);
#12=IFCMAPCONVERSION(#10,#11,2684146.,1247953.,469.,0.,0.,1.);
#13=IFCGEOMETRICREPRESENTATIONSUBCONTEXT('Body','Model',*,*,*,*,#10,$,.MODEL_VIEW.,$);
#14=IFCSITE('0BDGp0AbzCChZLQaIP2FMh',$,'TEMP',$,$,$,$,$,$,$,$,$,$,$);
#15=IFCRELAGGREGATES('0Yyqlybsf5$hyt4O3b9elp',$,$,$,#1,(#14));
#16=IFCPIPESEGMENTTYPE('3Jss_1lGb4cPDCnZmj6kh7',$,'NIS_pipe_segment_type',$,$,$,$,$,$,.NOTDEFINED.);
#17=IFCCARTESIANPOINTLIST3D(((-0.479,-43.28,-4.996603),(-16.282,-16.017,-2.943391),(-17.785,-6.42,-1.869175),(-16.685,0.679,-0.883098),(-11.392502,6.824456,0.34625),(-11.392502,6.824456,0.34625),(-11.082,7.185,0.394353),(-3.585,11.083,1.136873),(4.119,12.182,1.646593),(11.722,11.879,2.028708),(29.619,7.285,2.589991),(47.219,2.387,3.108823)),$);
#18=IFCINDEXEDPOLYCURVE(#17,$,$);
#19=IFCSWEPTDISKSOLID(#18,0.4,$,$,$);
#20=IFCPIPESEGMENT('12IMTWgIv6peHqmp2iDagA',$,'TAB123456',$,'NIS_pipe_segment_type',#34,#36,$,.USERDEFINED.);
#21=IFCPROPERTYSET('0wZH_JCeT1dfLtWKr2524o',$,'NIS_PipeSegmentCommon',$,(#23,#24,#25,#26,#27));
#22=IFCRELDEFINESBYPROPERTIES('3RMITm4H5EIgc9a72dyKVT',$,$,$,(#20),#21);
#23=IFCPROPERTYSINGLEVALUE('OID',$,IFCLABEL('Z-9999'),$);
#24=IFCPROPERTYSINGLEVALUE('Width',$,IFCREAL(80.),$);
#25=IFCPROPERTYSINGLEVALUE('Precision',$,IFCLABEL('Genau'),$);
#26=IFCPROPERTYSINGLEVALUE('NIS_Nummer',$,IFCLABEL('TAB123456'),$);
#27=IFCPROPERTYSINGLEVALUE('District',$,IFCLABEL('Zurich'),$);
#28=IFCRELDEFINESBYTYPE('3dBwzEgZr9SOIWJTE6jCrR',$,$,$,(#20),#16);
#29=IFCRELCONTAINEDINSPATIALSTRUCTURE('3_aHv8Sir4SPMXC6lG9VGC',$,$,$,(#20),#14);
#30=IFCCARTESIANPOINT((0.,0.,0.));
#31=IFCDIRECTION((0.,0.,1.));
#32=IFCDIRECTION((1.,0.,0.));
#33=IFCAXIS2PLACEMENT3D(#30,#31,#32);
#34=IFCLOCALPLACEMENT($,#33);
#35=IFCSHAPEREPRESENTATION(#13,'Body','SolidModel',(#19));
#36=IFCPRODUCTDEFINITIONSHAPE($,$,(#35));
ENDSEC;
END-ISO-10303-21;
```

which can then be opened with 3D manipulation software such as [Blender](https://www.blender.org/) using the [Bonsai add-on](https://extensions.blender.org/add-ons/bonsai/):

![Screenshot from 2025-02-07 12-31-23](https://github.com/user-attachments/assets/232ded8b-8d38-4560-9831-0fcb4ce0d280)

Please notice that all object coordinates in the IFC file are roughly reduced to the gravity center of all points constituting the geometries.


## Running the container

Finally, run the docker container using:
```sh
docker compose up -d
```

It can take a little while to fetch the data and build the container the very first time you execute this command, don't worry and grab a coffee ☕! The resulting image is roughly 2 GB.

After running the script, new folders will have appeared:
```sh
/data
  ├── Project_Site_folder_1/
  │   ├── INPUT/
  │   │   ├── TRACE/
  │   │   │   └── Strom Einfaches Trasse Achse_3D.geojson
  │   │   └── MESH/
  │   │       └── Site1_terrain_mesh.ply (optional)
  │   ├── TEMP/
  │   └── OUTPUT/
  │       └── IFC/
  ├── Project_Site_folder_2/
  │   ├── INPUT/
  │   │   ├── TRACE/
  │   │   │   └── Strom Einfaches Trasse Achse_3D.geojson
  │   │   └── MESH/
  │   │       └── Site2_terrain_mesh.ply (optional)
  │   ├── TEMP/
  │   └── OUTPUT/
  │       └── IFC/
  └── Project_Site_folder_3/
      ├── INPUT/
      │   ├── TRACE/
      │   │   └── Strom Einfaches Trasse Achse_3D.geojson
      │   └── MESH/
      │       └── Site3_terrain_mesh.ply (optional)
      ├── TEMP/
      └── OUTPUT/
          └── IFC/
```

The `TEMP` folder inside each project's folder will containg temporary data. It can safely be deleted.

The `OUTPUT/IFC` folders in your project directories is were you can find the resulting IFC files.


### Extras

If need be you can check the logs with:
```sh
docker compose logs -f app
```

To kill the container:
```sh
docker compose down
```


## License

This package is released under the [GNU General Public License version 3, 29 June 2007](https://www.gnu.org/licenses/gpl-3.0.html#license-text)

SPDX short identifier: [GPL-3.0-only](https://spdx.org/licenses/GPL-3.0-only.html)

[OSI link](https://opensource.org/license/gpl-3-0).


## Third Party Licenses

This package relies on many third party libraries. Please, carefully read the [NOTICE.md](./NOTICE.md) file.


## Going futher

Feel free to have a look at the [Wiki](../../wiki) if you want to go further.
