import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import os
from dotenv import load_dotenv
import json
import textwrap

load_dotenv()

import fitz
from moviepy.editor import ImageClip, CompositeVideoClip, concatenate_videoclips, AudioFileClip
from pydantic import BaseModel, Field
from typing import List, Optional, Dict

from presentation import generate_presentation, slides_to_images
from audio import generate_audio

HAS_AI = bool(os.getenv("TOKEN"))

if HAS_AI:
    from openai import OpenAI
    client = OpenAI(
        base_url=os.getenv("ENDPOINT", "https://api.deepseek.com"),
        api_key=os.getenv("TOKEN"),
    )

VOICES_BY_LANG = {
    "en": ["en-GB-RyanNeural", "en-GB-SoniaNeural", "en-US-JennyNeural", "en-US-GuyNeural", "en-AU-NatashaNeural", "en-IN-NeerjaNeural"],
    "es": ["es-ES-AlvaroNeural", "es-ES-ElviraNeural", "es-MX-JorgeNeural", "es-MX-DaliaNeural"],
    "fr": ["fr-FR-DeniseNeural", "fr-FR-HenriNeural", "fr-CA-SylvieNeural", "fr-CE-AntoineNeural"],
    "de": ["de-DE-KatjaNeural", "de-DE-ConradNeural", "de-CH-LeniNeural"],
    "it": ["it-IT-ElsaNeural", "it-IT-DiegoNeural", "it-IT-IsabellaNeural"],
    "pt": ["pt-BR-FranciscaNeural", "pt-BR-AntonioNeural", "pt-PT-RaquelNeural", "pt-PT-DuarteNeural"],
    "ja": ["ja-JP-NanamiNeural", "ja-JP-KeitaNeural"],
    "zh": ["zh-CN-XiaoxiaoNeural", "zh-CN-YunxiNeural", "zh-CN-XiaoyiNeural"],
    "ko": ["ko-KR-SunHiNeural", "ko-KR-InJoonNeural"],
    "ru": ["ru-RU-SvetlanaNeural", "ru-RU-DmitryNeural"],
    "ar": ["ar-SA-ZariyahNeural", "ar-SA-HamedNeural"],
    "nl": ["nl-NL-ColetteNeural", "nl-NL-MaartenNeural"],
    "pl": ["pl-PL-AgnieszkaNeural", "pl-PL-MarekNeural"],
    "sv": ["sv-SE-SofieNeural", "sv-SE-MattiasNeural"],
    "tr": ["tr-TR-EmelNeural", "tr-TR-AhmetNeural"],
    "hi": ["hi-IN-SwaraNeural", "hi-IN-MadhurNeural"],
}

LANG_LABELS = {
    "en": "English", "es": "Spanish", "fr": "French", "de": "German",
    "it": "Italian", "pt": "Portuguese", "ja": "Japanese", "zh": "Chinese",
    "ko": "Korean", "ru": "Russian", "ar": "Arabic", "nl": "Dutch",
    "pl": "Polish", "sv": "Swedish", "tr": "Turkish", "hi": "Hindi",
}

class SlideItem(BaseModel):
    title: str
    content: str
    key_points: List[str] = Field(default_factory=list)
    voice_over: str

class SlideChunk(BaseModel):
    slides: List[SlideItem]
    theme_colors: Optional[Dict[str, str]] = None

class VideoConfig(BaseModel):
    theme: str = "professional"
    language: str = "en"
    voice_style: str = "neutral"
    include_background_music: bool = False

DEFAULT_COLORS = {"primary": "1F497D", "secondary": "4F81BD", "accent": "C0504D", "background": "FFFFFF", "text": "000000"}

class App(ttk.Frame):
    def __init__(self, root):
        super().__init__(root, padding=20)
        self.root = root
        self.root.title("PDF to Video Generator")
        self.root.geometry("800x750")
        self.root.minsize(700, 650)
        self.running = False
        self.pack(fill=tk.BOTH, expand=True)
        self.create_widgets()

    def create_widgets(self):
        pad = {"padx": 8, "pady": 4}

        f1 = ttk.LabelFrame(self, text="PDF Input", padding=10)
        f1.pack(fill=tk.X, **pad)
        row1 = ttk.Frame(f1)
        row1.pack(fill=tk.X)
        self.pdf_path = tk.StringVar()
        ttk.Entry(row1, textvariable=self.pdf_path).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        ttk.Button(row1, text="Browse PDF", command=self.browse_pdf).pack(side=tk.RIGHT)

        f2 = ttk.LabelFrame(self, text="Configuration", padding=10)
        f2.pack(fill=tk.X, **pad)
        grid = ttk.Frame(f2)
        grid.pack(fill=tk.X)

        ttk.Label(grid, text="Mode:").grid(row=0, column=0, sticky=tk.W, **pad)
        self.use_ai = tk.BooleanVar(value=HAS_AI)
        ttk.Checkbutton(grid, text="Use AI (requires API key in .env)", variable=self.use_ai).grid(row=0, column=1, columnspan=3, sticky=tk.W, **pad)

        ttk.Label(grid, text="Theme:").grid(row=1, column=0, sticky=tk.W, **pad)
        self.theme = tk.StringVar(value="creative")
        ttk.Combobox(grid, textvariable=self.theme, values=["professional", "creative", "minimal"], state="readonly", width=20).grid(row=1, column=1, sticky=tk.W, **pad)

        ttk.Label(grid, text="Voice Style:").grid(row=1, column=2, sticky=tk.W, **pad)
        self.voice = tk.StringVar(value="enthusiastic")
        ttk.Combobox(grid, textvariable=self.voice, values=["neutral", "enthusiastic", "formal"], state="readonly", width=16).grid(row=1, column=3, sticky=tk.W, **pad)

        ttk.Label(grid, text="Language:").grid(row=2, column=0, sticky=tk.W, **pad)
        self.lang_var = tk.StringVar(value="en")
        self.lang_combo = ttk.Combobox(grid, textvariable=self.lang_var, values=[f"{k} - {v}" for k, v in LANG_LABELS.items()], state="readonly", width=20)
        self.lang_combo.grid(row=2, column=1, sticky=tk.W, **pad)
        self.lang_combo.bind("<<ComboboxSelected>>", self.on_lang_change)

        ttk.Label(grid, text="Voice:").grid(row=2, column=2, sticky=tk.W, **pad)
        self.voice_var = tk.StringVar()
        self.voice_combo = ttk.Combobox(grid, textvariable=self.voice_var, state="readonly", width=30)
        self.voice_combo.grid(row=2, column=3, sticky=tk.W, **pad)

        ttk.Label(grid, text="Speech Rate:").grid(row=3, column=0, sticky=tk.W, **pad)
        self.rate = tk.StringVar(value="+20%")
        ttk.Combobox(grid, textvariable=self.rate, values=["-20%", "-10%", "+0%", "+10%", "+20%", "+30%"], width=10).grid(row=3, column=1, sticky=tk.W, **pad)

        self.populate_voices("en")

        f3 = ttk.LabelFrame(self, text="Output", padding=10)
        f3.pack(fill=tk.X, **pad)
        row3 = ttk.Frame(f3)
        row3.pack(fill=tk.X)
        self.output_dir = tk.StringVar(value=os.path.abspath("output"))
        ttk.Entry(row3, textvariable=self.output_dir).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        ttk.Button(row3, text="Browse Output", command=self.browse_output).pack(side=tk.RIGHT)

        f4 = ttk.Frame(self)
        f4.pack(fill=tk.X, **pad)
        self.run_btn = ttk.Button(f4, text="Generate Video", command=self.toggle_run)
        self.run_btn.pack(side=tk.LEFT, **pad)
        self.progress = ttk.Progressbar(f4, mode="indeterminate")
        self.progress.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(8, 0))
        self.status_lbl = ttk.Label(f4, text="Ready")
        self.status_lbl.pack(side=tk.RIGHT, **pad)

        f5 = ttk.LabelFrame(self, text="Log", padding=5)
        f5.pack(fill=tk.BOTH, expand=True, **pad)
        self.log = tk.Text(f5, height=15, wrap=tk.WORD, state=tk.DISABLED, bg="#1e1e1e", fg="#d4d4d4", insertbackground="white")
        self.log.tag_configure("stdout", foreground="#d4d4d4")
        self.log.tag_configure("error", foreground="#f44747")
        scroll = ttk.Scrollbar(f5, orient=tk.VERTICAL, command=self.log.yview)
        self.log.configure(yscrollcommand=scroll.set)
        self.log.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

    def populate_voices(self, lang_code):
        voices = VOICES_BY_LANG.get(lang_code, ["en-GB-RyanNeural"])
        self.voice_combo["values"] = voices
        if voices:
            self.voice_var.set(voices[0])

    def on_lang_change(self, event=None):
        raw = self.lang_combo.get()
        code = raw.split(" - ")[0].strip() if " - " in raw else "en"
        self.populate_voices(code)

    def browse_pdf(self):
        path = filedialog.askopenfilename(filetypes=[("PDF files", "*.pdf")])
        if path:
            self.pdf_path.set(path)

    def browse_output(self):
        path = filedialog.askdirectory()
        if path:
            self.output_dir.set(path)

    def log_write(self, text, tag="stdout"):
        self.log.configure(state=tk.NORMAL)
        self.log.insert(tk.END, text, tag)
        self.log.see(tk.END)
        self.log.configure(state=tk.DISABLED)
        self.root.update_idletasks()

    def toggle_run(self):
        if self.running:
            return
        if not self.pdf_path.get():
            messagebox.showerror("Error", "Please select a PDF file.")
            return
        if self.use_ai.get() and not HAS_AI:
            messagebox.showerror("Error", "AI mode requires TOKEN set in .env file.")
            return
        self.running = True
        self.run_btn.configure(state=tk.DISABLED, text="Running...")
        self.progress.start()
        self.status_lbl.configure(text="Running...")
        self.log.configure(state=tk.NORMAL)
        self.log.delete(1.0, tk.END)
        self.log.configure(state=tk.DISABLED)
        threading.Thread(target=self.run_pipeline, daemon=True).start()

    def run_pipeline(self):
        try:
            config = VideoConfig(
                theme=self.theme.get(),
                voice_style=self.voice.get(),
            )
            pdf_path = self.pdf_path.get()
            output_dir = self.output_dir.get()
            os.makedirs(output_dir, exist_ok=True)

            raw_lang = self.lang_combo.get()
            lang_code = raw_lang.split(" - ")[0].strip() if " - " in raw_lang else "en"
            voice_name = self.voice_var.get()
            rate = self.rate.get()

            self.log_write("Extracting text from PDF...\n")
            doc = fitz.open(pdf_path)
            per_page = []
            for page in doc:
                t = page.get_text().strip()
                if t:
                    per_page.append(t)
            self.log_write(f"Extracted {len(per_page)} pages.\n")

            all_slides = []
            all_results = []
            theme_colors = dict(DEFAULT_COLORS)

            if self.use_ai.get():
                self.log_write("AI mode: generating content via API...\n")
                chunk_size = 100000
                full_text = "\n\n".join(per_page)
                chunks = textwrap.wrap(full_text, chunk_size, break_long_words=False)
                for idx, chunk in enumerate(chunks):
                    self.log_write(f"  Chunk {idx+1}/{len(chunks)}...\n")
                    theme_desc = {"professional": "formal, corporate style with clean design", "creative": "vibrant, engaging style with dynamic elements", "minimal": "clean, simple style with focus on key content"}.get(config.theme, "professional style")
                    voice_desc = {"neutral": "balanced and clear", "enthusiastic": "energetic and engaging", "formal": "serious and professional"}.get(config.voice_style, "clear and professional")
                    prompt = (
                        f"Generate a structured presentation based on the following content. "
                        f"Use a {theme_desc} visual approach and a {voice_desc} tone for narration.\n\n"
                        "Create a JSON with these keys:\n"
                        "1. 'slides': list of objects with 'title', 'content', 'key_points' (list of bullet points), "
                        "and 'voice_over' (narration script for this specific slide)\n"
                        "2. 'theme_colors': suggested color scheme (primary, secondary, accent, background, text)\n\n"
                        f"Content:\n{chunk}\n\nRespond with valid JSON only."
                    )
                    resp = client.chat.completions.create(
                        model="deepseek-chat",
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.3,
                        max_tokens=16000
                    ).choices[0].message.content.strip()
                    if resp.startswith("```json"):
                        resp = resp.lstrip("```json").rstrip("```").strip()
                    elif resp.startswith("```"):
                        resp = resp.lstrip("```").rstrip("```").strip()
                    parsed = json.loads(resp)
                    chunk_data = SlideChunk(**parsed)
                    if chunk_data.theme_colors:
                        theme_colors = chunk_data.theme_colors
                    all_results.append(chunk_data)
                    all_slides.extend(chunk_data.slides)
                    self.log_write(f"  -> {len(chunk_data.slides)} slides\n")
            else:
                self.log_write("Direct mode: using page text as slides (no API key needed).\n")
                for i, page_text in enumerate(per_page):
                    lines = [l.strip() for l in page_text.split("\n") if l.strip()]
                    title = lines[0][:80] if lines else f"Page {i+1}"
                    sentences = page_text.replace("\n", " ").split(". ")
                    key_points = [s.strip() + "." for s in sentences if len(s.strip()) > 20][:6]
                    slide = SlideItem(
                        title=title,
                        content=page_text[:300].replace("\n", " "),
                        key_points=key_points,
                        voice_over=page_text[:2000],
                    )
                    all_slides.append(slide)
                chunk_data = SlideChunk(slides=all_slides, theme_colors=theme_colors)
                all_results = [chunk_data]
                self.log_write(f"  -> {len(all_slides)} slides created from {len(per_page)} pages\n")

            self.log_write("Generating presentation...\n")
            ppt_file = os.path.join(output_dir, "presentation.pptx")
            generate_presentation(all_results, ppt_file, config)

            self.log_write("Converting slides to images...\n")
            slide_imgs = slides_to_images(ppt_file, output_dir, slides_data=all_slides, theme_colors=theme_colors)

            self.log_write("Generating audio and assembling video...\n")
            clips = []
            for i, slide in enumerate(all_slides):
                self.log_write(f"  Slide {i+1}/{len(all_slides)}...\n")
                slide_img = slide_imgs[i] if i < len(slide_imgs) else slide_imgs[-1]
                audio_path = os.path.join(output_dir, f"{i}_audio.mp3")
                generate_audio(slide.voice_over, audio_path, voice=voice_name, rate=rate)
                audio = AudioFileClip(audio_path)
                clip = CompositeVideoClip([ImageClip(slide_img).set_duration(audio.duration)]).set_audio(audio)
                clips.append(clip)

            self.log_write("Concatenating and exporting video...\n")
            final = concatenate_videoclips(clips, method="compose")
            video_path = os.path.join(output_dir, "final_video.mp4")
            final.write_videofile(video_path, fps=24, logger=None)
            self.log_write(f"\nVideo saved to: {video_path}\nDone!\n")
            self.root.after(0, lambda: messagebox.showinfo("Success", f"Video generated:\n{video_path}"))

        except Exception as e:
            self.log_write(f"ERROR: {e}\n", "error")
            import traceback
            self.log_write(traceback.format_exc() + "\n", "error")
        finally:
            self.running = False
            self.root.after(0, self.reset_ui)

    def reset_ui(self):
        self.run_btn.configure(state=tk.NORMAL, text="Generate Video")
        self.progress.stop()
        self.status_lbl.configure(text="Ready")


if __name__ == "__main__":
    root = tk.Tk()
    app = App(root)
    root.mainloop()
