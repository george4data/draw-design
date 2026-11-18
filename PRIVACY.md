# Privacy

`ddraw` makes no network requests during compile, lint or import of local files.

Vendor icons come from a catalog shipped with the plugin, and draw.io Desktop renders exports locally (`ddraw` passes `--disable-update`).

Network access happens only when:

1. A viewer opens a diagram whose theme uses web fonts (`fontSource=web`); the draw.io web app may load fonts from `fonts.googleapis.com`.
2. A maintainer rebuilds the shape catalog (`make shapes`). This downloads jgraph's public shape index from GitHub. End users never run it.

Planned features that will ask for confirmation before any request: URL onboarding (fetches the pages you name) and importing an icon pack from a URL.

No telemetry is collected.
