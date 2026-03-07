"""
services/google_drive.py
========================
Google Drive v3 upload service for UGC Video Pro.

Supports service account and OAuth 2.0 authentication.
Creates target folder if needed, optionally makes files public.
"""

import asyncio
import os
from pathlib import Path
from typing import Optional

from utils.logger import get_logger

logger = get_logger(__name__)

SCOPES = ["https://www.googleapis.com/auth/drive.file"]


class GoogleDriveUploader:
    """Upload videos to Google Drive using the Drive v3 API."""

    def __init__(self, config: dict):
        self.config = config
        drive_config = config.get("google_drive", {})
        self.credentials_path = drive_config.get("credentials_path", "credentials.json")
        self.folder_name = drive_config.get("folder_name", "UGC_Videos")
        self.make_public = drive_config.get("make_public", True)
        self._service = None
        self._folder_id_cache: dict[str, str] = {}

    def _build_service(self):
        """Build Google Drive service from credentials file."""
        if self._service:
            return self._service

        creds_path = Path(self.credentials_path)
        if not creds_path.exists():
            raise FileNotFoundError(
                f"Google Drive credentials not found: {self.credentials_path}"
            )

        from google.oauth2 import service_account
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
        import json

        with open(creds_path) as f:
            creds_data = json.load(f)

        cred_type = creds_data.get("type", "")

        if cred_type == "service_account":
            creds = service_account.Credentials.from_service_account_file(
                str(creds_path), scopes=SCOPES
            )
        else:
            token_path = Path("token.json")
            creds = None

            if token_path.exists():
                creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    flow = InstalledAppFlow.from_client_secrets_file(
                        str(creds_path), SCOPES
                    )
                    creds = flow.run_local_server(port=0)

                with open(token_path, "w") as token:
                    token.write(creds.to_json())

        self._service = build("drive", "v3", credentials=creds)
        logger.info("Google Drive service initialized")
        return self._service

    async def upload(self, file_path: str, folder_name: Optional[str] = None) -> str:
        """Upload a file to Google Drive and return a shareable link."""
        folder_name = folder_name or self.folder_name

        result = await asyncio.get_event_loop().run_in_executor(
            None, self._upload_sync, file_path, folder_name,
        )
        return result

    def _upload_sync(self, file_path: str, folder_name: str) -> str:
        """Synchronous upload implementation (runs in thread pool)."""
        from googleapiclient.http import MediaFileUpload

        service = self._build_service()
        file_path_obj = Path(file_path)

        if not file_path_obj.exists():
            raise FileNotFoundError(f"File to upload not found: {file_path}")

        folder_id = self._get_or_create_folder(service, folder_name)

        file_name = file_path_obj.name
        file_metadata = {
            "name": file_name,
            "parents": [folder_id],
        }

        suffix = file_path_obj.suffix.lower()
        mime_type = "video/mp4" if suffix == ".mp4" else "application/octet-stream"

        file_size = file_path_obj.stat().st_size
        logger.info(f"Uploading to Drive: {file_name} ({file_size / 1024 / 1024:.1f} MB) → {folder_name}")

        media = MediaFileUpload(
            str(file_path), mimetype=mime_type, resumable=True, chunksize=10 * 1024 * 1024,
        )

        request = service.files().create(
            body=file_metadata, media_body=media, fields="id, webViewLink, webContentLink",
        )

        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                logger.debug(f"Upload progress: {int(status.progress() * 100)}%")

        file_id = response.get("id")
        logger.info(f"Uploaded to Drive: {file_id}")

        share_link = response.get("webViewLink", "")
        if self.make_public:
            try:
                service.permissions().create(
                    fileId=file_id, body={"type": "anyone", "role": "reader"},
                ).execute()

                file_info = service.files().get(
                    fileId=file_id, fields="webViewLink, webContentLink"
                ).execute()
                share_link = file_info.get("webViewLink", share_link)
                logger.info(f"Made public: {share_link}")
            except Exception as e:
                logger.warning(f"Could not make file public: {e}")

        return share_link or f"https://drive.google.com/file/d/{file_id}/view"

    def _get_or_create_folder(self, service, folder_name: str) -> str:
        """Get existing folder ID or create new folder."""
        if folder_name in self._folder_id_cache:
            return self._folder_id_cache[folder_name]

        query = (
            f"name='{folder_name}' "
            f"and mimeType='application/vnd.google-apps.folder' "
            f"and trashed=false"
        )
        results = service.files().list(
            q=query, spaces="drive", fields="files(id, name)",
        ).execute()

        files = results.get("files", [])
        if files:
            folder_id = files[0]["id"]
            logger.debug(f"Found existing Drive folder: {folder_name} ({folder_id})")
        else:
            folder_metadata = {
                "name": folder_name,
                "mimeType": "application/vnd.google-apps.folder",
            }
            folder = service.files().create(
                body=folder_metadata, fields="id",
            ).execute()
            folder_id = folder.get("id")
            logger.info(f"Created Drive folder: {folder_name} ({folder_id})")

        self._folder_id_cache[folder_name] = folder_id
        return folder_id
