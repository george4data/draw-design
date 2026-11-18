# Security

`ddraw` treats every source diagram, website, label, link and icon pack as untrusted data (PRD §19).
Parsers are bounded, reject DTDs and entities, and never execute content. Outputs contain no scripts,
no `javascript:` links and no remote images.

Report vulnerabilities privately through GitHub security advisories on this repository.
