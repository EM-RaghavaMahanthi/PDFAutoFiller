# src/utils/storage.py
import os
import json
import boto3
import tempfile
import shutil
from botocore.exceptions import BotoCoreError, ClientError
from src.utils.logger import logger

def save_json(data: dict, storage_config: dict) -> str:
    storage_type = storage_config.get("name", "local")

    if storage_type == "local":
        output_path = storage_config.get("output_path")
        if not output_path:
            raise ValueError("Missing 'output_path' in storage_config for local storage.")

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        logger.info(f"Extracted data saved to local path: {output_path}")
        return os.path.abspath(output_path)

    elif storage_type == "s3":
        bucket = storage_config.get("bucket")
        prefix = storage_config.get("output_prefix", "")
        filename = storage_config.get("output_file", "extracted.json")
        region = storage_config.get("region", "us-east-1")

        if not bucket:
            raise ValueError("Missing 'bucket' in storage_config for S3 storage.")

        key = os.path.join(prefix, filename)
        s3_client = boto3.client("s3", region_name=region)

        try:
            s3_client.put_object(
                Bucket=bucket,
                Key=key,
                Body=json.dumps(data, indent=4, ensure_ascii=False).encode("utf-8"),
                ContentType="application/json"
            )
            uri = f"s3://{bucket}/{key}"
            logger.info(f"Extracted data uploaded to S3 at: {uri}")
            return uri
        except (BotoCoreError, ClientError) as e:
            logger.error(f"Failed to upload to S3: {e}")
            raise

    else:
        raise NotImplementedError(f"Storage type '{storage_type}' is not supported yet.")

def download_to_tempfile(storage_config: dict, key_name: str, suffix: str) -> str:
    """
    Download a file (PDF, JSON, etc.) from local or S3 to a local temp path.
    If from local, just return the path. If from cloud, download and return temp path.
    """
    storage_type = storage_config.get("name", "local")

    if storage_type == "local":
        path = storage_config.get(key_name)
        if not path or not os.path.exists(path):
            raise FileNotFoundError(f"{key_name} not found at path: {path}")
        return path

    elif storage_type == "s3":
        bucket = storage_config.get("bucket")
        key = storage_config.get(key_name)  # e.g., input_key, input_json_key
        region = storage_config.get("region", "us-east-1")

        if not bucket or not key:
            raise ValueError(f"Missing 'bucket' or '{key_name}' in storage_config")

        s3 = boto3.client("s3", region_name=region)
        tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)

        try:
            s3.download_fileobj(bucket, key, tmp_file)
            tmp_file.close()
            logger.info(f"Downloaded {key_name} from S3 to temp path: {tmp_file.name}")
            return tmp_file.name
        except Exception as e:
            logger.error(f"Failed to download {key_name} from S3: {e}")
            raise

    else:
        raise NotImplementedError(f"Storage type '{storage_type}' not supported for file downloading.")

def cleanup_temp_file(file_path: str, delete=False):
    if not delete:
        logger.info(f"Not deleting file: {file_path}")
        return
    try:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
            logger.info(f"Deleted temporary file: {file_path}")
    except Exception as e:
        logger.warning(f"Failed to delete temp file {file_path}: {e}")


def save_file(local_path: str, storage_config: dict, key_name: str = "output_file") -> str:
    storage_type = storage_config.get("name", "local")

    if storage_type == "local":
        final_path = storage_config.get(key_name)
        if not final_path:
            raise ValueError(f"Missing '{key_name}' in storage config for local output.")

        os.makedirs(os.path.dirname(final_path), exist_ok=True)
        shutil.copy(local_path, final_path)
        logger.info(f"Saved filled PDF locally at: {final_path}")
        return final_path

    elif storage_type == "s3":
        bucket = storage_config.get("bucket")
        output_prefix = storage_config.get("output_prefix", "")
        output_file = storage_config.get(key_name)
        region = storage_config.get("region", "us-east-1")

        if not bucket or not output_file:
            raise ValueError("Missing 'bucket' or output file name in storage config for S3 output.")

        s3_key = os.path.join(output_prefix, output_file)
        s3_client = boto3.client("s3", region_name=region)

        try:
            s3_client.upload_file(local_path, bucket, s3_key)
            logger.info(f"Uploaded filled PDF to s3://{bucket}/{s3_key}")
            return f"s3://{bucket}/{s3_key}"
        except (BotoCoreError, ClientError) as e:
            logger.error(f"Failed to upload to S3: {e}")
            raise

    else:
        raise NotImplementedError(f"Storage type '{storage_type}' is not supported for saving.")
