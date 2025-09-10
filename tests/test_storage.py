import unittest
from unittest.mock import MagicMock, patch

from django_minio_connector.storage import MinIOStorage


class MinIOStorageTests(unittest.TestCase):

    def setUp(self):
        """
        Set up the test environment.
        """
        self.storage_options = {
            'MINIO_ENDPOINT': 'test.minio.server',
            'MINIO_ROOT_USER': 'test_access_key',
            'MINIO_ROOT_PASSWORD': 'test_secret_key',
            'MINIO_BUCKET_NAME': 'test-bucket',
            'MINIO_USE_HTTPS': False,
        }
        # It's important to clear the client cache before each test
        from django_minio_connector import storage as minio_storage
        minio_storage._minio_clients.clear()

    @patch('django_minio_connector.storage.Minio')
    def test_save_new_file(self, mock_minio):
        """
        Test saving a new file.
        """
        mock_client = mock_minio.return_value
        storage = MinIOStorage(**self.storage_options)

        mock_content = MagicMock()
        mock_content.size = 1234

        with patch.object(storage, 'exists', return_value=False):
            storage._save('test_file.txt', mock_content)

        mock_client.put_object.assert_called_once_with(
            'test-bucket',
            'test_file.txt',
            mock_content,
            1234,
            content_type='text/plain'
        )

    @patch('django_minio_connector.storage.Minio')
    def test_save_existing_file_no_overwrite(self, mock_minio):
        """
        Test saving a file that already exists without overwriting.
        """
        mock_client = mock_minio.return_value
        storage = MinIOStorage(**self.storage_options)

        mock_content = MagicMock()
        mock_content.size = 1234

        # Simulate file existing and get_available_name providing a new name
        with patch.object(storage, 'exists', return_value=True) as mock_exists, \
             patch.object(storage, 'get_available_name', return_value='new_name.txt') as mock_get_available_name:

            new_name = storage._save('test_file.txt', mock_content)

            self.assertEqual(new_name, 'new_name.txt')
            mock_exists.assert_called_once_with('test_file.txt')
            mock_get_available_name.assert_called_once_with('test_file.txt')

            mock_client.put_object.assert_called_once_with(
                'test-bucket',
                'new_name.txt',
                mock_content,
                1234,
                content_type='text/plain'
            )

    @patch('django_minio_connector.storage.Minio')
    def test_exists(self, mock_minio):
        """
        Test the exists method.
        """
        mock_client = mock_minio.return_value
        storage = MinIOStorage(**self.storage_options)

        storage.exists('existing_file.txt')
        mock_client.stat_object.assert_called_once_with('test-bucket', 'existing_file.txt')

        mock_client.stat_object.side_effect = Exception("File not found")
        self.assertFalse(storage.exists('non_existing_file.txt'))

    @patch('django_minio_connector.storage.Minio')
    def test_delete(self, mock_minio):
        """
        Test deleting a file.
        """
        mock_client = mock_minio.return_value
        storage = MinIOStorage(**self.storage_options)
        storage.delete('test_file.txt')

        mock_client.remove_object.assert_called_once_with('test-bucket', 'test_file.txt')

    @patch('django_minio_connector.storage.Minio')
    def test_url_presigned(self, mock_minio):
        """
        Test generating a presigned URL.
        """
        mock_client = mock_minio.return_value
        mock_client.get_presigned_url.return_value = 'http://presigned.url/test.txt'

        storage = MinIOStorage(**self.storage_options)
        storage.pre_signed_url = True

        url = storage.url('test.txt')

        self.assertEqual(url, 'http://presigned.url/test.txt')
        mock_client.get_presigned_url.assert_called_once()

    @patch('django_minio_connector.storage.Minio')
    def test_url_public(self, mock_minio):
        """
        Test generating a public URL.
        """
        storage = MinIOStorage(**self.storage_options)
        storage.pre_signed_url = False

        url = storage.url('test.txt')

        expected_url = 'http://test.minio.server/test-bucket/test.txt'
        self.assertEqual(url, expected_url)

    @patch('django_minio_connector.storage.Minio')
    def test_client_caching(self, mock_minio):
        """
        Test that the Minio client is cached globally.
        """
        MinIOStorage(**self.storage_options)
        self.assertEqual(mock_minio.call_count, 1)

        MinIOStorage(**self.storage_options)
        self.assertEqual(mock_minio.call_count, 1)

        different_options = self.storage_options.copy()
        different_options['MINIO_ENDPOINT'] = 'another.server'
        MinIOStorage(**different_options)
        self.assertEqual(mock_minio.call_count, 2)

    @patch('django_minio_connector.storage.Minio')
    def test_stat_caching(self, mock_minio):
        """
        Test that object metadata (stat) is cached within a storage instance.
        """
        mock_client = mock_minio.return_value
        storage = MinIOStorage(**self.storage_options)

        storage.exists('test.txt')
        self.assertEqual(mock_client.stat_object.call_count, 1)

        storage.exists('test.txt')
        self.assertEqual(mock_client.stat_object.call_count, 1)

        storage.delete('test.txt')

        mock_client.stat_object.side_effect = Exception("File not found")
        storage.exists('test.txt')
        self.assertEqual(mock_client.stat_object.call_count, 2)


if __name__ == '__main__':
    unittest.main()
