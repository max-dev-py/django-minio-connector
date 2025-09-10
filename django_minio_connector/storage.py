# django_minio_connector/storage.py

import json
import mimetypes
import os
from datetime import timedelta
from random import randrange

from django.conf import settings
from django.core.files import File
from django.core.files.storage import Storage
from django.utils import timezone
from minio import Minio


class MinioStorageFile(File):
    """
    A helper class for MinIO files.
    """

    def close(self):
        """
        Closes the file and releases the connection to Minio.
        """
        super().close()
        self.file.release_conn()


# A global cache for MinIO client instances
_minio_clients = {}


class MinIOStorage(Storage):
    """
    A Django storage backend for MinIO.
    """

    def __init__(self, **kwargs):
        self.endpoint = kwargs['MINIO_ENDPOINT']
        self.access_key = kwargs['MINIO_ROOT_USER']
        self.secret_key = kwargs['MINIO_ROOT_PASSWORD']
        self.secure = kwargs.get('MINIO_USE_HTTPS', True)
        self.bucket_name = kwargs['MINIO_BUCKET_NAME']

        self.session_token = kwargs.get('SESSION_TOKEN', None)
        self.region = kwargs.get('REGION', None)
        self.http_client = kwargs.get('HTTP_CLIENT', None)
        self.credentials = kwargs.get('CREDENTIALS', None)
        self.cert_check = kwargs.get('CERT_CHECK', True)

        self.bucket_policy = kwargs.get('MINIO_BUCKET_POLICY', None)
        self.pre_signed_url = kwargs.get('MINIO_PRESIGNED_URL', True)
        self.overwrite_files = kwargs.get('MINIO_OVERWRITE_FILES', False)
        self.presigned_expiration = kwargs.get('MINIO_PRESIGNED_EXPIRATION', timedelta(days=1))

        self.minio_client = self._get_minio_client()
        self._stat_cache = {}

        if not self.minio_client.bucket_exists(self.bucket_name):
            self.minio_client.make_bucket(self.bucket_name)

        if self.bucket_policy:
            self.minio_client.set_bucket_policy(self.bucket_name, json.dumps(self.bucket_policy))

    def _get_minio_client(self):
        """
        Retrieves a MinIO client from the global cache or creates a new one if not available.
        """
        # Create a cache key based on the client configuration
        cache_key = (
            self.endpoint,
            self.access_key,
            self.secret_key,
            self.secure,
            self.session_token,
            self.region,
            self.http_client,
            self.credentials,
            self.cert_check,
        )

        # Check if a client is already cached for this configuration
        if cache_key in _minio_clients:
            return _minio_clients[cache_key]

        # If not cached, create a new client
        minio_client = Minio(
            endpoint=self.endpoint,
            access_key=self.access_key,
            secret_key=self.secret_key,
            secure=self.secure,
            session_token=self.session_token,
            region=self.region,
            http_client=self.http_client,
            credentials=self.credentials,
            cert_check=self.cert_check
        )

        # Cache the new client
        _minio_clients[cache_key] = minio_client

        return minio_client

    def _open(self, name, mode='rb'):
        data = self.minio_client.get_object(self.bucket_name, name)
        return MinioStorageFile(data, name)

    def _save(self, name, content):
        if self.exists(name) and not self.overwrite_files:
            name = self.get_available_name(name)

        content.seek(0)
        content_type = mimetypes.guess_type(name)[0]

        self.minio_client.put_object(
            self.bucket_name,
            name,
            content,
            content.size,
            content_type=content_type,
        )

        if name in self._stat_cache:
            del self._stat_cache[name]

        return name

    def delete(self, name):
        self.minio_client.remove_object(self.bucket_name, name)
        if name in self._stat_cache:
            del self._stat_cache[name]

    def exists(self, name):
        """
        Checks if a file with the given name exists in the MinIO storage.
        """
        try:
            self.get_stat(name)
            return True
        except Exception:  # Specifically, S3Error: S3 operation failed; code: NoSuchKey
            return False

    def get_accessed_time(self, name):
        """
        Returns the last accessed time of the file.
        """
        time = self.get_stat(name).last_modified
        if not settings.USE_TZ:
            time = timezone.make_naive(time)
        return time

    def get_created_time(self, name):
        """
        Returns the creation time of the file.
        """
        return self.get_accessed_time(name)

    def get_stat(self, name):
        """
        Retrieves metadata of a file from MinIO, using an internal cache.
        """
        if name not in self._stat_cache:
            try:
                self._stat_cache[name] = self.minio_client.stat_object(self.bucket_name, name)
            except Exception as e:
                # The object does not exist. Re-raise the exception.
                raise e
        return self._stat_cache[name]

    def get_available_name(self, name, max_length=1024):
        """
        Given a file name, this function appends an underscore and a random number to the name
        until a unique name is generated.

        Note: If the file name exceeds max_length, it's truncated to fit.

        Args:
            name (str): The original name of the file.
            max_length (int, optional): The maximum length a name can be. Defaults to 1024.

        Returns:
            name (str): The name modified to assure it's unique and doesn't exceed max_length.
        """

        # If the filename already exists, add an underscore and a number (before the file extension, if one exists)
        # to the filename until the generated filename doesn't exist.
        while self.exists(name) or (max_length and len(name) > max_length):
            # file_ext includes the dot.
            filename, file_ext = os.path.splitext(name)

            # Truncate filename to max_length
            if max_length:
                # Subtract one to allow for underscore
                filename = filename[:max_length - len(file_ext) - 1]

            # name = get_valid_filename("%s_%s%s" % (filename, randrange(100, 999), file_ext))
            name = "%s_%s%s" % (filename, randrange(100, 999), file_ext)

        return name

    def url(self, name):
        """
        Returns a URL where the content of the file referenced by the given name can be accessed directly by a client.

        The method differs in behavior based on the 'pre-signed_url' attribute. If 'presigned_url' is True, it generates
        a presigned URL that provides temporary access to the object.
        If 'presigned_url' is False, it generates a public URL for the object in the Minio server.

        Args:
            name (str): Name of the file in the Minio server for which the URL is to be generated

        Returns:
            str: A string representing the URL at which the file's content is accessible.
        """
        if self.pre_signed_url:
            url = self.minio_client.get_presigned_url(
                "GET", self.bucket_name, name, expires=self.presigned_expiration,
            )
        else:
            url = f'{"https://" if self.secure else "http://"}{self.endpoint}/{self.bucket_name}/{name}'
        return url

    def listdir(self, path):
        """
        Lists all the files located in a given directory on the MinIO storage server.

        This method uses MinIO client's `list_objects` method to retrieve the list of all
        files located in the directory specified by 'path'.

        Args:
            path (str): The directory whose files are to be listed.

        Returns:
            list_objects_v2: An iterable object over Object along with additional metadata for each object returned as
            ListObjectsV2Result.
        """
        return self.minio_client.list_objects(
            self.bucket_name,
            prefix=path,
            recursive=False,
            start_after=None,
            include_user_meta=False,
            include_version=False,
            use_api_v1=False,
            use_url_encoding_type=True
        )

    def size(self, name):
        """
        Returns the size of a specified file in the MinIO storage.

        This method uses the MinIO client's `stat_object` method to retrieve the metadata of a file,
        primarily the size of the file identified by its name.

        Args:
            name (str): The name of the file whose size to be retrieved.

        Returns:
            int: Size of the file in bytes.

        :param name: Name of the object whose size needs to be fetched
        :return: Size of the object in bytes
        """
        stat = self.get_stat(name)
        return stat.size
