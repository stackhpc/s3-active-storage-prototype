# syntax=docker/dockerfile:1

FROM python:3.11

RUN git clone -b deployment https://github.com/stackhpc/s3-active-storage/

WORKDIR /s3-active-storage
RUN pip install . 
RUN pip install uvicorn

EXPOSE 80
CMD ["uvicorn", "--host", "0.0.0.0", "--port", "80", "active_storage.app:app"]
