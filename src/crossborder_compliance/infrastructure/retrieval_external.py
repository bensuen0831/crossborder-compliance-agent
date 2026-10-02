"""Factory for the existing DNS-pinned HTTPS downloader, with versioned policy limits."""

from urllib.parse import urlsplit

from crossborder_compliance.infrastructure.knowledge_download import ControlledHTTPSDownloader


class AuditedExternalDownloader:
    def __init__(self, source, rule, policy):
        urls = (source["canonical_url"], *rule.approved_redirect_urls)
        self.adapter = ControlledHTTPSDownloader(
            {urlsplit(u).hostname for u in urls},
            timeout=policy.timeout_seconds,
            max_size=policy.max_file_size,
            redirect_limit=policy.redirect_limit,
        )

    def download(self, url):
        content, audit = self.adapter.download(url)
        return content, audit
