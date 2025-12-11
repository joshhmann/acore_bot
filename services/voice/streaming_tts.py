"""Streaming TTS Processor - Processes LLM streams and converts to audio in real-time.

This service allows the bot to speak LLM responses as they're being generated,
reducing perceived latency for voice responses.
"""

import asyncio
import logging
from typing import AsyncIterator, Optional
from pathlib import Path
import uuid

logger = logging.getLogger(__name__)


class StreamingTTSProcessor:
    """Processes streaming text and converts to TTS audio in real-time.
    
    This class handles:
    - Buffering text chunks into complete sentences
    - Generating TTS audio for each sentence
    - Playing audio through Discord voice client
    - Applying RVC voice conversion if enabled
    """
    
    def __init__(self, tts_service, rvc_service=None):
        """Initialize streaming TTS processor.
        
        Args:
            tts_service: TTSService instance for audio generation
            rvc_service: Optional RVCService for voice conversion
        """
        self.tts = tts_service
        self.rvc = rvc_service
        self.sentence_endings = {'.', '!', '?', '\n'}
        
    async def process_stream(
        self,
        text_stream: AsyncIterator[str],
        voice_client,
        speed: float = 1.0,
        rate: str = "+0%"
    ):
        """Process text stream and play as TTS audio.
        
        Args:
            text_stream: Async iterator yielding text chunks
            voice_client: Discord voice client to play audio through
            speed: Kokoro TTS speed modifier
            rate: Edge TTS rate modifier
            
        Returns:
            Full text that was spoken
        """
        buffer = ""
        full_text = ""
        
        try:
            async for chunk in text_stream:
                buffer += chunk
                full_text += chunk
                
                # Check if we have a complete sentence
                if any(ending in buffer for ending in self.sentence_endings):
                    # Find the last sentence ending
                    sentences = self._split_into_sentences(buffer)
                    
                    for sentence in sentences[:-1]:  # Process all complete sentences
                        if sentence.strip():
                            await self._speak_sentence(
                                sentence, voice_client, speed, rate
                            )
                    
                    # Keep incomplete sentence in buffer
                    buffer = sentences[-1] if sentences else ""
            
            # Process any remaining text
            if buffer.strip():
                await self._speak_sentence(buffer, voice_client, speed, rate)
                
        except Exception as e:
            logger.error(f"Streaming TTS error: {e}")
        
        return full_text
    
    def _split_into_sentences(self, text: str) -> list[str]:
        """Split text into sentences.
        
        Args:
            text: Text to split
            
        Returns:
            List of sentences (last may be incomplete)
        """
        sentences = []
        current = ""
        
        for char in text:
            current += char
            if char in self.sentence_endings:
                sentences.append(current)
                current = ""
        
        # Add any remaining text
        if current:
            sentences.append(current)
        
        return sentences if sentences else [""]
    
    async def _speak_sentence(
        self,
        sentence: str,
        voice_client,
        speed: float,
        rate: str
    ):
        """Generate and play TTS for a single sentence.
        
        Args:
            sentence: Text to speak
            voice_client: Discord voice client
            speed: TTS speed
            rate: TTS rate
        """
        # Skip if already playing
        if voice_client.is_playing():
            # Wait for current to finish
            while voice_client.is_playing():
                await asyncio.sleep(0.1)
        
        try:
            # Generate TTS
            from config import Config
            audio_file = Path(Config.TEMP_DIR) / f"stream_tts_{uuid.uuid4()}.wav"
            
            await self.tts.generate(
                sentence,
                str(audio_file),
                speed=speed,
                rate=rate
            )
            
            # Apply RVC if enabled
            if self.rvc and Config.RVC_ENABLED:
                rvc_file = Path(Config.TEMP_DIR) / f"stream_rvc_{uuid.uuid4()}.wav"
                await self.rvc.convert(audio_file, rvc_file)
                audio_file = rvc_file
            
            # Play audio
            import discord
            audio_source = discord.FFmpegPCMAudio(
                str(audio_file),
                options="-vn -af aresample=48000,aformat=sample_fmts=s16:channel_layouts=stereo"
            )
            
            # Create cleanup callback
            def after_playing(error):
                if error:
                    logger.error(f"Audio playback error: {error}")
                # Clean up temp file
                try:
                    audio_file.unlink(missing_ok=True)
                except Exception as e:
                    logger.debug(f"Failed to delete temp audio: {e}")
            
            voice_client.play(audio_source, after=after_playing)
            
            # Wait for playback to finish
            while voice_client.is_playing():
                await asyncio.sleep(0.1)
                
        except Exception as e:
            logger.error(f"Failed to speak sentence: {e}")
