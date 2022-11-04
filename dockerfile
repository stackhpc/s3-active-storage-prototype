# syntax=docker/dockerfile:1
FROM python:3.11

# WORKDIR /root
# RUN git clone https://github.com/stackhpc/s3-active-storage

COPY ./active_storage /s3-active-storage/active_storage
COPY ./setup.* /s3-active-storage/
COPY ./pyproject.toml /s3-active-storage/

CMD bash

# WORKDIR /root/s3-active-storage
# RUN pip install .
# RUN pip install uvicorn

# EXPOSE 8000
# CMD ["uvicorn", "--host", "0.0.0.0", "active_storage.server:app"]
#Replace CMD with this one once 'simpler-implementation' branch is merged on github:
# CMD ["uvicorn", "--host", "0.0.0.0", "active_storage.app:app"]
