from __future__ import annotations
import io
import os
import wave
from typing import Optional
from google import genai
from google.genai import types
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False


class AudioService:
    """Generate audio and store it in S3."""

    def __init__(self, bucket: Optional[str] = None, prefix: str = "", storage: Optional[str] = None):
        # Support both 'bucket' and 'storage' parameter names (storage is for deployed code compatibility)
        bucket = bucket or storage
        if not bucket:
            raise ValueError("bucket is required for S3 storage")
        self.bucket = bucket
        self.prefix = prefix.rstrip("/") + "/" if prefix and not prefix.endswith("/") else prefix

    @staticmethod
    def _wave_file(file_obj, pcm, channels: int = 1, rate: int = 24000, sample_width: int = 2):
        """Write WAV data to a file-like object."""
        with wave.open(file_obj, "wb") as wf:
            wf.setnchannels(channels)
            wf.setsampwidth(sample_width)
            wf.setframerate(rate)
            wf.writeframes(pcm)

    def _get_fallback_api_key(self, lang: str, gemini_key: Optional[str]) -> Optional[str]:
        """
        Get the appropriate OpenAI fallback API key based on language.
        
        Args:
            lang: Language code ('english' or 'hindi')
            gemini_key: The Gemini API key that was attempted (to determine which OpenAI key to use)
            
        Returns:
            OpenAI API key string or None if not available
        """
        # Determine which OpenAI key to use based on which Gemini key was attempted
        if gemini_key == os.environ.get("GEMINI_API_KEY"):
            # English audio fallback
            return os.environ.get("OPENAI_API_KEY")
        elif gemini_key == os.environ.get("GEMINI_API_KEY2"):
            # Hindi audio fallback
            return os.environ.get("OPENAI_API_KEY2")
        else:
            # Fallback: try to determine by language
            if lang.lower() in ("english", "en"):
                return os.environ.get("OPENAI_API_KEY")
            elif lang.lower() in ("hindi", "hi"):
                return os.environ.get("OPENAI_API_KEY2")
        return None

    def _generate_with_openai(self, text: str, lang: str, api_key: str) -> bytes:
        """
        Generate audio using OpenAI TTS API with Indian accent instructions.
        
        Args:
            text: Text to convert to speech
            lang: Language ('english' or 'hindi')
            api_key: OpenAI API key
            
        Returns:
            PCM audio data as bytes
        """
        if not OPENAI_AVAILABLE:
            raise ImportError("OpenAI package not installed. Install with: pip install openai")
        
        # Map language to OpenAI voice and accent instructions
        # Keep instructions concise but effective - focus on key accent characteristics
        # Normalize language parameter to handle both "hi"/"en" and "hi-IN"/"en-IN" formats
        lang_normalized = lang.lower().split("-")[0]  # Extract base language code (e.g., "hi-IN" -> "hi")
        
        if lang_normalized in ("english", "en") or lang.lower() in ("english", "en", "en-in"):
            voice = "alloy"
            instructions = """Speak in Indian English only, using everyday Indian pronunciation and rhythm. Do not sound British or American. Avoid over-corrected English, elongated vowels, or clipped Western consonants; keep vowels flat and speech syllable-timed. Apply subtle phonetic grounding repeatedly: soften “th” to d/t when natural (this→dis, that→dat), allow occasional v/w interchange on emphasis, keep t/d dental and soft, and keep r light and neutral. Use a calm, engaged Indian news-explainer tone with gentle variation (slight lift on new ideas, soft fall at endings, brief pauses after facts). Speak slightly slower than conversation, unhurried, attentive, and human. Avoid drama, sing-song delivery, and announcer or radio-host energy. Prefer clarity and warmth over formal correctness."""
        elif lang_normalized in ("hindi", "hi") or lang.lower() in ("hindi", "hi", "hi-in"):
            voice = "nova"
            instructions = """Speak in North Indian Hindi (Hindustani) only, matching Delhi–UP urban Hindi. Do not sound South Indian, English-influenced, Urdu-heavy, or overly Sanskritised. Avoid South Indian vowel opening, syllable timing, or phonetic patterns. Keep vowels short, flat, and relaxed; never stretch or round them. Suppress retroflex heaviness—do not over-emphasise ट / ड / ण / ळ. Do not add extra vowels at word endings (सरकार, समस्या — not सरकारा). Maintain natural North-Indian schwa deletion (विकास → vikaas, समय → samay, not vikaasa / samaya). Avoid hard English “t/d” or breathy aspiration. Keep र soft and flowing, never rolled. Let Hindi flow by phrases, not equal syllables. Use a sweet, calm, human news-explainer tone with gentle variation (soft lift on new ideas, gentle settling at sentence ends, light emphasis on key words, short thoughtful pauses). Speak at a medium-slow, relaxed pace. Avoid Doordarshan formality, chanting, sing-song delivery, stiff articulation, or Bollywood drama. Prefer warmth and ease over sharp correctness so the voice remains comfortable for long listening."""
        else:
            voice = "alloy"
            instructions = None
        
        client = OpenAI(api_key=api_key)
        
        # Call API with instructions as direct parameter
        if instructions:
            response = client.audio.speech.create(
                model="gpt-4o-mini-tts",
                voice=voice,
                input=text,  # Only the actual text, not instructions
                instructions=instructions,  # Pass instructions directly
                response_format="pcm",  # Use PCM format to match Gemini output
            )
        else:
            response = client.audio.speech.create(
                model="gpt-4o-mini-tts",
                voice=voice,
                input=text,
                response_format="pcm",
            )
        
        # Read the audio data
        audio_data = response.content
        return audio_data

    def _is_rate_limit_error(self, error: Exception) -> bool:
        """
        Check if an error is a rate limit or quota error.
        
        Args:
            error: Exception to check
            
        Returns:
            True if it's a rate limit/quota error, False otherwise
        """
        error_str = str(error).lower()
        error_type = type(error).__name__.lower()
        
        # Check for common rate limit indicators
        rate_limit_indicators = [
            "rate limit",
            "quota",
            "quota exceeded",
            "429",
            "resource_exhausted",
            "too many requests",
            "rate_limit_exceeded"
        ]
        
        return any(indicator in error_str for indicator in rate_limit_indicators) or \
               any(indicator in error_type for indicator in rate_limit_indicators)

    def _validate_response(self, response) -> bool:
        """
        Validate that the response has valid audio data.
        
        Args:
            response: Response object from Gemini API
            
        Returns:
            True if response is valid, False otherwise
        """
        try:
            if not response or not hasattr(response, 'candidates'):
                return False
            
            if not response.candidates or len(response.candidates) == 0:
                return False
            
            candidate = response.candidates[0]
            if not hasattr(candidate, 'content') or candidate.content is None:
                return False
            
            if not hasattr(candidate.content, 'parts') or not candidate.content.parts:
                return False
            
            if not hasattr(candidate.content.parts[0], 'inline_data'):
                return False
            
            if not hasattr(candidate.content.parts[0].inline_data, 'data'):
                return False
            
            return True
        except Exception:
            return False

    def _create_openai_wrapper(self, audio_data: bytes):
        """
        Create a wrapper object that mimics Gemini response structure.
        
        Args:
            audio_data: Audio data bytes from OpenAI
            
        Returns:
            OpenAIResponseWrapper object
        """
        class OpenAIResponseWrapper:
            def __init__(self, audio_data: bytes):
                self.candidates = [type('obj', (object,), {
                    'content': type('obj', (object,), {
                        'parts': [type('obj', (object,), {
                            'inline_data': type('obj', (object,), {
                                'data': audio_data
                            })()
                        })()]
                    })()
                })()]
        
        return OpenAIResponseWrapper(audio_data)

    def _try_openai_fallback(self, text: str, lang: str, api_key: str, reason: str):
        """
        Attempt to generate audio using OpenAI as fallback.
        
        Args:
            text: Text to convert to speech
            lang: Language ('english' or 'hindi')
            api_key: Original Gemini API key (to determine which OpenAI key to use)
            reason: Reason for fallback (for logging)
            
        Returns:
            OpenAIResponseWrapper object with audio data
        """
        # Get the appropriate OpenAI key
        openai_key = self._get_fallback_api_key(lang, api_key)
        if not openai_key:
            raise ValueError(f"No OpenAI fallback key available for language '{lang}'")
        
        audio_data = self._generate_with_openai(text, lang, openai_key)
        return self._create_openai_wrapper(audio_data)

    def generate(self, text: str, lang: str, api_key=os.environ.get("GEMINI_API_KEY")):
        """
        Generate audio using Gemini API with OpenAI fallback.
        
        Args:
            text: Text to convert to speech
            lang: Language ('english' or 'hindi')
            api_key: Gemini API key to try first
            
        Returns:
            Response object (Gemini response or OpenAI-compatible response wrapper)
        """
        # Try Gemini first
        try:
            # Map language parameter to BCP-47 codes
            bcp47_map = {
                "english": "en-IN",
                "en-IN": "en-IN",
                "hindi": "hi-IN",
                "hi-IN": "hi-IN"
            }
            bcp47_code = bcp47_map.get(lang, "en-IN")  # Default to en-IN

            contents = f"""You are a person reading the news in an app. Listeners are from India. Be clearer so that users can understand better.
            Audio language is in {bcp47_code}
            Content:
            {text}"""
            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(
                model="gemini-2.5-flash-preview-tts",
                contents=contents,
                config=types.GenerateContentConfig(
                    response_modalities=["AUDIO"],
                    speech_config=types.SpeechConfig(
                        voice_config=types.VoiceConfig(
                            prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                voice_name="Zephyr"
                            )
                        )
                    ),
                ),
            )
            
            if not self._validate_response(response):
                return self._try_openai_fallback(text, lang, api_key, "Gemini returned invalid response")
            
            return response
        except Exception as gemini_error:
            try:
                return self._try_openai_fallback(text, lang, api_key, f"Gemini API error: {gemini_error}")
            except Exception as openai_error:
                print(f"[ERROR] Audio generation failed for {lang} (Gemini: {gemini_error}, OpenAI: {openai_error})")
                raise gemini_error

    def save(self, response, file_name):
        # Validate response structure before accessing nested attributes
        if not self._validate_response(response):
            raise ValueError("Invalid response: response structure is invalid or content is None")
        
        data = response.candidates[0].content.parts[0].inline_data.data
        buffer = io.BytesIO()
        self._wave_file(buffer, data)
        buffer.seek(0)
        s3_file_path = self._upload_s3(buffer, file_name)
        return s3_file_path

    def _upload_s3(self, buffer, filename) -> str:
        import boto3
        if not self.bucket:
            raise ValueError("bucket required for s3 storage")
        s3 = boto3.client("s3", aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),
                          aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY'))
        s3.upload_fileobj(buffer, self.bucket, self.prefix + os.path.basename(filename))
        return self.bucket + '/' + self.prefix + os.path.basename(filename)

    def generate_and_save(self, text: str, file_name: str, lang:str, api_key:str=os.environ.get("GEMINI_API_KEY")):
        max_retries = 2
        last_error = None
        
        for attempt in range(max_retries):
            try:
                response = self.generate(text, lang=lang, api_key=api_key)
                
                # Validate response before trying to save
                if not self._validate_response(response):
                    raise ValueError("Invalid response: response structure is invalid or content is None")
                
                # If we get here, the response structure is valid, try to save
                save_file = self.save(response, file_name)
                return response, save_file
                
            except Exception as e:
                last_error = e
        
        # If we get here, all retries failed
        raise Exception(f"Failed to generate and save audio after {max_retries} attempts. Last error: {last_error}")
