# syntax=docker/dockerfile:1

FROM python:3.11

# COPY ./active_storage /s3-active-storage/active_storage
# COPY ./setup.* /s3-active-storage/
# COPY ./pyproject.toml /s3-active-storage/
# COPY ./README.md /s3-active-storage/
RUN git clone -b deployment https://github.com/stackhpc/s3-active-storage/

WORKDIR /s3-active-storage
RUN pip install -e .
RUN pip install uvicorn

EXPOSE 8000
CMD ["uvicorn", "--host", "0.0.0.0", "active_storage.app:app"]
