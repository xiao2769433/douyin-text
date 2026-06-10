import contextlib
import io
import sys
import unittest
import warnings
from pathlib import Path

warnings.filterwarnings("ignore", category=Warning, module="requests")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from extract import DouyinExtractor, TextProcessor


class TextProcessorTest(unittest.TestCase):
    def test_corrects_obvious_asr_errors(self):
        text = "元风五年, 苏氏因被扁黄周, 回首向来消瘦处, 规去也无风雨也无情。"

        corrected = TextProcessor.correct_obvious_asr_errors(text)

        self.assertIn("元丰五年", corrected)
        self.assertIn("苏轼", corrected)
        self.assertIn("被贬黄州", corrected)
        self.assertIn("回首向来萧瑟处", corrected)
        self.assertIn("归去，也无风雨也无晴", corrected)

    def test_process_uses_asr_corrections_before_cleaning(self):
        text = "元风五年, 苏氏因被扁黄周, 然后回首向来消瘦处, 规去也无风雨也无情。"

        processed = TextProcessor.process(text)

        self.assertIn("元丰五年", processed["cleaned"])
        self.assertIn("苏轼", processed["cleaned"])
        self.assertIn("被贬黄州", processed["cleaned"])
        self.assertIn("回首向来萧瑟处", processed["cleaned"])
        self.assertIn("归去，也无风雨也无晴", processed["cleaned"])

    def test_leaves_unknown_text_unchanged_except_existing_cleanup(self):
        text = "今天的天气很好，适合出门散步。"

        corrected = TextProcessor.correct_obvious_asr_errors(text)

        self.assertEqual(text, corrected)

    def test_does_not_rewrite_valid_su_family_phrase(self):
        text = "苏氏家族历史悠久。"

        corrected = TextProcessor.correct_obvious_asr_errors(text)

        self.assertEqual(text, corrected)

    def test_extract_transcription_preserves_raw_text(self):
        extractor = DouyinExtractor()
        raw_text = "元风五年, 苏氏因被扁黄周。"

        extractor.extract_via_share_page = lambda url: {"author": "作者", "desc": "描述"}
        extractor.download_video_file = lambda url, video_path, cookies_browser, cookies_file: True
        extractor.extract_audio = lambda video_path, output_dir: str(Path(output_dir) / "audio.wav")
        extractor.transcribe_audio = lambda audio_path, model_size: raw_text

        with contextlib.redirect_stderr(io.StringIO()):
            result = extractor.extract_transcription("https://v.douyin.com/test/", output_dir=str(Path(__file__).parent))

        self.assertEqual(raw_text, result["transcription_raw"])
        self.assertIn("元丰五年", result["transcription_cleaned"])
        self.assertIn("苏轼因被贬黄州", result["transcription_cleaned"])


if __name__ == "__main__":
    unittest.main()
