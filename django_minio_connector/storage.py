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
    Class representing a file stored in Minio storage.

    This class extends the base File class and provides additional methods to interact
    with files stored in Minio storage.

    Attributes:
        Parent class attributes

    Methods:
        close(): Close the file and release the connection to Minio storage.
    """

    def close(self):
        """
        Closes the file and releases the connection to Minio storage.

        This method first calls the parent class's close method to perform any necessary cleanup,
        then it calls the 'release_conn' method on the 'file' attribute to close the connection
        to Minio storage.

        :return: None
        """
        super(MinioStorageFile, self).close()
        self.file.release_conn()


class MinIOStorage(Storage):
    """
    The constructor for MinioStorage class, which initiates the settings of the Minio server and its properties.

    Parameters:
    *args (tuple): Variable length argument list.
    **kwargs (dict): Arbitrary keyword arguments.

    Following arguments are expected in kwargs:
    MINIO_ENDPOINT (str): MinIO service URL.
    MINIO_ROOT_USER (str): Access key (aka user ID) of an account in the S3 service.
    MINIO_ROOT_PASSWORD (str): Secret key (aka password) of an account in the S3 service.
    MINIO_USE_HTTPS (bool): If True, access the S3 service over a TLS (secure) connection, Defaults to True.
    MINIO_BUCKET_NAME (str): Name of the bucket in the minio server.
    SESSION_TOKEN (str): Session token of an account in the S3 service, Defaults to None.
    REGION (str): Region of an account in the S3 service, Defaults to None.
    HTTP_CLIENT (str): Pre-configured http.client object , defaults to None.
    CREDENTIALS (str): Pre-configured Credentials object , defaults to None.
    CERT_CHECK (bool): Enable/Disable server certificate verification , defaults to True.
    MINIO_BUCKET_POLICY (dict): Bucket policy for MinIO bucket, default to None.
    MINIO_PRESIGNED_URL (bool): If True, use pre-signed URLs instead of public URLs, default to True.
    MINIO_OVERWRITE_FILES (bool): If False, avoid overwriting files, default to False.

    """

    def __init__(self, **kwargs):
        """
        The constructor for MinioStorage class, which initiates the settings of the Minio server and its properties.

        Parameters:
        *args (tuple): Variable length argument list.
        **kwargs (dict): Arbitrary keyword arguments.

        Following arguments are expected in kwargs:
        MINIO_ENDPOINT (str): MinIO service URL.
        MINIO_ROOT_USER (str): Access key (aka user ID) of an account in the S3 service.
        MINIO_ROOT_PASSWORD (str): Secret key (aka password) of an account in the S3 service.
        MINIO_USE_HTTPS (bool): If True, access the S3 service over a TLS (secure) connection, Defaults to True.
        MINIO_BUCKET_NAME (str): Name of the bucket in the minio server.
        SESSION_TOKEN (str): Session token of an account in the S3 service, Defaults to None.
        REGION (str): Region of an account in the S3 service, Defaults to None.
        HTTP_CLIENT (str): Pre-configured http.client object , defaults to None.
        CREDENTIALS (str): Pre-configured Credentials object , defaults to None.
        CERT_CHECK (bool): Enable/Disable server certificate verification , defaults to True.
        MINIO_BUCKET_POLICY (dict): Bucket policy for MinIO bucket, default to None.
        MINIO_PRESIGNED_URL (bool): If True, use pre-signed URLs instead of public URLs, default to True.
        MINIO_OVERWRITE_FILES (bool): If False, avoid overwriting files, default to False.

        """
        self.endpoint = kwargs['MINIO_ENDPOINT']
        self.access_key = kwargs['MINIO_ROOT_USER']
        self.secret_key = kwargs['MINIO_ROOT_PASSWORD']
        self.secure = kwargs.get('MINIO_USE_HTTPS', True)
        self.bucket_name = kwargs['MINIO_BUCKET_NAME']

        self.session_token = kwargs.get('SESSION_TOKEN', None)
        self.region = kwargs.get('REGION', None)
        self.http_client = kwargs.get('HTTP_CLIENT', None)  # PoolManager
        self.credentials = kwargs.get('CREDENTIALS', None)  # Provider
        self.cert_check = kwargs.get('CERT_CHECK', True)  # Provider

        self.bucket_policy = kwargs.get('MINIO_BUCKET_POLICY', None)
        self.pre_signed_url = kwargs.get('MINIO_PRESIGNED_URL', True)
        self.overwrite_files = kwargs.get('MINIO_OVERWRITE_FILES', False)

        self.minio_client = self._get_minio_client()

        if not self.minio_client.bucket_exists(self.bucket_name):
            self.minio_client.make_bucket(self.bucket_name)

        if self.bucket_policy:
            self.minio_client.set_bucket_policy(self.bucket_name, json.dumps(self.bucket_policy))

    def _get_minio_client(self):
        """
            This method configures and returns a MinIO client that will be used
            for interacting with the MinIO server.

            The client is configured using the instance variables: endpoint, access_key,
            secret_key, secure, session_token, region, http_client, credentials and cert_check.

            Returns:
                minio.Minio: An instance of a Minio client. This client has been configured
                             with the attributes provided during the initialization of the
                             MinIOStorage class and is ready for making operations against
                             the MinIO server.
            """
        return Minio(
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

    def _open(self, name, mode='rb'):
        """
        Opens the file associated with the specified file name in a particular mode.

        :param name: str
            The name of the file to open
        :param mode: str, optional
            The mode in which to open the file. By default, it is 'rb' (read binary).
        :return: MinioStorageFile
            The MinioStorageFile object associated with the specified file name.
        :param name: the name of the file to open
        :param mode: the mode in which to open the file (default is 'rb')
        :return: MinioStorageFile object associated with the specified file name
        """
        data = self.minio_client.get_object(self.bucket_name, name)
        return MinioStorageFile(data, name)

    def _save(self, name, content):
        """
        Saves a file to the MinIO bucket.

        This method checks if a file with a given name exists. If it exists and you do not want to overwrite files,
        a new name is generated, otherwise the file is overwritten.
        Django has self system for checking if a file exists.

        Args:
            name (str): The name of the file to save.
            content (BinaryIO): the content of the file to save.

        Returns:
            str: The final name under which the content file was saved.
        """
        if self.exists(name) and not self.overwrite_files:
            name = self.get_available_name(name)

        content.seek(0)

        # Guess the mimetype of your file
        content_type = mimetypes.guess_type(name)[0]

        self.minio_client.put_object(
            self.bucket_name,
            name,
            content,
            content.size,
            content_type=content_type,  # Add the content_type here
        )

        return name

    def delete(self, name):
        """
        Deletes the file with a specified name from the MinIO storage.

        This function uses the MinIO client to remove the specified object from the storage.
        The file is defined by its name and if it exists in the storage, it will be permanently deleted.

        Args:
            name (str): The name of the file to delete.
        """
        self.minio_client.remove_object(self.bucket_name, name)

    def exists(self, name):
        """
        Checks if the file with the given name exists in the MinIO storage.

        This method uses the MinIO client to retrieve the meta-data of an object
        identified by its name. If the object exists, stat_object raises no
        exception and the method returns True, otherwise False.

        Args:
            name (str): The name of the file to check for its existence.

        Returns:
            bool: True if the file exists in MinIO storage; False otherwise.
        """
        try:
            self.get_stat(name)
            return True
        except (Exception,):
            return False

    def get_accessed_time(self, name):
        """
        Returns the last accessed time of the file with a given name from the MinIO storage.

        This method uses the MinIO client's `stat_object` method to retrieve the metadata of a file,
        primarily the last accessed time.

        Args:
            name (str): The name of the file whose accessed time is to be retrieved.

        Returns:
            datetime.datetime: A datetime object representing the last accessed time of the file.
            If the Django setting USE_TZ is True, the time is made aware by the Django timezone.

        Raises:
            MinioException: An error occurred in retrieving the time.
        """
        time = self.get_stat(name).last_modified
        if not settings.USE_TZ:
            time = timezone.make_naive(time)
        return time

    def get_created_time(self, name):
        """
        Returns the creation time of the file with a given name from the MinIO storage.

        This method utilizes the `get_accessed_time` method to fetch the creation time of a file.

        Args:
            name (str): The name of the file whose creation time is to be retrieved.

        Returns:
            datetime.datetime: A datetime object showing the creation time of the file.
            If the Django setting USE_TZ is True, the time is made aware by the Django timezone.
        """
        return self.get_accessed_time(name)

    def get_stat(self, name):
        """
        Retrieves metadata of a specified file from the MinIO storage.

        This method uses MinIO client's `stat_object` method to retrieve the metadata
        of a file identified by its name.

        Args:
            name (str): The name of the file whose metadata is to be retrieved.

        Returns:
            Object: An instance representing the metadata of the specified file.

        Raises:
            MinioException: An error occurred while retrieving the metadata.
        """
        return self.minio_client.stat_object(self.bucket_name, name)

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
                "GET", self.bucket_name, name, expires=timedelta(days=1),
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
