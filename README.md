# ClipBridge extensions

The catalogue behind the **Store** in the ClipBridge app. Each file in
[`extensions/`](extensions) is one extension: an app for the ClipBridge home
screen, with a page and home screen widgets made of the app's own blocks
(buttons that type text or press shortcuts, the trackpad, the key bar,
library lists and so on).

## Writing an extension

1. Copy one of the files in `extensions/` and rename it to your extension's id
   (`my-thing.json` for `"id": "my-thing"`).
2. Follow [`schema/extension.schema.json`](schema/extension.schema.json). Most
   editors check against it if you add
   `"$schema": "../schema/extension.schema.json"` while you work (take it out
   before committing).
3. Check it:

   ```bash
   pip install jsonschema cryptography
   python3 tools/build.py --check
   ```

4. Open a pull request. CI runs the same check.

An extension can't hide what it does: before installing, the app lists what
it can do on the user's computer (type text, press keys, move the mouse, run
DuckyScript, read the clipboard), worked out from its blocks as well as its
`permissions`. Pull requests are reviewed for what the buttons actually send.

### Scripts

For more than fixed steps, an extension can carry JavaScript in `script`, and
buttons call its functions with `{"type": "script", "call": "name", "args": [...]}`.
Scripts run in a sandbox with no network, and talk to the app only through
`cb`: `cb.type`, `cb.keys`, `cb.wait`, `cb.mouse.*`, `cb.ducky`,
`cb.storage.*`, and the prompts `cb.ask`, `cb.choose`, `cb.confirm` and
`cb.notify`. Every call is checked against the extension's permissions.
[`extensions/dev-server.json`](extensions/dev-server.json) is a worked
example, and the app's
[docs/extensions.md](https://github.com/HaydenKaufmann/clipbridge/blob/main/docs/extensions.md#scripts)
has the whole API.

The check also makes sure every function a button calls is defined, and,
when `node` is installed, that the script parses.

## How the app gets it

Every push to `main` runs [the catalogue workflow](.github/workflows/catalogue.yml):
it checks every extension, builds an index, signs it with the catalogue key
(Ed25519, held in the `CATALOGUE_SIGNING_KEY` secret of the
`catalogue-signing` environment), and publishes `catalogue.json` to the
`dist` branch. The app downloads it from

    https://raw.githubusercontent.com/HaydenKaufmann/clipbridge-extensions/dist/catalogue.json

and only accepts it if the signature matches the public key built into the
app, and its sequence number isn't older than one it has already seen.

## The schema

`schema/extension.schema.json` is generated from the app (so it lists exactly
the blocks, icons and keys the app knows). Don't edit it here: regenerate it in
the app repository and copy it over.
