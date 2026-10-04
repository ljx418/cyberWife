"""No-egress TTS shim: cyberWife Gateway sends already synthesized PCM/WAV."""
from .base_tts import BaseTTS
from registry import register
from utils.logger import logger


@register("tts", "external")
class ExternalAudioTTS(BaseTTS):
    def txt_to_audio(self, _msg):
        logger.warning("text TTS ignored: external PCM input is required")
