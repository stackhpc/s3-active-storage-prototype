from pydantic import Field, HttpUrl

from configomatic import Configuration


class Settings(Configuration):
    """
    Model for s3-active-storage configuration.
    """
    class Config:
        default_path = "/etc/s3-active-storage/config.yaml"
        path_env_var = "S3_ACTIVE_STORAGE_CONFIG"
        env_prefix = "S3_ACTIVE_STORAGE"

    #: The S3 endpoint where the objects we are operating on live
    s3_endpoint: HttpUrl = "http://localhost:9000"


settings = Settings()
