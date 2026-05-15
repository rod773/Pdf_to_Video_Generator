# PDF to Video Generator

Converts PDF documents into narrated video presentations with synchronized slides and audio. Works fully offline — no API key required.

## Features

- **No API key needed** — Direct mode extracts page text and creates slides automatically
- **Optional AI mode** — Uses DeepSeek (or any OpenAI-compatible API) for smarter slide structuring
- **GUI** — Tkinter desktop app with language/voice selectors and live log output
- **16 languages, 40+ voices** — via edge-tts (Microsoft Edge TTS)
- **LibreOffice optional** — Falls back to Pillow-based slide rendering when LibreOffice isn't installed
- **Outputs**: `final_video.mp4`, `presentation.pptx`, per-slide audio files

## Project Structure

```
├── gui.py               # Tkinter GUI (main entry point)
├── main_version_4.py    # CLI version
├── presentation.py      # PPTX generation + slide-to-image rendering
├── audio.py             # edge-tts audio generation
├── yt_shorts.py         # YouTube Shorts generator (experimental)
├── contents/            # Sample PDFs and assets
├── .env.example         # Environment config template
└── requirements.txt
```

## Requirements

- Python 3.10+
- [LibreOffice](https://www.libreoffice.org/download/) *(optional — only needed for higher-quality PPTX→image conversion)*

## Quick Start

```bash
pip install -r requirements.txt
python gui.py
```

Select a PDF, choose your language and voice, then click **Generate Video**. No `.env` file or API key needed.

## Modes

### Direct Mode (default, no API key)

Extracts text per page from the PDF and creates one slide per page. The page's first line becomes the slide title, sentences become bullet points, and the full text is read as voice-over.

### AI Mode (check "Use AI" in GUI)

Requires `TOKEN` in `.env`. Sends PDF text to DeepSeek (or any OpenAI-compatible API) to generate structured slide content, key points, voice-over scripts, and theme colors.

```
# .env
TOKEN=sk-your-api-key
ENDPOINT=https://api.deepseek.com   # optional, defaults to DeepSeek
```

The `openai` package is only needed for AI mode — uncomment it in `requirements.txt` if using this mode.

## GUI Controls

| Control | Options |
|---|---|
| Mode | Direct (default) / AI |
| Theme | Professional, Creative, Minimal |
| Voice Style | Neutral, Enthusiastic, Formal |
| Language | English, Spanish, French, German, Italian, Portuguese, Japanese, Chinese, Korean, Russian, Arabic, Dutch, Polish, Swedish, Turkish, Hindi |
| Voice | 40+ edge-tts voices, filtered by language |
| Speech Rate | −20% to +30% |

## How It Works

1. **Extract** — PDF text is read per-page using PyMuPDF (fitz)
2. **Structure** — Either direct extraction (no API) or AI-powered structuring via DeepSeek
3. **Present** — A PPTX file is generated with title, content, and bullet points
4. **Render** — Slides are converted to 1920×1080 PNG images (LibreOffice → pdf2image, or Pillow fallback)
5. **Narrate** — Voice-over scripts are converted to MP3 audio via edge-tts
6. **Assemble** — Slides and audio are combined into `final_video.mp4` using MoviePy

## CLI Usage

```bash
python main_version_4.py
```

Edit the `Args` class at the bottom of the file to change the PDF path and settings.

## License

MIT
