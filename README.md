Django Minio Connector
====================
Django storage backend to use [Minio Server](https://github.com/minio/minio) as file storage. It is wrapper over "minio" library.

Installation
-----------
At first, you need to have working minio server. How to do that you can found at [Minio Quickstart Guide](http://docs.minio.io/docs/minio-quickstart-guide).

Install Django Minio Storage from pip:
```
pip install django-minio-connector
```

Add configuration of Minio storage to your projects settings file:
```
STORAGES = {
    "staticfiles": {
        "BACKEND": 'django_minio_connector.storage.MinIOStorage',
        "OPTIONS": {
            "MINIO_ENDPOINT": 'your_minio_server_address',
            "MINIO_ROOT_USER": "your_minio_server_access_key",
            "MINIO_ROOT_PASSWORD": "your_minio_server_secret_key",
            'MINIO_USE_HTTPS': False,
            'MINIO_BUCKET_NAME': 'static-bucket-name',
            'MINIO_BUCKET_POLICY': {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": {"AWS": "*"},
                        "Action": [
                            "s3:GetBucketLocation",
                            "s3:ListBucket"
                        ],
                        "Resource": f"arn:aws:s3:::static"
                    },
                    {
                        "Effect": "Allow",
                        "Principal": {"AWS": "*"},
                        "Action": "s3:GetObject",
                        "Resource": f"arn:aws:s3:::static/*"
                    }
                ]
            },
            'MINIO_PRESIGNED_URL': False,
        },
    },
    'default': {
        'BACKEND': 'django_minio_connector.storage.MinIOStorage',
        "OPTIONS": {
            "MINIO_ENDPOINT": 'your_minio_server_address',
            "MINIO_ROOT_USER": "your_minio_server_access_key",
            "MINIO_ROOT_PASSWORD": "your_minio_server_secret_key",
            'MINIO_USE_HTTPS': False,
            'MINIO_BUCKET_NAME': 'media-bucket-name',
        },

    }
}
```
For using MinIO server in development stage could install it by Docker [MinIO Quickstart Guide](https://hub.docker.com/r/minio/minio)

Demo MinIO server and it's credentials can be found at [MinIO console](https://min.io/docs/minio/linux/administration/minio-console.html#logging-in).

MinIO library documentation [Python Client API Reference](https://min.io/docs/minio/linux/developers/python/API.html)

More information about file storages can be found at [Django Docs](https://docs.djangoproject.com/en/5.1/ref/files/storage/).

Description of STORAGE settings [Settings](https://docs.djangoproject.com/en/5.1/ref/settings/#storages)

Currently tested only at Django 5.1. Does not work on earlier versions because the DEFAULT_FILE_STORAGE and STATICFILES_STORAGE settings is removed.