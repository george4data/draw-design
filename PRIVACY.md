# Privacy

`ddraw` makes no network requests during compile, lint or import of local files.

Network access happens only when:

1. You run URL onboarding and confirm the trust prompt (fetches the pages you named).
2. You import an icon pack from a URL and confirm the prompt.
3. A viewer opens a diagram whose theme uses web fonts (`fontSource=web`); the draw.io web app may load fonts from `fonts.googleapis.com`.

No telemetry is collected.
