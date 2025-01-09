ARG DEBIAN_FRONTEND=noninteractive


FROM python:3.11-slim-bookworm AS build
# The latest version of Blender only supports the Python 3.11.x family as of 2025-01-01

ARG DEBIAN_FRONTEND

LABEL org.opencontainers.image.authors="Nicolas Blanc @ HEIG-VD"
LABEL org.opencontainers.image.title="gis_to_ifc"
LABEL org.opencontainers.image.description="Convert GIS data as GeoJSON to IFC 4x3 (BIM)."
LABEL org.opencontainers.image.source="https://github.com/nicolas-heigvd/gis_to_ifc"
LABEL org.opencontainers.image.url="https://github.com/nicolas-heigvd/gis_to_ifc"
LABEL org.opencontainers.image.documentation="https://github.com/nicolas-heigvd/gis_to_ifc/blob/main/README.md"
LABEL org.opencontainers.image.licenses="GPL-3.0-only"
LABEL org.opencontainers.image.vendor="HES-SO/HEIG-VD"
LABEL org.opencontainers.image.created="2025-02-05T20:00:00Z"
LABEL license-url="https://www.gnu.org/licenses/gpl-3.0.html"
LABEL notice-file="https://github.com/nicolas-heigvd/gis_to_ifc/NOTICE.md"


# Create a new group and a new user with your UID/GID
RUN groupadd -g 1000 sepm
RUN useradd -u 1000 -g 1000 -m sepm

WORKDIR /app

RUN apt-get -yq update \
  && apt-get install -yq --fix-missing --no-install-recommends \
  build-essential \
  libgdal-dev \
  libx11-6 \
  libxrender1 \
  libxxf86vm1 \
  libxfixes3 \
  libxi6 \
  libxkbcommon-x11-0 \
  libsm6 \
  libgl1 \
  curl \
  unzip \
  git \
  jq \
  && apt-get -yq autoremove --purge \
  && apt-get -yq autoclean \
  && ln -fs /usr/share/zoneinfo/Europe/Zurich /etc/localtime \
  && dpkg-reconfigure -f noninteractive tzdata

COPY requirements/*.in ./requirements/
COPY src /app/

RUN python -m pip install --trusted-host pypi.python.org --upgrade pip \
  && pip install --trusted-host pypi.python.org --upgrade \
  setuptools \
  wheel \
  pip-tools \
  && for req_file in /app/requirements/*.in; do \
       pip-compile "${req_file}" 2> /dev/null; \
     done \
  && pip install --trusted-host pypi.python.org -r requirements/common.txt \
  && BASE_URL="https://api.github.com/repos/IfcOpenShell/IfcOpenShell/releases/latest" \
  && RELEASE_DATA=$(curl -s "${BASE_URL}") \
  && ASSET_URL=$(echo ${RELEASE_DATA} | jq -r '.assets[] | select(.name | contains("py311") and contains("alpha") and contains("linux-x64")).browser_download_url') \
  && LATEST_FILE=$(basename "${ASSET_URL}") \
  && cd /tmp \
  && curl -L -o "${LATEST_FILE}" "${ASSET_URL}" \
  && if [ ! -f "${LATEST_FILE}" ]; then \
      echo "Download failed!"; \
      exit 1; \
  fi \
  && echo "${LATEST_FILE} downloaded successfully!" \
  && unzip ${LATEST_FILE} \
  && cd bonsai/wheels \
  && pip install ifcopenshell-*_x86_64.whl \
  && apt-get -yq autoremove --purge build-essential wget unzip git \
  && apt-get -yq autoclean \
  && echo "Image succcessfully build!"


# Stage 2: Production Stage
FROM build AS prod
# The latest version of Blender only supports the Python 3.11.x family as of 2025-01-01

WORKDIR /app

# Copy the production requirements
COPY --from=build /app/requirements/prod.txt ./requirements/
RUN pip install --trusted-host pypi.python.org -r requirements/prod.txt

# Switch to this user
USER sepm
ENTRYPOINT ["python3"]
CMD ["main.py"]


# Stage 3: Development Stage
FROM build AS dev

WORKDIR /app

# Copy the development requirements
COPY --from=build /app/requirements/dev.txt ./requirements/
RUN pip install --trusted-host pypi.python.org -r requirements/dev.txt

# Switch to this user
USER sepm
ENTRYPOINT ["python3"]
