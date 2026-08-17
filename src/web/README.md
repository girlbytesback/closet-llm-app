# closetLLM web (Pick your palette)

The Python side of closetLLM still runs the same as always. This `src/web/`
folder is a separate little React app that shows the palette-picker screen in a browser.
It has the 19 palettes built in, so it runs on its own.

## One-time setup

You need Node.js installed (https://nodejs.org — pick the "LTS" version).
Check it's there:

    node --version

Then, from the project root, move into this folder and install the app's tools
once:

    cd src/web
    npm install

## Run it

From `src/web` (not the project root):

    npm run dev

The terminal will print a link like http://localhost:5173 — open that in your
browser and you'll see the UI.

Press Ctrl + C in the terminal to stop it.

## Files

- index.html ............ the empty page the app draws into
- src/main.jsx .......... starts the app
- src/PickYourCharacter.jsx  the actual UI (photos + colors live here)
- package.json .......... the list of tools this app needs
- vite.config.js ........ tells the build tool it's a React app
