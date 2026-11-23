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
