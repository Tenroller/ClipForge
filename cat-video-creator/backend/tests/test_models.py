import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from pydantic import ValidationError
from app import MoneyPrinterRequest, BrainrotRequest


class TestMoneyPrinterRequest:
    def test_valid_request(self):
        req = MoneyPrinterRequest(
            videoSubject="Test video about cats",
            aiModel="gemini-2.0-flash",
            paragraphNumber=3,
            threads=4
        )
        assert req.videoSubject == "Test video about cats"
        assert req.paragraphNumber == 3
        assert req.threads == 4

    def test_paragraph_number_validation(self):
        # Test minimum
        with pytest.raises(ValidationError):
            MoneyPrinterRequest(videoSubject="test", paragraphNumber=0)
        
        # Test maximum
        with pytest.raises(ValidationError):
            MoneyPrinterRequest(videoSubject="test", paragraphNumber=11)
        
        # Valid range
        req = MoneyPrinterRequest(videoSubject="test", paragraphNumber=5)
        assert req.paragraphNumber == 5

    def test_threads_validation(self):
        # Test minimum
        with pytest.raises(ValidationError):
            MoneyPrinterRequest(videoSubject="test", threads=0)
        
        # Test maximum
        with pytest.raises(ValidationError):
            MoneyPrinterRequest(videoSubject="test", threads=17)
        
        # Valid range
        req = MoneyPrinterRequest(videoSubject="test", threads=8)
        assert req.threads == 8

    def test_defaults(self):
        req = MoneyPrinterRequest(videoSubject="test")
        assert req.aiModel == "gemini-2.0-flash"
        assert req.paragraphNumber == 1
        assert req.subtitlesPosition == "center,bottom"
        assert req.color == "#FFFF00"
        assert req.useMusic is False
        assert req.useGPU is True


class TestBrainrotRequest:
    def test_valid_request(self):
        req = BrainrotRequest(
            youtubeUrl="https://youtu.be/dQw4w9WgXcQ",
            numCompilations=3,
            minDuration=30,
            maxDuration=120
        )
        assert req.youtubeUrl == "https://youtu.be/dQw4w9WgXcQ"
        assert req.numCompilations == 3
        assert req.minDuration == 30
        assert req.maxDuration == 120

    def test_compilation_count_validation(self):
        with pytest.raises(ValidationError):
            BrainrotRequest(youtubeUrl="https://youtu.be/test", numCompilations=0)
        
        with pytest.raises(ValidationError):
            BrainrotRequest(youtubeUrl="https://youtu.be/test", numCompilations=11)

    def test_duration_validation(self):
        with pytest.raises(ValidationError):
            BrainrotRequest(youtubeUrl="https://youtu.be/test", minDuration=5)
        
        with pytest.raises(ValidationError):
            BrainrotRequest(youtubeUrl="https://youtu.be/test", maxDuration=3700)

    def test_defaults(self):
        req = BrainrotRequest(youtubeUrl="https://youtu.be/test")
        assert req.numCompilations == 1
        assert req.minDuration == 60
        assert req.maxDuration == 110
        assert req.maxReuse == 3
