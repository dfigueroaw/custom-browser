# Custom Browser

A lightweight educational web browser implemented in Python. This repository is a work in progress and primarily intended for learning and experimentation. This project is inspired by concepts presented in [Web Browser Engineering](https://browser.engineering), which serves as a reference for architecture and implementation ideas.

## Emoji Support

The browser uses emoji images for rendering Unicode emoji characters. On first run, the project automatically downloads emoji assets from the [OpenMoji](https://openmoji.org/) dataset and generates optimized local sprites. These files are stored in:

```
assets/emoji/
```

You may also provide your own emoji assets instead of downloading them automatically. To do so:

- Place emoji PNG files inside `assets/emoji/`
- Each filename must be the hexadecimal Unicode codepoint of the emoji (uppercase), e.g.:
  - `1F600.png`
  - `1F601.png`
- Images should be square and small (recommended ~12–16 px)

If the folder exists, automatic download and processing are skipped.

> [!note]
> Emoji assets downloaded by default come from the OpenMoji project and are licensed under [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/#). If you provide your own emoji set, you are responsible for complying with its respective license.

## Running

```
python browser.py <url>
```

Example:

```
python browser.py https://browser.engineering/examples/example1-simple.html
```
