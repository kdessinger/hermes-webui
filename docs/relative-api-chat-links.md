# Relative API download links in chat

The finalized Markdown renderer supports both root-relative `/api/...` links and app-relative `api/...` links. This includes authenticated workspace downloads with query strings and percent-encoded file paths. Root-relative URLs resolve from the domain root; app-relative URLs follow the document base, including subpath deployments.

Both inline/table parsing and the final link pass recognize these destinations. The URL sanitizer allows these API paths, while continuing to reject protocol-relative URLs, executable schemes, backslashes and embedded ASCII whitespace/control characters in API destinations. This does not add support for arbitrary relative filesystem or web paths.

After a deployed JavaScript update, refresh an already-open browser tab before checking old or new messages. Authentication and file authorization are unchanged: a rendered link does not bypass sign-in or workspace boundaries.

Regression coverage: `tests/test_relative_download_links.py` exercises actual `renderMd` through Node, including paragraphs, lists, quotes, table cells, query strings and unsafe destinations. Neighboring renderer, workspace-link and streaming-Markdown tests should also pass.
