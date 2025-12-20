"""Stream Multiplexer - Allows multiple consumers of a single async stream.

This utility enables streaming LLM responses to both Discord (text display)
and TTS (voice synthesis) simultaneously without re-generating the response.
"""

import asyncio
from typing import AsyncIterator, List
import logging

logger = logging.getLogger(__name__)


class StreamMultiplexer:
    """Multiplexes a single async stream to multiple consumers.

    Usage:
        stream = llm.chat_stream(messages)
        multiplexer = StreamMultiplexer(stream)
        text_stream = multiplexer.create_consumer()
        tts_stream = multiplexer.create_consumer()

        # Both consumers receive the same chunks
        await asyncio.gather(
            process_text(text_stream),
            process_tts(tts_stream)
        )
    """

    def __init__(self, source_stream: AsyncIterator[str]):
        """Initialize multiplexer with source stream.

        Args:
            source_stream: The async iterator to multiplex
        """
        self.source_stream = source_stream
        self.consumers: List[asyncio.Queue] = []
        self._producer_task = None
        self._started = False

    def create_consumer(self) -> AsyncIterator[str]:
        """Create a new consumer for the stream.

        Returns:
            Async iterator that yields the same chunks as the source
        """
        queue = asyncio.Queue()
        self.consumers.append(queue)

        # Start producer on first consumer
        if not self._started:
            self._started = True
            self._producer_task = asyncio.create_task(self._produce())

        return self._consume(queue)

    async def _produce(self):
        """Producer coroutine that reads from source and distributes to consumers."""
        try:
            async for chunk in self.source_stream:
                # Send chunk to all consumers
                for queue in self.consumers:
                    await queue.put(chunk)
        except Exception as e:
            logger.error(f"Stream multiplexer producer error: {e}")
        finally:
            # Signal end of stream to all consumers
            for queue in self.consumers:
                await queue.put(None)  # Sentinel value

    async def _consume(self, queue: asyncio.Queue) -> AsyncIterator[str]:
        """Consumer coroutine that yields chunks from its queue.

        Args:
            queue: The queue for this consumer

        Yields:
            String chunks from the stream
        """
        try:
            while True:
                chunk = await queue.get()
                if chunk is None:  # End of stream
                    break
                yield chunk
        except Exception as e:
            logger.error(f"Stream multiplexer consumer error: {e}")
