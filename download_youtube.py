import os
import subprocess
import time
import re
import sys
from pathlib import Path

import audio_to_subtitle

def extract_video_id(url):
    """Extract video ID from YouTube URL"""
    # Try to match common YouTube URL formats
    pattern = r'(?:youtube\.com\/(?:[^\/\n\s]+\/\S+\/|(?:v|e(?:mbed)?)\/|\S*?[?&]v=)|youtu\.be\/)([a-zA-Z0-9_-]{11})'
    match = re.search(pattern, url)
    if match:
        return match.group(1)
    return None

def download_youtube(url, content_type="video", quality="best", audio_format="mp3", audio_quality="0", show_progress=True, threads=8):
    """
    Use yt-dlp to download YouTube videos or audio to a specified directory, using video ID or timestamp as filename
    
    Parameters:
        url (str): YouTube video URL
        content_type (str): Content type, 'video' or 'audio'
        quality (str): Video quality, default is 'best', options include:
                      - 'best': Best video and audio quality
                      - '1080p': 1080p video
                      - '720p': 720p video
        audio_format (str): Audio format, default 'mp3', options include 'm4a', 'wav', 'opus', etc.
        audio_quality (str): Audio quality, from 0 (best) to 9 (worst), default is 0
        show_progress (bool): Whether to display download progress, default is True
        threads (int): Number of parallel download threads, default is 8
    
    Returns:
        str: Returns the relative path of the downloaded file on success, or error message on failure
    """
    
    # Try to extract video ID, use timestamp if failed
    video_id = extract_video_id(url)
    if not video_id:
        video_id = str(int(time.time()))
    
    # Build command
    command = ["yt-dlp"]
    
    # Add multi-threading parameter
    if threads > 1:
        command.extend(["--concurrent-fragments", str(threads)])
    
    if content_type == "video":
        # Build video format parameter
        if quality == "best":
            format_arg = "bestvideo+bestaudio/best"
        elif quality == "1080p":
            format_arg = "bestvideo[height<=1080]+bestaudio/best[height<=1080]"
        elif quality == "720p":
            format_arg = "bestvideo[height<=720]+bestaudio/best[height<=720]"
        else:
            format_arg = quality
        
        command.extend([
            "-f", format_arg,
            "--merge-output-format", "mp4"
        ])
        output_dir = "resources/videos"
        file_path = f"{output_dir}/{video_id}.mp4"
        output_template = file_path
    
    else:  # Audio download
        command.extend([
            "-x",  # Extract audio
            "--audio-format", audio_format,
            "--audio-quality", str(audio_quality)  # Ensure audio_quality is converted to string
        ])
        output_dir = "resources/audios"
        file_path = f"{output_dir}/{video_id}.{audio_format}"
        output_template = file_path
    
    # Ensure output directory exists
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Add output template
    command.extend(["-o", output_template])
    
    # Add URL
    command.append(url)
    
    try:
        if show_progress:
            # Use Popen to get real-time output to display progress
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1
            )
            
            # Read output in real-time and display progress
            for line in process.stdout:
                line = line.strip()
                # Filter and display download progress information
                if '[download]' in line and '%' in line:
                    print(f"\r{line}", end='', flush=True)
                # Display multi-threading download information
                elif 'fragment' in line.lower() and '%' in line:
                    print(f"\r{line}", end='', flush=True)
                
            # Wait for process to complete
            process.wait()
            print()  # Line break, keep output clean
            
            # Check return code
            if process.returncode != 0:
                return f"Download failed, return code: {process.returncode}"
        else:
            # Use the original way to execute command
            result = subprocess.run(
                command, 
                check=True,
                capture_output=True,
                text=True
            )
        
        # Check if file exists
        if os.path.exists(file_path):
            return file_path
        
        # If expected file is not found, try to extract from output
        print("File not found: {}".format(file_path))
        
        if show_progress:
            return file_path
        else:
            output_lines = result.stdout.strip().split('\n')
            for line in output_lines:
                if "Destination" in line and ":" in line:
                    return line.split(":", 1)[1].strip()
                elif "[Merger] Merging formats into" in line:
                    return line.replace("[Merger] Merging formats into ", "").replace('"', '').strip()
        
        # If still not found, return possible path
        return file_path
    
    except subprocess.CalledProcessError as e:
        return f"Download failed: {e.stderr}"
    
    except Exception as e:
        return f"Error occurred: {str(e)}"

    

    