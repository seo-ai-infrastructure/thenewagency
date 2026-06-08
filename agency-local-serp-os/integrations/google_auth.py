"""Mint a read-only bearer token from a service-account JSON for GSC + GA4 ingestion.
Uses GSC_GA4_CREDENTIALS (a dedicated var, separate from any media credentials)."""
import os
from google.oauth2 import service_account
from google.auth.transport.requests import Request


def bearer_token(scopes):
    path = os.environ["GSC_GA4_CREDENTIALS"]
    creds = service_account.Credentials.from_service_account_file(path, scopes=scopes)
    creds.refresh(Request())
    return creds.token
