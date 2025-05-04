# Magic Video

A comprehensive video processing tool that automatically translates YouTube videos into Chinese with dubbed voice-over.

## Features

- **YouTube Video Download**: Download any YouTube video with high quality
- **Speech-to-Text**: Convert video audio to text subtitles
- **Translation**: Translate English subtitles to Chinese
- **Text-to-Speech**: Convert Chinese subtitles to natural-sounding speech
- **Audio Mixing**: Merge translated speech with original video
- **Ad Removal**: Automatically detect and remove advertisement segments

## System Requirements

- Python 3.8+
- FFmpeg
- Internet connection for API services

## Installation

1. Clone the repository:
   ```
   git clone [repository-url]
   cd magic_video
   ```

2. Set up environment variables:
   Create a `.env` file in the project root with the following API keys:
   ```
   ASSEMBLYAI_API_KEY=your_assemblyai_key
   OPENAI_API_KEY=your_openai_key
   FISH_API_KEY=your_fish_audio_sdk_key
   ```

## Usage

Run the main script with a YouTube URL:

```
python main.py https://www.youtube.com/watch?v=VIDEO_ID
```

The processing pipeline includes:
1. Downloading the video and audio from YouTube
2. Converting audio to subtitles
3. Translating subtitles to Chinese
4. Converting Chinese subtitles to speech
5. Merging the translated speech with the original video
6. Removing advertisement segments

## Project Structure

- `main.py`: Main processing pipeline
- `download_youtube.py`: YouTube video downloader
- `audio_to_subtitle.py`: Audio to text conversion
- `translate_subtitles.py`: Subtitle translation
- `subtitle_to_speech.py`: Text to speech conversion
- `merge_audio.py`: Audio-video merging
- `detect_ads.py`: Advertisement detection
- `resources/`: Directory for all processed files
  - `videos/`: Downloaded videos
  - `audios/`: Audio files
  - `transcripts/`: Subtitle files
  - `results/`: Final processed videos

## Dependencies

Main dependencies include:
- yt-dlp
- assemblyai
- openai
- ffmpeg-python
- fish-audio-sdk
- demucs
- pydub

## License

[Specify your license here]

## Acknowledgements

- [AssemblyAI](https://www.assemblyai.com/) for speech-to-text services
- [OpenAI](https://openai.com/) for translation services
- [Fish Audio SDK](https://github.com/fishaudio/fish-audio) for text-to-speech services 
