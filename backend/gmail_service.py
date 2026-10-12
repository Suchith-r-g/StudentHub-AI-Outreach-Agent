import os
import base64
import logging
from email.message import EmailMessage
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from backend.config import settings
from backend.models import OAuthToken, OAuthState, SessionLocal

logger = logging.getLogger(__name__)

class GmailService:
    """
    Manages Google OAuth 2.0 and interacts with the Gmail API:
    - Minimum scope: https://www.googleapis.com/auth/gmail.compose
    - Creating authentic unsent drafts
    - Sending Company Research Reports directly to the owner email
    - Token lifecycle & refresh management
    """

    def __init__(self):
        pass

    @property
    def scopes(self) -> list[str]:
        return settings.GMAIL_SCOPES

    def get_oauth_flow(self, state: Optional[str] = None) -> Flow:
        if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
            raise ValueError("GOOGLE_CLIENT_ID or GOOGLE_CLIENT_SECRET is missing from environment.")

        client_config = {
            "web": {
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [settings.GOOGLE_REDIRECT_URI]
            }
        }
        flow = Flow.from_client_config(
            client_config,
            scopes=self.scopes,
            redirect_uri=settings.GOOGLE_REDIRECT_URI,
            state=state
        )
        return flow

    def get_authorization_url(self) -> str:
        flow = self.get_oauth_flow()
        authorization_url, state = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent"
        )
        
        # Save code_verifier mapped by state for PKCE callback verification
        code_verifier = getattr(flow, "code_verifier", None)
        if state and code_verifier:
            db = SessionLocal()
            try:
                state_record = OAuthState(state=state, code_verifier=code_verifier)
                db.merge(state_record)
                db.commit()
            finally:
                db.close()

        return authorization_url

    def exchange_code_for_token(self, code: str, state: Optional[str] = None) -> OAuthToken:
        flow = self.get_oauth_flow(state=state)

        # Restore code_verifier from DB if state was passed
        if state:
            db = SessionLocal()
            try:
                st = db.query(OAuthState).filter(OAuthState.state == state).first()
                if st and st.code_verifier:
                    flow.code_verifier = st.code_verifier
            finally:
                db.close()

        flow.fetch_token(code=code)
        creds = flow.credentials

        # Fetch connected user profile email
        service = build("gmail", "v1", credentials=creds)
        profile = service.users().getProfile(userId="me").execute()
        connected_email = profile.get("emailAddress")

        db = SessionLocal()
        try:
            token_record = db.query(OAuthToken).filter(OAuthToken.provider == "google").first()
            if not token_record:
                token_record = OAuthToken(provider="google")
                db.add(token_record)

            token_record.access_token = creds.token
            token_record.refresh_token = creds.refresh_token or token_record.refresh_token
            token_record.token_uri = creds.token_uri
            token_record.client_id = creds.client_id
            token_record.client_secret = creds.client_secret
            token_record.scopes = " ".join(creds.scopes or self.scopes)
            token_record.expiry = creds.expiry
            token_record.connected_email = connected_email
            token_record.updated_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(token_record)

            # Cleanup used OAuthState
            if state:
                db.query(OAuthState).filter(OAuthState.state == state).delete()
                db.commit()

            return token_record
        finally:
            db.close()

    def get_active_credentials(self) -> Optional[Credentials]:
        """
        Retrieves active OAuth credentials from database, automatically refreshing if expired.
        Updates refreshed tokens back to database.
        """
        db = SessionLocal()
        try:
            token_record = db.query(OAuthToken).filter(OAuthToken.provider == "google").first()
            if not token_record or not token_record.access_token:
                return None

            creds = Credentials(
                token=token_record.access_token,
                refresh_token=token_record.refresh_token,
                token_uri=token_record.token_uri or "https://oauth2.googleapis.com/token",
                client_id=token_record.client_id or settings.GOOGLE_CLIENT_ID,
                client_secret=token_record.client_secret or settings.GOOGLE_CLIENT_SECRET,
                scopes=token_record.scopes.split() if token_record.scopes else self.scopes
            )

            # Check if expired and refresh if possible
            from google.auth.transport.requests import Request
            if creds.expired and creds.refresh_token:
                try:
                    logger.info("Gmail OAuth token expired. Refreshing token via refresh_token...")
                    creds.refresh(Request())
                    token_record.access_token = creds.token
                    token_record.expiry = creds.expiry
                    token_record.updated_at = datetime.now(timezone.utc)
                    db.commit()
                    logger.info("Successfully refreshed and persisted updated Gmail OAuth token.")
                except Exception as e:
                    logger.error(f"Failed to refresh expired Gmail token: {e}")
                    # Return creds anyway to allow caller to handle failure
            elif not creds.valid and creds.refresh_token:
                try:
                    creds.refresh(Request())
                    token_record.access_token = creds.token
                    token_record.expiry = creds.expiry
                    token_record.updated_at = datetime.now(timezone.utc)
                    db.commit()
                except Exception as e:
                    logger.error(f"Failed to refresh invalid Gmail token: {e}")

            return creds
        finally:
            db.close()

    def is_connected(self) -> Dict[str, Any]:
        """
        Returns comprehensive Gmail connectivity and permission diagnostics.
        """
        configured = bool(settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET)
        db = SessionLocal()
        try:
            token_record = db.query(OAuthToken).filter(OAuthToken.provider == "google").first()
            if not token_record or not token_record.access_token:
                return {
                    "connected": False,
                    "email": None,
                    "test_mode": settings.TEST_MODE,
                    "configured": configured,
                    "has_compose_scope": False,
                    "granted_scopes": [],
                    "status_label": "Test Simulation Ready" if settings.TEST_MODE else "Disconnected (OAuth Required)"
                }

            creds = self.get_active_credentials()
            email = token_record.connected_email
            granted_scopes = (token_record.scopes or "").split()
            compose_scope = "https://www.googleapis.com/auth/gmail.compose"
            has_compose_scope = compose_scope in granted_scopes

            status_label = f"Connected ({email})" if email else "Connected"
            if not has_compose_scope:
                status_label = f"Connected ({email}) - Missing Compose Scope"

            return {
                "connected": True,
                "email": email,
                "test_mode": settings.TEST_MODE,
                "configured": configured,
                "has_compose_scope": has_compose_scope,
                "granted_scopes": granted_scopes,
                "status_label": status_label
            }
        finally:
            db.close()

    def check_connection_diagnostics(self) -> Dict[str, Any]:
        """
        Performs live diagnostic probe to Gmail API:
        Validates profile access, draft creation permissions, and token validity.
        """
        status = self.is_connected()
        if not status["connected"]:
            return {
                "healthy": False,
                "connected": False,
                "reason": "No OAuth credentials stored. User must connect Gmail.",
                "details": status
            }

        creds = self.get_active_credentials()
        try:
            service = build("gmail", "v1", credentials=creds)
            profile = service.users().getProfile(userId="me").execute()
            return {
                "healthy": True,
                "connected": True,
                "email": profile.get("emailAddress"),
                "messages_total": profile.get("messagesTotal"),
                "has_compose_scope": status.get("has_compose_scope", False),
                "granted_scopes": status.get("granted_scopes", [])
            }
        except HttpError as e:
            return {
                "healthy": False,
                "connected": True,
                "http_status": e.status_code,
                "reason": f"Gmail API error: {e.reason or str(e)}",
                "needs_reauth": e.status_code in (401, 403)
            }
        except Exception as e:
            return {
                "healthy": False,
                "connected": True,
                "reason": str(e),
                "needs_reauth": True
            }

    def create_one_test_draft(self) -> Dict[str, Any]:
        """
        Creates exactly one clearly labelled test draft in the connected Gmail account
        without sending it, and confirms its existence.
        """
        subject = f"[TEST DRAFT] StudentHub Outreach Integration Probe ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})"
        body = (
            "Hello,\n\n"
            "This is a verified test draft created by StudentHub AI Outreach Agent to test end-to-end "
            "Google OAuth and Gmail API draft creation permissions.\n\n"
            "This email is deliberately created as an UNSENT DRAFT and will NEVER be sent automatically.\n\n"
            "Best regards,\n"
            f"{settings.FOUNDER_NAME}\n"
            f"{settings.FOUNDER_ROLE}, {settings.FOUNDER_COMPANY}"
        )
        return self.create_draft(
            recipient_email=settings.OWNER_EMAIL,
            subject=subject,
            body_text=body
        )

    def create_draft(self, recipient_email: str, subject: str, body_text: str) -> Dict[str, Any]:
        """
        Creates a genuine unsent draft in Gmail using the Gmail API (drafts.create).
        Never sends the email.
        In LIVE MODE (TEST_MODE=false), strictly calls the real Gmail API or fails visibly.
        In TEST_MODE (TEST_MODE=true), explicitly labels the draft as a simulated mock unless real creds are present.
        """
        if not recipient_email or "@" not in recipient_email:
            raise ValueError(f"Invalid or missing recipient email: '{recipient_email}'. Draft creation aborted.")

        creds = self.get_active_credentials()

        # TEST_MODE: Clearly distinguished simulation with simulated metadata if credentials missing
        if settings.TEST_MODE and (not creds or not creds.token or not settings.GOOGLE_CLIENT_ID):
            import uuid
            logger.info(f"[TEST_MODE] Simulating Gmail API Draft creation for {recipient_email}")
            sim_uid = uuid.uuid4().hex[:12]
            return {
                "id": f"simulated_draft_{sim_uid}",
                "message": {
                    "id": f"simulated_msg_{sim_uid}",
                    "threadId": f"simulated_thread_{sim_uid}"
                },
                "simulated": True,
                "mode": "test_mode"
            }

        # If we have valid credentials (or in LIVE MODE), create real genuine draft
        if not creds:
            raise PermissionError(
                "Gmail account not connected. In LIVE MODE (TEST_MODE=false), a real connected Gmail account is required. "
                "Please click 'Connect Gmail' on the dashboard to authenticate via OAuth 2.0."
            )

        try:
            service = build("gmail", "v1", credentials=creds)
            message = EmailMessage()
            message.set_content(body_text)
            message["To"] = recipient_email
            
            # Use authenticated owner email
            db = SessionLocal()
            try:
                tok = db.query(OAuthToken).filter(OAuthToken.provider == "google").first()
                from_email = (tok.connected_email if tok else None) or settings.OWNER_EMAIL
            finally:
                db.close()

            message["From"] = from_email
            message["Subject"] = subject

            encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
            create_message = {"message": {"raw": encoded_message}}

            draft = service.users().drafts().create(userId="me", body=create_message).execute()
            draft["simulated"] = False
            draft["mode"] = "live"
            draft["connected_account"] = from_email
            logger.info(f"Successfully created genuine Gmail draft: ID={draft.get('id')}")
            return draft
        except HttpError as e:
            logger.error(f"Gmail API HttpError while creating draft: {e}")
            raise RuntimeError(f"Gmail API rejected draft creation: {e.reason or str(e)}")
        except Exception as e:
            logger.error(f"Failed to create draft in Gmail: {e}")
            raise

    def send_research_report(self, to_email: str, subject: str, html_content: str, text_content: str) -> Dict[str, Any]:
        """
        Sends the research report exclusively to the owner email address.
        In LIVE MODE (TEST_MODE=false), requires authentic Gmail connection.
        In TEST_MODE (TEST_MODE=true), safely simulates delivery if credentials are not configured.
        """
        creds = self.get_active_credentials()

        if settings.TEST_MODE and (not creds or not creds.token or not settings.GOOGLE_CLIENT_ID):
            logger.info(f"[TEST_MODE] Simulating research report email sent to owner {to_email}")
            sim_timestamp = int(datetime.now(timezone.utc).timestamp())
            return {
                "id": f"simulated_report_msg_{sim_timestamp}",
                "threadId": f"simulated_report_thread_{sim_timestamp}",
                "simulated": True,
                "mode": "test_mode"
            }

        if not creds:
            raise PermissionError(
                "Gmail account not connected. In LIVE MODE, cannot send research report without authentic Gmail credentials."
            )

        try:
            service = build("gmail", "v1", credentials=creds)
            message = EmailMessage()
            message.set_content(text_content)
            message.add_alternative(html_content, subtype="html")
            message["To"] = to_email

            db = SessionLocal()
            try:
                tok = db.query(OAuthToken).filter(OAuthToken.provider == "google").first()
                from_email = (tok.connected_email if tok else None) or settings.OWNER_EMAIL
            finally:
                db.close()

            message["From"] = from_email
            message["Subject"] = subject

            encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
            body = {"raw": encoded_message}

            sent = service.users().messages().send(userId="me", body=body).execute()
            sent["simulated"] = False
            return sent
        except HttpError as e:
            logger.error(f"Gmail API HttpError while sending report: {e}")
            raise RuntimeError(f"Gmail API failed to send report email: {e.reason or str(e)}")
