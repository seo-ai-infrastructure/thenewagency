from unittest.mock import patch, MagicMock
import integrations.google_auth as ga

def test_bearer_token_minted_from_service_account():
    creds = MagicMock(); creds.token = "ya29.fake"
    with patch.dict("os.environ", {"GSC_GA4_CREDENTIALS": "C:/k.json"}), \
         patch.object(ga.service_account.Credentials, "from_service_account_file", return_value=creds) as mk, \
         patch.object(ga, "Request", return_value="REQ"):
        tok = ga.bearer_token(["https://www.googleapis.com/auth/webmasters.readonly"])
    assert tok == "ya29.fake"
    creds.refresh.assert_called_once_with("REQ")
    assert mk.call_args.kwargs["scopes"] == ["https://www.googleapis.com/auth/webmasters.readonly"]
