import os
import json
import fitz
import requests
from gtts import gTTS
import sounddevice as sd
from scipy.io.wavfile import write
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.formatters import TextFormatter
from faster_whisper import WhisperModel
from fpdf import FPDF
import pytesseract
from PIL import Image
import pdf2image
import re
import yt_dlp
from flask import Flask, request, jsonify, render_template
import threading
import logging
import hashlib
import time
import ffmpeg

app = Flask(__name__)


logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

API_KEY = "your api key"  
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={API_KEY}"
HEADERS = {"Content-Type": "application/json"}
BOT_NAME = "Silk"


TTS_CACHE = {}
tts_lock = threading.Lock()


PREDEFINED_RESPONSES = {
    "who made you": "Mujhe Ashwinder Pal Singh ne banaya hai.",
    "आपके निर्माता का नाम क्या है": "Mere creator ka naam Ashwinder Pal Singh hai.",
    "what's your creator's name": "Mere creator ka naam Ashwinder Pal Singh hai.",
    "tell me about yourself": "Main ek AI assistant hoon – naam hai Silk, aur mujhe Ashwinder Pal Singh ne banaya hai tumhari madad ke liye.",
    "what is your name": "Mera naam Silk hai, banaaya gaya Ashwinder Pal Singh ke dwara.",
    "आपका नाम क्या है": "Mera naam Silk hai, jise Ashwinder Pal Singh ne design kiya hai.",
    "can you speak hindi": "Bilkul! Main Hindi mein baat kar sakta hoon. Bolo kya madad chahiye?",
    "क्या आप हिंदी बोल सकते हैं": "Haan haan, Hindi meri bhi language hai! Aap kya poochhna chahenge?",
    "can you help with studies": "100%! Bas topic batao, main notes, question paper ya quiz sab ready kar dunga.",
    "क्या आप पढ़ाई में मदद कर सकते हैं": "Haanji, padhai mein full support milega. Notes chahiye ya sawal? Bas mujhe batao.",
    "what can you do": "Main tumhare liye notes, quiz, question paper bana sakta hoon, videos ya documents summarize kar sakta hoon aur bhi bahut kuch!",
    "how do you work": "Main AI models jese Gemini ka use karta hoon, input padhta hoon aur smart response generate karta hoon – simple!",
    "kya haal hai": "Sab badhiya! Tumhara kya scene hai?",
    "kya kar rahe ho": "Tumhari help ke liye standby hoon. Tum kya kar rahe ho?",
    "tum kaun ho": "Main Silk hoon, tumhara study buddy AI.",
    "kya tum mere dost banoge": "Pakka! Main toh already tumhara virtual dost hoon.",
    "tum kaha rehte ho": "Main online hoon, cloud ke upar! Internet se chalta hoon.",
    "tum kis language mein baat karte ho": "Main Hindi, English, aur Hinglish sab mein baat kar sakta hoon.",
    "aaj kya din hai": "Main calendar dekh sakta hoon, ek sec...",
    "tum mujhe padha sakte ho": "Bilkul! Tum topic batao, main explain kar deta hoon easy words mein.",
    "tum quiz bana sakte ho": "Haan, tumhare liye topic-wise quiz generate kar sakta hoon.",
    "tum notes bana sakte ho": "Yes, tumhare liye short ya detailed notes dono bana sakta hoon.",
    "kya tum jokes bhi sunate ho": "Haan haan, padhai ke saath thoda masti bhi honi chahiye!"
}

def speak(text):
    try:
        text_hash = hashlib.md5(text.encode()).hexdigest()
        audio_path = os.path.join(os.getcwd(), f"tts_{text_hash}.mp3")

        with tts_lock:
            if text_hash in TTS_CACHE and os.path.exists(audio_path):
                logging.debug(f"Using cached TTS for text: {text[:50]}...")
                return text

            tts = gTTS(text=text, lang='en')
            tts.save(audio_path)
            TTS_CACHE[text_hash] = audio_path
            logging.debug(f"Generated TTS audio: {audio_path}")
        return text
    except Exception as e:
        logging.error(f"TTS error: {e}")
        return text

def record_audio(filename="temp.wav", duration=6, fs=16000):
    try:
        recording = sd.rec(int(duration * fs), samplerate=fs, channels=1)
        sd.wait()
        write(filename, fs, recording)
        return filename
    except Exception as e:
        logging.error(f"Audio recording error: {e}")
        return None

def transcribe_audio(file_path):
    try:
        model = WhisperModel("base", device="cpu", compute_type="int8")
        segments, _ = model.transcribe(file_path, language=None)
        transcript = " ".join([segment.text.strip() for segment in segments if segment.text.strip()])
        logging.debug(f"Transcribed audio: {transcript[:100]}...")
        return transcript if transcript else None
    except Exception as e:
        logging.error(f"Audio transcription error: {e}")
        return None

def convert_to_wav(input_path, output_path):
    try:
        stream = ffmpeg.input(input_path)
        stream = ffmpeg.output(stream, output_path, format='wav', acodec='pcm_s16le', ar=16000)
        ffmpeg.run(stream, overwrite_output=True)
        logging.debug(f"Converted {input_path} to {output_path}")
        return output_path
    except Exception as e:
        logging.error(f"File conversion error: {e}")
        return None

def download_youtube_audio(url, output_path="youtube_audio"):
    try:
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': output_path,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'wav',
                'preferredquality': '192',
            }],
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        output_file = output_path + '.wav'
        logging.debug(f"YouTube audio downloaded: {output_file}")
        return output_file
    except Exception as e:
        logging.error(f"YouTube download error: {e}")
        return None

def get_youtube_transcript(url):
    if not url or not isinstance(url, str):
        logging.error("Invalid YouTube URL: empty or not a string")
        return None
    try:
        video_id = None
        patterns = [
            r'(?:v=|youtu\.be/|youtube\.com/watch\?v=)([0-9A-Za-z_-]{11})',
            r'(?:youtube\.com/shorts/)([0-9A-Za-z_-]{11})',
            r'(?:youtube\.com/embed/)([0-9A-Za-z_-]{11})'
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                video_id = match.group(1)
                break
        if not video_id:
            raise ValueError("Invalid YouTube URL")

        try:
            transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=["en", "hi", "en-US", "en-GB"])
            formatted_transcript = TextFormatter().format_transcript(transcript)
            logging.debug(f"YouTube transcript extracted: {formatted_transcript[:100]}...")
            return formatted_transcript
        except Exception as e:
            logging.warning(f"YouTube transcript not available: {e}")
            audio_file = download_youtube_audio(url)
            if audio_file:
                transcript = transcribe_audio(audio_file)
                os.remove(audio_file) if os.path.exists(audio_file) else None
                return transcript
            return None
    except Exception as e:
        logging.error(f"YouTube processing error: {e}")
        return None

def ask_gemini(prompt):
    try:
        data = {"contents": [{"parts": [{"text": prompt}]}]}
        response = requests.post(GEMINI_URL, headers=HEADERS, json=data)
        if response.ok:
            result = response.json()
            text = result["candidates"][0]["content"]["parts"][0]["text"]
            logging.debug(f"Gemini response: {text[:100]}...")
            return text
        logging.error(f"Gemini API error: HTTP {response.status_code} - {response.text}")
        return "Gemini couldn't process that."
    except Exception as e:
        logging.error(f"Gemini API error: {e}")
        return "Something went wrong."

def extract_text_from_pdf(pdf_path):
    try:
        text = ""
        with fitz.open(pdf_path) as doc:
            for page in doc:
                text += page.get_text() or ""
        text = text.strip()
        if not text:
            text = ocr_pdf(pdf_path)
        logging.debug(f"PDF extracted text: {text[:100]}...")
        return text if text else None
    except Exception as e:
        logging.error(f"PDF extraction error: {e}")
        return None

def extract_text_from_txt(txt_path):
    try:
        with open(txt_path, 'r', encoding='utf-8') as file:
            text = file.read().strip()
        logging.debug(f"TXT extracted text: {text[:100]}...")
        return text if text else None
    except Exception as e:
        logging.error(f"Text file extraction error: {e}")
        return None

def extract_text_from_audio(audio_path):
    try:
        if not audio_path.endswith('.wav'):
            wav_path = audio_path.rsplit('.', 1)[0] + '_converted.wav'
            audio_path = convert_to_wav(audio_path, wav_path)
        transcript = transcribe_audio(audio_path)
        os.remove(audio_path) if os.path.exists(audio_path) else None
        logging.debug(f"Audio extracted text: {transcript[:100]}..." if transcript else "No transcript")
        return transcript
    except Exception as e:
        logging.error(f"Audio extraction error: {e}")
        return None

def ocr_pdf(pdf_path):
    try:
        images = pdf2image.convert_from_path(pdf_path)
        text = "".join(pytesseract.image_to_string(img) for img in images).strip()
        logging.debug(f"OCR extracted text: {text[:100]}...")
        return text if text else ""
    except Exception as e:
        logging.error(f"PDF OCR error: {e}")
        return ""

def save_to_pdf(title, content, filename="output.pdf"):
    try:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", "B", 14)
        pdf.cell(0, 10, title, ln=True)
        pdf.set_font("Arial", "", 12)
        for line in content.split('\n'):
            pdf.multi_cell(0, 10, line)
        path = os.path.join(os.getcwd(), filename)
        pdf.output(path)
        logging.debug(f"PDF saved to: {path}")
        return path
    except Exception as e:
        logging.error(f"PDF save error: {e}")
        return None

def clean_text(text):
    if not text:
        return ""
    # Remove markdown artifacts
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)  # Remove **bold**
    text = re.sub(r'__([^_]+)__', r'\1', text)     # Remove __underline__
    text = re.sub(r'\*([^*]+)\*', r'\1', text)     # Remove *italic*
    text = re.sub(r'#+ ', '', text)                # Remove markdown headers
    replacements = {
        "→": "->", "←": "<-", "⇒": "=>", "⇐": "<=", "✓": "[yes]", "✔": "[yes]",
        "✗": "[no]", "•": "-", "“": '"', "”": '"', "‘": "'", "’": "'", "–": "-", "—": "-", "…": "...",
    }
    for uni_char, ascii_equiv in replacements.items():
        text = text.replace(uni_char, ascii_equiv)
    text = text.encode("latin-1", errors="ignore").decode("latin-1").strip()
    logging.debug(f"Cleaned text: {text[:100]}...")
    return text

def generate_notes(content):
    if not content:
        logging.error("Empty content provided for notes generation")
        return "No content provided to generate notes."
    prompt = f"""
    Create detailed, easy-to-understand study notes based strictly on the following content. 
    Ensure all key points are covered, organized into sections with headings, and avoid adding unrelated information.
    Content: {content}
    """
    notes = ask_gemini(prompt)
    logging.debug(f"Generated notes: {notes[:100]}...")
    return clean_text(notes)

def generate_question_paper(content):
    if not content:
        logging.error("Empty content provided for question paper generation")
        return "No content provided to generate question paper.", "Answer key not generated."
    prompt = f"""
    You are an exam assistant for Thapar Institute of Engineering and Technology. 
    Based strictly on the following content, generate a structured question paper with three sections:
    - Short Answer Questions (10)
    - Medium Answer Questions (10)
    - Long Answer Questions (10)
    Print all questions first, followed by the answers at the end under 'Answer Key'.
    Add the heading: Thapar Institute of Engineering and Technology
    Subheading: Sample Question Paper
    Format: [QUESTIONS] === Answer Key === [ANSWERS]
    Ensure questions are directly derived from the content and avoid unrelated topics.
    Content: {content}
    """
    full_output = ask_gemini(prompt)
    logging.debug(f"Generated question paper: {full_output[:100]}...")
    if "=== Answer Key ===" in full_output:
        parts = full_output.split("=== Answer Key ===")
        return clean_text(parts[0].strip()), clean_text(parts[1].strip())
    return clean_text(full_output), "Answer key not found."

def generate_quiz(content):
    if not content:
        logging.error("Empty content provided for quiz generation")
        return "No content provided to generate quiz.", "Answer key not generated."
    prompt = f"""
    Create a multiple-choice quiz with 10 questions based strictly on the following content. 
    Each question must have 4 answer options, with one correct answer. 
    Ensure questions and options are directly derived from the content and avoid unrelated topics.
    Format the output as:
    [QUIZ]
    1. Question text
       a) Option 1
       b) Option 2
       c) Option 3
       d) Option 4
    ...
    === Answer Key ===
    1. Correct answer (e.g., a)
    ...
    Content: {content}
    """
    full_output = ask_gemini(prompt)
    logging.debug(f"Generated quiz: {full_output[:100]}...")
    if "=== Answer Key ===" in full_output:
        parts = full_output.split("=== Answer Key ===")
        return clean_text(parts[0].strip()), clean_text(parts[1].strip())
    return clean_text(full_output), "Answer key not found."

def summarize_text(content):
    if not content:
        logging.error("Empty content provided for summarization")
        return "No content provided to summarize."
    prompt = f"""
    Provide a concise summary (150-200 words) based strictly on the following content. 
    Focus on key points and avoid adding unrelated information.
    Content: {content}
    """
    summary = ask_gemini(prompt)
    logging.debug(f"Generated summary: {summary[:100]}...")
    return clean_text(summary)

@app.route('/')
def index():
    return render_template('geminitutor.html')

@app.route('/api/chat', methods=['POST'])
def chat():
    try:
        # Handle audio input
        if 'audio' in request.files:
            audio_file = request.files['audio']
            file_path = os.path.join(os.getcwd(), f"temp_audio_{int(time.time())}.wav")
            audio_file.save(file_path)
            transcribed_text = transcribe_audio(file_path)
            os.remove(file_path) if os.path.exists(file_path) else None
            if not transcribed_text:
                logging.error("Audio transcription failed")
                return jsonify({'response': speak("Could not transcribe audio."), 'transcribed': ''})

            logging.debug(f"Transcribed audio: {transcribed_text}")
            for key, value in PREDEFINED_RESPONSES.items():
                if key.lower() in transcribed_text.lower():
                    return jsonify({'response': speak(value), 'transcribed': transcribed_text})

            response = ask_gemini(transcribed_text)
            return jsonify({'response': speak(response), 'transcribed': transcribed_text})

        # Handle file upload
        if 'file' in request.files:
            file = request.files['file']
            action = request.form.get('action', '').lower()
            logging.debug(f"File upload: {file.filename}, Action: {action}")
            if not file.filename:
                logging.error("No file selected")
                return jsonify({'response': speak("No file selected.")})

            file_path = os.path.join(os.getcwd(), f"upload_{int(time.time())}_{file.filename}")
            file.save(file_path)

            content = None
            if file.filename.endswith('.pdf'):
                content = extract_text_from_pdf(file_path)
            elif file.filename.endswith('.txt'):
                content = extract_text_from_txt(file_path)
            elif file.filename.endswith(('.mp3', '.mp4', '.wav')):
                content = extract_text_from_audio(file_path)
            else:
                os.remove(file_path) if os.path.exists(file_path) else None
                logging.error(f"Unsupported file format: {file.filename}")
                return jsonify({'response': speak("Unsupported file format. Use PDF, TXT, MP3, MP4, or WAV.")})

            if not content:
                os.remove(file_path) if os.path.exists(file_path) else None
                logging.error(f"No content extracted from file: {file.filename}")
                return jsonify({'response': speak("Could not extract content from file.")})

            if action == "generate notes":
                notes = generate_notes(content)
                path = save_to_pdf("Generated Notes", notes, file.filename.rsplit('.', 1)[0] + "_notes.pdf")
                os.remove(file_path) if os.path.exists(file_path) else None
                if path:
                    return jsonify({'response': speak(f"Notes generated and saved to {path}"), 'notes': notes, 'input_content': content[:200]})
                return jsonify({'response': speak("Failed to save notes."), 'notes': notes, 'input_content': content[:200]})

            elif action == "generate question paper":
                qp, ak = generate_question_paper(content)
                filename = file.filename.rsplit('.', 1)[0] + "_qpaper.pdf"
                path = save_to_pdf("Question Paper", f"{qp}\n\n=== Answer Key ===\n{ak}", filename)
                os.remove(file_path) if os.path.exists(file_path) else None
                if path:
                    return jsonify({'response': speak(f"Question paper saved to {path}"), 'qp': qp, 'ak': ak, 'input_content': content[:200]})
                return jsonify({'response': speak("Failed to save question paper."), 'qp': qp, 'ak': ak, 'input_content': content[:200]})

            elif action == "generate quiz":
                quiz, quiz_ak = generate_quiz(content)
                path = save_to_pdf("Generated Quiz", f"{quiz}\n\n=== Answer Key ===\n{quiz_ak}", file.filename.rsplit('.', 1)[0] + "_quiz.pdf")
                os.remove(file_path) if os.path.exists(file_path) else None
                if path:
                    return jsonify({'response': speak(f"Quiz generated and saved to {path}"), 'quiz': quiz, 'quiz_ak': quiz_ak, 'input_content': content[:200]})
                return jsonify({'response': speak("Failed to save quiz."), 'quiz': quiz, 'quiz_ak': quiz_ak, 'input_content': content[:200]})

            elif action == "summarize text":
                summary = summarize_text(content)
                os.remove(file_path) if os.path.exists(file_path) else None
                return jsonify({'response': speak("Summary generated."), 'summary': summary, 'input_content': content[:200]})

            os.remove(file_path) if os.path.exists(file_path) else None
            logging.error(f"Invalid action: {action}")
            return jsonify({'response': speak("Invalid action specified.")})

        # Handle JSON input
        data = request.json
        user_input = data.get('input', '').strip()
        url = data.get('url', '') if 'summarize youtube' in user_input.lower() else None
        logging.debug(f"JSON input: {user_input}, URL: {url}")

        if not user_input:
            logging.error("Empty input provided")
            return jsonify({'response': speak("Please provide input.")})

        for key, value in PREDEFINED_RESPONSES.items():
            if key.lower() in user_input.lower():
                return jsonify({'response': speak(value)})

        if "who made you" in user_input.lower():
            return jsonify({'response': speak("I was created by Ashwinder Pal Singh.")})

        if "summarize youtube" in user_input.lower():
            if not url:
                logging.error("No YouTube URL provided")
                return jsonify({'response': speak("Please provide a valid YouTube URL.")})
            content = get_youtube_transcript(url)
            if content:
                summary = summarize_text(content)
                return jsonify({'response': speak(summary), 'summary': summary, 'input_content': content[:200]})
            logging.error(f"Failed to retrieve YouTube content for URL: {url}")
            return jsonify({'response': speak("Could not retrieve content from YouTube.")})

        if "generate notes" in user_input.lower():
            content = data.get('content', '').strip()
            if not content:
                logging.error("No content provided for notes")
                return jsonify({'response': speak("Please provide content for notes.")})
            notes = generate_notes(content)
            path = save_to_pdf("Generated Notes", notes, content[:10] + "_notes.pdf")
            if path:
                return jsonify({'response': speak(f"Notes generated and saved to {path}"), 'notes': notes, 'input_content': content[:200]})
            return jsonify({'response': speak("Failed to save notes."), 'notes': notes, 'input_content': content[:200]})

        if "generate question paper" in user_input.lower():
            source = data.get('source', '').strip()
            if not source:
                logging.error("No source provided for question paper")
                return jsonify({'response': speak("Please provide a source for the question paper.")})
            content = get_youtube_transcript(source)
            if content:
                qp, ak = generate_question_paper(content)
                filename = f"{source[:10]}_qpaper.pdf"
                path = save_to_pdf("Question Paper", f"{qp}\n\n=== Answer Key ===\n{ak}", filename)
                if path:
                    return jsonify({'response': speak(f"Question paper saved to {path}"), 'qp': qp, 'ak': ak, 'input_content': content[:200]})
                return jsonify({'response': speak("Failed to save question paper."), 'qp': qp, 'ak': ak, 'input_content': content[:200]})
            logging.error(f"Failed to retrieve content for source: {source}")
            return jsonify({'response': speak("Could not process source.")})

        if "generate quiz" in user_input.lower():
            content = data.get('content', '').strip()
            if not content:
                logging.error("No content provided for quiz")
                return jsonify({'response': speak("Please provide content for quiz.")})
            quiz, quiz_ak = generate_quiz(content)
            path = save_to_pdf("Generated Quiz", f"{quiz}\n\n=== Answer Key ===\n{quiz_ak}", content[:10] + "_quiz.pdf")
            if path:
                return jsonify({'response': speak(f"Quiz generated and saved to {path}"), 'quiz': quiz, 'quiz_ak': quiz_ak, 'input_content': content[:200]})
            return jsonify({'response': speak("Failed to save quiz."), 'quiz': quiz, 'quiz_ak': quiz_ak, 'input_content': content[:200]})

        if "summarize text" in user_input.lower():
            content = data.get('content', '').strip()
            if not content:
                logging.error("No content provided for summarization")
                return jsonify({'response': speak("Please provide content to summarize.")})
            summary = summarize_text(content)
            return jsonify({'response': speak("Summary generated."), 'summary': summary, 'input_content': content[:200]})

        response = ask_gemini(user_input)
        return jsonify({'response': speak(response)})
    except Exception as e:
        logging.error(f"Chat endpoint error: {e}")
        return jsonify({'response': speak("Something went wrong.")})

if __name__ == "__main__":
    app.run(debug=True)
