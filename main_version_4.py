import fitz
from pptx import Presentation
from pptx.util import Inches, Pt
from moviepy.editor import VideoFileClip, ImageClip, CompositeVideoClip, concatenate_videoclips, AudioFileClip
from pydantic import BaseModel, Field, ValidationError
import tempfile
import os
import json
import textwrap
from typing import List, Optional, Dict
from dotenv import load_dotenv
from presentation import generate_presentation, slides_to_images
from audio import generate_audio
import time

load_dotenv()

HAS_AI = bool(os.getenv("TOKEN"))
if HAS_AI:
    from openai import OpenAI
    client = OpenAI(
        base_url=os.getenv("ENDPOINT", "https://api.deepseek.com"),
        api_key=os.getenv("TOKEN"),
    )

class SlideItem(BaseModel):
    title: str
    content: str
    key_points: List[str] = Field(default_factory=list)
    voice_over: str

class ShortVideoSegment(BaseModel):
    title: str
    content: str
    script: str
    duration: float = 60.0

class SlideChunk(BaseModel):
    slides: List[SlideItem]
    short_segments: List[ShortVideoSegment] = Field(default_factory=list)
    theme_colors: Optional[Dict[str, str]] = None

class VideoConfig(BaseModel):
    theme: str = "professional"
    presenter_type: str = "human"
    language: str = "en"
    voice_style: str = "neutral"
    include_background_music: bool = True
    resolution: str = "1080p"
    aspect_ratio: str = "16:9"
    animation_level: str = "moderate"

DEFAULT_COLORS = {"primary": "1F497D", "secondary": "4F81BD", "accent": "C0504D", "background": "FFFFFF", "text": "000000"}

def extract_text_from_pdf(pdf_path):
    print("Extracting text from PDF...")
    doc = fitz.open(pdf_path)
    pages = []
    for page in doc:
        t = page.get_text().strip()
        if t:
            pages.append(t)
    print(f"Extracted {len(pages)} pages.")
    return pages

def generate_with_ai(pages, config):
    print("Generating structured content with DeepSeek...")
    chunk_size = 100000
    full_text = "\n\n".join(pages)
    chunks = textwrap.wrap(full_text, chunk_size, break_long_words=False)
    all_slides, all_results = [], []
    theme_colors = dict(DEFAULT_COLORS)

    for chunk in chunks:
        theme_desc = {"professional": "formal, corporate style with clean design", "creative": "vibrant, engaging style with dynamic elements", "minimal": "clean, simple style with focus on key content"}.get(config.theme, "professional style")
        voice_desc = {"neutral": "balanced and clear", "enthusiastic": "energetic and engaging", "formal": "serious and professional"}.get(config.voice_style, "clear and professional")
        prompt = (
            f"Generate a structured presentation based on the following content. "
            f"Use a {theme_desc} visual approach and a {voice_desc} tone for narration.\n\n"
            "Create a JSON with these keys:\n"
            "1. 'slides': list of objects with 'title', 'content', 'key_points' (list of bullet points), "
            "and 'voice_over' (narration script for this specific slide)\n"
            "2. 'short_segments': 3-5 stand-alone segments for short-form videos (under 2 minutes each) "
            "with 'title', 'content', 'script', and 'duration' (in seconds) fields\n"
            "3. 'theme_colors': suggested color scheme (primary, secondary, accent, background, text)\n\n"
            f"Content:\n{chunk}\n\nRespond with valid JSON only."
        )
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=16000
        ).choices[0].message.content.strip()

        if response.startswith("```json"):
            response = response.lstrip("```json").rstrip("```").strip()
        elif response.startswith("```"):
            response = response.lstrip("```").rstrip("```").strip()

        parsed = json.loads(response)
        validated = SlideChunk(**parsed)
        if validated.theme_colors:
            theme_colors = validated.theme_colors
        all_results.append(validated)
        all_slides.extend(validated.slides)

    return all_slides, all_results, theme_colors

def generate_direct(pages):
    print("Direct mode: creating slides from page text (no API key).")
    slides = []
    for i, page_text in enumerate(pages):
        lines = [l.strip() for l in page_text.split("\n") if l.strip()]
        title = lines[0][:80] if lines else f"Page {i+1}"
        sentences = page_text.replace("\n", " ").split(". ")
        key_points = [s.strip() + "." for s in sentences if len(s.strip()) > 20][:6]
        slides.append(SlideItem(
            title=title,
            content=page_text[:300].replace("\n", " "),
            key_points=key_points,
            voice_over=page_text[:2000],
        ))
    result = SlideChunk(slides=slides, theme_colors=DEFAULT_COLORS)
    return slides, [result], DEFAULT_COLORS

def main():
    args = Args()
    config = VideoConfig(
        theme=args.theme,
        language=args.language,
        voice_style=args.voice,
        include_background_music=bool(args.music)
    )

    pages = extract_text_from_pdf(args.pdf_path)

    if HAS_AI and args.use_ai:
        all_slides, results, theme_colors = generate_with_ai(pages, config)
    else:
        all_slides, results, theme_colors = generate_direct(pages)

    print(f"Total slides: {len(all_slides)}")

    ppt_file = "presentation.pptx"
    generate_presentation(results, ppt_file, config)

    with tempfile.TemporaryDirectory() as tmpdir:
        slide_imgs = slides_to_images(ppt_file, tmpdir, slides_data=all_slides, theme_colors=theme_colors)

        clips = []
        for i, slide in enumerate(all_slides):
            slide_img = slide_imgs[i]
            audio_path = f"{i}_audio.mp3"
            generate_audio(slide.voice_over, audio_path)
            audio = AudioFileClip(audio_path)
            image_clip = ImageClip(slide_img).set_duration(audio.duration)
            final_clip = CompositeVideoClip([image_clip]).set_audio(audio)
            clips.append(final_clip)

        final_video = concatenate_videoclips(clips, method="compose")
        final_video.write_videofile("final_video.mp4", fps=24)
        print("Video exported")

class Args:
    pdf_path = 'contents/Basics_of_Machine_Learning_Notes.pdf'
    avatar = '/content/man.png'
    music = '/contents/breath-of-life_10-minutes-320859.mp3'
    theme = 'creative'
    language = 'en'
    voice = 'enthusiastic'
    output = '/content/output/'
    api_path = ''
    use_ai = True

if __name__ == "__main__":
    main()
