
ARG PYTHON_IMAGE=python:3.12.3-slim-bookworm

FROM $PYTHON_IMAGE AS base

ARG DEBIAN_FRONTEND=noninteractive

# Set locale
RUN apt-get update && \
    apt-get -y upgrade && \
    apt-get -y install --no-install-recommends locales && \
    sed -i -e 's/# en_US.UTF-8 UTF-8/en_US.UTF-8 UTF-8/' /etc/locale.gen && \
    locale-gen
ENV LANG=en_US.UTF-8
ENV LANGUAGE=§en_US:en
ENV LC_ALL=en_US.UTF-8

RUN apt-get update && \
    apt-get -y install --no-install-recommends apt-utils ca-certificates syslog-ng && \
    pip install --upgrade pip

# ==============================================================================
# Requirements stage - generate requirements.txt
# ==============================================================================
FROM base AS requirements

WORKDIR /tmp

RUN apt-get update && \
    apt-get -y install --no-install-recommends pipx && \
    pipx ensurepath

RUN pipx install poetry && \
    pipx inject poetry poetry-plugin-export

ENV PATH="/root/.local/bin:${PATH}"

COPY ./pyproject.toml ./poetry.lock* /tmp/

RUN poetry export -f requirements.txt --output requirements.txt --without-hashes

# ==============================================================================
# builder stage - copy requirements.txt from requirements and install dependencies
# ==============================================================================
FROM base AS builder

ARG USERNAME=serviceuser
ARG USER_UID=1000
ARG USER_GID=$USER_UID
ARG LOG_DIR=/var/log/polebot

RUN apt-get update && \
    apt-get -y install --no-install-recommends sudo procps

RUN mkdir -p ${LOG_DIR}

RUN addgroup --gid $USER_GID $USERNAME && adduser --uid $USER_UID --gid $USER_GID $USERNAME
RUN chown -R $USER_UID:$USER_GID ${LOG_DIR}

WORKDIR /app

COPY --from=requirements /tmp/requirements.txt /app/requirements.txt

RUN pip install --no-cache-dir --upgrade -r /app/requirements.txt \
  && pip install --target /tmp debugpy

# Set environment variables to ensure that Python output is sent straight to the terminal
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

COPY ./src/ /app/

# ==============================================================================
# debug stage - install debugpy
# ==============================================================================
FROM builder AS debug

ARG USERNAME=serviceuser

USER $USERNAME

CMD ["python", "-m", "polebot"]

# ==============================================================================
# production stage - run the application
# ==============================================================================
FROM builder AS production

RUN pip uninstall debugpy

ARG USERNAME=serviceuser

USER $USERNAME

CMD ["python", "-m", "polebot"]
