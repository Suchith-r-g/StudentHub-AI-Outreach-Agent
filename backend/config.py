import os
from typing import Optional
from dotenv import load_dotenv

load_dotenv(override=True)

class Settings:
    @property
    def TEST_MODE(self) -> bool:
        val = os.getenv("TEST_MODE", "true").strip().lower()
        return val in ("true", "1", "yes", "t")

    @property
    def APP_SECRET_KEY(self) -> str:
        return os.getenv("APP_SECRET_KEY", "studenthub_outreach_dev_secret_key_2026")

    @property
    def HOST(self) -> str:
        return os.getenv("HOST", "127.0.0.1")

    @property
    def PORT(self) -> int:
        return int(os.getenv("PORT", "3000"))

    # Founder / Company Context (Source of Truth)
    @property
    def FOUNDER_NAME(self) -> str:
        return os.getenv("FOUNDER_NAME", "Suchithreddy G")

    @property
    def FOUNDER_ROLE(self) -> str:
        return os.getenv("FOUNDER_ROLE", "CEO")

    @property
    def FOUNDER_COMPANY(self) -> str:
        return os.getenv("FOUNDER_COMPANY", "StudentHub")

    @property
    def OWNER_EMAIL(self) -> str:
        return os.getenv("OWNER_EMAIL", "suchithreddy@studenthub.co")

    # Product Description (Source of Truth - strictly no fabricated claims)
    COMPANY_CONTEXT: str = (
        "StudentHub is a student-focused recruitment and career platform designed around "
        "verified college students, developer profiles, resume and certificate evaluation, "
        "Career DNA competency modeling, and structured recruitment workflows. "
        "Primary objective: Recruit founding hiring partners for the platform. "
        "Target partners: Indian technology companies, software engineering teams, IoT businesses, "
        "HR-tech companies, and digital engineering firms."
    )

    # Hugging Face
    @property
    def HUGGINGFACE_API_KEY(self) -> Optional[str]:
        return os.getenv("HUGGINGFACE_API_KEY")

    @property
    def HF_MODEL_ID(self) -> str:
        return os.getenv("HF_MODEL_ID", "meta-llama/Meta-Llama-3-8B-Instruct")

    # Search Provider ('mock', 'tavily', 'serpapi')
    @property
    def SEARCH_PROVIDER(self) -> str:
        return os.getenv("SEARCH_PROVIDER", "serpapi")

    @property
    def SEARCH_API_KEY(self) -> Optional[str]:
        # Accept both SEARCH_API_KEY and SERPAPI_API_KEY
        return os.getenv("SEARCH_API_KEY") or os.getenv("SERPAPI_API_KEY")

    # Google OAuth 2.0 Credentials
    @property
    def GOOGLE_CLIENT_ID(self) -> Optional[str]:
        return os.getenv("GOOGLE_CLIENT_ID")

    @property
    def GOOGLE_CLIENT_SECRET(self) -> Optional[str]:
        return os.getenv("GOOGLE_CLIENT_SECRET")

    @property
    def GOOGLE_REDIRECT_URI(self) -> str:
        return os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:3000/api/auth/google/callback")

    # Scopes: Request minimal required scope
    # gmail.compose allows creating drafts and sending research reports to the authenticated owner
    GMAIL_SCOPES: list[str] = [
        "https://www.googleapis.com/auth/gmail.compose",
        "openid",
        "https://www.googleapis.com/auth/userinfo.email"
    ]

    @property
    def DATABASE_URL(self) -> str:
        return os.getenv("DATABASE_URL", "sqlite:///./studenthub_outreach.db")

settings = Settings()
