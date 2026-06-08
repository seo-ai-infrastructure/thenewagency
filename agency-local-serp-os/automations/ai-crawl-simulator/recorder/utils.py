# Utility functions for DOM pruning and text cleanup
import re

def clean_dom(dom_html: str) -> str:
    """Optionally strip scripts and stylesheets to reduce token sizes."""
    cleaned = re.sub(r'<script.*?</script>', '', dom_html, flags=re.DOTALL)
    cleaned = re.sub(r'<style.*?</style>', '', cleaned, flags=re.DOTALL)
    return cleaned.strip()
