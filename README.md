# eztick

A keyboard-driven terminal client for [TickTick](https://ticktick.com).

![screenshot placeholder](#)

## Install

Prebuilt single-file binaries are published on every push to `main` (rolling [`latest`](https://github.com/estevE11/eztick/releases/tag/latest)) and on every `v*` tag (versioned releases).

### Linux

```bash
curl -L -o eztick https://github.com/estevE11/eztick/releases/latest/download/eztick-linux-x86_64
chmod +x eztick
mkdir -p ~/.local/bin
mv eztick ~/.local/bin/
```

### macOS (Apple Silicon)

```bash
curl -L -o eztick https://github.com/estevE11/eztick/releases/latest/download/eztick-macos-arm64
chmod +x eztick
mkdir -p ~/.local/bin
mv eztick ~/.local/bin/
```

You may also need to clear Gatekeeper quarantine the first time:

```bash
xattr -d com.apple.quarantine ~/.local/bin/eztick
```

### Add `~/.local/bin` to your PATH

If `eztick` isn't found after install, your shell doesn't have `~/.local/bin` on `PATH`. Add it:

```bash
# bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc

# zsh
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc

# fish
fish_add_path ~/.local/bin
```

### Windows

Download `eztick-windows-x86_64.exe` from the [releases page](https://github.com/estevE11/eztick/releases), rename it to `eztick.exe`, and drop it in any folder on your `PATH` (e.g. `%USERPROFILE%\bin`).

### Pinning a specific version

Replace `latest` in the URL with a tag, e.g.:

```bash
curl -L -o eztick https://github.com/estevE11/eztick/releases/download/v0.1.0/eztick-linux-x86_64
```

## First run

Create a TickTick Developer App at <https://developer.ticktick.com>:

1. Create a new app named `eztick` (or whatever).
2. Set the redirect URI to `http://localhost:8765/callback`.
3. Copy the **Client ID** and **Client Secret**.

Then run:

```bash
eztick
```

On first launch you'll be asked for the Client ID, Client Secret, and redirect URI, then prompted to authorize in your browser and paste the `?code=` value back into the TUI. Credentials and tokens are stored in `~/.config/eztick/config.json`.

## Keybindings

| Key       | Action            |
|-----------|-------------------|
| `j` / `k` | Move down / up    |
| `space`   | Toggle selection  |
| `n`       | New task          |
| `e`       | Edit selected     |
| `d`       | Delete selected   |
| `r`       | Refresh           |
| `Ctrl+Z`  | Undo last complete|
| `q`       | Quit              |

Dates are entered as `DD-MM`. The year is inferred as the current year, or the next year if that day has already passed.

## Building from source

```bash
git clone https://github.com/estevE11/eztick
cd eztick
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m eztick
```
