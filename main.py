#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import os
import logging

from merge_audio import delete_ads_from_video, merge_audio
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from audio_to_subtitle import assembly_audio_to_subtitle
from download_youtube import download_youtube
from subtitle_to_speech import process_subtitles
from translate_subtitles import translate_srt_file

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("video_processing.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def process(url):
    video_name = url.split("=")[1]
    
    # Step 1: Download video and audio
    # Use default parameters to download video (default type is video, quality is best)
    logger.info("Step 1, start downloading video and audio")
    audio_result = download_youtube(url, content_type="audio", audio_format="mp3", audio_quality="0")
    video_result = download_youtube(url, content_type="video", quality="best")

    if video_result.startswith("Download failed") or video_result.startswith("Error occurred"):
        logger.error(f"Video download error: {video_result}")
        sys.exit(1)
    
    if audio_result.startswith("Download failed") or audio_result.startswith("Error occurred"):
        logger.error(f"Audio download error: {audio_result}")
        sys.exit(1)
    
    logger.info(f"Download successful, video file saved at: {video_result}")
    logger.info(f"Download successful, audio file saved at: {audio_result}")
    
    # Step 2: Convert audio to subtitles
    # Use assembly_audio_to_subtitle function to process the audio file
    logger.info("Step 2, start converting audio to subtitles")
    subtitle_result = str(assembly_audio_to_subtitle(audio_result))
    
    if subtitle_result.startswith("Error"):
        logger.error(f"Audio to subtitle error: {subtitle_result}")
        sys.exit(1)
    
    logger.info(f"Subtitle file has been saved to: {subtitle_result}")

    # Step 3: Convert subtitles to Chinese subtitles
    # Get output filename
    logger.info("Step 3, start converting subtitles to Chinese subtitles")
    subtitle_name = os.path.basename(subtitle_result)
    name, ext = os.path.splitext(subtitle_name)
    chinese_subtitle = os.path.join(os.path.dirname(subtitle_result), f"{name}_cn{ext}")
    
    # Call translate_srt_file function to translate English subtitles to Chinese subtitles
    max_attempts = 5
    attempt = 0
    translated_subtitle = None
    
    while attempt < max_attempts:
        attempt += 1
        logger.info(f"Attempting to translate subtitles, attempt {attempt}")
        try:
            translated_subtitle = translate_srt_file(subtitle_result, chinese_subtitle)
            if translated_subtitle and os.path.exists(translated_subtitle):
                logger.info(f"Translation successful, attempt {attempt}")
                break
            else:
                logger.warning(f"Attempt {attempt} did not generate a file")
        except Exception as e:
            logger.error(f"Error in attempt {attempt}: {str(e)}")
            if attempt < max_attempts:
                logger.info("Preparing to retry...")
    
    if not translated_subtitle or not os.path.exists(translated_subtitle):
        logger.error("Translation failed, still no translation file after three attempts")
        sys.exit(1)
    
    logger.info(f"Chinese subtitle file has been saved to: {translated_subtitle}")
    
    # Step 4: Convert Chinese subtitles to speech
    # Use process_subtitles function to process subtitle file
    logger.info("Step 4, start converting Chinese subtitles to speech")
    try:
        generated_audio = process_subtitles(translated_subtitle, video_name, output_dir=f"resources/audios/{video_name}")
        if not os.path.exists(generated_audio):
            logger.error("Subtitle to speech failed, no audio file generated")
            sys.exit(1)
        logger.info(f"Generated audio file has been saved to: {generated_audio}")
    except Exception as e:
        logger.error(f"Error in subtitle to speech process: {str(e)}")
        sys.exit(1)
    
    # Step 5: Replace the original audio in the video with the mixed audio
    logger.info("Step 5, start replacing the original audio in the video with the mixed audio")
    try:
        print(f"call merge_audio(original_video={video_result}, original_audio={audio_result}, generated_audio={generated_audio}, output_filename=f\"resources/results/{video_name}.mp4\", subtitle_path={translated_subtitle})")
        final_video = merge_audio(original_video=video_result, 
                    original_audio=audio_result, 
                    speaking_audio=generated_audio, 
                    output_filename=f"resources/results/{video_name}.mp4",
                    subtitle_path=translated_subtitle)
        
        if not os.path.exists(final_video):
            logger.error("Audio-video merging failed, no final video file generated")
            sys.exit(1)
            
        logger.info(f"Final video file has been saved to: {final_video}")
    except Exception as e:
        logger.error(f"Error in audio-video merging process: {str(e)}")
        sys.exit(1)
    
    # Step 6: Remove advertisement segments from the video
    logger.info("Step 6, start removing advertisement segments from the video")
    delete_ads_from_video(video_path=final_video, 
                         srt_file=subtitle_result)
    
    return final_video

if __name__ == "__main__":
    # Complete process test
    try:
        url = "https://www.youtube.com/watch?v=C1UgGbiUTTo"
        final_video = process(url)
        logger.info(f"Processing completed, final video file has been saved to: {final_video}")
    except Exception as e:
        logger.error(f"Uncaught error occurred during processing: {str(e)}")
        sys.exit(1)
    